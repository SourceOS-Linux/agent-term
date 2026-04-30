"""Adapter contracts for AgentTerm participants.

Adapters translate between AgentTerm events and concrete systems: Matrix rooms,
Agent Registry, Sociosphere, Prophet Workspace, Slash Topics, Memory Mesh, New Hope,
Holmes, Sherlock Search, MeshRush, cloudshell-fog, AgentPlane, Policy Fabric, Hermes,
Codex, Claude Code, OpenCLAW, GitHub, CI, MCP, and local process agents.

This file intentionally avoids vendor SDK dependencies. Real network adapters should live behind
this small contract so the terminal UI, local event log, and policy boundary remain stable.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Protocol

from agent_term.events import AgentTermEvent


@dataclass(frozen=True)
class AdapterResult:
    """Normalized adapter result emitted back into the AgentTerm event log."""

    ok: bool
    body: str
    source: str
    kind: str = "adapter_result"
    metadata: dict[str, object] = field(default_factory=dict)

    def to_event(self, request: AgentTermEvent, sender: str = "@agent-term") -> AgentTermEvent:
        return AgentTermEvent(
            channel=request.channel,
            sender=sender,
            kind=self.kind,
            source=self.source,
            body=self.body,
            thread_id=request.thread_id,
            metadata={"request_event_id": request.event_id, **self.metadata},
        )


class AgentTermAdapter(Protocol):
    """Protocol implemented by AgentTerm integration adapters."""

    key: str

    def supports(self, event: AgentTermEvent) -> bool:
        """Return true when this adapter can handle the event."""

    def handle(self, event: AgentTermEvent) -> AdapterResult:
        """Handle an event and return a normalized result."""


@dataclass(frozen=True)
class ProcessAdapter:
    """Simple command-backed adapter for local agents and CLIs.

    The command is passed to the shell only when explicitly configured by the operator. This is
    deliberately not wired to the interactive shell yet; Agent Registry resolution, Policy Fabric
    approval, and SourceOS execution envelopes should be inserted before side-effecting commands
    are enabled.
    """

    key: str
    command: tuple[str, ...]
    accepted_kinds: tuple[str, ...] = ("command",)
    timeout_seconds: int = 300

    def supports(self, event: AgentTermEvent) -> bool:
        return event.kind in self.accepted_kinds or event.source == self.key

    def handle(self, event: AgentTermEvent) -> AdapterResult:
        completed = subprocess.run(
            [*self.command, event.body],
            check=False,
            text=True,
            capture_output=True,
            timeout=self.timeout_seconds,
        )
        output = completed.stdout.strip() or completed.stderr.strip()
        return AdapterResult(
            ok=completed.returncode == 0,
            body=output or f"{self.key} exited with code {completed.returncode}",
            source=self.key,
            metadata={
                "returncode": completed.returncode,
                "command": list(self.command),
                "stderr_present": bool(completed.stderr.strip()),
            },
        )


ADAPTER_TARGETS = {
    "matrix": "Canonical room/event transport adapter; preserve room IDs, event IDs, redactions, membership, bridge metadata, and E2EE posture.",
    "agent-registry": "Agent identity and runtime-authority adapter for specs, participants, sessions, tool grants, revocation, memories, and registration state.",
    "sociosphere": "Meta-workspace controller adapter for manifest, lock, topology, governance registry, and validation-lane events.",
    "prophet-workspace": "Professional Workrooms and workspace product adapter for workroom binding, policy-aware UX, admin, audit, and search surfaces.",
    "slash-topics": "Governed topic-scope adapter for signed topic packs, policy membranes, and deterministic receipts.",
    "memory-mesh": "Governed memory/context adapter for recall, writeback, context packs, LiteLLM hooks, and OpenCLAW memory tools.",
    "new-hope": "Semantic runtime adapter for messages, threads, claims, citations, entities, lenses, receptors, membranes, and moderation events.",
    "holmes": "Boundary-respecting Holmes adapter for request/status/artifact correlation only; AgentTerm must not define Holmes behavior.",
    "sherlock-search": "Preferred Sherlock integration for scoped search packets and context hydration.",
    "legacy-sherlock": "High-friction policy-gated OSINT wrapper only; never a default ambient tool.",
    "meshrush": "Graph-operating runtime adapter for graph views, diffusion, crystallization, traces, and graph evidence.",
    "cloudshell-fog": "Fog-first shell/session substrate; AgentTerm requests sessions but does not bypass OIDC, placement, TTL, or audit.",
    "agentplane": "Execution authority for bundle validation, placement, runs, replay, and evidence artifacts.",
    "policy-fabric": "Policy decision and evidence authority for side-effecting commands and sensitive context release.",
    "hermes": "Personal/multi-channel agent gateway participant; must resolve identity and grants through Agent Registry before enablement.",
    "codex": "Code-writing participant; must be registered and operate through repo branches, diffs, PRs, and approval-gated shell/test commands.",
    "claude-code": "Codebase reasoning participant; must be registered and emit plan, diff, command, and evidence events.",
    "openclaw": "Local/open agent runtime participant; must be registered and run inside SourceOS capability and policy envelopes.",
    "github": "Issue, PR, review, check, branch, and bot-event integration; GitHub bots must be represented in Agent Registry where acting as agents.",
    "ci": "Workflow status/log/retry integration with explicit retry approval gates; CI bots must be represented in Agent Registry where acting as agents.",
    "mcp": "Tool-plane adapter for files, docs, search, memory, calendar, and other governed capabilities; tool grants should resolve through Agent Registry.",
}
