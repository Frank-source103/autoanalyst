"""Mock sandbox executor for offline development, browser testing, and automated test suites."""

import json
from typing import Optional
from backend.sandbox.base import SandboxExecutor
from backend.sandbox.result import ExecutionResult


class MockSandboxExecutor(SandboxExecutor):
    """Executes mock responses matching the AutoAnalyst demo workflow."""

    def __init__(self, persistent_fail: bool = False):
        self.persistent_fail = persistent_fail
        self.execution_attempts = 0

    def is_available(self) -> bool:
        return True

    async def execute_code(
        self,
        code: str,
        dataset_path: str,
        timeout_seconds: int = 30,
        run_id: Optional[str] = None,
    ) -> ExecutionResult:
        self.execution_attempts += 1

        # 1. Profiling script
        if "run_profiling" in code or "__PROFILE_OUTPUT_START__" in code or "profile_dataset" in code:
            mock_profile = {
                "row_count": 500,
                "columns": ["order_id", "category", "price", "quantity", "discount", "order_date"],
                "dtypes": {
                    "order_id": "object",
                    "category": "object",
                    "price": "float64",
                    "quantity": "int64",
                    "discount": "float64",
                    "order_date": "object",
                },
                "sample_rows": [
                    {"order_id": "ORD-0001", "category": "Electronics", "price": 499.99, "quantity": 1, "discount": 0.05, "order_date": "2024-01-15"},
                    {"order_id": "ORD-0002", "category": "Home & Kitchen", "price": 49.50, "quantity": 2, "discount": 0.0, "order_date": "2024-01-16"},
                    {"order_id": "ORD-0003", "category": "Apparel", "price": 89.00, "quantity": 3, "discount": 0.15, "order_date": "2024-01-18"},
                ],
            }
            return ExecutionResult(
                status="success",
                stdout=f"__PROFILE_OUTPUT_START__\n{json.dumps(mock_profile)}\n__PROFILE_OUTPUT_END__",
                exit_code=0,
                duration_seconds=0.12,
            )

        # 2. Intentional bug in demo script (Step 1 first attempt)
        if "non_existent_column" in code:
            return ExecutionResult(
                status="failed",
                stderr="KeyError: 'non_existent_column_for_test'",
                exit_code=1,
                duration_seconds=0.08,
                error_signature="KeyError: 'non_existent_column_for_test'",
            )

        # 3. Successful execution with chart data
        chart = {
            "chart_type": "bar",
            "title": "Total Revenue by Product Category",
            "x_label": "Category",
            "y_label": "Total Sales ($)",
            "data": [
                {"category": "Electronics", "sales": 45200.0},
                {"category": "Home & Kitchen", "sales": 32150.0},
                {"category": "Apparel", "sales": 28400.0},
                {"category": "Sports & Outdoors", "sales": 19800.0},
                {"category": "Books & Stationery", "sales": 11250.0},
            ],
            "series": ["sales"],
        }

        return ExecutionResult(
            status="success",
            stdout="Successfully processed category breakdown. Aggregated 500 rows across 5 categories.",
            exit_code=0,
            duration_seconds=0.21,
            chart_data=chart,
        )
