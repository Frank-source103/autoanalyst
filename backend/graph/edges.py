"""Conditional routing logic and loop guards for AutoAnalyst graph."""

from typing import Literal
from backend.app.core.config import settings
from backend.graph.state import AgentState


def route_after_generate_code(state: AgentState) -> Literal["human_checkpoint", "synthesize_report"]:
    """Route after code generation: proceed to checkpoint or finish if all steps are done."""
    if state.current_step_idx >= len(state.plan):
        return "synthesize_report"
    return "human_checkpoint"


def route_after_evaluate(
    state: AgentState,
) -> Literal["generate_code", "self_correct", "synthesize_report"]:
    """Route after evaluation: self-correct on failure, generate code for next step, or report."""
    # 1. Total graph iteration guard
    if state.iteration_count >= settings.MAX_TOTAL_ITERATIONS:
        return "synthesize_report"

    # 2. Critical failure or terminal status
    if state.status in ("failed", "aborted", "budget_exceeded"):
        return "synthesize_report"

    # 3. Active retry attempt for current step
    if state.per_step_retry_count > 0:
        return "self_correct"

    # 4. Step succeeded or non-critical step finished: check if remaining steps exist
    if state.current_step_idx < len(state.plan):
        return "generate_code"

    # 5. All steps completed
    return "synthesize_report"
