from agent_term.events import AgentTermEvent
from agent_term.workspace import (
    InMemoryProphetWorkspaceBackend,
    InMemorySociosphereBackend,
    ProphetWorkspaceAdapter,
    SociosphereAdapter,
)


def make_event(
    kind: str,
    source: str,
    metadata: dict[str, object] | None = None,
) -> AgentTermEvent:
    return AgentTermEvent(
        channel=f"!{source}",
        sender="@operator",
        kind=kind,
        source=source,
        body="workspace test event",
        thread_id="thread-1",
        metadata=metadata or {},
    )


def test_sociosphere_resolves_workspace_manifest_and_topology_refs():
    adapter = SociosphereAdapter(InMemorySociosphereBackend())

    result = adapter.handle(
        make_event("workspace_manifest", "sociosphere", {"workspace_ref": "sourceos"})
    )

    assert result.ok is True
    assert result.source == "sociosphere"
    assert result.metadata["workspace_status"] == "resolved"
    assert result.metadata["manifest_ref"] == "sociosphere://sourceos/manifest/workspace.toml"
    assert result.metadata["lock_ref"] == "sociosphere://sourceos/manifest/workspace.lock.json"
    assert result.metadata["topology_ref"] == "sociosphere://sourceos/docs/TOPOLOGY.md"


def test_sociosphere_topology_validation_emits_validation_reference():
    adapter = SociosphereAdapter(InMemorySociosphereBackend())

    result = adapter.handle(
        make_event("topology_validation", "sociosphere", {"workspace_ref": "sourceos"})
    )

    assert result.ok is True
    assert result.metadata["workspace_status"] == "validated"
    assert result.metadata["validation_ref"] == "sociosphere://sourceos/validation/topology.json"


def test_sociosphere_materialization_requires_policy_decision():
    adapter = SociosphereAdapter(InMemorySociosphereBackend())

    result = adapter.handle(
        make_event("workspace_materialization", "sociosphere", {"workspace_ref": "sourceos"})
    )

    assert result.ok is False
    assert result.metadata["fail_closed"] is True
    assert result.metadata["deny_reason"] == "missing_policy_decision"


def test_sociosphere_materialization_preserves_policy_agent_and_topic_metadata():
    adapter = SociosphereAdapter(InMemorySociosphereBackend())

    result = adapter.handle(
        make_event(
            "workspace_materialization",
            "sociosphere",
            {
                "workspace_ref": "sourceos",
                "policy_decision_ref": "decision-materialize-1",
                "agent_id": "agent.codex",
                "matrix_room_id": "!room:example.org",
                "topic_scope": "professional-intelligence",
            },
        )
    )

    assert result.ok is True
    assert result.metadata["workspace_status"] == "materialized"
    assert result.metadata["policy_decision_ref"] == "decision-materialize-1"
    assert result.metadata["agent_id"] == "agent.codex"
    assert result.metadata["topic_scope"] == "professional-intelligence"
    assert result.metadata["materialization_ref"] == "sociosphere://sourceos/materializations/latest"


def test_prophet_workspace_binds_workroom_to_matrix_and_topic():
    adapter = ProphetWorkspaceAdapter(InMemoryProphetWorkspaceBackend())

    result = adapter.handle(
        make_event(
            "workroom",
            "prophet-workspace",
            {
                "workroom": "pi-demo",
                "matrix_room_id": "!room:example.org",
                "topic_scope": "professional-intelligence",
            },
        )
    )

    assert result.ok is True
    assert result.source == "prophet-workspace"
    assert result.metadata["workroom"] == "pi-demo"
    assert result.metadata["workroom_status"] == "bound"
    assert result.metadata["matrix_room_id"] == "!room:example.org"
    assert result.metadata["topic_scope"] == "professional-intelligence"
    assert result.metadata["workspace_audit_ref"] == "prophet-workspace://workrooms/pi-demo/audit"


def test_prophet_workspace_context_hydration_requires_policy_decision():
    adapter = ProphetWorkspaceAdapter(InMemoryProphetWorkspaceBackend())

    result = adapter.handle(
        make_event("context_pack", "prophet-workspace", {"workroom": "pi-demo"})
    )

    assert result.ok is False
    assert result.metadata["fail_closed"] is True
    assert result.metadata["deny_reason"] == "missing_policy_decision"


def test_prophet_workspace_context_hydration_requires_known_workroom():
    adapter = ProphetWorkspaceAdapter(InMemoryProphetWorkspaceBackend())

    result = adapter.handle(
        make_event(
            "context_pack",
            "prophet-workspace",
            {"workroom": "missing", "policy_decision_ref": "decision-context"},
        )
    )

    assert result.ok is False
    assert result.metadata["deny_reason"] == "unknown_workroom"


def test_prophet_workspace_context_hydration_preserves_policy_and_context_pack_ref():
    backend = InMemoryProphetWorkspaceBackend()
    adapter = ProphetWorkspaceAdapter(backend)
    adapter.handle(
        make_event(
            "workroom",
            "prophet-workspace",
            {
                "workroom": "pi-demo",
                "matrix_room_id": "!room:example.org",
                "topic_scope": "professional-intelligence",
            },
        )
    )

    result = adapter.handle(
        make_event(
            "context_pack",
            "prophet-workspace",
            {
                "workroom": "pi-demo",
                "policy_decision_ref": "decision-context",
                "agent_id": "agent.claude-code",
            },
        )
    )

    assert result.ok is True
    assert result.metadata["policy_decision_ref"] == "decision-context"
    assert result.metadata["agent_id"] == "agent.claude-code"
    assert result.metadata["workroom_status"] == "context_hydrated"
    assert result.metadata["context_pack_ref"] == (
        "prophet-workspace://workrooms/pi-demo/context-pack/latest"
    )
