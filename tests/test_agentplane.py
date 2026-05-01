from agent_term.agentplane import AgentPlaneAdapter, InMemoryAgentPlaneBackend
from agent_term.events import AgentTermEvent


def make_event(kind: str, metadata: dict[str, object] | None = None) -> AgentTermEvent:
    return AgentTermEvent(
        channel="!agentplane",
        sender="@operator",
        kind=kind,
        source="agentplane",
        body="agentplane test event",
        thread_id="thread-1",
        metadata=metadata or {},
    )


def test_validation_requires_bundle_ref():
    adapter = AgentPlaneAdapter(InMemoryAgentPlaneBackend())

    result = adapter.handle(make_event("validation"))

    assert result.ok is False
    assert result.metadata["fail_closed"] is True
    assert result.metadata["deny_reason"] == "missing_bundle_ref"


def test_validation_emits_validation_artifact_reference():
    adapter = AgentPlaneAdapter(InMemoryAgentPlaneBackend())

    result = adapter.handle(make_event("validation", {"bundle_ref": "bundles/example-agent"}))

    assert result.ok is True
    assert result.kind == "validate"
    assert result.metadata["agentplane_status"] == "valid"
    assert result.metadata["bundle_ref"] == "bundles/example-agent"
    assert result.metadata["artifacts"][0]["artifact_kind"] == "ValidationArtifact"


def test_placement_emits_placement_decision_reference():
    adapter = AgentPlaneAdapter(InMemoryAgentPlaneBackend())

    result = adapter.handle(make_event("placement", {"bundle_ref": "bundles/example-agent"}))

    assert result.ok is True
    assert result.kind == "place"
    assert result.metadata["agentplane_status"] == "placed"
    assert result.metadata["executor_ref"] == "executor.local"
    assert result.metadata["artifacts"][0]["artifact_kind"] == "PlacementDecision"


def test_run_requires_policy_decision():
    adapter = AgentPlaneAdapter(InMemoryAgentPlaneBackend())

    result = adapter.handle(make_event("run", {"bundle_ref": "bundles/example-agent"}))

    assert result.ok is False
    assert result.metadata["fail_closed"] is True
    assert result.metadata["deny_reason"] == "missing_policy_decision"


def test_run_preserves_policy_agent_workroom_topic_and_artifacts():
    adapter = AgentPlaneAdapter(InMemoryAgentPlaneBackend())
    event = make_event(
        "run",
        {
            "bundle_ref": "bundles/example-agent",
            "policy_decision_ref": "decision-run-1",
            "executor_ref": "executor.fog-1",
            "agent_id": "agent.codex",
            "workroom": "pi-demo",
            "topic_scope": "professional-intelligence",
            "matrix_room_id": "!room:example.org",
        },
    )

    result = adapter.handle(event)

    assert result.ok is True
    assert result.kind == "run"
    assert result.metadata["policy_decision_ref"] == "decision-run-1"
    assert result.metadata["agent_id"] == "agent.codex"
    assert result.metadata["workroom"] == "pi-demo"
    assert result.metadata["topic_scope"] == "professional-intelligence"
    assert result.metadata["executor_ref"] == "executor.fog-1"
    assert {artifact["artifact_kind"] for artifact in result.metadata["artifacts"]} == {
        "RunArtifact",
        "ReplayArtifact",
    }


def test_replay_requires_policy_decision():
    adapter = AgentPlaneAdapter(InMemoryAgentPlaneBackend())

    result = adapter.handle(make_event("replay", {"run_id": "run-1"}))

    assert result.ok is False
    assert result.metadata["deny_reason"] == "missing_policy_decision"


def test_replay_unknown_run_fails_closed():
    adapter = AgentPlaneAdapter(InMemoryAgentPlaneBackend())

    result = adapter.handle(
        make_event("replay", {"run_id": "run-missing", "policy_decision_ref": "decision-replay"})
    )

    assert result.ok is False
    assert result.metadata["fail_closed"] is True
    assert result.metadata["deny_reason"] == "unknown_run"
    assert result.metadata["run_id"] == "run-missing"


def test_replay_known_run_preserves_artifacts():
    backend = InMemoryAgentPlaneBackend()
    adapter = AgentPlaneAdapter(backend)
    run_result = adapter.handle(
        make_event(
            "run",
            {"bundle_ref": "bundles/example-agent", "policy_decision_ref": "decision-run"},
        )
    )

    replay_result = adapter.handle(
        make_event(
            "replay",
            {
                "run_id": run_result.metadata["run_id"],
                "policy_decision_ref": "decision-replay",
            },
        )
    )

    assert replay_result.ok is True
    assert replay_result.kind == "replay"
    assert replay_result.metadata["policy_decision_ref"] == "decision-replay"
    assert replay_result.metadata["artifacts"] == run_result.metadata["artifacts"]
