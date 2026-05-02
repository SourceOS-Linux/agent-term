"""Matrix service backend boundary.

This module is the first live-service seam for Matrix. It keeps network I/O behind a
small protocol, keeps `matrix-nio` optional, and lets CI exercise Matrix send/sync
behavior without a live homeserver.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from agent_term.adapters import AdapterResult
from agent_term.config import AgentTermConfig
from agent_term.events import AgentTermEvent
from agent_term.matrix_adapter import MatrixRoomEvent, normalize_matrix_payload, posture_from_metadata


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


class MatrixServiceConfigError(RuntimeError):
    """Raised when Matrix service config is insufficient for a live backend."""


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


class MatrixServiceAdapter:
    """Adapter that performs Matrix service send/sync operations through a backend."""

    key = "matrix-service"

    def __init__(self, backend: MatrixServiceBackend) -> None:
        self.backend = backend

    def supports(self, event: AgentTermEvent) -> bool:
        return event.source == self.key or event.kind in {"matrix_service_send", "matrix_sync"}

    def handle(self, event: AgentTermEvent) -> AdapterResult:
        if event.kind == "matrix_service_send":
            return self._send(event)
        if event.kind == "matrix_sync":
            return self._sync(event)
        return AdapterResult(
            ok=False,
            source=self.key,
            body=f"Unsupported Matrix service event kind: {event.kind}",
            metadata={"matrix_service_status": "unsupported_kind", "fail_closed": True},
        )

    def _send(self, event: AgentTermEvent) -> AdapterResult:
        posture = posture_from_metadata(event.metadata)
        if event.metadata.get("sensitive_context") and not posture.can_release_sensitive_context:
            return AdapterResult(
                ok=False,
                source=self.key,
                body="Matrix service send blocked by E2EE posture",
                kind="matrix_service_send",
                metadata={
                    "request_event_id": event.event_id,
                    "matrix_service_status": "blocked",
                    "deny_reason": "matrix_posture_blocked",
                    "fail_closed": True,
                    **posture.to_metadata(),
                },
            )

        room_id = _optional_str(event.metadata.get("matrix_room_id") or event.channel)
        if not room_id:
            return AdapterResult(
                ok=False,
                source=self.key,
                body="Matrix service send blocked: missing room ID",
                kind="matrix_service_send",
                metadata={"deny_reason": "missing_matrix_room_id", "fail_closed": True},
            )

        result = self.backend.send_text(
            MatrixSendRequest(
                room_id=room_id,
                body=event.body,
                msgtype=str(event.metadata.get("msgtype") or "m.text"),
                thread_root_event_id=_optional_str(
                    event.metadata.get("matrix_thread_root_event_id") or event.thread_id
                ),
                txn_id=_optional_str(event.metadata.get("txn_id")),
                metadata={"request_event_id": event.event_id},
            )
        )
        return AdapterResult(
            ok=result.ok,
            source=self.key,
            body=f"Matrix service send {result.status}: {room_id}",
            kind="matrix_service_send",
            metadata={
                "request_event_id": event.event_id,
                "matrix_service_status": result.status,
                **result.to_metadata(),
                **posture.to_metadata(),
            },
        )

    def _sync(self, event: AgentTermEvent) -> AdapterResult:
        payload = event.metadata.get("matrix_sync") or event.metadata.get("payload")
        if not isinstance(payload, dict):
            return AdapterResult(
                ok=False,
                source=self.key,
                body="Matrix service sync blocked: missing sync payload",
                kind="matrix_sync",
                metadata={"deny_reason": "missing_sync_payload", "fail_closed": True},
            )
        batch = self.backend.normalize_sync(payload)
        return AdapterResult(
            ok=True,
            source=self.key,
            body=f"Matrix service normalized {len(batch.events)} sync events",
            kind="matrix_sync",
            metadata={
                "request_event_id": event.event_id,
                "matrix_service_status": "synced",
                "matrix_sync_event_count": len(batch.events),
                "matrix_next_batch": batch.next_batch,
                "matrix_events": [matrix_event.to_metadata() for matrix_event in batch.events],
            },
        )


def build_matrix_service_backend(
    config: AgentTermConfig,
    *,
    access_token_env: str = "AGENT_TERM_MATRIX_ACCESS_TOKEN",
) -> MatrixServiceBackend:
    """Build a Matrix backend from AgentTerm config.

    Disabled Matrix config returns the offline backend. Enabled Matrix config requires
    homeserver URL, user ID, and an access token from the environment. We avoid storing
    access tokens in JSON config.
    """

    if not config.matrix.enabled:
        return InMemoryMatrixServiceBackend()

    token = os.environ.get(access_token_env)
    if not token:
        raise MatrixServiceConfigError(f"missing Matrix access token env var: {access_token_env}")
    if not config.matrix.homeserver_url:
        raise MatrixServiceConfigError("missing matrix.homeserverUrl")
    if not config.matrix.user_id:
        raise MatrixServiceConfigError("missing matrix.userId")

    return NioMatrixServiceBackend(
        homeserver_url=config.matrix.homeserver_url,
        user_id=config.matrix.user_id,
        access_token=token,
        device_name=config.matrix.device_name,
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
