"""Sandboxed code execution node."""

from typing import Any, Dict
from langchain_core.runnables import RunnableConfig

from backend.app.core.config import settings
from backend.app.core.events import make_event
from backend.graph.state import AgentState
from backend.sandbox import get_sandbox_executor


async def execute_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Execute cumulative Python script inside the Docker sandbox container."""
    executor = config.get("configurable", {}).get("executor") or get_sandbox_executor()
    seq = len(state.events) + 1
    current_step = state.plan[state.current_step_idx]

    # Cumulative execution: prior successful steps + new step script
    if state.cumulative_code.strip():
        cumulative_script = (
            f"{state.cumulative_code.strip()}\n\n"
            f"# ==========================================\n"
            f"# Step {current_step.step_id}: {current_step.title}\n"
            f"# ==========================================\n"
            f"{state.last_code.strip()}\n"
        )
    else:
        cumulative_script = (
            f"# ==========================================\n"
            f"# Step {current_step.step_id}: {current_step.title}\n"
            f"# ==========================================\n"
            f"{state.last_code.strip()}\n"
        )

    start_evt = make_event(
        seq=seq,
        run_id=state.run_id,
        event_type="execution_started",
        data={
            "step_id": current_step.step_id,
            "title": current_step.title,
            "script_bytes": len(cumulative_script.encode("utf-8")),
        },
    )

    result = await executor.execute_code(
        code=cumulative_script,
        dataset_path=state.dataset_meta.file_path,
        timeout_seconds=settings.SANDBOX_TIMEOUT_SECONDS,
        run_id=state.run_id,
    )

    events_to_emit = [start_evt]

    if result.stdout.strip():
        events_to_emit.append(
            make_event(
                seq=seq + 1,
                run_id=state.run_id,
                event_type="stdout",
                data={"step_id": current_step.step_id, "text": result.stdout},
            )
        )

    if result.stderr.strip():
        events_to_emit.append(
            make_event(
                seq=seq + 2,
                run_id=state.run_id,
                event_type="stderr",
                data={"step_id": current_step.step_id, "text": result.stderr},
            )
        )

    exec_res_evt = make_event(
        seq=seq + 3,
        run_id=state.run_id,
        event_type="execution_result",
        data={
            "step_id": current_step.step_id,
            "status": result.status,
            "exit_code": result.exit_code,
            "duration_seconds": result.duration_seconds,
            "error_signature": result.error_signature,
            "output_files": result.output_files,
            "has_chart": result.chart_data is not None,
        },
    )
    events_to_emit.append(exec_res_evt)

    return {
        "last_execution_result": result.model_dump(),
        "events": events_to_emit,
        "iteration_count": state.iteration_count + 1,
    }
