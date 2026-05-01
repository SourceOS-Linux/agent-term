"""Terminal UI view-model primitives.

This is intentionally dependency-light. A future Textual application can render this
model, but the grouping, status classification, and safety affordances are tested here
without requiring a live terminal session in CI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from agent_term.events import AgentTermEvent


PANE_ORDER = (
    "rooms",
    "threads",
    "agents",
    "approvals",
    "workrooms",
    "topics",
    "context",
    "semantic",
    "investigations",
    "graphs",
    "shells",
    "runs",
    "evidence",
    "events",
)


@dataclass(frozen=True)
class TuiLine:
    """One rendered line in a TUI pane."""

    text: str
    status: str = "info"
    event_id: str | None = None
    source: str | None = None
    kind: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TuiPane:
    """A named TUI pane."""

    name: str
    title: str
    lines: tuple[TuiLine, ...] = ()


@dataclass(frozen=True)
class TuiSnapshot:
    """Complete dependency-free AgentTerm TUI snapshot."""

    panes: tuple[TuiPane, ...]

    def pane(self, name: str) -> TuiPane:
        for pane in self.panes:
            if pane.name == name:
                return pane
        raise KeyError(f"unknown pane: {name}")

    def render_text(self) -> str:
        blocks: list[str] = []
        for pane in self.panes:
            blocks.append(f"[{pane.title}]")
            if not pane.lines:
                blocks.append("  <empty>")
                continue
            for line in pane.lines:
                blocks.append(f"  {line.status.upper()}: {line.text}")
        return "\n".join(blocks)


class TuiSnapshotBuilder:
    """Builds an operator-oriented TUI snapshot from AgentTerm events."""

    def build(self, events: Iterable[AgentTermEvent]) -> TuiSnapshot:
        pane_lines: dict[str, list[TuiLine]] = {name: [] for name in PANE_ORDER}
        seen_rooms: set[str] = set()
        seen_threads: set[str] = set()

        for event in events:
            room_line = _room_line(event)
            if room_line.text not in seen_rooms:
                pane_lines["rooms"].append(room_line)
                seen_rooms.add(room_line.text)

            if event.thread_id and event.thread_id not in seen_threads:
                pane_lines["threads"].append(
                    TuiLine(
                        text=f"{event.thread_id} in {event.channel}",
                        status="info",
                        event_id=event.event_id,
                        source=event.source,
                        kind=event.kind,
                    )
                )
                seen_threads.add(event.thread_id)

            pane_name = classify_event(event)
            pane_lines[pane_name].append(event_line(event))
            pane_lines["events"].append(event_line(event))

        panes = tuple(
            TuiPane(name=name, title=title_for_pane(name), lines=tuple(pane_lines[name]))
            for name in PANE_ORDER
        )
        return TuiSnapshot(panes=panes)


def classify_event(event: AgentTermEvent) -> str:
    if event.source in {"agent-registry", "hermes", "codex", "claude-code", "openclaw"}:
        return "agents"
    if event.source in {"github", "ci", "mcp", "local-process"}:
        return "agents"
    if event.source == "policy-fabric" or event.kind in {"decision", "policy_check"}:
        return "approvals"
    if event.source == "prophet-workspace" or event.kind == "workroom":
        return "workrooms"
    if event.source == "slash-topics" or event.kind in {"topic_scope", "topic_membrane"}:
        return "topics"
    if event.source == "memory-mesh" or event.kind in {"memory_recall", "memory_write", "context_pack"}:
        return "context"
    if event.source == "new-hope" or event.kind in {"semantic_thread", "claim", "citation"}:
        return "semantic"
    if event.source in {"holmes", "sherlock-search"}:
        return "investigations"
    if event.source == "meshrush" or event.kind in {"graph_view", "graph_artifact"}:
        return "graphs"
    if event.source == "cloudshell-fog" or event.kind in {"shell_session", "shell_attach"}:
        return "shells"
    if event.source == "agentplane" or event.kind in {"validation", "placement", "run", "replay"}:
        return "runs"
    if _has_evidence(event):
        return "evidence"
    return "events"


def event_line(event: AgentTermEvent) -> TuiLine:
    status = status_for_event(event)
    prefix = _event_prefix(event)
    text = f"{prefix}{event.body}"
    return TuiLine(
        text=text,
        status=status,
        event_id=event.event_id,
        source=event.source,
        kind=event.kind,
        metadata=event.metadata,
    )


def status_for_event(event: AgentTermEvent) -> str:
    metadata = event.metadata
    if bool(metadata.get("revoked")):
        return "revoked"
    if metadata.get("deny_reason") or metadata.get("admission_status") == "denied":
        return "denied"
    if metadata.get("policy_status") == "pending" or metadata.get("approval_required"):
        return "pending"
    if metadata.get("fail_closed"):
        return "blocked"
    if metadata.get("matrix_sensitive_context_allowed") is False:
        return "blocked"
    if metadata.get("dispatch_status") == "invoked":
        return "active"
    if metadata.get("cloudshell_status") in {"running", "attach_prepared"}:
        return "active"
    if metadata.get("agentplane_status") in {"completed", "placed", "valid"}:
        return "active"
    return "info"


def title_for_pane(name: str) -> str:
    titles = {
        "rooms": "Matrix Rooms / Channels",
        "threads": "Threads / Work Orders",
        "agents": "Agents / Grants / Revocation",
        "approvals": "Approvals / Policy Fabric",
        "workrooms": "Prophet Workrooms",
        "topics": "Slash Topics",
        "context": "Memory / Context",
        "semantic": "New Hope Semantic Objects",
        "investigations": "Holmes / Sherlock",
        "graphs": "MeshRush Graphs",
        "shells": "cloudshell-fog",
        "runs": "AgentPlane Runs",
        "evidence": "Evidence",
        "events": "Event Log",
    }
    return titles[name]


def _room_line(event: AgentTermEvent) -> TuiLine:
    room = str(event.metadata.get("matrix_room_alias") or event.channel)
    return TuiLine(text=room, status="info", event_id=event.event_id, source=event.source)


def _event_prefix(event: AgentTermEvent) -> str:
    agent = event.metadata.get("agent_id")
    workroom = event.metadata.get("workroom")
    topic = event.metadata.get("topic_scope")
    pieces = [piece for piece in (agent, workroom, topic) if piece]
    return f"({' / '.join(str(piece) for piece in pieces)}) " if pieces else ""


def _has_evidence(event: AgentTermEvent) -> bool:
    artifacts = event.metadata.get("artifacts")
    return bool(artifacts or event.metadata.get("artifact_ref") or event.metadata.get("evidence_ref"))
