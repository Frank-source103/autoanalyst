"""Adversarial security and isolation tests for DockerSandboxExecutor."""

import os
import tempfile
import pytest
import docker
from docker.errors import DockerException

from backend.sandbox.docker_executor import DockerSandboxExecutor
from backend.sandbox.result import ExecutionResult, ChartSpec


@pytest.mark.asyncio
async def test_daemon_unavailable_returns_structured_result():
    """Verify that if Docker daemon is unreachable, executor returns a structured failure without crashing."""
    # Pass a dummy client that raises DockerException
    class MockFailingDockerClient:
        def ping(self):
            raise DockerException("Simulated Docker daemon failure: connection refused")

    executor = DockerSandboxExecutor(client=MockFailingDockerClient())
    dummy_code = "print('hello')"

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        f.write(b"colA,colB\n1,2\n")
        temp_dataset = f.name

    try:
        result = await executor.execute_code(dummy_code, temp_dataset)
        assert isinstance(result, ExecutionResult)
        assert result.status == "daemon_unavailable"
        assert result.exit_code == -1
        assert "Docker daemon unavailable" in result.stderr
        assert result.error_signature == "DockerDaemonUnavailable"
    finally:
        if os.path.exists(temp_dataset):
            os.remove(temp_dataset)


@pytest.mark.asyncio
async def test_script_size_cap_enforced():
    """Verify that scripts exceeding the 64KB cumulative code limit are rejected immediately."""
    executor = DockerSandboxExecutor()
    huge_code = "# " + ("A" * (65 * 1024)) + "\nprint('oversized')"

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        f.write(b"colA,colB\n1,2\n")
        temp_dataset = f.name

    try:
        result = await executor.execute_code(huge_code, temp_dataset)
        assert result.status == "failed"
        assert result.exit_code == -1
        assert "exceeds maximum limit" in result.stderr
        assert "ScriptSizeLimitExceeded" in result.error_signature
    finally:
        if os.path.exists(temp_dataset):
            os.remove(temp_dataset)


def test_chart_spec_validation_rules():
    """Verify ChartSpec enforces schema, point limits, and series existence."""
    # Valid spec
    valid_spec = {
        "chart_type": "bar",
        "title": "Monthly Revenue",
        "data": [{"month": "Jan", "revenue": 100}, {"month": "Feb", "revenue": 150}],
        "series": ["revenue"],
    }
    spec = ChartSpec.model_validate(valid_spec)
    assert spec.chart_type == "bar"

    # Exceeding 500 data points rejected
    invalid_points = {
        "chart_type": "line",
        "title": "Too Many Points",
        "data": [{"x": i, "y": i} for i in range(501)],
    }
    with pytest.raises(ValueError, match="exceeding maximum limit of 500 points"):
        ChartSpec.model_validate(invalid_points)

    # Empty data rejected
    invalid_empty = {
        "chart_type": "scatter",
        "title": "Empty",
        "data": [],
    }
    with pytest.raises(ValueError, match="must not be empty"):
        ChartSpec.model_validate(invalid_empty)

    # Missing series key rejected
    invalid_series = {
        "chart_type": "line",
        "title": "Missing Series",
        "data": [{"x": 1, "val": 2}],
        "series": ["non_existent_key"],
    }
    with pytest.raises(ValueError, match="Series key 'non_existent_key' not found"):
        ChartSpec.model_validate(invalid_series)


# =========================================================================
# Docker-dependent Adversarial Security Tests
# Skipped with descriptive message if Docker daemon is not active on host.
# =========================================================================

@pytest.mark.docker
def test_docker_inspect_container_limits_assertion(docker_client):
    """Verify Docker container is configured with mandatory security limits before running tests."""
    assert docker_client is not None, "Docker client must be available"
    
    executor = DockerSandboxExecutor()
    # Create test container to inspect configuration
    container = docker_client.containers.create(
        image=executor.image_name,
        command=["python", "-c", "import sys; sys.exit(0)"],
        network_disabled=True,
        read_only=True,
        user="1000:1000",
        cap_drop=["ALL"],
        security_opt=["no-new-privileges:true"],
        mem_limit=executor.mem_limit,
        memswap_limit=executor.mem_limit,
        cpu_quota=executor.cpu_quota,
        pids_limit=executor.pids_limit,
        tmpfs={"/tmp/output": "rw,noexec,nosuid,size=50m"},
    )
    try:
        attrs = docker_client.api.inspect_container(container.id)
        host_config = attrs.get("HostConfig", {})
        config = attrs.get("Config", {})

        # Assert mandatory isolation parameters
        assert host_config.get("ReadonlyRootfs") is True, "Rootfs must be read-only"
        assert host_config.get("NetworkMode") == "none", "Network must be disabled"
        assert host_config.get("PidsLimit") == 50, "PidsLimit must be 50"
        assert host_config.get("Memory") == 512 * 1024 * 1024, "MemLimit must be 512MB"
        assert host_config.get("MemorySwap") == 512 * 1024 * 1024, "MemSwap must equal MemLimit"
        assert host_config.get("CapDrop") == ["ALL"], "All capabilities must be dropped"
        assert "no-new-privileges:true" in host_config.get("SecurityOpt", []), "no-new-privileges required"
        assert config.get("User") == "1000:1000", "Must run as non-root UID 1000"
    finally:
        container.remove(force=True)


@pytest.mark.docker
@pytest.mark.asyncio
async def test_infinite_loop_timeout_killed():
    """Verify that an infinite loop is killed by the execution timeout without hanging."""
    executor = DockerSandboxExecutor()
    infinite_code = "import time\nwhile True:\n    time.sleep(0.1)"

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        f.write(b"colA\n1\n")
        dataset_path = f.name

    try:
        result = await executor.execute_code(infinite_code, dataset_path, timeout_seconds=3)
        assert result.status == "timeout"
        assert "TimeoutError" in (result.error_signature or "")
    finally:
        if os.path.exists(dataset_path):
            os.remove(dataset_path)


@pytest.mark.docker
@pytest.mark.asyncio
async def test_network_egress_blocked():
    """Verify that socket network egress is strictly refused by container isolation."""
    executor = DockerSandboxExecutor()
    egress_code = """
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
try:
    s.connect(("8.8.8.8", 53))
    print("EGRESS_ALLOWED")
except Exception as e:
    print(f"EGRESS_BLOCKED: {e}")
"""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        f.write(b"colA\n1\n")
        dataset_path = f.name

    try:
        result = await executor.execute_code(egress_code, dataset_path, timeout_seconds=10)
        assert "EGRESS_ALLOWED" not in result.stdout
        assert "EGRESS_BLOCKED" in result.stdout or result.exit_code != 0
    finally:
        if os.path.exists(dataset_path):
            os.remove(dataset_path)


@pytest.mark.docker
@pytest.mark.asyncio
async def test_readonly_filesystem_rejects_writes():
    """Verify that writes outside /tmp/output raise Read-only file system error."""
    executor = DockerSandboxExecutor()
    write_code = """
try:
    with open('/etc/hacked.txt', 'w') as f:
        f.write('malicious')
except OSError as e:
    print(f"WRITE_REJECTED: {type(e).__name__}: {e}")
"""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        f.write(b"colA\n1\n")
        dataset_path = f.name

    try:
        result = await executor.execute_code(write_code, dataset_path, timeout_seconds=10)
        assert "WRITE_REJECTED: OSError: [Errno 30] Read-only file system" in result.stdout or "Read-only" in result.stderr
    finally:
        if os.path.exists(dataset_path):
            os.remove(dataset_path)


@pytest.mark.docker
@pytest.mark.asyncio
async def test_memory_bomb_cleanly_oom_killed():
    """Verify that a memory bomb allocating >512MB is caught as an OOM kill."""
    executor = DockerSandboxExecutor()
    oom_code = """
# Attempt to allocate 700MB in 512MB limit
chunks = []
for _ in range(70):
    chunks.append(b'x' * (10 * 1024 * 1024))
"""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        f.write(b"colA\n1\n")
        dataset_path = f.name

    try:
        result = await executor.execute_code(oom_code, dataset_path, timeout_seconds=15)
        assert result.status == "oom"
        assert "OutOfMemoryError" in (result.error_signature or "")
    finally:
        if os.path.exists(dataset_path):
            os.remove(dataset_path)


@pytest.mark.docker
@pytest.mark.asyncio
async def test_fork_bomb_stopped_by_pids_limit():
    """Verify that a fork bomb is halted by pids_limit=50 without starving host processes."""
    executor = DockerSandboxExecutor()
    fork_bomb_code = """
import os, time
try:
    while True:
        os.fork()
except (BlockingIOError, OSError) as e:
    print(f"FORK_STOPPED: {e}")
"""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        f.write(b"colA\n1\n")
        dataset_path = f.name

    try:
        result = await executor.execute_code(fork_bomb_code, dataset_path, timeout_seconds=10)
        assert result.exit_code != 0 or "FORK_STOPPED" in result.stdout
    finally:
        if os.path.exists(dataset_path):
            os.remove(dataset_path)
