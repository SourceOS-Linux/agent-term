"""Agent Machine workspace adapter for AgentTerm.

Exposes operator-facing ChatOps commands for SourceOS Agent Machine workspaces.
Preserves Matrix-first event log semantics — all actions produce governed events.
Agent Registry resolution happens before any dispatch. Podman logic is deferred
to AgentPlane. Implements issue agent-term#18.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from agent_term.adapters import AdapterResult
from agent_term.events import AgentTermEvent


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


_GOVERNED_PARTICIPANT_KINDS = frozenset(
    ["codex", "claude-code", "hermes", "openclaw", "local-shell", "github-bot"]
)


@dataclass(frozen=True)
class AgentMachineProfile:
    """A resolved Agent Machine workspace profile."""

    profile_ref: str
    repo_ref: str
    agent_kind: str
    registry_entry_ref: str
    policy_profile_ref: str | None = None


@dataclass(frozen=True)
class WorkspaceAttachment:
    """An active Agent Machine workspace attachment."""

    workspace_ref: str
    profile_ref: str
    agent_ref: str
    attached_at: str
    agentplane_ref: str | None = None
    policy_decision_ref: str | None = None


@dataclass
class AgentMachineEventTrace:
    """Lifecycle event trace for an Agent Machine workspace session."""

    workspace_ref: str
    events: list[dict[str, Any]] = field(default_factory=list)

    def append(self, kind: str, **kwargs: Any) -> None:
        self.events.append({"kind": kind, "observedAt": _now(), **kwargs})


def _make_agent_machine_event(
    kind: str,
    channel: str,
    sender: str,
    body: str,
    metadata: dict[str, Any],
    requires_approval: bool = False,
) -> AgentTermEvent:
    return AgentTermEvent(
        channel=channel,
        sender=sender,
        body=body,
        kind=kind,
        source="agent-machine",
        requires_approval=requires_approval,
        metadata=metadata,
    )


def cmd_doctor(channel: str, sender: str) -> AgentTermEvent:
    """Record a doctor event for the Agent Machine workspace surface."""
    return _make_agent_machine_event(
        kind="agent_machine_doctor",
        channel=channel,
        sender=sender,
        body="Agent Machine doctor: check workspace health and registry resolution.",
        metadata={
            "agentMachineCommand": "doctor",
            "policyDecisionRequired": False,
            "note": "Stub — AgentPlane integration pending per agent-term#18.",
        },
    )


def cmd_init(channel: str, sender: str, profile: str, repo: str) -> AgentTermEvent:
    """Record an init event for a new Agent Machine workspace."""
    return _make_agent_machine_event(
        kind="agent_machine_init",
        channel=channel,
        sender=sender,
        body=f"Agent Machine init: profile={profile} repo={repo}",
        metadata={
            "agentMachineCommand": "init",
            "profile": profile,
            "repo": repo,
            "policyDecisionRequired": True,
            "note": "Stub — workspace engine (Podman) deferred to AgentPlane per agent-term#18.",
        },
        requires_approval=True,
    )


def cmd_attach(channel: str, sender: str, workspace_ref: str) -> AgentTermEvent:
    """Record a workspace attach event. Logs direct operator attach."""
    return _make_agent_machine_event(
        kind="agent_machine_attach",
        channel=channel,
        sender=sender,
        body=f"Agent Machine attach: workspace={workspace_ref}",
        metadata={
            "agentMachineCommand": "attach",
            "workspaceRef": workspace_ref,
            "attachKind": "direct-operator",
            "policyDecisionRequired": True,
            "note": "Direct operator attach logged. Governed execution hands off to AgentPlane.",
        },
        requires_approval=True,
    )


def cmd_run(channel: str, sender: str, tool: str, workspace_ref: str) -> AgentTermEvent:
    """Record a governed tool run request for an Agent Machine workspace."""
    return _make_agent_machine_event(
        kind="agent_machine_run",
        channel=channel,
        sender=sender,
        body=f"Agent Machine run: tool={tool} workspace={workspace_ref}",
        metadata={
            "agentMachineCommand": "run",
            "tool": tool,
            "workspaceRef": workspace_ref,
            "policyDecisionRequired": True,
            "agentplaneHandoff": True,
            "note": "Execution gated on policy decision; handoff to AgentPlane for governed run.",
        },
        requires_approval=True,
    )


def cmd_fingerprint(channel: str, sender: str, workspace_ref: str) -> AgentTermEvent:
    """Record a workspace fingerprint/identity verification event."""
    return _make_agent_machine_event(
        kind="agent_machine_fingerprint",
        channel=channel,
        sender=sender,
        body=f"Agent Machine fingerprint: workspace={workspace_ref}",
        metadata={
            "agentMachineCommand": "fingerprint",
            "workspaceRef": workspace_ref,
            "policyDecisionRequired": False,
            "note": "Identity verification — non-mutating, no approval required.",
        },
    )


def cmd_evidence(channel: str, sender: str, workspace_ref: str) -> AgentTermEvent:
    """Record an evidence retrieval request for a workspace session."""
    return _make_agent_machine_event(
        kind="agent_machine_evidence",
        channel=channel,
        sender=sender,
        body=f"Agent Machine evidence: workspace={workspace_ref}",
        metadata={
            "agentMachineCommand": "evidence",
            "workspaceRef": workspace_ref,
            "policyDecisionRequired": True,
            "note": "Evidence retrieval gated on policy; AgentPlane is the evidence authority.",
        },
        requires_approval=True,
    )


def resolve_participant(sender: str, agent_kind: str | None = None) -> dict[str, Any]:
    """Resolve a participant through Agent Registry before dispatch.

    Non-human participants (Codex, Claude Code, OpenCLAW, etc.) must be
    registered before being treated as governed actors.
    """
    kind = agent_kind or "unknown"
    is_governed = kind in _GOVERNED_PARTICIPANT_KINDS
    return {
        "senderRef": sender,
        "agentKind": kind,
        "governed": is_governed,
        "registryResolutionNote": (
            "Resolved via Agent Registry stub. Live registry check pending per agent-term#18."
        ),
    }


EXAMPLE_LIFECYCLE_TRACE = [
    {
        "kind": "agent_machine_init",
        "profile": "claude-code-devtools",
        "repo": "urn:srcos:repo:sourceos-devtools",
        "policyDecisionRef": "urn:srcos:policy-decision:am-init-admit-20260718",
        "observedAt": "2026-07-18T10:00:00Z",
    },
    {
        "kind": "agent_machine_attach",
        "workspaceRef": "urn:srcos:workspace:claude-code-devtools-20260718",
        "attachKind": "agentplane-governed",
        "agentplaneRef": "urn:srcos:agentplane:session:20260718T100001Z",
        "observedAt": "2026-07-18T10:00:01Z",
    },
    {
        "kind": "agent_machine_run",
        "tool": "sourceos-agent",
        "workspaceRef": "urn:srcos:workspace:claude-code-devtools-20260718",
        "executionStart": "2026-07-18T10:00:02Z",
        "observedAt": "2026-07-18T10:00:02Z",
    },
    {
        "kind": "agent_machine_evidence",
        "workspaceRef": "urn:srcos:workspace:claude-code-devtools-20260718",
        "evidenceRef": "urn:srcos:evidence:am-run-receipt-20260718",
        "observedAt": "2026-07-18T10:05:00Z",
    },
]
