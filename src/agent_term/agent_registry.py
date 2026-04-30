"""Agent Registry adapter primitives.

AgentTerm is not the authority for agent identity. This module provides a small,
fakeable adapter boundary so AgentTerm can resolve agent identity, session state,
tool grants, and revocation posture before dispatching non-human participants.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from agent_term.adapters import AdapterResult
from agent_term.events import AgentTermEvent


ACTIVE_STATUSES = {"registered", "active"}


@dataclass(frozen=True)
class AgentRegistration:
    """Resolved Agent Registry record for one non-human participant."""

    agent_id: str
    registry_ref: str
    spec_version: str
    runtime_authority: str = "agent-registry"
    status: str = "registered"
    session_id: str | None = None
    tool_grants: frozenset[str] = field(default_factory=frozenset)
    revoked: bool = False
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def is_enabled(self) -> bool:
        return self.status in ACTIVE_STATUSES and not self.revoked

    def to_metadata(self) -> dict[str, object]:
        return {
            "agent_id": self.agent_id,
            "agent_registry_ref": self.registry_ref,
            "agent_spec_version": self.spec_version,
            "runtime_authority": self.runtime_authority,
            "agent_status": self.status,
            "session_id": self.session_id,
            "tool_grants": sorted(self.tool_grants),
            "revoked": self.revoked,
            **self.metadata,
        }


@dataclass(frozen=True)
class ToolGrant:
    """Resolved tool grant for an agent participant."""

    grant_id: str
    agent_id: str
    tool: str
    status: str = "active"
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def to_metadata(self) -> dict[str, object]:
        return {
            "grant_id": self.grant_id,
            "agent_id": self.agent_id,
            "tool": self.tool,
            "grant_status": self.status,
            **self.metadata,
        }


class AgentRegistryBackend(Protocol):
    """Backend contract for Agent Registry lookups."""

    def resolve_agent(self, agent_id: str) -> AgentRegistration | None:
        """Return the agent registration if known."""

    def resolve_tool_grant(self, agent_id: str, tool: str) -> ToolGrant | None:
        """Return a tool grant if active or known."""


class InMemoryAgentRegistryBackend:
    """Test/development backend for Agent Registry lookups.

    This backend is intentionally explicit. It should not be used as production
    authority; it exists so AgentTerm can validate fail-closed behavior in CI.
    """

    def __init__(
        self,
        agents: list[AgentRegistration] | None = None,
        grants: list[ToolGrant] | None = None,
    ) -> None:
        self._agents = {agent.agent_id: agent for agent in agents or []}
        self._grants = {(grant.agent_id, grant.tool): grant for grant in grants or []}

    def resolve_agent(self, agent_id: str) -> AgentRegistration | None:
        return self._agents.get(agent_id)

    def resolve_tool_grant(self, agent_id: str, tool: str) -> ToolGrant | None:
        return self._grants.get((agent_id, tool))


class AgentRegistryAdapter:
    """Adapter that resolves agent identity, grants, and revocation posture."""

    key = "agent-registry"

    def __init__(self, backend: AgentRegistryBackend) -> None:
        self.backend = backend

    def supports(self, event: AgentTermEvent) -> bool:
        return event.source == self.key or event.kind in {
            "agent_identity",
            "validate_agent_registration",
            "tool_grant",
            "revocation_check",
        }

    def handle(self, event: AgentTermEvent) -> AdapterResult:
        if event.kind in {"agent_identity", "validate_agent_registration"}:
            return self._resolve_identity(event)
        if event.kind == "tool_grant":
            return self._resolve_tool_grant(event)
        if event.kind == "revocation_check":
            return self._check_revocation(event)
        return AdapterResult(
            ok=False,
            source=self.key,
            body=f"Unsupported Agent Registry event kind: {event.kind}",
            metadata=self._base_metadata(event, status="unsupported_kind"),
        )

    def _resolve_identity(self, event: AgentTermEvent) -> AdapterResult:
        agent_id = self._agent_id(event)
        if not agent_id:
            return self._deny(event, "missing_agent_id")

        registration = self.backend.resolve_agent(agent_id)
        if registration is None:
            return self._deny(event, "unknown_agent", agent_id=agent_id)
        if not registration.is_enabled:
            return self._deny(
                event,
                "agent_not_enabled",
                agent_id=agent_id,
                extra=registration.to_metadata(),
            )

        return AdapterResult(
            ok=True,
            source=self.key,
            body=f"Agent Registry resolved {agent_id}",
            metadata={
                **self._base_metadata(event, status="resolved"),
                **registration.to_metadata(),
            },
        )

    def _resolve_tool_grant(self, event: AgentTermEvent) -> AdapterResult:
        agent_id = self._agent_id(event)
        tool = self._tool(event)
        if not agent_id:
            return self._deny(event, "missing_agent_id")
        if not tool:
            return self._deny(event, "missing_tool", agent_id=agent_id)

        registration = self.backend.resolve_agent(agent_id)
        if registration is None:
            return self._deny(event, "unknown_agent", agent_id=agent_id)
        if not registration.is_enabled:
            return self._deny(
                event,
                "agent_not_enabled",
                agent_id=agent_id,
                extra=registration.to_metadata(),
            )

        grant = self.backend.resolve_tool_grant(agent_id, tool)
        if grant is None or not grant.is_active:
            return self._deny(
                event,
                "tool_grant_not_active",
                agent_id=agent_id,
                extra={"tool": tool},
            )

        return AdapterResult(
            ok=True,
            source=self.key,
            body=f"Agent Registry granted {agent_id} tool access: {tool}",
            metadata={
                **self._base_metadata(event, status="tool_granted"),
                **registration.to_metadata(),
                **grant.to_metadata(),
            },
        )

    def _check_revocation(self, event: AgentTermEvent) -> AdapterResult:
        agent_id = self._agent_id(event)
        if not agent_id:
            return self._deny(event, "missing_agent_id")

        registration = self.backend.resolve_agent(agent_id)
        if registration is None:
            return self._deny(event, "unknown_agent", agent_id=agent_id)
        if registration.revoked:
            return self._deny(
                event,
                "agent_revoked",
                agent_id=agent_id,
                extra=registration.to_metadata(),
            )

        return AdapterResult(
            ok=True,
            source=self.key,
            body=f"Agent Registry revocation check passed for {agent_id}",
            metadata={
                **self._base_metadata(event, status="not_revoked"),
                **registration.to_metadata(),
            },
        )

    def _deny(
        self,
        event: AgentTermEvent,
        reason: str,
        *,
        agent_id: str | None = None,
        extra: dict[str, object] | None = None,
    ) -> AdapterResult:
        metadata = self._base_metadata(event, status="denied")
        metadata["deny_reason"] = reason
        if agent_id:
            metadata["agent_id"] = agent_id
        if extra:
            metadata.update(extra)
        return AdapterResult(
            ok=False,
            source=self.key,
            body=f"Agent Registry denied request: {reason}",
            metadata=metadata,
        )

    def _base_metadata(self, event: AgentTermEvent, *, status: str) -> dict[str, object]:
        return {
            "request_event_id": event.event_id,
            "registry_status": status,
            "revocation_check_at": datetime.now(UTC).isoformat(),
            "fail_closed": True,
        }

    def _agent_id(self, event: AgentTermEvent) -> str | None:
        value = (
            event.metadata.get("agent_id")
            or event.metadata.get("agentRegistryId")
            or event.metadata.get("agent_registry_id")
        )
        return str(value) if value else None

    def _tool(self, event: AgentTermEvent) -> str | None:
        value = event.metadata.get("tool") or event.metadata.get("tool_name")
        return str(value) if value else None
