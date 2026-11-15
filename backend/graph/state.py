"""Typed AgentState definition using Pydantic v2 and LangGraph annotations."""

import operator
from typing import Annotated, Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from backend.app.core.events import AgentEvent


class DatasetMeta(BaseModel):
    """Metadata and profile summary for the uploaded dataset."""

    filename: str = Field(default="", description="Original file name")
    file_path: str = Field(default="", description="Host file path to dataset")
    file_type: Literal["csv", "parquet", "unknown"] = Field(default="csv")
    size_bytes: int = Field(default=0)
    columns: List[str] = Field(default_factory=list)
    dtypes: Dict[str, str] = Field(default_factory=dict)
    row_count: int = Field(default=0)
    profile: Dict[str, Any] = Field(
        default_factory=dict, description="Deterministic profile stats and sample rows"
    )


class PlanStep(BaseModel):
    """A single step in the agent's analytical plan."""

    step_id: int = Field(..., description="1-indexed step number")
    title: str = Field(..., max_length=120)
    description: str = Field(..., max_length=300)
    is_critical: bool = Field(
        default=False,
        description="If True, failure of this step aborts run; if False, non-critical failure continues",
    )
    status: Literal["pending", "running", "completed", "failed", "skipped"] = Field(
        default="pending"
    )


class AgentState(BaseModel):
    """Full persistent state of an AutoAnalyst run, checkpointed to SQLite."""

    run_id: str = Field(..., description="Unique run identifier")
    user_question: str = Field(..., description="Analytical query asked by user")
    dataset_meta: DatasetMeta = Field(default_factory=DatasetMeta)
    plan: List[PlanStep] = Field(
        default_factory=list, description="Ordered analytical plan (max 6 steps)"
    )
    current_step_idx: int = Field(default=0, description="Index into plan list (0-indexed)")
    per_step_retry_count: int = Field(
        default=0, description="Self-correction retries attempted on current step"
    )
    last_code: str = Field(default="", description="Most recent Python code generated for step")
    last_code_hash: str = Field(default="", description="MD5 hash of last generated code")
    last_error_signature: Optional[str] = Field(
        default=None, description="Normalized error signature from most recent failure"
    )
    cumulative_code: str = Field(
        default="", description="Accumulated successful Python scripts from prior steps"
    )
    iteration_count: int = Field(
        default=0, description="Total graph node visits / loop iterations executed"
    )
    status: Literal[
        "pending",
        "planning",
        "running",
        "paused",
        "completed",
        "failed",
        "aborted",
        "budget_exceeded",
    ] = Field(default="pending")

    # Monotonic event history aggregated via operator.add
    events: Annotated[List[AgentEvent], operator.add] = Field(default_factory=list)

    # Wall-clock and token budgets (survive restarts)
    wall_clock_active_seconds: float = Field(default=0.0)
    wall_clock_last_resumed_at: Optional[float] = Field(default=None)
    token_budget_used: int = Field(default=0)
    llm_call_count: int = Field(default=0)

    # Human-in-the-loop flags
    review_before_run: bool = Field(
        default=False, description="Pause before every step execute to review code"
    )
    is_paused: bool = Field(default=False, description="Whether run was paused by user")
    pending_code: Optional[str] = Field(
        default=None, description="Staged code waiting for human review / resume"
    )

    # Execution artifacts
    last_execution_result: Optional[Dict[str, Any]] = Field(default=None)
    charts: List[Dict[str, Any]] = Field(default_factory=list)
    final_report: Optional[str] = Field(default=None)
