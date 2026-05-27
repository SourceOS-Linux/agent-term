"""Pre-dispatch decision boundary for AgentTerm runtime actions.

AgentTerm renders, records, and coordinates operator events. It is not the
authority for non-human participant identity, grants, policy admission, or
side-effecting execution. This module creates a typed decision object that must
exist before dispatch is performed by an adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

DispatchDecision = Literal["allow", "require-review", "deny", "fail-closed"]
RevocationState = Literal["not-revoked", "revoked", "unknown"]

SIDE_EFFECTING_ACTIONS = frozenset(
    {
        "shell_session",
        "shell_attach",
        "terminal_attach",
        "tool_use",
        "mcp_tool_call",
        "github_mutation",
        "ci_retry",
        "workspace_materialization",
        "memory_write",
        "matrix_service_send",
    }
)


@dataclass(frozen=True)
class AgentTermPreDispatchDecision:
    """Decision-only record produced before any runtime dispatch occurs."""

    decision_id: str
    requested_action: str
    participant_ref: str
    participant_kind: str
    agent_registry_ref: str | None
    grant_refs: tuple[str, ...]
    session_ref: str | None
    revocation_state: RevocationState
    policy_decision_refs: tuple[str, ...]
    policy_status: str
    dispatch_decision: DispatchDecision
    dispatch_target: str
    side_effecting: bool
    sensitive_context_requested: bool = False
    context_pack_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    performed_dispatch: bool = False
    reason: str | None = None
    decided_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": "agent-term.pre-dispatch-decision.v0.1",
            "recordType": "AgentTermPreDispatchDecision",
            "decision_id": self.decision_id,
            "requested_action": self.requested_action,
            "participant_ref": self.participant_ref,
            "participant_kind": self.participant_kind,
            "agent_registry_ref": self.agent_registry_ref,
            "grant_refs": list(self.grant_refs),
            "session_ref": self.session_ref,
            "revocation_state": self.revocation_state,
            "policy_decision_refs": list(self.policy_decision_refs),
            "policy_status": self.policy_status,
            "dispatch_decision": self.dispatch_decision,
            "dispatch_target": self.dispatch_target,
            "side_effecting": self.side_effecting,
            "sensitive_context_requested": self.sensitive_context_requested,
            "context_pack_refs": list(self.context_pack_refs),
            "evidence_refs": list(self.evidence_refs),
            "performed_dispatch": self.performed_dispatch,
            "reason": self.reason,
            "decided_at": self.decided_at,
        }


def build_pre_dispatch_decision(
    *,
    decision_id: str,
    requested_action: str,
    participant_ref: str,
    participant_kind: str,
    dispatch_target: str,
    agent_registry_ref: str | None = None,
    grant_refs: tuple[str, ...] = (),
    session_ref: str | None = None,
    revocation_state: RevocationState = "unknown",
    policy_decision_refs: tuple[str, ...] = (),
    policy_status: str = "unknown",
    sensitive_context_requested: bool = False,
    context_pack_refs: tuple[str, ...] = (),
    evidence_refs: tuple[str, ...] = (),
) -> AgentTermPreDispatchDecision:
    """Build a decision-only pre-dispatch record.

    This function never performs dispatch. It classifies whether a later adapter
    may dispatch after Agent Registry and Policy Fabric evidence has been checked.
    """

    side_effecting = requested_action in SIDE_EFFECTING_ACTIONS
    decision: DispatchDecision = "allow"
    reason: str | None = "all required pre-dispatch gates satisfied"

    if participant_kind != "human" and not agent_registry_ref:
        decision = "fail-closed"
        reason = "non-human participant missing Agent Registry resolution"
    elif participant_kind != "human" and (not grant_refs or not session_ref):
        decision = "fail-closed"
        reason = "non-human participant missing grant or session reference"
    elif revocation_state != "not-revoked":
        decision = "deny" if revocation_state == "revoked" else "fail-closed"
        reason = f"participant revocation_state={revocation_state}"
    elif side_effecting and not policy_decision_refs:
        decision = "fail-closed"
        reason = "side-effecting action missing Policy Fabric decision refs"
    elif sensitive_context_requested and policy_status != "allow":
        decision = "deny" if policy_status in {"deny", "denied"} else "require-review"
        reason = "sensitive context requires explicit policy admission"
    elif policy_status in {"deny", "denied"}:
        decision = "deny"
        reason = "Policy Fabric denied dispatch"
    elif policy_status in {"pending", "require-review"}:
        decision = "require-review"
        reason = "Policy Fabric requires review before dispatch"

    record = AgentTermPreDispatchDecision(
        decision_id=decision_id,
        requested_action=requested_action,
        participant_ref=participant_ref,
        participant_kind=participant_kind,
        agent_registry_ref=agent_registry_ref,
        grant_refs=grant_refs,
        session_ref=session_ref,
        revocation_state=revocation_state,
        policy_decision_refs=policy_decision_refs,
        policy_status=policy_status,
        dispatch_decision=decision,
        dispatch_target=dispatch_target,
        side_effecting=side_effecting,
        sensitive_context_requested=sensitive_context_requested,
        context_pack_refs=context_pack_refs,
        evidence_refs=evidence_refs,
        performed_dispatch=False,
        reason=reason,
    )
    validate_pre_dispatch_decision(record)
    return record


def validate_pre_dispatch_decision(record: AgentTermPreDispatchDecision | dict[str, Any]) -> None:
    """Reject collapsed pre-dispatch records."""

    data = record.to_dict() if isinstance(record, AgentTermPreDispatchDecision) else record
    if data.get("recordType") != "AgentTermPreDispatchDecision":
        raise ValueError("recordType must be AgentTermPreDispatchDecision")
    if data.get("performed_dispatch") is not False:
        raise ValueError("pre-dispatch decisions must not claim dispatch was performed")

    participant_kind = str(data.get("participant_kind", ""))
    if participant_kind != "human":
        if not data.get("agent_registry_ref"):
            raise ValueError("non-human participant requires Agent Registry ref")
        if not data.get("grant_refs"):
            raise ValueError("non-human participant requires grant refs")
        if not data.get("session_ref"):
            raise ValueError("non-human participant requires session ref")

    if data.get("revocation_state") in {"revoked", "unknown"} and data.get("dispatch_decision") == "allow":
        raise ValueError("revoked or unknown revocation state cannot allow dispatch")

    if data.get("side_effecting") is True and not data.get("policy_decision_refs"):
        raise ValueError("side-effecting dispatch requires policy decision refs")

    if data.get("sensitive_context_requested") is True and data.get("policy_status") not in {"allow", "admitted"}:
        raise ValueError("sensitive context requires policy admission")

    if data.get("dispatch_decision") == "allow" and data.get("policy_status") in {"deny", "denied", "pending", "require-review"}:
        raise ValueError("allow dispatch is inconsistent with policy status")
