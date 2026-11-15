"""Report synthesis node."""

from typing import Any, Dict
from langchain_core.runnables import RunnableConfig

from backend.app.core.events import make_event
from backend.graph.llm import get_llm
from backend.graph.state import AgentState


async def synthesize_report_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Synthesize Markdown analytical report and transition to terminal status."""
    llm = config.get("configurable", {}).get("llm") or get_llm()
    seq = len(state.events) + 1

    # Determine terminal status
    terminal_status = state.status
    is_partial = False
    failure_reason = None

    if terminal_status in ("failed", "aborted", "budget_exceeded"):
        is_partial = True
        failure_reason = f"Execution terminated with status: {terminal_status}"
    else:
        # Check if any critical step failed
        any_critical_failed = any(s.status == "failed" and s.is_critical for s in state.plan)
        if any_critical_failed:
            terminal_status = "failed"
            is_partial = True
            failure_reason = "Critical analytical step failed."
        else:
            terminal_status = "completed"

    report_markdown = await llm.synthesize_report(
        question=state.user_question,
        plan=state.plan,
        step_outputs=[],
        charts=state.charts,
        is_partial=is_partial,
        failure_reason=failure_reason,
    )

    report_evt = make_event(
        seq=seq,
        run_id=state.run_id,
        event_type="report",
        data={"markdown": report_markdown, "is_partial": is_partial},
    )
    status_evt = make_event(
        seq=seq + 1,
        run_id=state.run_id,
        event_type="run_status",
        data={"status": terminal_status},
    )

    return {
        "status": terminal_status,
        "final_report": report_markdown,
        "events": [report_evt, status_evt],
        "iteration_count": state.iteration_count + 1,
    }
