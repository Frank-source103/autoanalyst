"""Base abstraction for sandboxed code execution."""

from abc import ABC, abstractmethod
from typing import Optional
from backend.sandbox.result import ExecutionResult


class SandboxExecutor(ABC):
    """Abstract interface for executing untrusted data-science scripts in an isolated sandbox."""

    @abstractmethod
    async def execute_code(
        self,
        code: str,
        dataset_path: str,
        timeout_seconds: int = 30,
        run_id: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute a self-contained Python script with a dataset mounted.

        Args:
            code: The Python script to execute.
            dataset_path: Host path to the dataset (CSV or Parquet).
            timeout_seconds: Maximum wall-clock execution time allowed.
            run_id: Optional tracking identifier for log correlation.

        Returns:
            ExecutionResult containing execution status, logs, exit code, and chart data.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the execution runtime daemon (e.g. Docker) is available and responsive."""
        pass
