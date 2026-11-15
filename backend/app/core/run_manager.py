"""Run execution manager coordinating LangGraph, WebSocket streaming, and state persistence."""

import asyncio
import logging
import os
import time
from typing import Any, Dict, Optional, Set
from fastapi import WebSocket
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from backend.app.core.config import settings
from backend.app.core.event_store import event_store
from backend.app.core.events import AgentEvent, make_event
from backend.graph.builder import build_graph, calculate_recursion_limit
from backend.graph.llm import get_llm
from backend.graph.state import AgentState, DatasetMeta
from backend.sandbox import get_sandbox_executor

logger = logging.getLogger(__name__)


class ActiveRun:
    """In-memory tracking structure for an active analysis run."""

    def __init__(self, run_id: str, state: AgentState):
        self.run_id = run_id
        self.state = state
        self.status = state.status
        self.task: Optional[asyncio.Task] = None
        self.subscribers: Set[WebSocket] = set()
        self.is_paused = False
        self.pending_code: Optional[str] = None
        self.active_time_seconds = 0.0
        self.last_resumed_at = time.time()
        self.paused_at: Optional[float] = None


class RunManager:
    """Orchestrates run lifecycle, background execution tasks, and WebSocket subscribers."""

    def __init__(self):
        self.active_runs: Dict[str, ActiveRun] = {}
        self._lock = asyncio.Lock()

    async def register_subscriber(self, run_id: str, websocket: WebSocket) -> None:
        """Register a WebSocket connection to receive live run events."""
        async with self._lock:
            if run_id not in self.active_runs:
                # Run might be in DB from previous process session
                latest_state = await self.load_state_from_db(run_id)
                self.active_runs[run_id] = ActiveRun(run_id, latest_state)
            self.active_runs[run_id].subscribers.add(websocket)

    async def unregister_subscriber(self, run_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket connection on disconnect."""
        async with self._lock:
            if run_id in self.active_runs:
                self.active_runs[run_id].subscribers.discard(websocket)

    async def broadcast_event(self, run_id: str, event: AgentEvent) -> None:
        """Persist event to SQLite and broadcast to all connected WebSocket clients."""
        await event_store.save_event(event)

        active = self.active_runs.get(run_id)
        if not active or not active.subscribers:
            return

        dead_sockets = set()
        msg_dict = event.to_dict()

        for ws in active.subscribers:
            try:
                await ws.send_json(msg_dict)
            except Exception:
                dead_sockets.add(ws)

        for ds in dead_sockets:
            active.subscribers.discard(ds)

    async def start_run(
        self,
        run_id: str,
        user_question: str,
        dataset_path: str,
        filename: Optional[str] = None,
        review_before_run: bool = False,
    ) -> ActiveRun:
        """Initialize and launch an autonomous analysis run in the background."""
        dataset_name = filename or os.path.basename(dataset_path)
        ext = os.path.splitext(dataset_name)[1].lower().lstrip(".")
        file_type = "parquet" if ext == "parquet" else "csv"
        size_bytes = os.path.getsize(dataset_path) if os.path.exists(dataset_path) else 0

        initial_state = AgentState(
            run_id=run_id,
            user_question=user_question,
            dataset_meta=DatasetMeta(
                filename=dataset_name,
                file_path=dataset_path,
                file_type=file_type,
                size_bytes=size_bytes,
            ),
            review_before_run=review_before_run,
            status="pending",
        )

        active_run = ActiveRun(run_id, initial_state)
        async with self._lock:
            self.active_runs[run_id] = active_run

        # Launch graph loop in background task
        active_run.task = asyncio.create_task(self._run_graph_loop(active_run, initial_input=initial_state))
        return active_run

    async def pause_run(self, run_id: str) -> None:
        """Signal an active run to pause before the next execution."""
        active = self.active_runs.get(run_id)
        if not active:
            raise ValueError(f"Run {run_id} not found")
        active.is_paused = True
        active.state.is_paused = True

    async def resume_run(self, run_id: str, edited_code: Optional[str] = None) -> None:
        """Resume an interrupted run using Command(resume={"edited_code": ...})."""
        active = self.active_runs.get(run_id)
        if not active:
            latest_state = await self.load_state_from_db(run_id)
            active = ActiveRun(run_id, latest_state)
            async with self._lock:
                self.active_runs[run_id] = active

        active.is_paused = False
        active.state.is_paused = False
        active.status = "running"
        active.last_resumed_at = time.time()
        active.paused_at = None

        resume_cmd = Command(resume={"edited_code": edited_code} if edited_code else {})
        active.task = asyncio.create_task(self._run_graph_loop(active, initial_input=resume_cmd))

    async def abort_run(self, run_id: str) -> None:
        """Abort active execution, terminate containers, and emit terminal aborted event."""
        active = self.active_runs.get(run_id)
        if active and active.task and not active.task.done():
            active.task.cancel()

        latest_seq = await event_store.get_latest_seq(run_id)
        aborted_evt = make_event(
            seq=latest_seq + 1,
            run_id=run_id,
            event_type="run_status",
            data={"status": "aborted", "reason": "User aborted execution"},
        )
        await self.broadcast_event(run_id, aborted_evt)

        if active:
            active.status = "aborted"
            active.state.status = "aborted"

    async def get_run_details(self, run_id: str) -> Dict[str, Any]:
        """Fetch current run state and persisted events."""
        active = self.active_runs.get(run_id)
        state_obj = active.state if active else await self.load_state_from_db(run_id)
        events = await event_store.get_events_for_run(run_id)

        return {
            "run_id": run_id,
            "status": active.status if active else state_obj.status,
            "user_question": state_obj.user_question,
            "current_step_idx": state_obj.current_step_idx,
            "per_step_retry_count": state_obj.per_step_retry_count,
            "plan": [s.model_dump() for s in state_obj.plan],
            "charts": state_obj.charts,
            "final_report": state_obj.final_report,
            "is_paused": active.is_paused if active else (state_obj.status == "paused"),
            "pending_code": active.pending_code if active else state_obj.pending_code,
            "events": [e.to_dict() for e in events],
        }

    async def load_state_from_db(self, run_id: str) -> AgentState:
        """Reload state snapshot from SQLite checkpointer."""
        try:
            async with AsyncSqliteSaver.from_conn_string(settings.CHECKPOINTS_DB_PATH) as saver:
                graph = build_graph(checkpointer=saver)
                state_snapshot = await graph.aget_state({"configurable": {"thread_id": run_id}})
                if state_snapshot and state_snapshot.values:
                    return AgentState.model_validate(state_snapshot.values)
        except Exception as e:
            logger.debug("Failed loading checkpoint state for %s: %s", run_id, e)

        # Fallback empty state if none exists yet
        return AgentState(run_id=run_id, user_question="")

    async def _run_graph_loop(self, active_run: ActiveRun, initial_input: Any) -> None:
        """Internal background loop streaming LangGraph updates."""
        run_id = active_run.run_id
        config = {
            "configurable": {
                "thread_id": run_id,
                "llm": get_llm(),
                "executor": get_sandbox_executor(),
            },
            "recursion_limit": calculate_recursion_limit(),
        }

        try:
            async with AsyncSqliteSaver.from_conn_string(settings.CHECKPOINTS_DB_PATH) as saver:
                graph = build_graph(checkpointer=saver)

                async for chunk in graph.astream(
                    initial_input,
                    config=config,
                    stream_mode="updates",
                ):
                    # Check for LangGraph interrupt
                    if "__interrupt__" in chunk:
                        interrupt_tuple = chunk["__interrupt__"]
                        interrupt_val = interrupt_tuple[0].value if interrupt_tuple else {}
                        active_run.is_paused = True
                        active_run.status = "paused"
                        active_run.paused_at = time.time()
                        active_run.pending_code = interrupt_val.get("pending_code")

                        latest_seq = await event_store.get_latest_seq(run_id)
                        pause_evt = make_event(
                            seq=latest_seq + 1,
                            run_id=run_id,
                            event_type="paused",
                            data={
                                "step_id": interrupt_val.get("step_id"),
                                "pending_code": active_run.pending_code,
                            },
                        )
                        await self.broadcast_event(run_id, pause_evt)
                        return

                    # Broadcast events emitted by graph nodes
                    for node_name, updates in chunk.items():
                        if isinstance(updates, dict):
                            # Update local state tracking
                            for k, v in updates.items():
                                if hasattr(active_run.state, k) and k != "events":
                                    setattr(active_run.state, k, v)

                            if "status" in updates:
                                active_run.status = updates["status"]

                            # Broadcast newly added events
                            new_events = updates.get("events", [])
                            for evt in new_events:
                                await self.broadcast_event(run_id, evt)

            active_run.status = active_run.state.status

        except asyncio.CancelledError:
            logger.info("Run %s background task was cancelled.", run_id)
        except Exception as e:
            logger.error("Unhandled error in run graph loop for %s: %s", run_id, e, exc_info=True)
            active_run.status = "failed"
            latest_seq = await event_store.get_latest_seq(run_id)
            err_evt = make_event(
                seq=latest_seq + 1,
                run_id=run_id,
                event_type="run_status",
                data={"status": "failed", "error": str(e)},
            )
            await self.broadcast_event(run_id, err_evt)


# Global singleton run manager
run_manager = RunManager()
