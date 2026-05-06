"""Dry-run OpsHistory planning helpers for AgentTerm.

These helpers intentionally do not contact Matrix, Policy Fabric, Agent Registry,
Memory Mesh, AgentPlane, or any local service endpoint. They produce deterministic
contract-shaped plans that the operator can inspect before runtime integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


DEFAULT_POLICY_REF = "urn:srcos:policy-decision:ops-history-hydrate-context-demo-0001"
DEFAULT_AGENT_GRANT_REF = "urn:srcos:agent-grant:ops-history-summarizer-demo"
DEFAULT_WORKROOM = "urn:srcos:workroom:professional-intelligence-demo"
DEFAULT_TOPIC = "urn:srcos:topic:professional-intelligence"


@dataclass(frozen=True)
class OpsHistoryScope:
    """Bounded scope for an OpsHistory dry-run plan."""

    room_ref: str | None = None
    thread_ref: str | None = None
    workroom_ref: str = DEFAULT_WORKROOM
    topic_ref: str | None = DEFAULT_TOPIC
    session_ref: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "roomRef": self.room_ref,
            "threadRef": self.thread_ref,
            "workroomRef": self.workroom_ref,
            "topicRef": self.topic_ref,
            "sessionRef": self.session_ref,
        }


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def policy_explain(profile: str) -> dict[str, Any]:
    """Return an inspectable sync-policy explanation for a named profile."""

    if profile == "active-multi-agent-room":
        lanes = [
            {
                "lane": "control",
                "priority": "high",
                "cadence": [
                    {"count": 50, "intervalSeconds": 60},
                    {"count": 20, "intervalSeconds": 300},
                    {"count": 10, "intervalSeconds": 1800},
                ],
                "payloadMode": "summary",
                "requiresPolicyDecision": True,
            },
            {
                "lane": "operational",
                "priority": "normal",
                "cadence": [
                    {"count": 50, "intervalSeconds": 180},
                    {"count": 20, "intervalSeconds": 600},
                    {"count": 10, "intervalSeconds": 3600},
                ],
                "payloadMode": "metadata-only",
                "requiresPolicyDecision": True,
            },
            {
                "lane": "redaction",
                "priority": "critical",
                "cadence": [
                    {"count": 20, "intervalSeconds": 5},
                    {"count": 10, "intervalSeconds": 30},
                ],
                "payloadMode": "redacted",
                "requiresPolicyDecision": True,
            },
        ]
    else:
        lanes = [
            {
                "lane": "control",
                "priority": "maintenance",
                "cadence": [{"count": 1, "intervalSeconds": 3600}],
                "payloadMode": "metadata-only",
                "requiresPolicyDecision": True,
            },
            {
                "lane": "redaction",
                "priority": "critical",
                "cadence": [{"count": 5, "intervalSeconds": 5}],
                "payloadMode": "redacted",
                "requiresPolicyDecision": True,
            },
        ]

    return {
        "planKind": "ops-history-policy-explain",
        "dryRun": True,
        "profile": profile,
        "generatedAt": _now(),
        "policyRef": "urn:srcos:ops-history-sync-policy:default-local-first-v1",
        "defaultPayloadCapChars": 100000,
        "defaultSyncWindowSeconds": 1209600,
        "offlineBehavior": "queue-local",
        "lanes": lanes,
        "redactionPriority": {
            "priority": "critical",
            "targetPropagationSeconds": 30,
            "invalidateContextPacks": True,
            "invalidateMemoryWritebacks": True,
            "invalidateArtifactExports": True,
        },
        "nonGoals": [
            "no live sync",
            "no live memory writeback",
            "no raw sensitive payload release",
        ],
    }


def replay_plan(thread_id: str, scope: OpsHistoryScope | None = None) -> dict[str, Any]:
    """Return a deterministic replay dry-run envelope."""

    selected_scope = scope or OpsHistoryScope(thread_ref=f"urn:srcos:thread:{thread_id}")
    return {
        "planKind": "ops-history-replay",
        "dryRun": True,
        "generatedAt": _now(),
        "threadId": thread_id,
        "scope": selected_scope.as_dict(),
        "sourceEventRefs": [f"urn:srcos:ops-history-event:{thread_id}-demo-0001"],
        "policyDecisionRefs": [DEFAULT_POLICY_REF],
        "agentRegistryRefs": [DEFAULT_AGENT_GRANT_REF],
        "steps": [
            "select bounded thread events",
            "apply Policy Fabric hydration decision",
            "apply Agent Registry grant constraints",
            "exclude redacted refs",
            "emit replay plan without side effects",
        ],
    }


def context_pack_plan(workroom: str, topic: str | None = None) -> dict[str, Any]:
    """Return a context-pack dry-run envelope for Memory Mesh / AgentPlane handoff."""

    topic_ref = topic or DEFAULT_TOPIC
    workroom_ref = workroom if workroom.startswith("urn:") else f"urn:srcos:workroom:{workroom}"
    return {
        "planKind": "ops-history-context-pack",
        "dryRun": True,
        "generatedAt": _now(),
        "contextPackRef": f"urn:srcos:context-pack:{workroom_ref.rsplit(':', 1)[-1]}-ops-history-demo",
        "scope": OpsHistoryScope(workroom_ref=workroom_ref, topic_ref=topic_ref).as_dict(),
        "payloadMode": "summary",
        "sourceEventRefs": ["urn:srcos:ops-history-event:demo-agentterm-0001"],
        "policyDecisionRefs": [DEFAULT_POLICY_REF],
        "agentRegistryRefs": [DEFAULT_AGENT_GRANT_REF],
        "retention": {
            "mode": "ephemeral",
            "ttlSeconds": 604800,
            "writebackAllowed": False,
            "promotionRequiresPolicyDecision": True,
        },
        "targetConsumers": ["memory-mesh", "agentplane"],
    }


def redactions_pending() -> dict[str, Any]:
    """Return a deterministic pending-redactions dry-run posture."""

    return {
        "planKind": "ops-history-redactions-pending",
        "dryRun": True,
        "generatedAt": _now(),
        "pending": [],
        "policy": {
            "redactionPriority": "critical",
            "targetPropagationSeconds": 30,
            "invalidateContextPacks": True,
            "invalidateMemoryWritebacks": True,
            "invalidateArtifactExports": True,
        },
    }
