"""Code generation node."""

import hashlib
from typing import Any, Dict
from langchain_core.runnables import RunnableConfig

from backend.app.core.events import make_event
from backend.graph.llm import get_llm
from backend.graph.state import AgentState


async def generate_code_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Generate Python script and visible rationale/thought for the current plan step."""
    llm = config.get("configurable", {}).get("llm") or get_llm()
    seq = len(state.events) + 1

    if state.current_step_idx >= len(state.plan):
        return {"status": "completed", "iteration_count": state.iteration_count + 1}

    current_step = state.plan[state.current_step_idx]

    # Generate code and rationale without asking model for hidden reasoning traces
    thought, code = await llm.generate_code(
        question=state.user_question,
        step=current_step,
        cumulative_code=state.cumulative_code,
        dataset_meta=state.dataset_meta.model_dump(),
    )

    code_hash = hashlib.md5(code.encode("utf-8")).hexdigest()

    thought_evt = make_event(
        seq=seq,
        run_id=state.run_id,
        event_type="thought",
        data={"thought": thought, "step_id": current_step.step_id},
    )
    code_evt = make_event(
        seq=seq + 1,
        run_id=state.run_id,
        event_type="code",
        data={
            "step_id": current_step.step_id,
            "code": code,
            "code_hash": code_hash,
            "is_correction": False,
        },
    )

    return {
        "last_code": code,
        "last_code_hash": code_hash,
        "pending_code": code,
        "events": [thought_evt, code_evt],
        "iteration_count": state.iteration_count + 1,
    }
