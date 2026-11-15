"""Cross-platform host path sanitization and mount normalization for Docker."""

import os
import re


def normalize_docker_bind_mount(host_path: str) -> str:
    """Normalize and sanitize a host path for Docker daemon bind mounts.

    Handles Windows drive letters (e.g., C:\\Users\\... -> /c/Users/... or C:/Users/...),
    backslashes, relative paths, and POSIX paths. Works uniformly across Windows,
    macOS, and Linux hosts.

    Args:
        host_path: Raw host filesystem path (can be Windows or POSIX format).

    Returns:
        Sanitized absolute path string formatted for Docker bind mounting.
    """
    if not host_path or not str(host_path).strip():
        raise ValueError("Host path cannot be empty")

    path_str = str(host_path).strip().strip("'\"")

    # Match Windows drive letter pattern (e.g., C:\ or c:/)
    drive_match = re.match(r"^([a-zA-Z]):[/\\](.*)", path_str)
    if drive_match:
        drive_letter = drive_match.group(1).lower()
        rest_of_path = drive_match.group(2).replace("\\", "/")
        # Clean redundant slashes
        rest_of_path = re.sub(r"/+", "/", rest_of_path).lstrip("/")
        return f"/{drive_letter}/{rest_of_path}"

    # If it is already an absolute POSIX path (starts with /)
    if path_str.startswith("/"):
        cleaned = re.sub(r"/+", "/", path_str)
        # Check if it starts with /c/... (drive pattern already)
        match_posix_drive = re.match(r"^/([a-zA-Z])/(.*)", cleaned)
        if match_posix_drive:
            return f"/{match_posix_drive.group(1).lower()}/{match_posix_drive.group(2)}"
        return cleaned

    # Handle relative paths: resolve with abspath
    normalized = os.path.abspath(path_str).replace("\\", "/")
    # If abspath on Windows produced a drive letter like C:/...
    abs_drive_match = re.match(r"^([a-zA-Z]):/(.*)", normalized)
    if abs_drive_match:
        drive_letter = abs_drive_match.group(1).lower()
        rest_of_path = abs_drive_match.group(2).lstrip("/")
        return f"/{drive_letter}/{rest_of_path}"

    return normalized


def get_dataset_mount_target(dataset_filename: str) -> str:
    """Return the container-side read-only mount target for a dataset file.

    Per the sandbox contract, datasets are mounted at /data/input.<ext>.

    Args:
        dataset_filename: Original or stored dataset filename (e.g. sales.csv, metrics.parquet).

    Returns:
        Fixed container mount path (e.g. /data/input.csv or /data/input.parquet).
    """
    ext = os.path.splitext(dataset_filename)[1].lower()
    if not ext:
        ext = ".csv"
    return f"/data/input{ext}"
