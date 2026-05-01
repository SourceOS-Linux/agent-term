from agent_term.events import AgentTermEvent
from agent_term.knowledge import (
    HolmesAdapter,
    InMemoryHolmesBackend,
    InMemoryMemoryMeshBackend,
    InMemoryMeshRushBackend,
    InMemoryNewHopeBackend,
    InMemorySherlockSearchBackend,
    InMemorySlashTopicsBackend,
    MemoryMeshAdapter,
    MeshRushAdapter,
    NewHopeAdapter,
    SherlockSearchAdapter,
    SlashTopicsAdapter,
)


def make_event(
    kind: str,
    source: str,
    metadata: dict[str, object] | None = None,
    body: str = "knowledge test event",
) -> AgentTermEvent:
    return AgentTermEvent(
        channel=f"!{source}",
        sender="@operator",
        kind=kind,
        source=source,
        body=body,
        thread_id="thread-1",
        metadata=metadata or {},
    )


def test_slash_topics_selects_scope_without_policy_side_effect():
    adapter = SlashTopicsAdapter(InMemorySlashTopicsBackend())

    result = adapter.handle(
        make_event("topic_scope", "slash-topics", {"topic_scope": "professional-intelligence"})
    )

    assert result.ok is True
    assert result.source == "slash-topics"
    assert result.metadata["knowledge_operation"] == "select_topic_scope"
    assert result.metadata["topic_scope"] == "professional-intelligence"
    assert result.metadata["artifacts"][0]["artifact_kind"] == "TopicScopeReceipt"


def test_slash_topics_membrane_requires_policy_decision():
    adapter = SlashTopicsAdapter(InMemorySlashTopicsBackend())

    result = adapter.handle(
        make_event("topic_membrane", "slash-topics", {"topic_scope": "restricted"})
    )

    assert result.ok is False
    assert result.metadata["fail_closed"] is True
    assert result.metadata["deny_reason"] == "missing_policy_decision"


def test_memory_mesh_recall_requires_policy_decision():
    adapter = MemoryMeshAdapter(InMemoryMemoryMeshBackend())

    result = adapter.handle(make_event("memory_recall", "memory-mesh", {"query": "workroom"}))

    assert result.ok is False
    assert result.metadata["deny_reason"] == "missing_policy_decision"


def test_memory_mesh_recall_preserves_context_metadata():
    adapter = MemoryMeshAdapter(InMemoryMemoryMeshBackend())

    result = adapter.handle(
        make_event(
            "memory_recall",
            "memory-mesh",
            {
                "query": "workroom context",
                "policy_decision_ref": "decision-memory",
                "agent_id": "agent.claude-code",
                "workroom": "pi-demo",
                "topic_scope": "professional-intelligence",
                "matrix_room_id": "!room:example.org",
            },
        )
    )

    assert result.ok is True
    assert result.metadata["knowledge_operation"] == "recall_context"
    assert result.metadata["policy_decision_ref"] == "decision-memory"
    assert result.metadata["agent_id"] == "agent.claude-code"
    assert result.metadata["artifacts"][0]["artifact_kind"] == "ContextPack"


def test_new_hope_normalizes_thread_without_redefining_downstream_planes():
    adapter = NewHopeAdapter(InMemoryNewHopeBackend())

    result = adapter.handle(
        make_event("semantic_thread", "new-hope", {"semantic_ref": "$matrix-thread-root"})
    )

    assert result.ok is True
    assert result.source == "new-hope"
    assert result.metadata["knowledge_operation"] == "normalize_thread"
    assert result.metadata["artifacts"][0]["artifact_kind"] == "SemanticThread"


def test_new_hope_claim_extraction_requires_policy_decision():
    adapter = NewHopeAdapter(InMemoryNewHopeBackend())

    result = adapter.handle(make_event("claim", "new-hope", {"semantic_ref": "$thread"}))

    assert result.ok is False
    assert result.metadata["deny_reason"] == "missing_policy_decision"


def test_sherlock_search_packet_requires_policy_decision():
    adapter = SherlockSearchAdapter(InMemorySherlockSearchBackend())

    result = adapter.handle(make_event("search_packet", "sherlock-search", {"query": "evidence"}))

    assert result.ok is False
    assert result.metadata["deny_reason"] == "missing_policy_decision"


def test_sherlock_search_packet_emits_packet_reference():
    adapter = SherlockSearchAdapter(InMemorySherlockSearchBackend())

    result = adapter.handle(
        make_event(
            "search_packet",
            "sherlock-search",
            {
                "query": "evidence gap",
                "policy_decision_ref": "decision-search",
                "workroom": "pi-demo",
                "topic_scope": "professional-intelligence",
            },
        )
    )

    assert result.ok is True
    assert result.metadata["knowledge_operation"] == "create_search_packet"
    assert result.metadata["policy_decision_ref"] == "decision-search"
    assert result.metadata["workroom"] == "pi-demo"
    assert result.metadata["artifacts"][0]["artifact_kind"] == "SearchPacket"


def test_holmes_investigation_requires_policy_and_stays_correlation_only():
    adapter = HolmesAdapter(InMemoryHolmesBackend())

    denied = adapter.handle(make_event("investigation", "holmes", {"request": "investigate"}))
    admitted = adapter.handle(
        make_event(
            "investigation",
            "holmes",
            {"request": "investigate evidence gap", "policy_decision_ref": "decision-holmes"},
        )
    )

    assert denied.ok is False
    assert denied.metadata["deny_reason"] == "missing_policy_decision"
    assert admitted.ok is True
    assert admitted.metadata["knowledge_plane"] == "holmes"
    assert admitted.metadata["boundary"] == "correlation-only"
    assert admitted.metadata["artifacts"][0]["artifact_kind"] == "HolmesCasefileRef"


def test_holmes_artifact_correlation_does_not_define_holmes_behavior():
    adapter = HolmesAdapter(InMemoryHolmesBackend())

    result = adapter.handle(
        make_event("correlation", "holmes", {"artifact_ref": "holmes://casefiles/pi-demo"})
    )

    assert result.ok is True
    assert result.metadata["knowledge_operation"] == "correlate_artifact"
    assert result.metadata["boundary"] == "correlation-only"


def test_meshrush_graph_view_requires_policy_decision():
    adapter = MeshRushAdapter(InMemoryMeshRushBackend())

    result = adapter.handle(make_event("graph_view", "meshrush", {"graph_ref": "world-model"}))

    assert result.ok is False
    assert result.metadata["deny_reason"] == "missing_policy_decision"


def test_meshrush_graph_artifact_preserves_policy_and_artifact_refs():
    adapter = MeshRushAdapter(InMemoryMeshRushBackend())

    result = adapter.handle(
        make_event(
            "graph_artifact",
            "meshrush",
            {
                "graph_ref": "professional intelligence graph",
                "policy_decision_ref": "decision-graph",
                "topic_scope": "professional-intelligence",
            },
        )
    )

    assert result.ok is True
    assert result.metadata["knowledge_operation"] == "crystallize_artifact"
    assert result.metadata["policy_decision_ref"] == "decision-graph"
    assert result.metadata["artifacts"][0]["artifact_kind"] == "GraphArtifact"
