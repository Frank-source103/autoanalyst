"""LangGraph 0.2+ state machine, loop guards, and persistence tests."""

import os
import tempfile
import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from backend.graph.builder import build_graph, calculate_recursion_limit
from backend.graph.llm import MockLLM
from backend.graph.state import AgentState, DatasetMeta
from backend.sandbox.base import SandboxExecutor
from backend.sandbox.result import ExecutionResult


class MockTestSandboxExecutor(SandboxExecutor):
    """Deterministic sandbox executor for graph logic and loop verification tests."""

    def __init__(self, fail_first_step: bool = True, persistent_fail: bool = False):
        self.fail_first_step = fail_first_step
        self.persistent_fail = persistent_fail
        self.execution_attempts = 0

    def is_available(self) -> bool:
        return True

    async def execute_code(
        self,
        code: str,
        dataset_path: str,
        timeout_seconds: int = 30,
        run_id: str = None,
    ) -> ExecutionResult:
        self.execution_attempts += 1

        # Profile script response
        if "run_profiling" in code:
            mock_profile_json = (
                '{"row_count": 100, "columns": ["category", "sales"], "dtypes": {"category": "object", "sales": "float64"}, "sample_rows": []}'
            )
            return ExecutionResult(
                status="success",
                stdout=f"__PROFILE_OUTPUT_START__\n{mock_profile_json}\n__PROFILE_OUTPUT_END__",
                exit_code=0,
            )

        # Persistent failure scenario: varies error signature across retries to test retry cap
        if self.persistent_fail:
            err_signatures = [
                "KeyError: 'missing_dimension'",
                "ValueError: 'invalid_shape'",
                "TypeError: 'mismatched_types'",
                "IndexError: 'out_of_bounds'",
            ]
            err = err_signatures[(self.execution_attempts - 1) % len(err_signatures)]
            return ExecutionResult(
                status="failed",
                stderr=err,
                exit_code=1,
                error_signature=err,
            )

        # Fail initial attempt if code has the intentional bug
        if "non_existent_column" in code:
            return ExecutionResult(
                status="failed",
                stderr="KeyError: 'non_existent_column_for_test'",
                exit_code=1,
                error_signature="KeyError: 'non_existent_column_for_test'",
            )

        # Success case with chart output
        return ExecutionResult(
            status="success",
            stdout="Analysis completed successfully.",
            exit_code=0,
            chart_data={
                "chart_type": "bar",
                "title": "Category Sales",
                "data": [{"category": "Apparel", "sales": 500.0}],
                "series": ["sales"],
            },
            output_files=["result.json"],
        )


@pytest.mark.asyncio
async def test_self_correction_flow():
    """Verify that an initial execution error triggers self-correction and subsequently succeeds."""
    mock_llm = MockLLM(scenario="demo")
    mock_executor = MockTestSandboxExecutor(fail_first_step=True)

    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        chk_db = f.name

    try:
        async with AsyncSqliteSaver.from_conn_string(chk_db) as saver:
            graph = build_graph(checkpointer=saver)
            config = {
                "configurable": {
                    "thread_id": "test-self-correct-run",
                    "llm": mock_llm,
                    "executor": mock_executor,
                },
                "recursion_limit": calculate_recursion_limit(),
            }

            initial_state = AgentState(
                run_id="test-self-correct-run",
                user_question="Summarize total sales by category",
                dataset_meta=DatasetMeta(
                    filename="sales.csv",
                    file_path="dummy_path.csv",
                    columns=["category", "sales"],
                ),
            )

            final_state = await graph.ainvoke(initial_state, config=config)

            # Check that self correction occurred and completed
            assert final_state["status"] == "completed"
            assert mock_llm.correction_count >= 1
            assert len(final_state["charts"]) >= 1
            assert final_state["final_report"] is not None
            assert "Executive Analytical Report" in final_state["final_report"]
    finally:
        if os.path.exists(chk_db):
            os.remove(chk_db)


@pytest.mark.asyncio
async def test_persistent_error_stops_at_retry_cap_and_emits_partial_report():
    """Verify that a persistent runtime error stops after reaching max retries and emits a partial report."""
    mock_llm = MockLLM(scenario="persistent_error")
    mock_executor = MockTestSandboxExecutor(persistent_fail=True)

    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        chk_db = f.name

    try:
        async with AsyncSqliteSaver.from_conn_string(chk_db) as saver:
            graph = build_graph(checkpointer=saver)
            config = {
                "configurable": {
                    "thread_id": "test-retry-cap-run",
                    "llm": mock_llm,
                    "executor": mock_executor,
                },
                "recursion_limit": calculate_recursion_limit(),
            }

            initial_state = AgentState(
                run_id="test-retry-cap-run",
                user_question="Analyze error prone dataset",
                dataset_meta=DatasetMeta(
                    filename="faulty.csv",
                    file_path="dummy_path.csv",
                    columns=["a", "b"],
                ),
            )

            final_state = await graph.ainvoke(initial_state, config=config)

            # Step was critical, so run status should be failed with partial report
            assert final_state["status"] == "failed"
            assert final_state["final_report"] is not None
            assert "Partial Analysis Report" in final_state["final_report"]
            # Retry count reached limit (3 retries)
            retry_events = [e for e in final_state["events"] if e.event_type == "retry"]
            assert len(retry_events) >= 3
            assert any(e.data.get("halted") is True for e in retry_events)
    finally:
        if os.path.exists(chk_db):
            os.remove(chk_db)


@pytest.mark.asyncio
async def test_repeated_failure_detection_stops_retrying():
    """Verify that repeated identical error signatures trigger repeated-failure protection."""
    mock_llm = MockLLM(scenario="repeated_error")

    class RepeatingErrorExecutor(SandboxExecutor):
        def is_available(self):
            return True

        async def execute_code(self, code, dataset_path, timeout_seconds=30, run_id=None):
            if "run_profiling" in code:
                return ExecutionResult(
                    status="success",
                    stdout='__PROFILE_OUTPUT_START__\n{"row_count": 10, "columns": ["x"]}\n__PROFILE_OUTPUT_END__',
                    exit_code=0,
                )
            # Returns exact same error signature every time
            return ExecutionResult(
                status="failed",
                stderr="ZeroDivisionError: division by zero",
                exit_code=1,
                error_signature="ZeroDivisionError: division by zero",
            )

    executor = RepeatingErrorExecutor()

    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        chk_db = f.name

    try:
        async with AsyncSqliteSaver.from_conn_string(chk_db) as saver:
            graph = build_graph(checkpointer=saver)
            config = {
                "configurable": {
                    "thread_id": "test-repeated-failure-run",
                    "llm": mock_llm,
                    "executor": executor,
                },
                "recursion_limit": calculate_recursion_limit(),
            }

            initial_state = AgentState(
                run_id="test-repeated-failure-run",
                user_question="Compute division metrics",
                dataset_meta=DatasetMeta(filename="d.csv", file_path="d.csv", columns=["x"]),
            )

            final_state = await graph.ainvoke(initial_state, config=config)

            # Should halt early due to repeated error signature
            assert final_state["status"] == "failed"
            retry_events = [e for e in final_state["events"] if e.event_type == "retry"]
            halted_event = next((e for e in retry_events if e.data.get("halted") is True), None)
            assert halted_event is not None
            assert "Repeated error signature" in halted_event.data.get("reason", "")
    finally:
        if os.path.exists(chk_db):
            os.remove(chk_db)


@pytest.mark.asyncio
async def test_pause_and_resume_survives_process_restart():
    """Verify that a run paused with interrupt() persists in SQLite and successfully resumes after process restart."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        db_path = f.name

    thread_id = "test-process-restart-thread"
    mock_llm = MockLLM(scenario="single_step")
    mock_executor = MockTestSandboxExecutor(fail_first_step=False)

    try:
        # ===============================================================
        # PROCESS 1: Run with review_before_run=True, halts at checkpoint
        # ===============================================================
        async with AsyncSqliteSaver.from_conn_string(db_path) as saver1:
            graph1 = build_graph(checkpointer=saver1)
            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "llm": mock_llm,
                    "executor": mock_executor,
                },
                "recursion_limit": calculate_recursion_limit(),
            }

            initial_state = AgentState(
                run_id=thread_id,
                user_question="Calculate single step summary with human review",
                dataset_meta=DatasetMeta(
                    filename="sales.csv",
                    file_path="sales.csv",
                    columns=["category", "sales"],
                ),
                review_before_run=True,  # Triggers interrupt() at human_checkpoint
            )

            res1 = await graph1.ainvoke(initial_state, config=config)

            # Verify that execution paused at human_checkpoint
            assert "__interrupt__" in res1
            interrupt_val = res1["__interrupt__"][0].value
            assert interrupt_val["run_id"] == thread_id
            assert "pending_code" in interrupt_val

        # At this point, Process 1 exits and db connection is fully closed.

        # ===============================================================
        # PROCESS 2: Simulated backend reboot, reopening fresh connection
        # ===============================================================
        async with AsyncSqliteSaver.from_conn_string(db_path) as saver2:
            graph2 = build_graph(checkpointer=saver2)
            config2 = {
                "configurable": {
                    "thread_id": thread_id,
                    "llm": mock_llm,
                    "executor": mock_executor,
                },
                "recursion_limit": calculate_recursion_limit(),
            }

            # Resume using Command(resume={"edited_code": ...})
            user_edited_code = "print('User verified code after restart')\nimport json, os\nos.makedirs('/tmp/output', exist_ok=True)\nwith open('/tmp/output/result.json', 'w') as f: json.dump({'chart_type': 'bar', 'title': 'Resumed Chart', 'data': [{'category': 'A', 'sales': 10}], 'series': ['sales']}, f)"
            res2 = await graph2.ainvoke(Command(resume={"edited_code": user_edited_code}), config=config2)

            # Verify completion
            assert res2["status"] == "completed"
            assert res2["final_report"] is not None
            # Verify that edited_by_user was logged in resumed event
            resumed_event = next((e for e in res2["events"] if e.event_type == "resumed"), None)
            assert resumed_event is not None
            assert resumed_event.data.get("edited_by_user") is True
            assert len(res2["charts"]) >= 1

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
