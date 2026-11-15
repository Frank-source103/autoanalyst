"""Self-correction node for automated code repair."""

import hashlib
from typing import Any, Dict
from langchain_core.runnables import RunnableConfig

from backend.app.core.events import make_event
from backend.graph.llm import get_llm
from backend.graph.state import AgentState


async def self_correct_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Analyze execution failure diagnostics and generate corrected Python code."""
    llm = config.get("configurable", {}).get("llm") or get_llm()
    seq = len(state.events) + 1
    current_step = state.plan[state.current_step_idx]

    result_dict = state.last_execution_result or {}
    stderr = result_dict.get("stderr", "") or result_dict.get("error_signature", "Unknown error")

    thought, corrected_code = await llm.self_correct(
        question=state.user_question,
        step=current_step,
        failing_code=state.last_code,
        error_stderr=stderr,
        dataset_meta=state.dataset_meta.model_dump(),
    )

    code_hash = hashlib.md5(corrected_code.encode("utf-8")).hexdigest()

    thought_evt = make_event(
        seq=seq,
        run_id=state.run_id,
        event_type="thought",
        data={
            "thought": thought,
            "step_id": current_step.step_id,
            "retry_attempt": state.per_step_retry_count,
        },
    )
    code_evt = make_event(
        seq=seq + 1,
        run_id=state.run_id,
        event_type="code",
        data={
            "step_id": current_step.step_id,
            "code": corrected_code,
            "code_hash": code_hash,
            "is_correction": True,
        },
    )

    return {
        "last_code": corrected_code,
        "last_code_hash": code_hash,
        "pending_code": corrected_code,
        "events": [thought_evt, code_evt],
        "iteration_count": state.iteration_count + 1,
    }
