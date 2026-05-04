"""Local operator smoke runner for AgentTerm.

The smoke runner executes the documented local operator path without requiring live
Matrix, Agent Registry, or Policy Fabric services. It is intentionally explicit and
records all state into a caller-provided work directory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from agent_term.dispatch_cli import main as dispatch_main
from agent_term.health_cli import main as health_main
from agent_term.matrix_cli import main as matrix_main
from agent_term.snapshot_cli import main as snapshot_main


@dataclass(frozen=True)
class SmokeStep:
    """One executed smoke step."""

    name: str
    exit_code: int
    command: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


@dataclass(frozen=True)
class SmokeResult:
    """Complete local operator smoke result."""

    workdir: Path
    steps: tuple[SmokeStep, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return all(step.ok for step in self.steps)

    def render_text(self) -> str:
        lines = [f"smoke_status={'ok' if self.ok else 'failed'}", f"workdir={self.workdir}"]
        for step in self.steps:
            status = "ok" if step.ok else "failed"
            lines.append(f"{step.name}\t{status}\texit={step.exit_code}\t{' '.join(step.command)}")
        return "\n".join(lines)


DEFAULT_CONFIG = Path("configs/agent-term.local.example.json")
DEFAULT_MATRIX_SYNC = Path("configs/fixtures/matrix-sync.local.example.json")


def run_local_operator_smoke(
    *,
    workdir: Path,
    config_path: Path = DEFAULT_CONFIG,
    matrix_sync_fixture: Path = DEFAULT_MATRIX_SYNC,
) -> SmokeResult:
    """Run the local operator quickstart flow against isolated state."""

    workdir.mkdir(parents=True, exist_ok=True)
    db_path = workdir / "events.sqlite3"
    state_path = workdir / "matrix-state.json"

    steps = [
        _run(
            "check",
            health_main,
            (
                "--config",
                str(config_path),
                "--agent-id",
                "agent.github",
                "--tool",
                "repo-write",
                "--policy-action",
                "github.pr.create",
            ),
        ),
        _run(
            "matrix-normalize-sync",
            matrix_main,
            (
                "--config",
                str(config_path),
                "--db",
                str(db_path),
                "--state",
                str(state_path),
                "normalize-sync",
                str(matrix_sync_fixture),
                "--persist",
                "--save-state",
            ),
        ),
        _run(
            "matrix-send",
            matrix_main,
            (
                "--config",
                str(config_path),
                "--db",
                str(db_path),
                "--state",
                str(state_path),
                "send",
                "sourceosOps",
                "AgentTerm local smoke runner is online.",
            ),
        ),
        _run(
            "github-dispatch",
            dispatch_main,
            (
                "--config",
                str(config_path),
                "--db",
                str(db_path),
                "--tool",
                "repo-write",
                "--policy-action",
                "github.pr.create",
                "github",
                "github_mutation",
                "!github",
                "Create PR for AgentTerm local smoke runner",
            ),
        ),
        _run(
            "memory-dispatch",
            dispatch_main,
            (
                "--config",
                str(config_path),
                "--db",
                str(db_path),
                "--metadata-json",
                json.dumps(
                    {
                        "query": "operator smoke runner context",
                        "policy_action": "memory-mesh.memory_recall",
                        "workroom": "operator-smoke",
                        "topic_scope": "sourceos-agentterm",
                    },
                    sort_keys=True,
                ),
                "memory-mesh",
                "memory_recall",
                "!memory-mesh",
                "Recall operator smoke runner context",
            ),
        ),
        _run(
            "snapshot",
            snapshot_main,
            ("--db", str(db_path), "--limit", "200"),
        ),
    ]

    return SmokeResult(workdir=workdir, steps=tuple(steps))


def _run(name: str, fn, argv: tuple[str, ...]) -> SmokeStep:
    try:
        exit_code = int(fn(list(argv)))
    except SystemExit as exc:
        exit_code = int(exc.code or 0)
    return SmokeStep(name=name, exit_code=exit_code, command=argv)
