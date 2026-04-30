"""Matrix adapter primitives.

AgentTerm is Matrix-first, but this module intentionally avoids a live Matrix SDK.
It normalizes Matrix-style event payloads and enforces encrypted-room posture so
network I/O can be added later behind the same contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_term.adapters import AdapterResult
from agent_term.events import AgentTermEvent


@dataclass(frozen=True)
class MatrixE2EEPosture:
    """Encrypted-room posture for a Matrix room or event."""

    encrypted: bool = False
    verified: bool | None = None
    reason: str | None = None

    @property
    def can_release_sensitive_context(self) -> bool:
        if not self.encrypted:
            return True
        return self.verified is True

    def to_metadata(self) -> dict[str, object]:
        return {
            "matrix_encrypted": self.encrypted,
            "matrix_e2ee_verified": self.verified,
            "matrix_e2ee_reason": self.reason,
            "matrix_sensitive_context_allowed": self.can_release_sensitive_context,
        }


@dataclass(frozen=True)
class MatrixRoomEvent:
    """Normalized Matrix event metadata preserved by AgentTerm."""

    room_id: str
    event_id: str
    sender_mxid: str
    event_type: str
    body: str
    room_alias: str | None = None
    thread_root_event_id: str | None = None
    redacted: bool = False
    membership: str | None = None
    bridge_metadata: dict[str, object] = field(default_factory=dict)
    e2ee: MatrixE2EEPosture = field(default_factory=MatrixE2EEPosture)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def channel(self) -> str:
        return self.room_alias or self.room_id

    def to_agentterm_event(self) -> AgentTermEvent:
        kind = "matrix_room_event"
        if self.redacted:
            kind = "matrix_redaction"
        elif self.membership:
            kind = "matrix_membership"

        return AgentTermEvent(
            channel=self.channel,
            sender=self.sender_mxid,
            kind=kind,
            source="matrix",
            body=self.body,
            thread_id=self.thread_root_event_id,
            metadata=self.to_metadata(),
        )

    def to_metadata(self) -> dict[str, object]:
        return {
            "matrix_room_id": self.room_id,
            "matrix_room_alias": self.room_alias,
            "matrix_event_id": self.event_id,
            "matrix_sender_mxid": self.sender_mxid,
            "matrix_event_type": self.event_type,
            "matrix_thread_root_event_id": self.thread_root_event_id,
            "matrix_redacted": self.redacted,
            "matrix_membership": self.membership,
            "matrix_bridge_metadata": self.bridge_metadata,
            **self.e2ee.to_metadata(),
        }


class MatrixAdapter:
    """Matrix adapter scaffold for event normalization and posture checks."""

    key = "matrix"

    def supports(self, event: AgentTermEvent) -> bool:
        return event.source == self.key or event.kind in {
            "matrix_room_event",
            "matrix_redaction",
            "matrix_membership",
            "matrix_e2ee_posture_check",
            "matrix_emit",
        }

    def handle(self, event: AgentTermEvent) -> AdapterResult:
        if event.kind in {"matrix_room_event", "matrix_redaction", "matrix_membership"}:
            return self._normalize_room_event(event)
        if event.kind == "matrix_e2ee_posture_check":
            return self._check_e2ee_posture(event)
        if event.kind == "matrix_emit":
            return self._prepare_emit(event)
        return AdapterResult(
            ok=False,
            source=self.key,
            body=f"Unsupported Matrix event kind: {event.kind}",
            metadata={"matrix_status": "unsupported_kind", "fail_closed": True},
        )

    def _normalize_room_event(self, event: AgentTermEvent) -> AdapterResult:
        payload = _payload_from_event(event)
        normalized = normalize_matrix_payload(payload)
        return AdapterResult(
            ok=True,
            source=self.key,
            body=f"Matrix event normalized: {normalized.event_id}",
            kind="matrix_room_event",
            metadata={
                "request_event_id": event.event_id,
                "matrix_status": "normalized",
                **normalized.to_metadata(),
            },
        )

    def _check_e2ee_posture(self, event: AgentTermEvent) -> AdapterResult:
        posture = posture_from_metadata(event.metadata)
        if not posture.can_release_sensitive_context:
            return AdapterResult(
                ok=False,
                source=self.key,
                body="Matrix E2EE posture blocks sensitive context release",
                kind="matrix_e2ee_posture_check",
                metadata={
                    "request_event_id": event.event_id,
                    "matrix_status": "blocked",
                    "fail_closed": True,
                    **posture.to_metadata(),
                },
            )
        return AdapterResult(
            ok=True,
            source=self.key,
            body="Matrix E2EE posture allows sensitive context release",
            kind="matrix_e2ee_posture_check",
            metadata={
                "request_event_id": event.event_id,
                "matrix_status": "allowed",
                **posture.to_metadata(),
            },
        )

    def _prepare_emit(self, event: AgentTermEvent) -> AdapterResult:
        posture = posture_from_metadata(event.metadata)
        if event.metadata.get("sensitive_context") and not posture.can_release_sensitive_context:
            return AdapterResult(
                ok=False,
                source=self.key,
                body="Matrix emit blocked by E2EE posture",
                kind="matrix_emit",
                metadata={
                    "request_event_id": event.event_id,
                    "matrix_status": "blocked",
                    "fail_closed": True,
                    **posture.to_metadata(),
                },
            )
        return AdapterResult(
            ok=True,
            source=self.key,
            body="Matrix emit prepared for live adapter dispatch",
            kind="matrix_emit",
            metadata={
                "request_event_id": event.event_id,
                "matrix_status": "prepared",
                "matrix_room_id": event.metadata.get("matrix_room_id"),
                "matrix_room_alias": event.metadata.get("matrix_room_alias"),
                **posture.to_metadata(),
            },
        )


def normalize_matrix_payload(payload: dict[str, Any]) -> MatrixRoomEvent:
    content = _dict(payload.get("content"))
    unsigned = _dict(payload.get("unsigned"))
    room_id = str(payload.get("room_id") or payload.get("roomId") or "")
    event_id = str(payload.get("event_id") or payload.get("eventId") or "")
    sender = str(payload.get("sender") or payload.get("sender_mxid") or "")
    event_type = str(payload.get("type") or payload.get("event_type") or "m.room.message")
    room_alias = _optional_str(payload.get("room_alias") or payload.get("roomAlias"))
    membership = _optional_str(content.get("membership")) if event_type == "m.room.member" else None
    redacted = event_type == "m.room.redaction" or bool(payload.get("redacted"))
    thread_root = _thread_root_event_id(content, unsigned)
    bridge_metadata = _bridge_metadata(payload, content, unsigned)
    e2ee = posture_from_metadata({**payload, **content})

    body = _body_from_payload(payload, content, redacted=redacted, membership=membership)

    return MatrixRoomEvent(
        room_id=room_id,
        event_id=event_id,
        sender_mxid=sender,
        event_type=event_type,
        body=body,
        room_alias=room_alias,
        thread_root_event_id=thread_root,
        redacted=redacted,
        membership=membership,
        bridge_metadata=bridge_metadata,
        e2ee=e2ee,
        raw=payload,
    )


def posture_from_metadata(metadata: dict[str, Any]) -> MatrixE2EEPosture:
    encrypted = bool(
        metadata.get("matrix_encrypted")
        or metadata.get("encrypted")
        or metadata.get("is_encrypted")
    )
    verified_value = (
        metadata.get("matrix_e2ee_verified")
        if "matrix_e2ee_verified" in metadata
        else metadata.get("verified")
    )
    verified = None if verified_value is None else bool(verified_value)
    reason = _optional_str(metadata.get("matrix_e2ee_reason") or metadata.get("e2ee_reason"))
    return MatrixE2EEPosture(encrypted=encrypted, verified=verified, reason=reason)


def _payload_from_event(event: AgentTermEvent) -> dict[str, Any]:
    payload = event.metadata.get("matrix_event") or event.metadata.get("payload")
    if isinstance(payload, dict):
        return payload
    return {
        "room_id": event.metadata.get("matrix_room_id") or event.channel,
        "room_alias": event.metadata.get("matrix_room_alias") or event.channel,
        "event_id": event.metadata.get("matrix_event_id") or event.event_id,
        "sender": event.sender,
        "type": event.metadata.get("matrix_event_type") or "m.room.message",
        "content": {"body": event.body},
        "matrix_encrypted": event.metadata.get("matrix_encrypted"),
        "matrix_e2ee_verified": event.metadata.get("matrix_e2ee_verified"),
    }


def _body_from_payload(
    payload: dict[str, Any],
    content: dict[str, Any],
    *,
    redacted: bool,
    membership: str | None,
) -> str:
    if redacted:
        return "<redacted>"
    if membership:
        return f"membership:{membership}"
    return str(content.get("body") or payload.get("body") or "")


def _thread_root_event_id(content: dict[str, Any], unsigned: dict[str, Any]) -> str | None:
    relates_to = _dict(content.get("m.relates_to"))
    if relates_to.get("rel_type") == "m.thread" and relates_to.get("event_id"):
        return str(relates_to["event_id"])
    reply = _dict(_dict(unsigned.get("m.relations")).get("m.in_reply_to"))
    if reply.get("event_id"):
        return str(reply["event_id"])
    return None


def _bridge_metadata(
    payload: dict[str, Any],
    content: dict[str, Any],
    unsigned: dict[str, Any],
) -> dict[str, object]:
    bridge = payload.get("bridge") or content.get("bridge") or unsigned.get("bridge")
    if isinstance(bridge, dict):
        return bridge

    keys = (
        "fi.mau.double_puppet_source",
        "com.beeper.linkedin.puppet",
        "uk.half-shot.bridge",
        "matrix_bridge",
    )
    bridged = {key: content[key] for key in keys if key in content}
    return bridged


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None
