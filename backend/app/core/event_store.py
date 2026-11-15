"""SQLite persistence for monotonic run events."""

import json
import logging
from typing import List, Optional
import aiosqlite

from backend.app.core.config import settings
from backend.app.core.events import AgentEvent

logger = logging.getLogger(__name__)


class EventStore:
    """Stores and retrieves sequential agent events backed by SQLite."""

    def __init__(self, db_path: str = settings.EVENTS_DB_PATH):
        self.db_path = db_path

    async def init_db(self) -> None:
        """Create the events table if it does not already exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS run_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    UNIQUE(run_id, seq)
                );
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_run_events_run_id_seq ON run_events(run_id, seq);"
            )
            await db.commit()

    async def save_event(self, event: AgentEvent) -> None:
        """Persist a single event into SQLite."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO run_events (run_id, seq, timestamp, event_type, data_json)
                VALUES (?, ?, ?, ?, ?);
                """,
                (
                    event.run_id,
                    event.seq,
                    event.timestamp,
                    event.event_type,
                    json.dumps(event.data),
                ),
            )
            await db.commit()

    async def save_events(self, events: List[AgentEvent]) -> None:
        """Persist a batch of events in a single transaction."""
        if not events:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany(
                """
                INSERT OR REPLACE INTO run_events (run_id, seq, timestamp, event_type, data_json)
                VALUES (?, ?, ?, ?, ?);
                """,
                [
                    (e.run_id, e.seq, e.timestamp, e.event_type, json.dumps(e.data))
                    for e in events
                ],
            )
            await db.commit()

    async def get_events_for_run(self, run_id: str, after_seq: int = 0) -> List[AgentEvent]:
        """Fetch ordered events for a run, optionally filtering by seq > after_seq."""
        events: List[AgentEvent] = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT run_id, seq, timestamp, event_type, data_json
                FROM run_events
                WHERE run_id = ? AND seq > ?
                ORDER BY seq ASC;
                """,
                (run_id, after_seq),
            )
            rows = await cursor.fetchall()
            for row in rows:
                try:
                    data = json.loads(row["data_json"])
                except Exception:
                    data = {}
                events.append(
                    AgentEvent(
                        seq=row["seq"],
                        run_id=row["run_id"],
                        timestamp=row["timestamp"],
                        event_type=row["event_type"],
                        data=data,
                    )
                )
        return events

    async def get_latest_seq(self, run_id: str) -> int:
        """Return the highest recorded seq for a run, or 0 if none exist."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM run_events WHERE run_id = ?;",
                (run_id,),
            )
            row = await cursor.fetchone()
            return row[0] if row else 0


# Shared singleton instance
event_store = EventStore()
