"""Run lifecycle endpoints."""

import os
import uuid
from fastapi import APIRouter, HTTPException, status

from backend.app.core.models import (
    CreateRunRequest,
    CreateRunResponse,
    ResumeRunRequest,
    RunDetailResponse,
)
from backend.app.core.run_manager import run_manager

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.post("", response_model=CreateRunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(request: CreateRunRequest) -> CreateRunResponse:
    """Initiate an autonomous data-science analysis run."""
    if not os.path.exists(request.dataset_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset file not found at: {request.dataset_path}",
        )

    run_id = f"run_{uuid.uuid4().hex[:12]}"

    await run_manager.start_run(
        run_id=run_id,
        user_question=request.user_question,
        dataset_path=request.dataset_path,
        filename=request.filename,
        review_before_run=request.review_before_run,
    )

    return CreateRunResponse(run_id=run_id, status="pending")


@router.get("/{run_id}", response_model=RunDetailResponse)
async def get_run_details(run_id: str) -> RunDetailResponse:
    """Retrieve full run state, current step, plan, and persisted event history."""
    try:
        details = await run_manager.get_run_details(run_id)
        return RunDetailResponse.model_validate(details)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found or could not be loaded: {e}",
        )


@router.post("/{run_id}/pause", status_code=status.HTTP_200_OK)
async def pause_run(run_id: str):
    """Signal run to hold execution at human checkpoint before next execution."""
    try:
        await run_manager.pause_run(run_id)
        return {"run_id": run_id, "status": "pausing"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{run_id}/resume", status_code=status.HTTP_200_OK)
async def resume_run(run_id: str, request: ResumeRunRequest):
    """Resume execution of an interrupted run with optional user-edited code."""
    try:
        await run_manager.resume_run(run_id, edited_code=request.edited_code)
        return {"run_id": run_id, "status": "resumed"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{run_id}/abort", status_code=status.HTTP_200_OK)
async def abort_run(run_id: str):
    """Abort an active run and terminate running sandbox containers."""
    try:
        await run_manager.abort_run(run_id)
        return {"run_id": run_id, "status": "aborted"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
