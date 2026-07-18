"""SourceOS State Integrity ChatOps surface for AgentTerm.

Exposes state integrity events, conflict queues, and repair approvals as
terminal-native operator interactions. All queries are dry-run stubs until
sourceos-syncd is available at runtime. Implements issue agent-term#36.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


STUB_NOTE = "sourceos-syncd not yet running — stub response per agent-term#36"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _syncd_available() -> bool:
    try:
        result = subprocess.run(
            ["sourceos-syncd", "status", "--json"],
            capture_output=True,
            timeout=2,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@dataclass(frozen=True)
class StateIntegrityStatus:
    """State integrity daemon status snapshot."""

    daemon_available: bool
    daemon_state: str
    active_profile: str
    active_workspace: str
    active_device: str
    degraded: bool
    policy_blocked: bool
    conflict_count: int
    repair_needed: bool
    note: str = STUB_NOTE

    def to_dict(self) -> dict[str, Any]:
        return {
            "daemon_available": self.daemon_available,
            "daemon_state": self.daemon_state,
            "active_profile": self.active_profile,
            "active_workspace": self.active_workspace,
            "active_device": self.active_device,
            "degraded": self.degraded,
            "policy_blocked": self.policy_blocked,
            "conflict_count": self.conflict_count,
            "repair_needed": self.repair_needed,
            "note": self.note,
        }


@dataclass(frozen=True)
class ConflictRecord:
    """A single state conflict awaiting operator review."""

    conflict_ref: str
    object_ref: str
    staleness_class: str
    local_value_redacted: bool
    remote_source_ref: str
    auto_repair_eligible: bool
    human_review_required: bool
    observed_at: str


@dataclass
class ConflictQueue:
    """Ordered queue of state conflicts for operator review."""

    conflicts: list[ConflictRecord] = field(default_factory=list)
    total: int = 0
    blocked_count: int = 0
    note: str = STUB_NOTE


@dataclass(frozen=True)
class RepairApproval:
    """Operator approval record for a state repair action."""

    approval_ref: str
    conflict_ref: str
    object_ref: str
    repair_action: str
    approved_by: str
    policy_decision_ref: str
    approved_at: str
    note: str = STUB_NOTE


def get_status() -> StateIntegrityStatus:
    """Return current state integrity status from syncd or stub."""
    available = _syncd_available()
    return StateIntegrityStatus(
        daemon_available=available,
        daemon_state="running" if available else "unavailable",
        active_profile="unknown",
        active_workspace="unknown",
        active_device="unknown",
        degraded=False,
        policy_blocked=False,
        conflict_count=0,
        repair_needed=False,
    )


def get_conflict_queue(limit: int = 20) -> ConflictQueue:
    """Return pending conflicts from syncd or stub."""
    return ConflictQueue(
        conflicts=[],
        total=0,
        blocked_count=0,
    )


def approve_repair(
    conflict_ref: str,
    actor_ref: str,
    policy_decision_ref: str,
) -> RepairApproval:
    """Record operator approval of a state repair. Dry-run until syncd is live."""
    return RepairApproval(
        approval_ref=f"urn:srcos:repair-approval:{conflict_ref}:{_now()}",
        conflict_ref=conflict_ref,
        object_ref="unknown",
        repair_action="auto-repair",
        approved_by=actor_ref,
        policy_decision_ref=policy_decision_ref,
        approved_at=_now(),
    )


def format_status(status: StateIntegrityStatus, json_mode: bool = False) -> str:
    if json_mode:
        return json.dumps(status.to_dict(), indent=2)
    lines = [
        "SourceOS State Integrity",
        f"  daemon:          {status.daemon_state} ({'available' if status.daemon_available else 'unavailable'})",
        f"  profile:         {status.active_profile}",
        f"  workspace:       {status.active_workspace}",
        f"  device:          {status.active_device}",
        f"  degraded:        {status.degraded}",
        f"  policy_blocked:  {status.policy_blocked}",
        f"  conflict_count:  {status.conflict_count}",
        f"  repair_needed:   {status.repair_needed}",
        f"  note:            {status.note}",
    ]
    return "\n".join(lines)


def format_conflict_queue(queue: ConflictQueue, json_mode: bool = False) -> str:
    if json_mode:
        return json.dumps(
            {
                "total": queue.total,
                "blocked_count": queue.blocked_count,
                "conflicts": [
                    {
                        "conflict_ref": c.conflict_ref,
                        "object_ref": c.object_ref,
                        "staleness_class": c.staleness_class,
                        "auto_repair_eligible": c.auto_repair_eligible,
                        "human_review_required": c.human_review_required,
                    }
                    for c in queue.conflicts
                ],
                "note": queue.note,
            },
            indent=2,
        )
    if not queue.conflicts:
        return f"No conflicts pending (note: {queue.note})"
    lines = [f"Conflict queue ({queue.total} total, {queue.blocked_count} blocked):"]
    for c in queue.conflicts:
        lines.append(f"  {c.conflict_ref}  [{c.staleness_class}]  review={'required' if c.human_review_required else 'optional'}")
    return "\n".join(lines)
