"""Event schema and monotonic event generation for AutoAnalyst."""

import datetime
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field

EventType = Literal[
    "state_transition",
    "plan",
    "thought",
    "code",
    "execution_started",
    "stdout",
    "stderr",
    "execution_result",
    "chart",
    "retry",
    "paused",
    "resumed",
    "report",
    "run_status",
]


class AgentEvent(BaseModel):
    """Monotonically sequenced event emitted by the agent graph and runtime."""

    seq: int = Field(..., description="Monotonically increasing sequence number")
    run_id: str = Field(..., description="Unique run identifier")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp",
    )
    event_type: EventType = Field(..., description="Specific typed event name")
    data: Dict[str, Any] = Field(default_factory=dict, description="Structured event payload")

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization and WebSocket broadcast."""
        return self.model_dump()


def make_event(
    seq: int,
    run_id: str,
    event_type: EventType,
    data: Optional[Dict[str, Any]] = None,
) -> AgentEvent:
    """Helper to construct a validated AgentEvent."""
    return AgentEvent(
        seq=seq,
        run_id=run_id,
        event_type=event_type,
        data=data or {},
    )
