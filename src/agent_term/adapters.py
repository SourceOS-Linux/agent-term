"""Adapter contracts for AgentTerm participants.

Adapters translate between AgentTerm events and concrete systems: Matrix rooms, Hermes,
Codex, Claude Code, OpenCLAW, AgentPlane, Policy Fabric, Sherlock Search, cloudshell-fog,
GitHub, CI, MCP, and local process agents.

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
    deliberately not wired to the interactive shell yet; Policy Fabric approval and SourceOS
    execution envelopes should be inserted before side-effecting commands are enabled.
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
    "matrix": "Canonical room/event transport adapter; must preserve room IDs, event IDs, redactions, membership, bridge metadata, and E2EE posture.",
    "hermes": "Personal/multi-channel agent gateway participant; may bridge external chat surfaces into Matrix-backed AgentTerm rooms.",
    "codex": "Code-writing participant; must operate through repo branches, diffs, PRs, and approval-gated shell/test commands.",
    "claude-code": "Codebase reasoning and patch participant; must emit plan, diff, command, and evidence events.",
    "openclaw": "Local/open agent runtime participant; must run inside SourceOS capability and policy envelopes.",
    "cloudshell-fog": "Fog-first shell/session substrate; AgentTerm requests sessions but does not bypass OIDC, placement, TTL, or audit.",
    "agentplane": "Execution authority for bundle validation, placement, runs, replay, and evidence artifacts.",
    "policy-fabric": "Policy decision and evidence authority for side-effecting commands and sensitive context release.",
    "sherlock-search": "Preferred Sherlock integration for scoped search packets and context hydration.",
    "legacy-sherlock": "High-friction policy-gated OSINT wrapper only; never a default ambient tool.",
    "github": "Issue, PR, review, check, and branch event integration.",
    "ci": "Workflow status/log/retry integration with explicit retry approval gates.",
    "mcp": "Tool-plane adapter for files, docs, search, memory, calendar, and other governed capabilities.",
}
