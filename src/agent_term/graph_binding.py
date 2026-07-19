"""Terminal-native graph, policy, and capability lease ChatOps for AgentTerm.

Provides operator commands for querying the SourceOS agentic graph foundation
(Agent Registry, Policy Fabric, Memory Mesh, SourceChannel) without bypassing
governed lanes. All queries are dry-run stubs until the live services are
reachable. Implements issue agent-term#37.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


STUB_NOTE = "Live graph services not yet reachable — stub response per agent-term#37"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class AgentRegistryEntry:
    """An agent registered in the SourceOS Agent Registry."""

    agent_ref: str
    name: str
    kind: str
    status: str
    capability_contract_ref: str | None
    policy_profile_ref: str | None
    registered_at: str


@dataclass(frozen=True)
class PolicyFabricDecision:
    """A policy decision record from the Policy Fabric."""

    decision_ref: str
    subject_ref: str
    action: str
    decision: str
    policy_ref: str
    decided_at: str
    note: str = STUB_NOTE


@dataclass(frozen=True)
class CapabilityLease:
    """A capability lease granted to an agent."""

    lease_ref: str
    agent_ref: str
    capability: str
    grant_source: str
    decision: str
    granted_at: str
    expires_at: str | None
    note: str = STUB_NOTE


@dataclass
class GraphSnapshot:
    """Snapshot of the local agentic graph state visible to AgentTerm."""

    agents: list[AgentRegistryEntry] = field(default_factory=list)
    active_leases: list[CapabilityLease] = field(default_factory=list)
    recent_decisions: list[PolicyFabricDecision] = field(default_factory=list)
    memory_mesh_connected: bool = False
    source_channel_connected: bool = False
    note: str = STUB_NOTE

    def to_dict(self) -> dict[str, Any]:
        return {
            "agents": [
                {
                    "agent_ref": a.agent_ref,
                    "name": a.name,
                    "kind": a.kind,
                    "status": a.status,
                }
                for a in self.agents
            ],
            "active_leases": [
                {
                    "lease_ref": lease.lease_ref,
                    "agent_ref": lease.agent_ref,
                    "capability": lease.capability,
                    "decision": lease.decision,
                }
                for lease in self.active_leases
            ],
            "recent_decisions_count": len(self.recent_decisions),
            "memory_mesh_connected": self.memory_mesh_connected,
            "source_channel_connected": self.source_channel_connected,
            "note": self.note,
        }


def get_graph_snapshot() -> GraphSnapshot:
    """Return current graph state. Stub until live services are reachable."""
    return GraphSnapshot()


def get_agent_list() -> list[AgentRegistryEntry]:
    """Return registered agents from Agent Registry. Stub."""
    return []


def get_capability_leases(agent_ref: str | None = None) -> list[CapabilityLease]:
    """Return active capability leases, optionally filtered by agent. Stub."""
    return []


def get_policy_decisions(limit: int = 10) -> list[PolicyFabricDecision]:
    """Return recent policy decisions from Policy Fabric. Stub."""
    return []


def format_graph_snapshot(snapshot: GraphSnapshot, json_mode: bool = False) -> str:
    if json_mode:
        return json.dumps(snapshot.to_dict(), indent=2)
    lines = [
        "SourceOS Agentic Graph",
        f"  agents:                  {len(snapshot.agents)}",
        f"  active_leases:           {len(snapshot.active_leases)}",
        f"  recent_decisions:        {len(snapshot.recent_decisions)}",
        f"  memory_mesh_connected:   {snapshot.memory_mesh_connected}",
        f"  source_channel_connected:{snapshot.source_channel_connected}",
        f"  note:                    {snapshot.note}",
    ]
    return "\n".join(lines)


def format_agent_list(agents: list[AgentRegistryEntry], json_mode: bool = False) -> str:
    if json_mode:
        return json.dumps(
            [{"agent_ref": a.agent_ref, "name": a.name, "kind": a.kind, "status": a.status} for a in agents],
            indent=2,
        )
    if not agents:
        return f"No agents registered. (note: {STUB_NOTE})"
    lines = ["Registered agents:"]
    for a in agents:
        lines.append(f"  {a.name}  [{a.kind}]  {a.status}  {a.agent_ref}")
    return "\n".join(lines)


def format_leases(leases: list[CapabilityLease], json_mode: bool = False) -> str:
    if json_mode:
        return json.dumps(
            [
                {"lease_ref": lease.lease_ref, "capability": lease.capability, "decision": lease.decision}
                for lease in leases
            ],
            indent=2,
        )
    if not leases:
        return f"No active capability leases. (note: {STUB_NOTE})"
    lines = ["Active capability leases:"]
    for lease in leases:
        lines.append(f"  {lease.capability}  {lease.decision}  {lease.lease_ref}")
    return "\n".join(lines)
