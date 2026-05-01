"""Sociosphere and Prophet Workspace adapter primitives.

AgentTerm is the terminal operator surface. Sociosphere remains the authority for
workspace manifests, locks, topology, governance registry state, and materialization.
Prophet Workspace remains the authority for Professional Workrooms and workspace
product semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from agent_term.adapters import AdapterResult
from agent_term.events import AgentTermEvent


@dataclass(frozen=True)
class WorkspaceState:
    """Sociosphere workspace state visible to AgentTerm."""

    workspace_ref: str
    status: str
    manifest_ref: str
    lock_ref: str
    topology_ref: str
    validation_ref: str | None = None
    materialization_ref: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, object]:
        return {
            "workspace_ref": self.workspace_ref,
            "workspace_status": self.status,
            "manifest_ref": self.manifest_ref,
            "lock_ref": self.lock_ref,
            "topology_ref": self.topology_ref,
            "validation_ref": self.validation_ref,
            "materialization_ref": self.materialization_ref,
            **self.metadata,
        }


@dataclass(frozen=True)
class ProfessionalWorkroom:
    """Prophet Workspace Professional Workroom state visible to AgentTerm."""

    workroom_id: str
    status: str
    title: str
    matrix_room_id: str | None = None
    topic_scope: str | None = None
    audit_ref: str | None = None
    receipt_ref: str | None = None
    context_pack_ref: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, object]:
        return {
            "workroom": self.workroom_id,
            "workroom_status": self.status,
            "workroom_title": self.title,
            "matrix_room_id": self.matrix_room_id,
            "topic_scope": self.topic_scope,
            "workspace_audit_ref": self.audit_ref,
            "workspace_receipt_ref": self.receipt_ref,
            "context_pack_ref": self.context_pack_ref,
            **self.metadata,
        }


class SociosphereBackend(Protocol):
    """Backend contract for Sociosphere workspace operations."""

    def resolve_workspace(self, workspace_ref: str) -> WorkspaceState:
        """Resolve canonical manifest, lock, and topology references."""

    def validate_topology(self, workspace_ref: str) -> WorkspaceState:
        """Validate topology/governance state for a workspace."""

    def materialize_workspace(self, workspace_ref: str) -> WorkspaceState:
        """Materialize a governed workspace."""


class ProphetWorkspaceBackend(Protocol):
    """Backend contract for Prophet Workspace workroom operations."""

    def bind_workroom(
        self,
        workroom_id: str,
        *,
        matrix_room_id: str | None = None,
        topic_scope: str | None = None,
    ) -> ProfessionalWorkroom:
        """Bind an AgentTerm context to a Professional Workroom."""

    def hydrate_context(self, workroom_id: str) -> ProfessionalWorkroom | None:
        """Hydrate governed context for a workroom."""


class InMemorySociosphereBackend:
    """Test/development backend for Sociosphere workspace operations."""

    def resolve_workspace(self, workspace_ref: str) -> WorkspaceState:
        return WorkspaceState(
            workspace_ref=workspace_ref,
            status="resolved",
            manifest_ref=f"sociosphere://{workspace_ref}/manifest/workspace.toml",
            lock_ref=f"sociosphere://{workspace_ref}/manifest/workspace.lock.json",
            topology_ref=f"sociosphere://{workspace_ref}/docs/TOPOLOGY.md",
        )

    def validate_topology(self, workspace_ref: str) -> WorkspaceState:
        return WorkspaceState(
            workspace_ref=workspace_ref,
            status="validated",
            manifest_ref=f"sociosphere://{workspace_ref}/manifest/workspace.toml",
            lock_ref=f"sociosphere://{workspace_ref}/manifest/workspace.lock.json",
            topology_ref=f"sociosphere://{workspace_ref}/docs/TOPOLOGY.md",
            validation_ref=f"sociosphere://{workspace_ref}/validation/topology.json",
        )

    def materialize_workspace(self, workspace_ref: str) -> WorkspaceState:
        return WorkspaceState(
            workspace_ref=workspace_ref,
            status="materialized",
            manifest_ref=f"sociosphere://{workspace_ref}/manifest/workspace.toml",
            lock_ref=f"sociosphere://{workspace_ref}/manifest/workspace.lock.json",
            topology_ref=f"sociosphere://{workspace_ref}/docs/TOPOLOGY.md",
            validation_ref=f"sociosphere://{workspace_ref}/validation/topology.json",
            materialization_ref=f"sociosphere://{workspace_ref}/materializations/latest",
            metadata={"materialized_at": datetime.now(UTC).isoformat()},
        )


class InMemoryProphetWorkspaceBackend:
    """Test/development backend for Prophet Workspace workroom operations."""

    def __init__(self) -> None:
        self._workrooms: dict[str, ProfessionalWorkroom] = {}

    def bind_workroom(
        self,
        workroom_id: str,
        *,
        matrix_room_id: str | None = None,
        topic_scope: str | None = None,
    ) -> ProfessionalWorkroom:
        workroom = ProfessionalWorkroom(
            workroom_id=workroom_id,
            status="bound",
            title=workroom_id,
            matrix_room_id=matrix_room_id,
            topic_scope=topic_scope,
            audit_ref=f"prophet-workspace://workrooms/{workroom_id}/audit",
            receipt_ref=f"prophet-workspace://workrooms/{workroom_id}/receipts/latest",
        )
        self._workrooms[workroom_id] = workroom
        return workroom

    def hydrate_context(self, workroom_id: str) -> ProfessionalWorkroom | None:
        existing = self._workrooms.get(workroom_id)
        if existing is None:
            return None
        hydrated = ProfessionalWorkroom(
            workroom_id=existing.workroom_id,
            status="context_hydrated",
            title=existing.title,
            matrix_room_id=existing.matrix_room_id,
            topic_scope=existing.topic_scope,
            audit_ref=existing.audit_ref,
            receipt_ref=existing.receipt_ref,
            context_pack_ref=f"prophet-workspace://workrooms/{workroom_id}/context-pack/latest",
            metadata=existing.metadata,
        )
        self._workrooms[workroom_id] = hydrated
        return hydrated


class SociosphereAdapter:
    """Adapter for Sociosphere workspace state and materialization requests."""

    key = "sociosphere"

    def __init__(self, backend: SociosphereBackend) -> None:
        self.backend = backend

    def supports(self, event: AgentTermEvent) -> bool:
        return event.source == self.key or event.kind in {
            "workspace_manifest",
            "topology_validation",
            "workspace_materialization",
        }

    def handle(self, event: AgentTermEvent) -> AdapterResult:
        workspace_ref = _workspace_ref(event)
        if not workspace_ref:
            return _deny(self.key, event, "missing_workspace_ref")
        if event.kind == "workspace_manifest":
            return _workspace_result(event, self.backend.resolve_workspace(workspace_ref))
        if event.kind == "topology_validation":
            return _workspace_result(event, self.backend.validate_topology(workspace_ref))
        if event.kind == "workspace_materialization":
            policy_ref = _policy_decision_ref(event)
            if not policy_ref:
                return _deny(self.key, event, "missing_policy_decision")
            return _workspace_result(
                event,
                self.backend.materialize_workspace(workspace_ref),
                policy_decision_ref=policy_ref,
            )
        return _deny(self.key, event, "unsupported_kind")


class ProphetWorkspaceAdapter:
    """Adapter for Prophet Workspace Professional Workroom operations."""

    key = "prophet-workspace"

    def __init__(self, backend: ProphetWorkspaceBackend) -> None:
        self.backend = backend

    def supports(self, event: AgentTermEvent) -> bool:
        return event.source == self.key or event.kind in {"workroom", "context_pack"}

    def handle(self, event: AgentTermEvent) -> AdapterResult:
        workroom_id = _workroom_id(event)
        if not workroom_id:
            return _deny(self.key, event, "missing_workroom")
        if event.kind == "workroom":
            workroom = self.backend.bind_workroom(
                workroom_id,
                matrix_room_id=_optional_str(event.metadata.get("matrix_room_id")),
                topic_scope=_optional_str(event.metadata.get("topic_scope")),
            )
            return _workroom_result(event, workroom)
        if event.kind == "context_pack":
            policy_ref = _policy_decision_ref(event)
            if not policy_ref:
                return _deny(self.key, event, "missing_policy_decision")
            workroom = self.backend.hydrate_context(workroom_id)
            if workroom is None:
                return _deny(self.key, event, "unknown_workroom")
            return _workroom_result(event, workroom, policy_decision_ref=policy_ref)
        return _deny(self.key, event, "unsupported_kind")


def _workspace_result(
    event: AgentTermEvent,
    state: WorkspaceState,
    *,
    policy_decision_ref: str | None = None,
) -> AdapterResult:
    return AdapterResult(
        ok=True,
        source="sociosphere",
        body=f"Sociosphere workspace {state.status}: {state.workspace_ref}",
        kind="workspace",
        metadata={
            "request_event_id": event.event_id,
            "policy_decision_ref": policy_decision_ref,
            "agent_id": event.metadata.get("agent_id"),
            "matrix_room_id": event.metadata.get("matrix_room_id"),
            "topic_scope": event.metadata.get("topic_scope"),
            **state.to_metadata(),
        },
    )


def _workroom_result(
    event: AgentTermEvent,
    workroom: ProfessionalWorkroom,
    *,
    policy_decision_ref: str | None = None,
) -> AdapterResult:
    return AdapterResult(
        ok=True,
        source="prophet-workspace",
        body=f"Prophet Workspace workroom {workroom.status}: {workroom.workroom_id}",
        kind="workroom",
        metadata={
            "request_event_id": event.event_id,
            "policy_decision_ref": policy_decision_ref,
            "agent_id": event.metadata.get("agent_id"),
            **workroom.to_metadata(),
        },
    )


def _deny(source: str, event: AgentTermEvent, reason: str) -> AdapterResult:
    return AdapterResult(
        ok=False,
        source=source,
        body=f"{source} denied request: {reason}",
        metadata={
            "request_event_id": event.event_id,
            "deny_reason": reason,
            "fail_closed": True,
        },
    )


def _workspace_ref(event: AgentTermEvent) -> str | None:
    return _optional_str(event.metadata.get("workspace_ref") or event.metadata.get("workspace"))


def _workroom_id(event: AgentTermEvent) -> str | None:
    return _optional_str(event.metadata.get("workroom") or event.metadata.get("workroom_id"))


def _policy_decision_ref(event: AgentTermEvent) -> str | None:
    return _optional_str(
        event.metadata.get("policy_decision_ref")
        or event.metadata.get("policy_decision_id")
        or event.metadata.get("policyDecisionRef")
    )


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None
