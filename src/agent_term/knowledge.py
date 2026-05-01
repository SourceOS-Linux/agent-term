"""Knowledge and intelligence adapter primitives.

These adapters preserve SourceOS plane boundaries. AgentTerm records governed
requests and artifact/status references; it does not own the semantics of Slash
Topics, Memory Mesh, New Hope, Sherlock Search, Holmes, or MeshRush.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from agent_term.adapters import AdapterResult
from agent_term.events import AgentTermEvent


@dataclass(frozen=True)
class KnowledgeArtifact:
    """Generic artifact reference emitted by a knowledge/intelligence plane."""

    kind: str
    ref: str
    metadata: dict[str, object] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, object]:
        return {"artifact_kind": self.kind, "artifact_ref": self.ref, **self.metadata}


@dataclass(frozen=True)
class KnowledgeResult:
    """Normalized result from a knowledge/intelligence plane."""

    plane: str
    operation: str
    status: str
    ref: str
    artifacts: tuple[KnowledgeArtifact, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, object]:
        return {
            "knowledge_plane": self.plane,
            "knowledge_operation": self.operation,
            "knowledge_status": self.status,
            "knowledge_ref": self.ref,
            "artifacts": [artifact.to_metadata() for artifact in self.artifacts],
            **self.metadata,
        }


class SlashTopicsBackend(Protocol):
    def select_scope(self, topic_scope: str) -> KnowledgeResult:
        """Select a topic scope."""

    def apply_membrane(self, topic_scope: str) -> KnowledgeResult:
        """Apply a topic-policy membrane."""


class MemoryMeshBackend(Protocol):
    def recall(self, query: str) -> KnowledgeResult:
        """Recall scoped context."""

    def write(self, entry: str) -> KnowledgeResult:
        """Write governed memory."""


class NewHopeBackend(Protocol):
    def normalize_thread(self, semantic_ref: str) -> KnowledgeResult:
        """Normalize message/thread objects."""

    def extract_claims(self, semantic_ref: str) -> KnowledgeResult:
        """Extract claims/citations/entities."""


class SherlockSearchBackend(Protocol):
    def create_packet(self, query: str) -> KnowledgeResult:
        """Create a governed search packet."""

    def hydrate_context(self, packet_ref: str) -> KnowledgeResult:
        """Hydrate context from a search packet."""


class HolmesBackend(Protocol):
    def request_investigation(self, request: str) -> KnowledgeResult:
        """Request Holmes-owned investigation work."""

    def correlate_artifact(self, artifact_ref: str) -> KnowledgeResult:
        """Correlate a Holmes-owned artifact or status reference."""


class MeshRushBackend(Protocol):
    def enter_graph_view(self, graph_ref: str) -> KnowledgeResult:
        """Enter a graph view."""

    def crystallize(self, graph_ref: str) -> KnowledgeResult:
        """Crystallize graph artifacts."""


class InMemorySlashTopicsBackend:
    def select_scope(self, topic_scope: str) -> KnowledgeResult:
        return KnowledgeResult(
            plane="slash-topics",
            operation="select_topic_scope",
            status="selected",
            ref=topic_scope,
            artifacts=(
                KnowledgeArtifact(
                    kind="TopicScopeReceipt",
                    ref=f"slash-topics://topics/{topic_scope}/receipt",
                ),
            ),
        )

    def apply_membrane(self, topic_scope: str) -> KnowledgeResult:
        return KnowledgeResult(
            plane="slash-topics",
            operation="apply_topic_membrane",
            status="applied",
            ref=topic_scope,
            artifacts=(
                KnowledgeArtifact(
                    kind="TopicMembraneDecision",
                    ref=f"slash-topics://topics/{topic_scope}/membrane-decision",
                ),
            ),
        )


class InMemoryMemoryMeshBackend:
    def recall(self, query: str) -> KnowledgeResult:
        context_ref = f"memory-mesh://context-packs/{_slug(query)}"
        return KnowledgeResult(
            plane="memory-mesh",
            operation="recall_context",
            status="recalled",
            ref=context_ref,
            artifacts=(KnowledgeArtifact(kind="ContextPack", ref=context_ref),),
            metadata={"query": query},
        )

    def write(self, entry: str) -> KnowledgeResult:
        memory_ref = f"memory-mesh://entries/{_slug(entry)}"
        return KnowledgeResult(
            plane="memory-mesh",
            operation="write_memory",
            status="written",
            ref=memory_ref,
            artifacts=(KnowledgeArtifact(kind="MemoryEntry", ref=memory_ref),),
            metadata={"entry": entry},
        )


class InMemoryNewHopeBackend:
    def normalize_thread(self, semantic_ref: str) -> KnowledgeResult:
        return KnowledgeResult(
            plane="new-hope",
            operation="normalize_thread",
            status="normalized",
            ref=f"new-hope://threads/{_slug(semantic_ref)}",
            artifacts=(
                KnowledgeArtifact(
                    kind="SemanticThread",
                    ref=f"new-hope://threads/{_slug(semantic_ref)}",
                ),
            ),
            metadata={"semantic_ref": semantic_ref},
        )

    def extract_claims(self, semantic_ref: str) -> KnowledgeResult:
        return KnowledgeResult(
            plane="new-hope",
            operation="extract_claims",
            status="extracted",
            ref=f"new-hope://claims/{_slug(semantic_ref)}",
            artifacts=(
                KnowledgeArtifact(kind="ClaimSet", ref=f"new-hope://claims/{_slug(semantic_ref)}"),
                KnowledgeArtifact(
                    kind="CitationSet",
                    ref=f"new-hope://citations/{_slug(semantic_ref)}",
                ),
            ),
            metadata={"semantic_ref": semantic_ref},
        )


class InMemorySherlockSearchBackend:
    def create_packet(self, query: str) -> KnowledgeResult:
        packet_ref = f"sherlock-search://packets/{_slug(query)}"
        return KnowledgeResult(
            plane="sherlock-search",
            operation="create_search_packet",
            status="created",
            ref=packet_ref,
            artifacts=(KnowledgeArtifact(kind="SearchPacket", ref=packet_ref),),
            metadata={"query": query},
        )

    def hydrate_context(self, packet_ref: str) -> KnowledgeResult:
        context_ref = f"sherlock-search://hydrated-context/{_slug(packet_ref)}"
        return KnowledgeResult(
            plane="sherlock-search",
            operation="hydrate_context_pack",
            status="hydrated",
            ref=context_ref,
            artifacts=(KnowledgeArtifact(kind="HydratedContext", ref=context_ref),),
            metadata={"search_packet_ref": packet_ref},
        )


class InMemoryHolmesBackend:
    def request_investigation(self, request: str) -> KnowledgeResult:
        case_ref = f"holmes://casefiles/{_slug(request)}"
        return KnowledgeResult(
            plane="holmes",
            operation="request_investigation",
            status="requested",
            ref=case_ref,
            artifacts=(KnowledgeArtifact(kind="HolmesCasefileRef", ref=case_ref),),
            metadata={"request": request, "boundary": "correlation-only"},
        )

    def correlate_artifact(self, artifact_ref: str) -> KnowledgeResult:
        return KnowledgeResult(
            plane="holmes",
            operation="correlate_artifact",
            status="correlated",
            ref=artifact_ref,
            artifacts=(KnowledgeArtifact(kind="HolmesArtifactRef", ref=artifact_ref),),
            metadata={"boundary": "correlation-only"},
        )


class InMemoryMeshRushBackend:
    def enter_graph_view(self, graph_ref: str) -> KnowledgeResult:
        return KnowledgeResult(
            plane="meshrush",
            operation="enter_graph_view",
            status="entered",
            ref=f"meshrush://graph-views/{_slug(graph_ref)}",
            artifacts=(
                KnowledgeArtifact(kind="GraphView", ref=f"meshrush://graph-views/{_slug(graph_ref)}"),
            ),
            metadata={"graph_ref": graph_ref},
        )

    def crystallize(self, graph_ref: str) -> KnowledgeResult:
        return KnowledgeResult(
            plane="meshrush",
            operation="crystallize_artifact",
            status="crystallized",
            ref=f"meshrush://artifacts/{_slug(graph_ref)}",
            artifacts=(
                KnowledgeArtifact(kind="GraphArtifact", ref=f"meshrush://artifacts/{_slug(graph_ref)}"),
            ),
            metadata={"graph_ref": graph_ref},
        )


class SlashTopicsAdapter:
    key = "slash-topics"

    def __init__(self, backend: SlashTopicsBackend) -> None:
        self.backend = backend

    def supports(self, event: AgentTermEvent) -> bool:
        return event.source == self.key or event.kind in {"topic_scope", "topic_membrane"}

    def handle(self, event: AgentTermEvent) -> AdapterResult:
        topic_scope = _topic_scope(event)
        if not topic_scope:
            return _deny(self.key, event, "missing_topic_scope")
        if event.kind == "topic_scope":
            return _result(event, self.backend.select_scope(topic_scope))
        if event.kind == "topic_membrane":
            if not _policy_decision_ref(event):
                return _deny(self.key, event, "missing_policy_decision")
            return _result(event, self.backend.apply_membrane(topic_scope))
        return _deny(self.key, event, "unsupported_kind")


class MemoryMeshAdapter:
    key = "memory-mesh"

    def __init__(self, backend: MemoryMeshBackend) -> None:
        self.backend = backend

    def supports(self, event: AgentTermEvent) -> bool:
        return event.source == self.key or event.kind in {"memory_recall", "memory_write"}

    def handle(self, event: AgentTermEvent) -> AdapterResult:
        if not _policy_decision_ref(event):
            return _deny(self.key, event, "missing_policy_decision")
        if event.kind == "memory_recall":
            query = _query(event)
            if not query:
                return _deny(self.key, event, "missing_query")
            return _result(event, self.backend.recall(query))
        if event.kind == "memory_write":
            entry = _entry(event)
            if not entry:
                return _deny(self.key, event, "missing_entry")
            return _result(event, self.backend.write(entry))
        return _deny(self.key, event, "unsupported_kind")


class NewHopeAdapter:
    key = "new-hope"

    def __init__(self, backend: NewHopeBackend) -> None:
        self.backend = backend

    def supports(self, event: AgentTermEvent) -> bool:
        return event.source == self.key or event.kind in {"semantic_thread", "claim"}

    def handle(self, event: AgentTermEvent) -> AdapterResult:
        semantic_ref = _semantic_ref(event)
        if not semantic_ref:
            return _deny(self.key, event, "missing_semantic_ref")
        if event.kind == "semantic_thread":
            return _result(event, self.backend.normalize_thread(semantic_ref))
        if event.kind == "claim":
            if not _policy_decision_ref(event):
                return _deny(self.key, event, "missing_policy_decision")
            return _result(event, self.backend.extract_claims(semantic_ref))
        return _deny(self.key, event, "unsupported_kind")


class SherlockSearchAdapter:
    key = "sherlock-search"

    def __init__(self, backend: SherlockSearchBackend) -> None:
        self.backend = backend

    def supports(self, event: AgentTermEvent) -> bool:
        return event.source == self.key or event.kind in {"search_packet", "context_pack"}

    def handle(self, event: AgentTermEvent) -> AdapterResult:
        if not _policy_decision_ref(event):
            return _deny(self.key, event, "missing_policy_decision")
        if event.kind == "search_packet":
            query = _query(event)
            if not query:
                return _deny(self.key, event, "missing_query")
            return _result(event, self.backend.create_packet(query))
        if event.kind == "context_pack":
            packet_ref = _packet_ref(event)
            if not packet_ref:
                return _deny(self.key, event, "missing_search_packet_ref")
            return _result(event, self.backend.hydrate_context(packet_ref))
        return _deny(self.key, event, "unsupported_kind")


class HolmesAdapter:
    key = "holmes"

    def __init__(self, backend: HolmesBackend) -> None:
        self.backend = backend

    def supports(self, event: AgentTermEvent) -> bool:
        return event.source == self.key or event.kind in {"investigation", "correlation"}

    def handle(self, event: AgentTermEvent) -> AdapterResult:
        if event.kind == "investigation":
            if not _policy_decision_ref(event):
                return _deny(self.key, event, "missing_policy_decision")
            request = _query(event)
            if not request:
                return _deny(self.key, event, "missing_request")
            return _result(event, self.backend.request_investigation(request))
        if event.kind == "correlation":
            artifact_ref = _artifact_ref(event)
            if not artifact_ref:
                return _deny(self.key, event, "missing_artifact_ref")
            return _result(event, self.backend.correlate_artifact(artifact_ref))
        return _deny(self.key, event, "unsupported_kind")


class MeshRushAdapter:
    key = "meshrush"

    def __init__(self, backend: MeshRushBackend) -> None:
        self.backend = backend

    def supports(self, event: AgentTermEvent) -> bool:
        return event.source == self.key or event.kind in {"graph_view", "graph_artifact"}

    def handle(self, event: AgentTermEvent) -> AdapterResult:
        if not _policy_decision_ref(event):
            return _deny(self.key, event, "missing_policy_decision")
        graph_ref = _graph_ref(event)
        if not graph_ref:
            return _deny(self.key, event, "missing_graph_ref")
        if event.kind == "graph_view":
            return _result(event, self.backend.enter_graph_view(graph_ref))
        if event.kind == "graph_artifact":
            return _result(event, self.backend.crystallize(graph_ref))
        return _deny(self.key, event, "unsupported_kind")


def _result(event: AgentTermEvent, result: KnowledgeResult) -> AdapterResult:
    return AdapterResult(
        ok=True,
        source=result.plane,
        body=f"{result.plane} {result.operation} {result.status}: {result.ref}",
        kind=result.operation,
        metadata={
            "request_event_id": event.event_id,
            "policy_decision_ref": _policy_decision_ref(event),
            "agent_id": event.metadata.get("agent_id"),
            "workroom": event.metadata.get("workroom"),
            "topic_scope": _topic_scope(event),
            "matrix_room_id": event.metadata.get("matrix_room_id"),
            "created_at": datetime.now(UTC).isoformat(),
            **result.to_metadata(),
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


def _policy_decision_ref(event: AgentTermEvent) -> str | None:
    return _optional_str(
        event.metadata.get("policy_decision_ref")
        or event.metadata.get("policy_decision_id")
        or event.metadata.get("policyDecisionRef")
    )


def _topic_scope(event: AgentTermEvent) -> str | None:
    return _optional_str(event.metadata.get("topic_scope") or event.metadata.get("topic"))


def _query(event: AgentTermEvent) -> str | None:
    return _optional_str(event.metadata.get("query") or event.metadata.get("request") or event.body)


def _entry(event: AgentTermEvent) -> str | None:
    return _optional_str(event.metadata.get("entry") or event.body)


def _semantic_ref(event: AgentTermEvent) -> str | None:
    return _optional_str(event.metadata.get("semantic_ref") or event.metadata.get("thread_ref"))


def _packet_ref(event: AgentTermEvent) -> str | None:
    return _optional_str(event.metadata.get("search_packet_ref") or event.metadata.get("packet_ref"))


def _artifact_ref(event: AgentTermEvent) -> str | None:
    return _optional_str(event.metadata.get("artifact_ref") or event.metadata.get("holmes_artifact_ref"))


def _graph_ref(event: AgentTermEvent) -> str | None:
    return _optional_str(event.metadata.get("graph_ref") or event.metadata.get("graph_view"))


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None


def _slug(value: str) -> str:
    normalized = "-".join(value.strip().lower().split())
    safe = "".join(ch for ch in normalized if ch.isalnum() or ch in {"-", "_", "."})
    return safe[:80] or "default"
