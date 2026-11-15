"""Sandbox execution package."""

import os
from backend.sandbox.base import SandboxExecutor
from backend.sandbox.docker_executor import DockerSandboxExecutor
from backend.sandbox.mock_executor import MockSandboxExecutor
from backend.sandbox.path_normalizer import get_dataset_mount_target, normalize_docker_bind_mount
from backend.sandbox.result import ChartSpec, ExecutionResult, compute_error_signature


def get_sandbox_executor() -> SandboxExecutor:
    """Return configured sandbox executor based on environment and daemon availability."""
    provider = os.getenv("SANDBOX_PROVIDER", "auto").lower()
    if provider == "mock":
        return MockSandboxExecutor()

    docker_exec = DockerSandboxExecutor()
    if docker_exec.is_available():
        return docker_exec

    if provider == "auto":
        # Docker daemon not running locally, seamlessly fallback to MockSandboxExecutor for demo/testing
        return MockSandboxExecutor()

    return docker_exec


__all__ = [
    "SandboxExecutor",
    "DockerSandboxExecutor",
    "MockSandboxExecutor",
    "get_sandbox_executor",
    "ExecutionResult",
    "ChartSpec",
    "compute_error_signature",
    "normalize_docker_bind_mount",
    "get_dataset_mount_target",
]
