"""Matrix service backend boundary.

This module is the first live-service seam for Matrix. It keeps network I/O behind a
small protocol, keeps `matrix-nio` optional, and lets CI exercise Matrix send/sync
behavior without a live homeserver.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Protocol

from agent_term.matrix_adapter import MatrixRoomEvent, normalize_matrix_payload


@dataclass(frozen=True)
class MatrixSendRequest:
    """A Matrix message send request."""

    room_id: str
    body: str
    msgtype: str = "m.text"
    thread_root_event_id: str | None = None
    txn_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def content(self) -> dict[str, object]:
        content: dict[str, object] = {"msgtype": self.msgtype, "body": self.body}
        if self.thread_root_event_id:
            content["m.relates_to"] = {
                "rel_type": "m.thread",
                "event_id": self.thread_root_event_id,
            }
        return content


@dataclass(frozen=True)
class MatrixSendResult:
    """Result of a Matrix message send attempt."""

    ok: bool
    room_id: str
    event_id: str | None = None
    status: str = "sent"
    error: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, object]:
        return {
            "matrix_room_id": self.room_id,
            "matrix_event_id": self.event_id,
            "matrix_send_status": self.status,
            "matrix_send_error": self.error,
            **self.metadata,
        }


@dataclass(frozen=True)
class MatrixSyncBatch:
    """Normalized Matrix sync batch."""

    events: tuple[MatrixRoomEvent, ...]
    next_batch: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class MatrixServiceBackend(Protocol):
    """Backend contract for Matrix service operations."""

    def send_text(self, request: MatrixSendRequest) -> MatrixSendResult:
        """Send a text event into a Matrix room."""

    def normalize_sync(self, payload: dict[str, Any]) -> MatrixSyncBatch:
        """Normalize a Matrix sync payload into AgentTerm MatrixRoomEvents."""


class InMemoryMatrixServiceBackend:
    """Offline Matrix backend for tests and local development."""

    def __init__(self) -> None:
        self.sent: list[MatrixSendRequest] = []

    def send_text(self, request: MatrixSendRequest) -> MatrixSendResult:
        self.sent.append(request)
        event_id = f"$local-{len(self.sent)}"
        return MatrixSendResult(
            ok=True,
            room_id=request.room_id,
            event_id=event_id,
            status="sent",
            metadata={"local_backend": True, "txn_id": request.txn_id},
        )

    def normalize_sync(self, payload: dict[str, Any]) -> MatrixSyncBatch:
        return normalize_sync_payload(payload)


class NioMatrixServiceBackend:
    """Optional matrix-nio backed Matrix service backend.

    The class imports `nio` lazily so the base package and CI do not require the
    optional Matrix dependency. Callers should use the `matrix` extra to enable it.
    """

    def __init__(
        self,
        *,
        homeserver_url: str,
        user_id: str,
        access_token: str,
        device_name: str | None = None,
    ) -> None:
        self.homeserver_url = homeserver_url
        self.user_id = user_id
        self.access_token = access_token
        self.device_name = device_name

    def send_text(self, request: MatrixSendRequest) -> MatrixSendResult:
        return asyncio.run(self._send_text_async(request))

    def normalize_sync(self, payload: dict[str, Any]) -> MatrixSyncBatch:
        return normalize_sync_payload(payload)

    async def _send_text_async(self, request: MatrixSendRequest) -> MatrixSendResult:
        try:
            from nio import AsyncClient, RoomSendError, RoomSendResponse
        except ImportError as exc:
            raise RuntimeError(
                "matrix-nio is required for NioMatrixServiceBackend; install agent-term[matrix]"
            ) from exc

        client = AsyncClient(self.homeserver_url, self.user_id, device_id=self.device_name)
        client.access_token = self.access_token
        try:
            response = await client.room_send(
                room_id=request.room_id,
                message_type="m.room.message",
                content=request.content(),
                txn_id=request.txn_id,
            )
        finally:
            await client.close()

        if isinstance(response, RoomSendResponse):
            return MatrixSendResult(
                ok=True,
                room_id=request.room_id,
                event_id=response.event_id,
                status="sent",
            )
        if isinstance(response, RoomSendError):
            return MatrixSendResult(
                ok=False,
                room_id=request.room_id,
                status="error",
                error=response.message,
            )
        return MatrixSendResult(
            ok=False,
            room_id=request.room_id,
            status="unknown_response",
            error=repr(response),
        )


def normalize_sync_payload(payload: dict[str, Any]) -> MatrixSyncBatch:
    """Normalize Matrix `/sync`-style payload into MatrixRoomEvents."""

    events: list[MatrixRoomEvent] = []
    rooms = _dict(payload.get("rooms"))
    joined = _dict(rooms.get("join"))
    for room_id, room_payload_raw in joined.items():
        room_payload = _dict(room_payload_raw)
        timeline = _dict(room_payload.get("timeline"))
        for event_raw in _list(timeline.get("events")):
            if not isinstance(event_raw, dict):
                continue
            event_payload = {**event_raw}
            event_payload.setdefault("room_id", str(room_id))
            events.append(normalize_matrix_payload(event_payload))

    return MatrixSyncBatch(
        events=tuple(events),
        next_batch=_optional_str(payload.get("next_batch")),
        metadata={"matrix_sync_event_count": len(events)},
    )


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None
