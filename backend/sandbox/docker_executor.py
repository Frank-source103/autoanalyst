"""DockerSandboxExecutor: Secure, isolated containerized execution for untrusted Python code."""

import asyncio
import io
import json
import logging
import os
import shutil
import tarfile
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

import docker
from docker.errors import APIError, DockerException, NotFound

from backend.sandbox.base import SandboxExecutor
from backend.sandbox.path_normalizer import get_dataset_mount_target, normalize_docker_bind_mount
from backend.sandbox.result import (
    ChartSpec,
    ExecutionResult,
    compute_error_signature,
)

logger = logging.getLogger(__name__)

# Constants
DEFAULT_IMAGE_NAME = "autoanalyst-sandbox:latest"
DEFAULT_TIMEOUT_SECONDS = 30
MAX_LOG_BYTES = 10 * 1024  # 10 KB cap for stdout/stderr
MAX_SCRIPT_BYTES = 64 * 1024  # 64 KB cumulative code cap
DEFAULT_MEM_LIMIT = "512m"
DEFAULT_PIDS_LIMIT = 50
DEFAULT_CPU_QUOTA = 100000  # 1 CPU core equivalent


class DockerSandboxExecutor(SandboxExecutor):
    """Executes untrusted data-science scripts inside isolated Docker containers with strict security constraints."""

    def __init__(
        self,
        image_name: str = DEFAULT_IMAGE_NAME,
        mem_limit: str = DEFAULT_MEM_LIMIT,
        pids_limit: int = DEFAULT_PIDS_LIMIT,
        cpu_quota: int = DEFAULT_CPU_QUOTA,
        max_log_bytes: int = MAX_LOG_BYTES,
        client: Optional[Any] = None,
    ):
        self.image_name = image_name
        self.mem_limit = mem_limit
        self.pids_limit = pids_limit
        self.cpu_quota = cpu_quota
        self.max_log_bytes = max_log_bytes
        self._client = client

    def _get_client(self) -> Any:
        """Obtain or initialize the Docker client. Validates daemon responsiveness."""
        if self._client is not None:
            if hasattr(self._client, "ping"):
                self._client.ping()
            return self._client
        try:
            client = docker.from_env()
            client.ping()
            self._client = client
            return self._client
        except Exception as e:
            raise DockerException(f"Docker daemon is not available: {e}") from e

    def is_available(self) -> bool:
        """Check if Docker daemon is running and reachable."""
        try:
            self._get_client()
            return True
        except Exception:
            return False

    async def execute_code(
        self,
        code: str,
        dataset_path: str,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        run_id: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute Python code in a fresh, isolated Docker container."""
        # 1. Validate script size limit
        encoded_script = code.encode("utf-8")
        if len(encoded_script) > MAX_SCRIPT_BYTES:
            return ExecutionResult(
                status="failed",
                stderr=f"Script size ({len(encoded_script)} bytes) exceeds maximum limit of {MAX_SCRIPT_BYTES} bytes",
                exit_code=-1,
                error_signature="ScriptSizeLimitExceeded: script exceeds 64KB",
            )

        # 2. Check Docker availability without raising
        try:
            client = self._get_client()
        except Exception as e:
            logger.warning("Docker execution failed: Docker daemon is unavailable: %s", e)
            return ExecutionResult(
                status="daemon_unavailable",
                stderr=f"Docker daemon unavailable: {e}",
                exit_code=-1,
                error_signature="DockerDaemonUnavailable",
            )

        # 3. Create per-run temporary host directory for script mounting
        temp_run_dir = tempfile.mkdtemp(prefix=f"autoanalyst_run_{run_id or 'anon'}_")
        script_file_path = os.path.join(temp_run_dir, "script.py")

        try:
            with open(script_file_path, "w", encoding="utf-8") as f:
                f.write(code)

            # 4. Prepare mounts using cross-platform normalizer
            normalized_script_dir = normalize_docker_bind_mount(temp_run_dir)
            normalized_dataset_path = normalize_docker_bind_mount(dataset_path)
            dataset_mount_target = get_dataset_mount_target(os.path.basename(dataset_path))

            volumes = {
                normalized_script_dir: {"bind": "/run_script", "mode": "ro"},
                normalized_dataset_path: {"bind": dataset_mount_target, "mode": "ro"},
            }

            # Run in worker thread to prevent blocking async event loop
            return await asyncio.to_thread(
                self._run_container_sync,
                client=client,
                volumes=volumes,
                timeout_seconds=timeout_seconds,
            )

        finally:
            # Clean up temporary run directory
            try:
                shutil.rmtree(temp_run_dir, ignore_errors=True)
            except Exception as e:
                logger.debug("Failed to clean up temp dir %s: %s", temp_run_dir, e)

    def _run_container_sync(
        self,
        client: Any,
        volumes: Dict[str, Dict[str, str]],
        timeout_seconds: int,
    ) -> ExecutionResult:
        """Synchronous execution worker that handles container lifecycle and constraints."""
        start_time = time.time()
        container = None
        stdout_chunks: List[bytes] = []
        stderr_chunks: List[bytes] = []
        total_log_bytes = 0
        log_cap_exceeded = False
        oom_killed = False
        timed_out = False
        exit_code = -1

        try:
            # Create fresh container with locked security configuration
            container = client.containers.create(
                image=self.image_name,
                command=["python", "-u", "/run_script/script.py"],
                network_disabled=True,
                read_only=True,
                user="1000:1000",
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                mem_limit=self.mem_limit,
                memswap_limit=self.mem_limit,
                cpu_quota=self.cpu_quota,
                pids_limit=self.pids_limit,
                volumes=volumes,
                tmpfs={"/tmp/output": "rw,noexec,nosuid,size=50m"},
                environment={
                    "HOME": "/tmp/output",
                    "MPLCONFIGDIR": "/tmp/output/.matplotlib",
                    "DUCKDB_TEMP_DIRECTORY": "/tmp/output/.duckdb_temp",
                    "PYTHONUNBUFFERED": "1",
                },
            )

            container.start()

            # Stream logs and enforce output size cap
            log_stream = container.logs(stream=True, stdout=True, stderr=True, follow=True)
            deadline = time.time() + timeout_seconds

            for chunk in log_stream:
                if time.time() > deadline:
                    timed_out = True
                    break

                total_log_bytes += len(chunk)
                if total_log_bytes > self.max_log_bytes:
                    log_cap_exceeded = True
                    stdout_chunks.append(b"\n[Log cap exceeded: output truncated]\n")
                    break

                stdout_chunks.append(chunk)

            if timed_out or log_cap_exceeded:
                try:
                    container.kill()
                except Exception:
                    pass

            # Wait for exit status with remaining timeout
            remaining_time = max(0.5, deadline - time.time())
            try:
                wait_res = container.wait(timeout=int(remaining_time))
                exit_code = wait_res.get("StatusCode", -1)
            except Exception:
                timed_out = True
                try:
                    container.kill()
                except Exception:
                    pass
                exit_code = -1

            # Refresh container inspection state for OOM detection
            try:
                container.reload()
                state = container.attrs.get("State", {})
                oom_killed = bool(state.get("OOMKilled", False))
                if exit_code == -1:
                    exit_code = state.get("ExitCode", -1)
            except Exception:
                pass

            duration = time.time() - start_time

            # Retrieve /tmp/output archive BEFORE removing container
            chart_data, output_files, extraction_error = self._extract_output_archive(container)

            stdout_str = b"".join(stdout_chunks).decode("utf-8", errors="replace")
            stderr_str = b"".join(stderr_chunks).decode("utf-8", errors="replace")

            # Append extraction error to stderr if result.json was invalid
            if extraction_error:
                stderr_str = f"{stderr_str}\n{extraction_error}".strip()

            # Determine final status
            if oom_killed:
                status = "oom"
                err_sig = "OutOfMemoryError: Container memory limit (512MB) exceeded"
            elif timed_out:
                status = "timeout"
                err_sig = f"TimeoutError: Execution exceeded {timeout_seconds}s limit"
            elif exit_code != 0 or extraction_error:
                status = "failed"
                err_sig = compute_error_signature(stderr_str) or f"ExitCodeError: exited with code {exit_code}"
            else:
                status = "success"
                err_sig = None

            return ExecutionResult(
                status=status,
                stdout=stdout_str,
                stderr=stderr_str,
                exit_code=exit_code,
                duration_seconds=round(duration, 3),
                error_signature=err_sig,
                chart_data=chart_data,
                output_files=output_files,
            )

        except Exception as e:
            return ExecutionResult(
                status="daemon_unavailable",
                stderr=f"Docker runtime error: {e}",
                exit_code=-1,
                error_signature="DockerDaemonUnavailable",
                duration_seconds=round(time.time() - start_time, 3),
            )
        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

    def _extract_output_archive(
        self, container: Any
    ) -> Tuple[Optional[Dict[str, Any]], List[str], Optional[str]]:
        """Extract files from /tmp/output before container removal."""
        output_files: List[str] = []
        chart_data: Optional[Dict[str, Any]] = None
        extraction_error: Optional[str] = None

        try:
            bits, _ = container.get_archive("/tmp/output")
            file_obj = io.BytesIO()
            for chunk in bits:
                file_obj.write(chunk)
            file_obj.seek(0)

            with tarfile.open(fileobj=file_obj, mode="r:*") as tar:
                for member in tar.getmembers():
                    # Tar root often includes 'output' directory itself
                    basename = os.path.basename(member.name)
                    if member.isfile() and basename:
                        output_files.append(basename)

                    if basename == "result.json":
                        extracted = tar.extractfile(member)
                        if extracted:
                            raw_content = extracted.read().decode("utf-8", errors="replace")
                            try:
                                json_dict = json.loads(raw_content)
                                # Validate against ChartSpec schema
                                validated_chart = ChartSpec.model_validate(json_dict)
                                chart_data = validated_chart.model_dump()
                            except json.JSONDecodeError as jde:
                                extraction_error = f"InvalidJSONError in result.json: {jde}"
                            except Exception as val_err:
                                extraction_error = f"ChartSchemaValidationError in result.json: {val_err}"

        except Exception as e:
            logger.debug("Failed to extract /tmp/output archive: %s", e)

        return chart_data, output_files, extraction_error
