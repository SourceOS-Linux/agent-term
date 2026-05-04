"""Release and command-index helpers for AgentTerm."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version


PACKAGE_NAME = "agent-term"


@dataclass(frozen=True)
class CommandInfo:
    """Installed AgentTerm command metadata."""

    name: str
    summary: str
    smoke: str | None = None


COMMANDS: tuple[CommandInfo, ...] = (
    CommandInfo(
        name="agent-term",
        summary="Core local event-log CLI and minimal interactive shell.",
        smoke="agent-term --help",
    ),
    CommandInfo(
        name="agent-term-check",
        summary="Preflight Matrix, Agent Registry, and Policy Fabric service seams.",
        smoke="agent-term-check --config configs/agent-term.local.example.json",
    ),
    CommandInfo(
        name="agent-term-dispatch",
        summary="Dispatch one event through Matrix posture, Agent Registry, Policy Fabric, adapters, EventStore, and snapshot generation.",
        smoke="agent-term-dispatch --help",
    ),
    CommandInfo(
        name="agent-term-matrix",
        summary="Matrix send, sync normalization, durable sync state, and incremental sync helper.",
        smoke="agent-term-matrix --help",
    ),
    CommandInfo(
        name="agent-term-smoke",
        summary="Run the local end-to-end operator smoke flow using offline fixtures.",
        smoke="agent-term-smoke --workdir .agent-term/smoke",
    ),
    CommandInfo(
        name="agent-term-snapshot",
        summary="Render a dependency-light operator snapshot from the local EventStore.",
        smoke="agent-term-snapshot --help",
    ),
    CommandInfo(
        name="agent-term-version",
        summary="Print installed AgentTerm package version and command index.",
        smoke="agent-term-version",
    ),
)


def package_version() -> str:
    """Return the installed AgentTerm package version."""

    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return "0.0.0+unknown"


def render_command_index() -> str:
    """Render a terminal-friendly command index."""

    lines = [f"AgentTerm {package_version()}", "", "Commands:"]
    for command in COMMANDS:
        lines.append(f"  {command.name}\n    {command.summary}")
        if command.smoke:
            lines.append(f"    smoke: {command.smoke}")
    return "\n".join(lines)
