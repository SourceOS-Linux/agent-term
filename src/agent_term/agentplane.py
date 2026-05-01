"""AgentPlane adapter primitives.

AgentTerm does not execute bundles. AgentPlane remains the authority for validation,
placement, run, replay, and evidence artifacts. This module provides a dependency-free
adapter boundary for recording governed execution operations and artifact references.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from agent_term.adapters import AdapterResult
from agent_term.events import AgentTermEvent


@dataclass(frozen=True)
class AgentPlaneArtifact:
    """AgentPlane evidence artifact reference."""

    kind: str
    ref: str
    digest: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, object]:
        return {
            "artifact_kind": self.kind,
            "artifact_ref": self.ref,
            "artifact_digest": self.digest,
            **self.metadata,
        }


@dataclass(frozen=True)
class AgentPlaneResult:
    """Normalized result from an AgentPlane operation."""

    operation: str
    status: str
    bundle_ref: str
    run_id: str | None = None
    executor_ref: str | None = None
    artifacts: tuple[AgentPlaneArtifact, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, object]:
        return {
            "agentplane_operation": self.operation,
            "agentplane_status": self.status,
            "bundle_ref": self.bundle_ref,
            "run_id": self.run_id,
            "executor_ref": self.executor_ref,
            "artifacts": [artifact.to_metadata() for artifact in self.artifacts],
            **self.metadata,
        }


class AgentPlaneBackend(Protocol):
    """Backend contract for AgentPlane operations."""

    def validate(self, bundle_ref: str) -> AgentPlaneResult:
        """Validate a bundle."""

    def place(self, bundle_ref: str) -> AgentPlaneResult:
        """Select an executor for a bundle."""

    def run(self, bundle_ref: str, executor_ref: str | None = None) -> AgentPlaneResult:
        """Run a bundle."""

    def replay(self, run_id: str) -> AgentPlaneResult | None:
        """Replay an existing run."""


class InMemoryAgentPlaneBackend:
    """Test/development backend for AgentPlane operations."""

    def __init__(self) -> None:
        self._runs: dict[str, AgentPlaneResult] = {}

    def validate(self, bundle_ref: str) -> AgentPlaneResult:
        return AgentPlaneResult(
            operation="validate",
            status="valid",
            bundle_ref=bundle_ref,
            artifacts=(
                AgentPlaneArtifact(
                    kind="ValidationArtifact",
                    ref=f"agentplane://artifacts/{bundle_ref}/validation-artifact.json",
                ),
            ),
        )

    def place(self, bundle_ref: str) -> AgentPlaneResult:
        return AgentPlaneResult(
            operation="place",
            status="placed",
            bundle_ref=bundle_ref,
            executor_ref="executor.local",
            artifacts=(
                AgentPlaneArtifact(
                    kind="PlacementDecision",
                    ref=f"agentplane://artifacts/{bundle_ref}/placement-decision.json",
                ),
            ),
        )

    def run(self, bundle_ref: str, executor_ref: str | None = None) -> AgentPlaneResult:
        run_id = f"run-{len(self._runs) + 1}"
        result = AgentPlaneResult(
            operation="run",
            status="completed",
            bundle_ref=bundle_ref,
            run_id=run_id,
            executor_ref=executor_ref or "executor.local",
            artifacts=(
                AgentPlaneArtifact(
                    kind="RunArtifact",
                    ref=f"agentplane://runs/{run_id}/run-artifact.json",
                ),
                AgentPlaneArtifact(
                    kind="ReplayArtifact",
                    ref=f"agentplane://runs/{run_id}/replay-artifact.json",
                ),
            ),
            metadata={"completed_at": datetime.now(UTC).isoformat()},
        )
        self._runs[run_id] = result
        return result

    def replay(self, run_id: str) -> AgentPlaneResult | None:
        prior = self._runs.get(run_id)
        if prior is None:
            return None
        return AgentPlaneResult(
            operation="replay",
            status="prepared",
            bundle_ref=prior.bundle_ref,
            run_id=run_id,
            executor_ref=prior.executor_ref,
            artifacts=prior.artifacts,
        )


class AgentPlaneAdapter:
    """Adapter that prepares governed AgentPlane operations."""

    key = "agentplane"

    def __init__(self, backend: AgentPlaneBackend) -> None:
        self.backend = backend

    def supports(self, event: AgentTermEvent) -> bool:
        return event.source == self.key or event.kind in {
            "validation",
            "placement",
            "run",
            "replay",
        }

    def handle(self, event: AgentTermEvent) -> AdapterResult:
        if event.kind == "validation":
            return self._validate(event)
        if event.kind == "placement":
            return self._place(event)
        if event.kind == "run":
            return self._run(event)
        if event.kind == "replay":
            return self._replay(event)
        return AdapterResult(
            ok=False,
            source=self.key,
            body=f"Unsupported AgentPlane event kind: {event.kind}",
            metadata={"agentplane_status": "unsupported_kind", "fail_closed": True},
        )

    def _validate(self, event: AgentTermEvent) -> AdapterResult:
        bundle_ref = _bundle_ref(event)
        if not bundle_ref:
            return _deny(event, "missing_bundle_ref")
        return _result(event, self.backend.validate(bundle_ref))

    def _place(self, event: AgentTermEvent) -> AdapterResult:
        bundle_ref = _bundle_ref(event)
        if not bundle_ref:
            return _deny(event, "missing_bundle_ref")
        return _result(event, self.backend.place(bundle_ref))

    def _run(self, event: AgentTermEvent) -> AdapterResult:
        policy_ref = _policy_decision_ref(event)
        if not policy_ref:
            return _deny(event, "missing_policy_decision")
        bundle_ref = _bundle_ref(event)
        if not bundle_ref:
            return _deny(event, "missing_bundle_ref")
        result = self.backend.run(bundle_ref, _optional_str(event.metadata.get("executor_ref")))
        return _result(event, result, policy_decision_ref=policy_ref)

    def _replay(self, event: AgentTermEvent) -> AdapterResult:
        policy_ref = _policy_decision_ref(event)
        if not policy_ref:
            return _deny(event, "missing_policy_decision")
        run_id = _optional_str(event.metadata.get("run_id"))
        if not run_id:
            return _deny(event, "missing_run_id")
        result = self.backend.replay(run_id)
        if result is None:
            return _deny(event, "unknown_run", run_id=run_id)
        return _result(event, result, policy_decision_ref=policy_ref)


def _result(
    event: AgentTermEvent,
    result: AgentPlaneResult,
    *,
    policy_decision_ref: str | None = None,
) -> AdapterResult:
    metadata = {
        "request_event_id": event.event_id,
        "agentplane_status": result.status,
        "policy_decision_ref": policy_decision_ref,
        "agent_id": event.metadata.get("agent_id"),
        "workroom": event.metadata.get("workroom"),
        "topic_scope": event.metadata.get("topic_scope"),
        "matrix_room_id": event.metadata.get("matrix_room_id"),
        **result.to_metadata(),
    }
    return AdapterResult(
        ok=True,
        source="agentplane",
        body=f"AgentPlane {result.operation} {result.status}: {result.bundle_ref}",
        kind=result.operation,
        metadata=metadata,
    )


def _deny(
    event: AgentTermEvent,
    reason: str,
    *,
    run_id: str | None = None,
) -> AdapterResult:
    metadata: dict[str, object] = {
        "request_event_id": event.event_id,
        "agentplane_status": "denied",
        "deny_reason": reason,
        "fail_closed": True,
    }
    if run_id:
        metadata["run_id"] = run_id
    return AdapterResult(
        ok=False,
        source="agentplane",
        body=f"AgentPlane denied request: {reason}",
        metadata=metadata,
    )


def _bundle_ref(event: AgentTermEvent) -> str | None:
    return _optional_str(event.metadata.get("bundle_ref") or event.metadata.get("bundle"))


def _policy_decision_ref(event: AgentTermEvent) -> str | None:
    return _optional_str(
        event.metadata.get("policy_decision_ref")
        or event.metadata.get("policy_decision_id")
        or event.metadata.get("policyDecisionRef")
    )


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None
