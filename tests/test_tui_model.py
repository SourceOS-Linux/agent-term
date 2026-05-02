from agent_term.events import AgentTermEvent
from agent_term.tui_model import TuiSnapshotBuilder, classify_event, status_for_event


def event(
    source: str,
    kind: str,
    body: str = "body",
    metadata: dict[str, object] | None = None,
    thread_id: str | None = None,
) -> AgentTermEvent:
    return AgentTermEvent(
        channel=f"!{source}",
        sender="@operator",
        kind=kind,
        source=source,
        body=body,
        thread_id=thread_id,
        metadata=metadata or {},
    )


def test_classifies_sourceos_control_panes():
    assert classify_event(event("agent-registry", "agent_identity")) == "agents"
    assert classify_event(event("policy-fabric", "decision")) == "approvals"
    assert classify_event(event("prophet-workspace", "workroom")) == "workrooms"
    assert classify_event(event("slash-topics", "topic_scope")) == "topics"
    assert classify_event(event("memory-mesh", "memory_recall")) == "context"
    assert classify_event(event("new-hope", "semantic_thread")) == "semantic"
    assert classify_event(event("holmes", "investigation")) == "investigations"
    assert classify_event(event("sherlock-search", "search_packet")) == "investigations"
    assert classify_event(event("meshrush", "graph_view")) == "graphs"
    assert classify_event(event("cloudshell-fog", "shell_session")) == "shells"
    assert classify_event(event("agentplane", "run")) == "runs"


def test_status_for_event_surfaces_operator_risk_states():
    assert status_for_event(event("policy-fabric", "decision", metadata={"deny_reason": "no"})) == "denied"
    assert status_for_event(event("agent-registry", "agent_identity", metadata={"revoked": True})) == "revoked"
    assert status_for_event(event("memory-mesh", "memory_recall", metadata={"approval_required": True})) == "pending"
    assert status_for_event(event("matrix", "matrix_emit", metadata={"matrix_sensitive_context_allowed": False})) == "blocked"
    assert status_for_event(event("codex", "agent_message", metadata={"dispatch_status": "invoked"})) == "active"


def test_snapshot_builds_rooms_threads_and_domain_panes():
    events = [
        event(
            "matrix",
            "matrix_room_event",
            "Matrix message",
            metadata={"matrix_room_alias": "#sourceos-ops:example.org"},
            thread_id="$root",
        ),
        event(
            "agent-registry",
            "agent_identity",
            "Resolve agent.codex",
            metadata={"agent_id": "agent.codex", "session_id": "session-1"},
        ),
        event(
            "policy-fabric",
            "decision",
            "Denied memory recall",
            metadata={"deny_reason": "no_policy_decision"},
        ),
        event(
            "prophet-workspace",
            "workroom",
            "Bind workroom",
            metadata={"workroom": "pi-demo"},
        ),
        event(
            "agentplane",
            "run",
            "Run complete",
            metadata={"agentplane_status": "completed", "artifacts": [{"artifact_kind": "RunArtifact"}]},
        ),
    ]

    snapshot = TuiSnapshotBuilder().build(events)

    assert snapshot.pane("rooms").lines[0].text == "#sourceos-ops:example.org"
    assert snapshot.pane("threads").lines[0].text == "$root in !matrix"
    assert snapshot.pane("agents").lines[0].text == "(agent.codex) Resolve agent.codex"
    assert snapshot.pane("approvals").lines[0].status == "denied"
    assert snapshot.pane("workrooms").lines[0].text == "(pi-demo) Bind workroom"
    assert snapshot.pane("runs").lines[0].status == "active"


def test_snapshot_render_text_is_operator_readable():
    snapshot = TuiSnapshotBuilder().build(
        [event("cloudshell-fog", "shell_session", "Shell ready", metadata={"cloudshell_status": "running"})]
    )

    rendered = snapshot.render_text()

    assert "[cloudshell-fog]" in rendered
    assert "ACTIVE: Shell ready" in rendered
    assert "[Matrix Rooms / Channels]" in rendered
