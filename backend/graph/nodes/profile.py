"""Trusted data profiling node."""

import json
import logging
import re
from typing import Any, Dict
from langchain_core.runnables import RunnableConfig

from backend.app.core.events import make_event
from backend.graph.profiler import get_trusted_profiling_code
from backend.graph.state import AgentState, DatasetMeta
from backend.sandbox import get_sandbox_executor

logger = logging.getLogger(__name__)


async def profile_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Execute fixed trusted profiling script inside the sandbox environment."""
    executor = config.get("configurable", {}).get("executor") or get_sandbox_executor()
    seq = len(state.events) + 1

    thought_evt = make_event(
        seq=seq,
        run_id=state.run_id,
        event_type="thought",
        data={"thought": "Executing trusted profiling script to inspect dataset structure, dtypes, and distributions."},
    )

    trusted_script = get_trusted_profiling_code()
    result = await executor.execute_code(
        code=trusted_script,
        dataset_path=state.dataset_meta.file_path,
        timeout_seconds=30,
        run_id=state.run_id,
    )

    profile_data: Dict[str, Any] = {}

    # Extract JSON profile from output markers
    if "__PROFILE_OUTPUT_START__" in result.stdout:
        try:
            match = re.search(r"__PROFILE_OUTPUT_START__\s*(.*?)\s*__PROFILE_OUTPUT_END__", result.stdout, re.DOTALL)
            if match:
                profile_data = json.loads(match.group(1))
        except Exception as e:
            logger.warning("Failed parsing profiling stdout JSON: %s", e)

    # Update dataset_meta
    updated_meta = state.dataset_meta.model_copy()
    if profile_data:
        updated_meta.columns = profile_data.get("columns", updated_meta.columns)
        updated_meta.dtypes = profile_data.get("dtypes", updated_meta.dtypes)
        updated_meta.row_count = profile_data.get("row_count", updated_meta.row_count)
        updated_meta.profile = profile_data

    exec_evt = make_event(
        seq=seq + 1,
        run_id=state.run_id,
        event_type="execution_result",
        data={
            "step": "profile",
            "status": result.status,
            "exit_code": result.exit_code,
            "row_count": updated_meta.row_count,
            "columns": updated_meta.columns,
        },
    )

    return {
        "dataset_meta": updated_meta,
        "events": [thought_evt, exec_evt],
        "iteration_count": state.iteration_count + 1,
    }
