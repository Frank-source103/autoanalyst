"""Evaluation and verification node enforcing loop guards."""

from typing import Any, Dict, List
from langchain_core.runnables import RunnableConfig

from backend.app.core.config import settings
from backend.app.core.events import make_event
from backend.graph.state import AgentState, PlanStep


async def evaluate_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Evaluate execution results, record charts, and enforce retry & loop guards."""
    seq = len(state.events) + 1
    current_step = state.plan[state.current_step_idx]
    result_dict = state.last_execution_result or {}
    status = result_dict.get("status", "failed")
    chart_data = result_dict.get("chart_data")
    current_error_sig = result_dict.get("error_signature")

    events_to_emit = []
    updated_plan: List[PlanStep] = [s.model_copy() for s in state.plan]

    # CASE 1: Successful execution
    if status == "success":
        new_charts = list(state.charts)
        if chart_data:
            new_charts.append(chart_data)
            events_to_emit.append(
                make_event(
                    seq=seq,
                    run_id=state.run_id,
                    event_type="chart",
                    data={"step_id": current_step.step_id, "chart": chart_data},
                )
            )

        # Mark step completed
        updated_plan[state.current_step_idx].status = "completed"

        # Update cumulative code
        new_cumulative = (
            f"{state.cumulative_code.strip()}\n\n"
            f"# --- Verified Step {current_step.step_id}: {current_step.title} ---\n"
            f"{state.last_code.strip()}\n"
        ).strip()

        return {
            "plan": updated_plan,
            "cumulative_code": new_cumulative,
            "charts": new_charts,
            "current_step_idx": state.current_step_idx + 1,
            "per_step_retry_count": 0,
            "last_error_signature": None,
            "events": events_to_emit,
            "iteration_count": state.iteration_count + 1,
        }

    # CASE 2: Execution failure
    retry_count = state.per_step_retry_count
    is_repeated_failure = False

    # Check for repeated failure: only if we have a previous recorded failure on this step
    if current_error_sig and state.last_error_signature and (current_error_sig == state.last_error_signature):
        is_repeated_failure = True

    exceeded_retries = retry_count >= settings.MAX_RETRIES_PER_STEP

    if is_repeated_failure or exceeded_retries:
        # Halt retries on this step
        reason = "Repeated error signature detected" if is_repeated_failure else f"Exceeded max retries ({settings.MAX_RETRIES_PER_STEP})"
        updated_plan[state.current_step_idx].status = "failed"

        fail_evt = make_event(
            seq=seq,
            run_id=state.run_id,
            event_type="retry",
            data={
                "step_id": current_step.step_id,
                "retry_count": retry_count,
                "halted": True,
                "reason": reason,
                "is_critical": current_step.is_critical,
            },
        )
        events_to_emit.append(fail_evt)

        # If step is critical, mark run failed
        if current_step.is_critical:
            return {
                "plan": updated_plan,
                "status": "failed",
                "last_error_signature": None,
                "events": events_to_emit,
                "iteration_count": state.iteration_count + 1,
            }

        # Non-critical step: skip to next step
        return {
            "plan": updated_plan,
            "current_step_idx": state.current_step_idx + 1,
            "per_step_retry_count": 0,
            "last_error_signature": None,
            "events": events_to_emit,
            "iteration_count": state.iteration_count + 1,
        }

    # Retry is permitted: record current error signature for next iteration's comparison
    retry_evt = make_event(
        seq=seq,
        run_id=state.run_id,
        event_type="retry",
        data={
            "step_id": current_step.step_id,
            "retry_count": retry_count + 1,
            "error_signature": current_error_sig,
            "halted": False,
        },
    )
    events_to_emit.append(retry_evt)

    return {
        "per_step_retry_count": retry_count + 1,
        "last_error_signature": current_error_sig,
        "events": events_to_emit,
        "iteration_count": state.iteration_count + 1,
    }
