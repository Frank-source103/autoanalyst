"""Pytest fixtures and configuration for AutoAnalyst."""

import os
import pytest
import docker
from docker.errors import DockerException


def is_docker_available() -> bool:
    """Check if the Docker daemon is running and accessible."""
    try:
        client = docker.from_env()
        return client.ping()
    except Exception:
        return False


# Register custom markers
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "docker: mark test as requiring a running Docker daemon (skips if absent)"
    )


# Automatically skip tests marked with @pytest.mark.docker if daemon is absent
def pytest_collection_modifyitems(config, items):
    docker_running = is_docker_available()
    skip_docker = pytest.mark.skip(
        reason="Docker daemon is absent or not responding. Start Docker Desktop to run this test."
    )
    for item in items:
        if "docker" in item.keywords and not docker_running:
            item.add_marker(skip_docker)


@pytest.fixture(scope="session")
def docker_client():
    """Session fixture returning a responsive Docker client or None."""
    try:
        client = docker.from_env()
        client.ping()
        return client
    except Exception:
        return None
