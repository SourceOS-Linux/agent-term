"""Durable Matrix sync state and room resolution helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from agent_term.config import AgentTermConfig


DEFAULT_STATE_PATH = Path(".agent-term/matrix-state.json")


@dataclass(frozen=True)
class MatrixSyncState:
    """Durable sync cursor and room-alias state for Matrix workflows."""

    next_batch: str | None = None
    rooms: dict[str, str] = field(default_factory=dict)
    updated_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "next_batch": self.next_batch,
            "rooms": self.rooms,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "MatrixSyncState":
        rooms_raw = value.get("rooms")
        rooms = rooms_raw if isinstance(rooms_raw, dict) else {}
        return cls(
            next_batch=_optional_str(value.get("next_batch")),
            rooms={str(key): str(room_id) for key, room_id in rooms.items()},
            updated_at=_optional_str(value.get("updated_at")),
        )

    def with_next_batch(self, next_batch: str | None) -> "MatrixSyncState":
        if next_batch is None:
            return self
        return MatrixSyncState(
            next_batch=next_batch,
            rooms=self.rooms,
            updated_at=datetime.now(UTC).isoformat(),
        )

    def with_rooms(self, rooms: dict[str, str]) -> "MatrixSyncState":
        merged = {**self.rooms, **rooms}
        return MatrixSyncState(
            next_batch=self.next_batch,
            rooms=merged,
            updated_at=datetime.now(UTC).isoformat(),
        )


class MatrixStateStore:
    """JSON-backed Matrix sync state store."""

    def __init__(self, path: Path | str = DEFAULT_STATE_PATH) -> None:
        self.path = Path(path)

    def load(self) -> MatrixSyncState:
        if not self.path.exists():
            return MatrixSyncState()
        with self.path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, dict):
            raise ValueError("Matrix state file must contain a JSON object")
        return MatrixSyncState.from_dict(raw)

    def save(self, state: MatrixSyncState) -> MatrixSyncState:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(state.to_dict(), handle, indent=2, sort_keys=True)
            handle.write("\n")
        return state

    def update_next_batch(self, next_batch: str | None) -> MatrixSyncState:
        state = self.load().with_next_batch(next_batch)
        return self.save(state)

    def update_rooms(self, rooms: dict[str, str]) -> MatrixSyncState:
        state = self.load().with_rooms(rooms)
        return self.save(state)


def resolve_matrix_room(room: str, config: AgentTermConfig, state: MatrixSyncState) -> str:
    """Resolve a room alias/key to a Matrix room ID when possible."""

    if room in state.rooms:
        return state.rooms[room]
    if room in config.matrix.rooms:
        return config.matrix.rooms[room]
    for alias, room_id in config.matrix.rooms.items():
        if room == alias or room == room_id:
            return room_id
    return room


def rooms_from_sync_payload(payload: dict[str, object]) -> dict[str, str]:
    """Extract room ID mappings from a Matrix sync payload."""

    rooms: dict[str, str] = {}
    rooms_raw = payload.get("rooms")
    if not isinstance(rooms_raw, dict):
        return rooms
    joined = rooms_raw.get("join")
    if not isinstance(joined, dict):
        return rooms
    for room_id in joined:
        rooms[str(room_id)] = str(room_id)
    return rooms


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None
