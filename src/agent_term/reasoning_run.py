"""Superconscious ReasoningRun trace rendering for AgentTerm.

Provides terminal operator views of governed recursive reasoning artifacts
emitted by Superconscious and promoted into SourceOS-Linux/sourceos-spec.
All queries are dry-run stubs until the live ReasoningRun evidence store
is reachable. Implements issue agent-term#38.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


STUB_NOTE = "ReasoningRun evidence store not yet reachable — stub response per agent-term#38"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ReasoningStep:
    """A single step in a recursive reasoning trace."""

    step_ref: str
    step_index: int
    step_kind: str
    premise_refs: list[str]
    conclusion_ref: str
    confidence: float
    policy_decision_ref: str | None
    suppress_mutation: bool
    observed_at: str


@dataclass(frozen=True)
class ReasoningRunTrace:
    """A complete governed ReasoningRun trace artifact."""

    run_ref: str
    agent_ref: str
    trigger_ref: str
    goal_ref: str
    steps: list[ReasoningStep]
    outcome: str
    confidence: float
    receipt_ref: str | None
    suppress_mutation: bool
    started_at: str
    completed_at: str | None
    note: str = STUB_NOTE

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_ref": self.run_ref,
            "agent_ref": self.agent_ref,
            "trigger_ref": self.trigger_ref,
            "goal_ref": self.goal_ref,
            "step_count": len(self.steps),
            "outcome": self.outcome,
            "confidence": self.confidence,
            "receipt_ref": self.receipt_ref,
            "suppress_mutation": self.suppress_mutation,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "note": self.note,
        }


@dataclass
class ReasoningRunIndex:
    """Index of recent ReasoningRun traces visible to the operator."""

    runs: list[ReasoningRunTrace] = field(default_factory=list)
    total: int = 0
    failed_count: int = 0
    suppressed_count: int = 0
    note: str = STUB_NOTE


def get_run_index(limit: int = 10, agent_ref: str | None = None) -> ReasoningRunIndex:
    """Return recent ReasoningRun traces. Stub until evidence store is live."""
    return ReasoningRunIndex()


def get_run_trace(run_ref: str) -> ReasoningRunTrace | None:
    """Return a single ReasoningRun trace by ref. Stub."""
    return None


def format_run_index(index: ReasoningRunIndex, json_mode: bool = False) -> str:
    if json_mode:
        return json.dumps(
            {
                "total": index.total,
                "failed_count": index.failed_count,
                "suppressed_count": index.suppressed_count,
                "runs": [r.to_dict() for r in index.runs],
                "note": index.note,
            },
            indent=2,
        )
    if not index.runs:
        return f"No ReasoningRun traces found. (note: {index.note})"
    lines = [f"ReasoningRun traces ({index.total} total, {index.failed_count} failed):"]
    for r in index.runs:
        status = r.outcome
        lines.append(f"  {r.run_ref}  [{status}]  confidence={r.confidence:.2f}  steps={len(r.steps)}")
    return "\n".join(lines)


def format_run_trace(trace: ReasoningRunTrace, json_mode: bool = False) -> str:
    if json_mode:
        return json.dumps(
            {
                **trace.to_dict(),
                "steps": [
                    {
                        "step_index": s.step_index,
                        "step_kind": s.step_kind,
                        "confidence": s.confidence,
                        "suppress_mutation": s.suppress_mutation,
                    }
                    for s in trace.steps
                ],
            },
            indent=2,
        )
    lines = [
        f"ReasoningRun: {trace.run_ref}",
        f"  agent:            {trace.agent_ref}",
        f"  outcome:          {trace.outcome}",
        f"  confidence:       {trace.confidence:.2f}",
        f"  steps:            {len(trace.steps)}",
        f"  suppress_mutation:{trace.suppress_mutation}",
        f"  started:          {trace.started_at}",
        f"  completed:        {trace.completed_at or 'in-progress'}",
    ]
    if trace.steps:
        lines.append("  Steps:")
        for s in trace.steps:
            lines.append(f"    [{s.step_index}] {s.step_kind}  confidence={s.confidence:.2f}  suppress={s.suppress_mutation}")
    return "\n".join(lines)
