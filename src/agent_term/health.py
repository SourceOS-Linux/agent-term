"""Service health checks for AgentTerm operator seams.

Health checks are diagnostic only. They verify local configuration posture and optional
fixture/service seams without becoming authority over Matrix, Agent Registry, or
Policy Fabric.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from agent_term.agent_registry import AgentRegistration, InMemoryAgentRegistryBackend, ToolGrant
from agent_term.agent_registry_service import build_agent_registry_backend_from_config
from agent_term.config import AgentTermConfig
from agent_term.events import AgentTermEvent
from agent_term.matrix_service import MatrixServiceConfigError, NioMatrixServiceBackend
from agent_term.matrix_service import build_matrix_service_backend
from agent_term.policy_fabric import ALLOW, InMemoryPolicyFabricBackend, PolicyDecision
from agent_term.policy_fabric_service import build_policy_fabric_backend_from_config


OK = "ok"
WARN = "warn"
BLOCKED = "blocked"


@dataclass(frozen=True)
class HealthCheckResult:
    """One service seam health result."""

    name: str
    status: str
    message: str
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == OK

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class HealthReport:
    """Complete health report for operator-facing service seams."""

    results: tuple[HealthCheckResult, ...]

    @property
    def ok(self) -> bool:
        return all(result.status in {OK, WARN} for result in self.results)

    @property
    def blocked(self) -> bool:
        return any(result.status == BLOCKED for result in self.results)

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "blocked": self.blocked,
            "results": [result.to_dict() for result in self.results],
        }

    def render_text(self) -> str:
        return "\n".join(
            f"{result.name}\t{result.status}\t{result.message}" for result in self.results
        )


@dataclass(frozen=True)
class HealthCheckOptions:
    """Optional probes for health checks."""

    agent_id: str | None = None
    tool: str | None = None
    policy_action: str | None = None


class HealthChecker:
    """Runs health checks for Matrix, Agent Registry, and Policy Fabric seams."""

    def __init__(self, config: AgentTermConfig) -> None:
        self.config = config

    def run(self, options: HealthCheckOptions | None = None) -> HealthReport:
        options = options or HealthCheckOptions()
        return HealthReport(
            results=(
                self.check_matrix(),
                self.check_agent_registry(options),
                self.check_policy_fabric(options),
            )
        )

    def check_matrix(self) -> HealthCheckResult:
        try:
            backend = build_matrix_service_backend(self.config)
        except MatrixServiceConfigError as exc:
            return HealthCheckResult(
                name="matrix",
                status=BLOCKED,
                message=str(exc),
                metadata={"enabled": self.config.matrix.enabled},
            )

        if isinstance(backend, NioMatrixServiceBackend):
            return HealthCheckResult(
                name="matrix",
                status=OK,
                message="Matrix live backend is configured.",
                metadata={
                    "enabled": True,
                    "homeserver_url": backend.homeserver_url,
                    "user_id": backend.user_id,
                    "device_name": backend.device_name,
                },
            )

        return HealthCheckResult(
            name="matrix",
            status=WARN,
            message="Matrix is using the offline/in-memory backend.",
            metadata={"enabled": self.config.matrix.enabled},
        )

    def check_agent_registry(self, options: HealthCheckOptions) -> HealthCheckResult:
        fallback = _fallback_agent_registry(options)
        try:
            backend = build_agent_registry_backend_from_config(self.config, fallback=fallback)
        except Exception as exc:  # defensive diagnostic path
            return HealthCheckResult(
                name="agent-registry",
                status=BLOCKED,
                message=f"Agent Registry backend could not be constructed: {exc}",
            )

        fixture_path = self.config.agent_registration.fixture_path
        endpoint_url = self.config.agent_registration.endpoint_url
        backend_kind = "fixture" if fixture_path else "http" if endpoint_url else "fallback"

        if fixture_path and not Path(fixture_path).exists():
            return HealthCheckResult(
                name="agent-registry",
                status=BLOCKED,
                message="Agent Registry fixture path does not exist.",
                metadata={"fixture_path": fixture_path},
            )

        if options.agent_id:
            agent = backend.resolve_agent(options.agent_id)
            if agent is None:
                return HealthCheckResult(
                    name="agent-registry",
                    status=BLOCKED,
                    message=f"Agent not resolved: {options.agent_id}",
                    metadata={"backend": backend_kind, "agent_id": options.agent_id},
                )
            if not agent.is_enabled:
                return HealthCheckResult(
                    name="agent-registry",
                    status=BLOCKED,
                    message=f"Agent is not enabled: {options.agent_id}",
                    metadata={"backend": backend_kind, **agent.to_metadata()},
                )
            if options.tool:
                grant = backend.resolve_tool_grant(options.agent_id, options.tool)
                if grant is None or not grant.is_active:
                    return HealthCheckResult(
                        name="agent-registry",
                        status=BLOCKED,
                        message=f"Tool grant is not active: {options.agent_id}:{options.tool}",
                        metadata={"backend": backend_kind, "agent_id": options.agent_id, "tool": options.tool},
                    )
                return HealthCheckResult(
                    name="agent-registry",
                    status=OK,
                    message=f"Agent and tool grant resolved: {options.agent_id}:{options.tool}",
                    metadata={"backend": backend_kind, **agent.to_metadata(), **grant.to_metadata()},
                )
            return HealthCheckResult(
                name="agent-registry",
                status=OK,
                message=f"Agent resolved: {options.agent_id}",
                metadata={"backend": backend_kind, **agent.to_metadata()},
            )

        status = OK if fixture_path or endpoint_url else WARN
        message = (
            "Agent Registry service seam is configured."
            if status == OK
            else "Agent Registry is using local fallback fixtures."
        )
        return HealthCheckResult(
            name="agent-registry",
            status=status,
            message=message,
            metadata={"backend": backend_kind, "repository": self.config.agent_registration.repository},
        )

    def check_policy_fabric(self, options: HealthCheckOptions) -> HealthCheckResult:
        fallback = _fallback_policy_fabric(options)
        try:
            backend = build_policy_fabric_backend_from_config(self.config, fallback=fallback)
        except Exception as exc:  # defensive diagnostic path
            return HealthCheckResult(
                name="policy-fabric",
                status=BLOCKED,
                message=f"Policy Fabric backend could not be constructed: {exc}",
            )

        fixture_path = self.config.policy_fabric.fixture_path
        endpoint_url = self.config.policy_fabric.endpoint_url
        backend_kind = "fixture" if fixture_path else "http" if endpoint_url else "fallback"

        if fixture_path and not Path(fixture_path).exists():
            return HealthCheckResult(
                name="policy-fabric",
                status=BLOCKED,
                message="Policy Fabric fixture path does not exist.",
                metadata={"fixture_path": fixture_path},
            )

        if options.policy_action:
            event = AgentTermEvent(
                channel="!policyfabric",
                sender="@agent-term",
                kind="policy_check",
                source="policy-fabric",
                body="Health-check policy decision lookup.",
                metadata={"policy_action": options.policy_action},
            )
            decision = backend.evaluate(event)
            if decision is None:
                return HealthCheckResult(
                    name="policy-fabric",
                    status=BLOCKED,
                    message=f"Policy decision not resolved: {options.policy_action}",
                    metadata={"backend": backend_kind, "policy_action": options.policy_action},
                )
            return HealthCheckResult(
                name="policy-fabric",
                status=OK if decision.is_allowed else WARN,
                message=f"Policy decision resolved: {options.policy_action} -> {decision.status}",
                metadata={"backend": backend_kind, **decision.to_metadata()},
            )

        status = OK if fixture_path or endpoint_url else WARN
        message = (
            "Policy Fabric service seam is configured."
            if status == OK
            else "Policy Fabric is using local fallback fixtures."
        )
        return HealthCheckResult(
            name="policy-fabric",
            status=status,
            message=message,
            metadata={"backend": backend_kind, "repository": self.config.policy_fabric.repository},
        )


def _fallback_agent_registry(options: HealthCheckOptions) -> InMemoryAgentRegistryBackend:
    agents: list[AgentRegistration] = []
    grants: list[ToolGrant] = []
    if options.agent_id:
        agents.append(
            AgentRegistration(
                agent_id=options.agent_id,
                registry_ref=f"local://agent-registry/{options.agent_id}",
                spec_version="health-check",
                session_id=f"session-{options.agent_id.replace('.', '-')}",
            )
        )
    if options.agent_id and options.tool:
        grants.append(
            ToolGrant(
                grant_id=f"grant.{options.agent_id}.{options.tool}",
                agent_id=options.agent_id,
                tool=options.tool,
            )
        )
    return InMemoryAgentRegistryBackend(agents=agents, grants=grants)


def _fallback_policy_fabric(options: HealthCheckOptions) -> InMemoryPolicyFabricBackend:
    decisions: list[PolicyDecision] = []
    if options.policy_action:
        decisions.append(
            PolicyDecision(
                decision_id=f"decision.allow.{options.policy_action}",
                action=options.policy_action,
                status=ALLOW,
                policy_ref="local://policy-fabric/health-check",
            )
        )
    return InMemoryPolicyFabricBackend(decisions)
