"""Plan generation node."""

from typing import Any, Dict
from langchain_core.runnables import RunnableConfig

from backend.app.core.config import settings
from backend.app.core.events import make_event
from backend.graph.llm import get_llm
from backend.graph.state import AgentState, PlanStep


async def plan_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Analyze the user's analytical query and dataset schema to generate an analytical plan."""
    llm = config.get("configurable", {}).get("llm") or get_llm()
    seq = len(state.events) + 1

    dataset_summary = {
        "columns": state.dataset_meta.columns,
        "dtypes": state.dataset_meta.dtypes,
        "row_count": state.dataset_meta.row_count,
        "sample_rows": state.dataset_meta.profile.get("sample_rows", []),
    }

    # Generate plan and enforce schema & step caps
    raw_steps = await llm.generate_plan(state.user_question, dataset_summary)
    capped_steps = raw_steps[: settings.MAX_PLAN_STEPS]

    # Validate step IDs are 1-indexed
    validated_plan = []
    for idx, s in enumerate(capped_steps, start=1):
        validated_plan.append(
            PlanStep(
                step_id=idx,
                title=s.title,
                description=s.description,
                is_critical=s.is_critical,
                status="pending",
            )
        )

    transition_evt = make_event(
        seq=seq,
        run_id=state.run_id,
        event_type="state_transition",
        data={"from": state.status, "to": "planning"},
    )
    plan_evt = make_event(
        seq=seq + 1,
        run_id=state.run_id,
        event_type="plan",
        data={"steps": [s.model_dump() for s in validated_plan]},
    )

    return {
        "plan": validated_plan,
        "status": "running",
        "current_step_idx": 0,
        "per_step_retry_count": 0,
        "events": [transition_evt, plan_evt],
        "iteration_count": state.iteration_count + 1,
    }
