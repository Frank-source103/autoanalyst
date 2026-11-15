"""Idempotent human-in-the-loop checkpoint node."""

import hashlib
from typing import Any, Dict
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from backend.app.core.config import settings
from backend.app.core.events import make_event
from backend.graph.state import AgentState


async def human_checkpoint_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Hold execution for human review or user-triggered pause.

    MUST be strictly idempotent: no side effects or state modifications occur before interrupt().
    """
    should_interrupt = state.review_before_run or state.is_paused

    if should_interrupt:
        # Halt execution; return pending code for client review/edit.
        # Idempotence guarantee: this is evaluated before any state mutations or events.
        resume_data = interrupt({
            "run_id": state.run_id,
            "step_id": state.current_step_idx + 1,
            "pending_code": state.pending_code or state.last_code,
        })

        # Resumed via Command(resume={"edited_code": ...})
        resume_data = resume_data or {}
        edited_code = resume_data.get("edited_code")
        seq = len(state.events) + 1

        final_code = state.last_code
        is_edited = False

        if edited_code is not None:
            stripped = edited_code.strip()
            if not stripped:
                raise ValueError("Edited code cannot be empty")
            if len(stripped.encode("utf-8")) > settings.MAX_SCRIPT_BYTES:
                raise ValueError(f"Edited code exceeds maximum limit of {settings.MAX_SCRIPT_BYTES} bytes")
            final_code = stripped
            is_edited = True

        code_hash = hashlib.md5(final_code.encode("utf-8")).hexdigest()

        resumed_evt = make_event(
            seq=seq,
            run_id=state.run_id,
            event_type="resumed",
            data={
                "edited_by_user": is_edited,
                "step_id": state.current_step_idx + 1,
                "code": final_code if is_edited else None,
            },
        )

        return {
            "last_code": final_code,
            "last_code_hash": code_hash,
            "pending_code": None,
            "is_paused": False,
            "status": "running",
            "events": [resumed_evt],
            "iteration_count": state.iteration_count + 1,
        }

    # Pass-through if no pause requested
    return {
        "pending_code": None,
        "iteration_count": state.iteration_count + 1,
    }
