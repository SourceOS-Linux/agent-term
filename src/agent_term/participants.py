"""Registered participant dispatch primitives.

AgentTerm cannot enable or invoke non-human participants from local config alone.
This module gates participant dispatch through Agent Registry first and Policy Fabric
where the event is side-effecting or context-sensitive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from agent_term.adapters import AdapterResult
from agent_term.agent_registry import AgentRegistration, AgentRegistryBackend, ToolGrant
from agent_term.events import AgentTermEvent
from agent_term.policy_fabric import ALLOW, PENDING, PolicyDecision, PolicyFabricBackend
from agent_term.policy_fabric import action_for_event, requires_admission


PARTICIPANT_AGENT_IDS = {
    "hermes": "agent.hermes",
    "codex": "agent.codex",
    "claude-code": "agent.claude-code",
    "openclaw": "agent.openclaw",
    "github": "agent.github",
    "ci": "agent.ci",
    "mcp": "agent.mcp",
    "local-process": "agent.local-process",
}


@dataclass(frozen=True)
class ParticipantInvocation:
    """Normalized participant invocation result."""

    participant: str
    status: str
    message: str
    artifacts: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, object]:
        return {
            "participant": self.participant,
            "participant_status": self.status,
            "participant_message": self.message,
            "participant_artifacts": list(self.artifacts),
            **self.metadata,
        }


class ParticipantBackend(Protocol):
    """Backend contract for invoking a registered participant."""

    def invoke(
        self,
        event: AgentTermEvent,
        registration: AgentRegistration,
    ) -> ParticipantInvocation:
        """Invoke a participant after registry and policy gates pass."""


class InMemoryParticipantBackend:
    """Test/development backend for participant dispatch."""

    def __init__(self) -> None:
        self.invocations: list[tuple[AgentTermEvent, AgentRegistration]] = []

    def invoke(
        self,
        event: AgentTermEvent,
        registration: AgentRegistration,
    ) -> ParticipantInvocation:
        self.invocations.append((event, registration))
        return ParticipantInvocation(
            participant=event.source,
            status="invoked",
            message=f"{registration.agent_id} handled {event.kind}",
            artifacts=tuple(str(item) for item in event.metadata.get("artifacts", ())),
            metadata={"handled_at": datetime.now(UTC).isoformat()},
        )


class RegisteredParticipantAdapter:
    """Dispatch gate for registered non-human participants."""

    key = "registered-participant"

    def __init__(
        self,
        registry_backend: AgentRegistryBackend,
        policy_backend: PolicyFabricBackend,
        participant_backend: ParticipantBackend,
    ) -> None:
        self.registry_backend = registry_backend
        self.policy_backend = policy_backend
        self.participant_backend = participant_backend

    def supports(self, event: AgentTermEvent) -> bool:
        return event.source in PARTICIPANT_AGENT_IDS or event.kind in {
            "participant_dispatch",
            "agent_message",
            "github_mutation",
            "ci_retry",
            "mcp_tool_call",
        }

    def handle(self, event: AgentTermEvent) -> AdapterResult:
        agent_id = _agent_id(event)
        if not agent_id:
            return _deny(event, "missing_agent_id")

        registration = self.registry_backend.resolve_agent(agent_id)
        if registration is None:
            return _deny(event, "unknown_agent", agent_id=agent_id)
        if not registration.is_enabled:
            return _deny(
                event,
                "agent_not_enabled",
                agent_id=agent_id,
                extra=registration.to_metadata(),
            )

        grant = None
        tool = _tool(event)
        if tool:
            grant = self.registry_backend.resolve_tool_grant(agent_id, tool)
            if grant is None or not grant.is_active:
                return _deny(
                    event,
                    "tool_grant_not_active",
                    agent_id=agent_id,
                    extra={"tool": tool},
                )

        decision = None
        if requires_admission(event):
            decision = self.policy_backend.evaluate(event)
            if decision is None:
                return _deny(event, "no_policy_decision", agent_id=agent_id)
            if decision.status == PENDING:
                return _deny(
                    event,
                    "policy_decision_pending",
                    agent_id=agent_id,
                    extra=decision.to_metadata(),
                )
            if decision.status != ALLOW:
                return _deny(
                    event,
                    decision.reason or "policy_denied",
                    agent_id=agent_id,
                    extra=decision.to_metadata(),
                )

        invocation = self.participant_backend.invoke(event, registration)
        return AdapterResult(
            ok=True,
            source=event.source,
            body=f"Registered participant invoked: {agent_id}",
            kind="participant_dispatch",
            metadata={
                "request_event_id": event.event_id,
                "dispatch_status": "invoked",
                "adapter_key": event.source,
                "policy_action": action_for_event(event),
                **registration.to_metadata(),
                **_grant_metadata(grant),
                **_decision_metadata(decision),
                **invocation.to_metadata(),
            },
        )


def _agent_id(event: AgentTermEvent) -> str | None:
    value = (
        event.metadata.get("agent_id")
        or event.metadata.get("agentRegistryId")
        or event.metadata.get("agent_registry_id")
        or PARTICIPANT_AGENT_IDS.get(event.source)
    )
    return str(value) if value else None


def _tool(event: AgentTermEvent) -> str | None:
    value = event.metadata.get("tool") or event.metadata.get("tool_name")
    return str(value) if value else None


def _grant_metadata(grant: ToolGrant | None) -> dict[str, object]:
    return grant.to_metadata() if grant else {}


def _decision_metadata(decision: PolicyDecision | None) -> dict[str, object]:
    return decision.to_metadata() if decision else {}


def _deny(
    event: AgentTermEvent,
    reason: str,
    *,
    agent_id: str | None = None,
    extra: dict[str, object] | None = None,
) -> AdapterResult:
    metadata: dict[str, object] = {
        "request_event_id": event.event_id,
        "dispatch_status": "denied",
        "deny_reason": reason,
        "fail_closed": True,
        "adapter_key": event.source,
        "policy_action": action_for_event(event),
    }
    if agent_id:
        metadata["agent_id"] = agent_id
    if extra:
        metadata.update(extra)
    return AdapterResult(
        ok=False,
        source=event.source,
        body=f"Registered participant denied request: {reason}",
        kind="participant_dispatch",
        metadata=metadata,
    )
