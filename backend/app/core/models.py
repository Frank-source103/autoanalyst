"""API request and response schemas."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    """Response returned upon successful dataset upload."""

    dataset_id: str = Field(..., description="Server-generated unique identifier")
    filename: str = Field(..., description="Original client filename")
    file_path: str = Field(..., description="Host filesystem path to uploaded dataset")
    file_type: str = Field(..., description="Validated format: csv or parquet")
    size_bytes: int = Field(..., description="File size in bytes")


class CreateRunRequest(BaseModel):
    """Payload to initiate an autonomous analysis run."""

    user_question: str = Field(..., min_length=1, max_length=1000)
    dataset_path: str = Field(..., description="Host path returned by upload endpoint")
    filename: Optional[str] = Field(None, description="Original dataset name")
    review_before_run: bool = Field(
        default=False, description="Pause before every step execution to review/edit code"
    )


class CreateRunResponse(BaseModel):
    """Initial confirmation of run creation."""

    run_id: str
    status: str


class ResumeRunRequest(BaseModel):
    """Payload to resume an interrupted or paused run."""

    edited_code: Optional[str] = Field(
        default=None, description="Optional user-edited Python script to execute"
    )


class RunDetailResponse(BaseModel):
    """Complete run snapshot including state and persisted events."""

    run_id: str
    status: str
    user_question: str
    current_step_idx: int
    per_step_retry_count: int
    plan: List[Dict[str, Any]]
    charts: List[Dict[str, Any]]
    final_report: Optional[str]
    is_paused: bool
    pending_code: Optional[str]
    events: List[Dict[str, Any]]
