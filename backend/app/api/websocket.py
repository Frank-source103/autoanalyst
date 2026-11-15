"""WebSocket endpoint with automatic monotonic event replay."""

import json
import logging
from typing import Optional
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from backend.app.core.event_store import event_store
from backend.app.core.run_manager import run_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/runs/{run_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    run_id: str,
    last_seq: Optional[int] = Query(None),
):
    """WebSocket stream for real-time run events with monotonic sequence replay upon reconnect."""
    await websocket.accept()

    try:
        # Replay missed events if client specified last_seq query parameter
        replay_after = last_seq if last_seq is not None else 0
        missed_events = await event_store.get_events_for_run(run_id, after_seq=replay_after)
        for evt in missed_events:
            await websocket.send_json(evt.to_dict())

        # Register for live event broadcasts
        await run_manager.register_subscriber(run_id, websocket)

        # Listen for client control messages (e.g. ping/heartbeat or subscription updates)
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
                msg_type = msg.get("type")

                # Handle client-requested replay: {"type": "replay", "last_seq": 10}
                if msg_type == "replay":
                    req_last_seq = msg.get("last_seq", 0)
                    events = await event_store.get_events_for_run(run_id, after_seq=req_last_seq)
                    for evt in events:
                        await websocket.send_json(evt.to_dict())

                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected for run %s", run_id)
    except Exception as e:
        logger.warning("WebSocket error for run %s: %s", run_id, e)
    finally:
        await run_manager.unregister_subscriber(run_id, websocket)
