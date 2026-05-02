"""Policy Fabric admission adapter primitives.

AgentTerm is not the authority for policy. This module provides a small,
fakeable adapter boundary so side-effecting actions and sensitive context release
can be admitted or denied by a Policy Fabric-compatible backend before dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from agent_term.adapters import AdapterResult
from agent_term.events import AgentTermEvent


ALLOW = "allow"
DENY = "deny"
PENDING = "pending"
UNKNOWN = "unknown"

SIDE_EFFECTING_KINDS = frozenset(
    {
        "shell_session",
        "shell_attach",
        "workspace_materialization",
        "context_pack",
        "memory_recall",
        "memory_write",
        "semantic_membrane",
        "investigation",
        "search_packet",
        "graph_view",
        "graph_diffusion",
        "graph_artifact",
        "run",
        "replay",
        "github_mutation",
        "ci_retry",
        "tool_grant",
        "revocation",
        "matrix_service_send",
    }
)

SENSITIVE_CONTEXT_KINDS = frozenset(
    {
        "context_pack",
        "memory_recall",
        "memory_write",
        "semantic_thread",
        "claim",
        "citation",
        "investigation",
        "search_packet",
        "synthesis",
    }
)


@dataclass(frozen=True)
class PolicyDecision:
    """Resolved policy decision for an AgentTerm event."""

    decision_id: str
    action: str
    status: str
    policy_ref: str
    reason: str | None = None
    obligations: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def is_allowed(self) -> bool:
        return self.status == ALLOW

    def to_metadata(self) -> dict[str, object]:
        return {
            "policy_decision_id": self.decision_id,
            "policy_action": self.action,
            "policy_status": self.status,
            "policy_ref": self.policy_ref,
            "policy_reason": self.reason,
            "policy_obligations": list(self.obligations),
            **self.metadata,
        }


class PolicyFabricBackend(Protocol):
    """Backend contract for Policy Fabric decision lookup."""

    def evaluate(self, event: AgentTermEvent) -> PolicyDecision | None:
        """Return the admission decision for an event, or None if unknown."""


class InMemoryPolicyFabricBackend:
    """Test/development backend for Policy Fabric decisions."""

    def __init__(self, decisions: list[PolicyDecision] | None = None) -> None:
        self._decisions = {decision.action: decision for decision in decisions or []}

    def evaluate(self, event: AgentTermEvent) -> PolicyDecision | None:
        action = action_for_event(event)
        return self._decisions.get(action)


class PolicyFabricAdapter:
    """Adapter that enforces policy admission before sensitive or side-effecting work."""

    key = "policy-fabric"

    def __init__(self, backend: PolicyFabricBackend) -> None:
        self.backend = backend

    def supports(self, event: AgentTermEvent) -> bool:
        return event.source == self.key or requires_admission(event)

    def handle(self, event: AgentTermEvent) -> AdapterResult:
        action = action_for_event(event)
        if not requires_admission(event):
            return AdapterResult(
                ok=True,
                source=self.key,
                body=f"Policy Fabric admission not required for {action}",
                kind="policy_check",
                metadata=self._base_metadata(event, action=action, status="not_required"),
            )

        decision = self.backend.evaluate(event)
        if decision is None:
            return self._deny(event, action, "no_policy_decision")
        if decision.status == PENDING:
            return self._deny(event, action, "policy_decision_pending", decision=decision)
        if decision.status != ALLOW:
            reason = decision.reason or "policy_denied"
            return self._deny(event, action, reason, decision=decision)

        return AdapterResult(
            ok=True,
            source=self.key,
            body=f"Policy Fabric admitted {action}",
            kind="decision",
            metadata={
                **self._base_metadata(event, action=action, status="admitted"),
                **decision.to_metadata(),
            },
        )

    def _deny(
        self,
        event: AgentTermEvent,
        action: str,
        reason: str,
        *,
        decision: PolicyDecision | None = None,
    ) -> AdapterResult:
        metadata = self._base_metadata(event, action=action, status="denied")
        metadata["deny_reason"] = reason
        if decision:
            metadata.update(decision.to_metadata())
        return AdapterResult(
            ok=False,
            source=self.key,
            body=f"Policy Fabric denied {action}: {reason}",
            kind="decision",
            metadata=metadata,
        )

    def _base_metadata(
        self,
        event: AgentTermEvent,
        *,
        action: str,
        status: str,
    ) -> dict[str, object]:
        return {
            "request_event_id": event.event_id,
            "policy_action": action,
            "admission_status": status,
            "policy_check_at": datetime.now(UTC).isoformat(),
            "requires_admission": requires_admission(event),
            "fail_closed": True,
        }


def action_for_event(event: AgentTermEvent) -> str:
    explicit_action = event.metadata.get("policy_action") or event.metadata.get("action")
    if explicit_action:
        return str(explicit_action)
    return f"{event.source}.{event.kind}"


def requires_admission(event: AgentTermEvent) -> bool:
    if bool(event.metadata.get("requires_policy_admission")):
        return True
    if bool(event.metadata.get("sensitive_context")):
        return True
    if bool(event.metadata.get("approval_required")):
        return True
    return event.kind in SIDE_EFFECTING_KINDS or event.kind in SENSITIVE_CONTEXT_KINDS
