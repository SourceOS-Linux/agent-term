"""Canonical AgentTerm event model.

AgentTerm treats terminal chat, Matrix room events, agent replies, policy decisions,
cloud-fog shell sessions, AgentPlane bundle runs, Sherlock search packets, and GitHub/CI
updates as append-only events. Keeping this model small makes the terminal shell usable now
while leaving enough structure for PolicyFabric and AgentPlane receipts later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class AgentTermEvent:
    """A single normalized ChatOps event.

    Attributes:
        event_id: AgentTerm-local stable ID.
        channel: Logical channel or Matrix room alias/ID.
        sender: Human, agent, bot, or system principal.
        kind: Event class such as message, command, decision, run, search, shell_session.
        body: Human-readable event body.
        thread_id: Optional thread/work-order identifier.
        source: Source plane or adapter: matrix, local, agentplane, policy-fabric, sherlock,
            cloudshell-fog, github, ci, mcp, hermes, codex, claude-code, openclaw.
        metadata: Adapter-specific structured fields.
        created_at: UTC timestamp.
    """

    channel: str
    sender: str
    kind: str
    body: str
    thread_id: str | None = None
    source: str = "local"
    metadata: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: f"evt_{uuid4().hex}")
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_record(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "channel": self.channel,
            "sender": self.sender,
            "kind": self.kind,
            "body": self.body,
            "thread_id": self.thread_id,
            "source": self.source,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "AgentTermEvent":
        created_at = record.get("created_at")
        if isinstance(created_at, str):
            parsed_created_at = datetime.fromisoformat(created_at)
        elif isinstance(created_at, datetime):
            parsed_created_at = created_at
        else:
            parsed_created_at = datetime.now(UTC)

        return cls(
            event_id=record["event_id"],
            channel=record["channel"],
            sender=record["sender"],
            kind=record["kind"],
            body=record["body"],
            thread_id=record.get("thread_id"),
            source=record.get("source", "local"),
            metadata=record.get("metadata") or {},
            created_at=parsed_created_at,
        )
