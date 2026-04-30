"""SQLite-backed local event log for AgentTerm."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from agent_term.events import AgentTermEvent


DEFAULT_DB_PATH = Path(".agent-term/events.sqlite3")


class EventStore:
    """Durable append-only store for AgentTerm events."""

    def __init__(self, path: Path | str = DEFAULT_DB_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self.init_schema()

    def init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                channel TEXT NOT NULL,
                sender TEXT NOT NULL,
                kind TEXT NOT NULL,
                body TEXT NOT NULL,
                thread_id TEXT,
                source TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_events_channel ON events(channel)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_events_thread ON events(thread_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_events_source ON events(source)")
        self._conn.commit()

    def append(self, event: AgentTermEvent) -> AgentTermEvent:
        self._conn.execute(
            """
            INSERT INTO events (
                event_id, channel, sender, kind, body, thread_id, source, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.channel,
                event.sender,
                event.kind,
                event.body,
                event.thread_id,
                event.source,
                json.dumps(event.metadata, sort_keys=True),
                event.created_at.isoformat(),
            ),
        )
        self._conn.commit()
        return event

    def tail(self, channel: str | None = None, limit: int = 25) -> list[AgentTermEvent]:
        if channel:
            rows: Iterable[sqlite3.Row] = self._conn.execute(
                """
                SELECT * FROM events
                WHERE channel = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (channel, limit),
            )
        else:
            rows = self._conn.execute(
                """
                SELECT * FROM events
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )

        events = [self._row_to_event(row) for row in rows]
        return list(reversed(events))

    def _row_to_event(self, row: sqlite3.Row) -> AgentTermEvent:
        return AgentTermEvent.from_record(
            {
                "event_id": row["event_id"],
                "channel": row["channel"],
                "sender": row["sender"],
                "kind": row["kind"],
                "body": row["body"],
                "thread_id": row["thread_id"],
                "source": row["source"],
                "metadata": json.loads(row["metadata_json"]),
                "created_at": row["created_at"],
            }
        )

    def close(self) -> None:
        self._conn.close()
