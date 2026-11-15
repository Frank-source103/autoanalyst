"""File upload route with format and size validation."""

import os
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, status

from backend.app.core.config import settings
from backend.app.core.models import UploadResponse

router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(file: UploadFile) -> UploadResponse:
    """Upload and validate a dataset (CSV or Parquet) with strict security limits."""
    filename = file.filename or "dataset.csv"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed formats: {', '.join(settings.ALLOWED_EXTENSIONS)}",
        )

    # Read and validate file size
    contents = await file.read()
    size_bytes = len(contents)

    if size_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    if size_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({size_bytes} bytes) exceeds limit of {settings.MAX_UPLOAD_SIZE_BYTES} bytes.",
        )

    # Store under server-generated UUID to prevent path traversal or collision
    dataset_id = uuid.uuid4().hex
    saved_filename = f"{dataset_id}{ext}"
    saved_path = os.path.join(settings.UPLOAD_DIR, saved_filename)

    with open(saved_path, "wb") as f:
        f.write(contents)

    return UploadResponse(
        dataset_id=dataset_id,
        filename=filename,
        file_path=os.path.abspath(saved_path),
        file_type="parquet" if ext == ".parquet" else "csv",
        size_bytes=size_bytes,
    )


@router.post("/upload/sample", response_model=UploadResponse)
async def load_sample_dataset() -> UploadResponse:
    """Load pre-packaged synthetic e-commerce sales sample dataset for demo and testing."""
    possible_paths = [
        os.path.abspath(os.path.join(settings.BASE_DIR, "sample-data", "ecommerce_sales.csv")),
        os.path.abspath(os.path.join(settings.BASE_DIR, "..", "sample-data", "ecommerce_sales.csv")),
        os.path.abspath("sample-data/ecommerce_sales.csv"),
    ]
    sample_path = next((p for p in possible_paths if os.path.exists(p)), None)
    if not sample_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sample dataset not found at any of: {possible_paths}",
        )

    with open(sample_path, "rb") as f:
        contents = f.read()

    dataset_id = "sample_ecommerce"
    saved_filename = f"{dataset_id}.csv"
    saved_path = os.path.join(settings.UPLOAD_DIR, saved_filename)
    with open(saved_path, "wb") as f:
        f.write(contents)

    return UploadResponse(
        dataset_id=dataset_id,
        filename="ecommerce_sales.csv",
        file_path=os.path.abspath(saved_path),
        file_type="csv",
        size_bytes=len(contents),
    )

