"""cloudshell-fog adapter primitives.

AgentTerm requests governed shell sessions; cloudshell-fog remains the authority for
OIDC, placement, TTL, PTY attach, and audit semantics. This module is a fakeable
adapter boundary and does not open local shells.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from agent_term.adapters import AdapterResult
from agent_term.events import AgentTermEvent


@dataclass(frozen=True)
class CloudShellSessionRequest:
    """Governed shell-session request handed to cloudshell-fog."""

    profile: str
    ttl_seconds: int
    placement_hint: str
    operator_ref: str
    channel: str
    thread_id: str | None = None
    agent_id: str | None = None
    policy_decision_ref: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "ttl_seconds": self.ttl_seconds,
            "placement_hint": self.placement_hint,
            "operator_ref": self.operator_ref,
            "channel": self.channel,
            "thread_id": self.thread_id,
            "agent_id": self.agent_id,
            "policy_decision_ref": self.policy_decision_ref,
            **self.metadata,
        }


@dataclass(frozen=True)
class CloudShellSession:
    """cloudshell-fog session metadata visible to AgentTerm."""

    session_id: str
    status: str
    placement: str
    attach_ref: str
    audit_correlation_id: str
    expires_at: str
    metadata: dict[str, object] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, object]:
        return {
            "cloudshell_session_id": self.session_id,
            "cloudshell_status": self.status,
            "cloudshell_placement": self.placement,
            "cloudshell_attach_ref": self.attach_ref,
            "cloudshell_audit_correlation_id": self.audit_correlation_id,
            "cloudshell_expires_at": self.expires_at,
            **self.metadata,
        }


class CloudShellFogBackend(Protocol):
    """Backend contract for cloudshell-fog session lifecycle."""

    def request_session(self, request: CloudShellSessionRequest) -> CloudShellSession:
        """Create or reserve a governed shell session."""

    def attach_session(self, session_id: str) -> CloudShellSession | None:
        """Return attach metadata for an existing session, if available."""


class InMemoryCloudShellFogBackend:
    """Test/development backend for cloudshell-fog session lifecycle."""

    def __init__(self) -> None:
        self._sessions: dict[str, CloudShellSession] = {}

    def request_session(self, request: CloudShellSessionRequest) -> CloudShellSession:
        session_id = f"shell-{len(self._sessions) + 1}"
        expires_at = datetime.now(UTC).isoformat()
        session = CloudShellSession(
            session_id=session_id,
            status="running",
            placement=request.placement_hint,
            attach_ref=f"cloudshell-fog://sessions/{session_id}/pty",
            audit_correlation_id=f"audit-{session_id}",
            expires_at=expires_at,
            metadata={
                "profile": request.profile,
                "ttl_seconds": request.ttl_seconds,
            },
        )
        self._sessions[session_id] = session
        return session

    def attach_session(self, session_id: str) -> CloudShellSession | None:
        return self._sessions.get(session_id)


class CloudShellFogAdapter:
    """Adapter that prepares governed shell-session operations."""

    key = "cloudshell-fog"

    def __init__(self, backend: CloudShellFogBackend) -> None:
        self.backend = backend

    def supports(self, event: AgentTermEvent) -> bool:
        return event.source == self.key or event.kind in {"shell_session", "shell_attach"}

    def handle(self, event: AgentTermEvent) -> AdapterResult:
        if event.kind == "shell_session":
            return self._request_session(event)
        if event.kind == "shell_attach":
            return self._attach_session(event)
        return AdapterResult(
            ok=False,
            source=self.key,
            body=f"Unsupported cloudshell-fog event kind: {event.kind}",
            metadata={"cloudshell_status": "unsupported_kind", "fail_closed": True},
        )

    def _request_session(self, event: AgentTermEvent) -> AdapterResult:
        policy_ref = _policy_decision_ref(event)
        if not policy_ref:
            return _deny(event, "missing_policy_decision")

        ttl_seconds = int(event.metadata.get("ttl_seconds") or 3600)
        if ttl_seconds <= 0:
            return _deny(event, "invalid_ttl_seconds")

        request = CloudShellSessionRequest(
            profile=str(event.metadata.get("profile") or "default"),
            ttl_seconds=ttl_seconds,
            placement_hint=str(event.metadata.get("placement_hint") or "fog-first"),
            operator_ref=event.sender,
            channel=event.channel,
            thread_id=event.thread_id,
            agent_id=_optional_str(event.metadata.get("agent_id")),
            policy_decision_ref=policy_ref,
            metadata={
                "matrix_room_id": event.metadata.get("matrix_room_id"),
                "workroom": event.metadata.get("workroom"),
                "topic_scope": event.metadata.get("topic_scope"),
            },
        )
        session = self.backend.request_session(request)
        return AdapterResult(
            ok=True,
            source=self.key,
            body=f"cloudshell-fog session requested: {session.session_id}",
            kind="shell_session",
            metadata={
                "request_event_id": event.event_id,
                "cloudshell_status": "session_requested",
                **request.to_metadata(),
                **session.to_metadata(),
            },
        )

    def _attach_session(self, event: AgentTermEvent) -> AdapterResult:
        policy_ref = _policy_decision_ref(event)
        if not policy_ref:
            return _deny(event, "missing_policy_decision")

        session_id = _optional_str(event.metadata.get("cloudshell_session_id"))
        if not session_id:
            return _deny(event, "missing_session_id")

        session = self.backend.attach_session(session_id)
        if session is None:
            return _deny(event, "unknown_session", session_id=session_id)

        return AdapterResult(
            ok=True,
            source=self.key,
            body=f"cloudshell-fog attach prepared: {session.session_id}",
            kind="shell_attach",
            metadata={
                "request_event_id": event.event_id,
                "cloudshell_status": "attach_prepared",
                "policy_decision_ref": policy_ref,
                **session.to_metadata(),
            },
        )


def _policy_decision_ref(event: AgentTermEvent) -> str | None:
    value = (
        event.metadata.get("policy_decision_ref")
        or event.metadata.get("policy_decision_id")
        or event.metadata.get("policyDecisionRef")
    )
    return _optional_str(value)


def _deny(
    event: AgentTermEvent,
    reason: str,
    *,
    session_id: str | None = None,
) -> AdapterResult:
    metadata: dict[str, object] = {
        "request_event_id": event.event_id,
        "cloudshell_status": "denied",
        "deny_reason": reason,
        "fail_closed": True,
    }
    if session_id:
        metadata["cloudshell_session_id"] = session_id
    return AdapterResult(
        ok=False,
        source="cloudshell-fog",
        body=f"cloudshell-fog denied request: {reason}",
        metadata=metadata,
    )


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None
