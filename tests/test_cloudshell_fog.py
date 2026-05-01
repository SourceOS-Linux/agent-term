from agent_term.cloudshell_fog import CloudShellFogAdapter, InMemoryCloudShellFogBackend
from agent_term.events import AgentTermEvent


def make_event(kind: str, metadata: dict[str, object] | None = None) -> AgentTermEvent:
    return AgentTermEvent(
        channel="!cloudshell-fog",
        sender="@operator",
        kind=kind,
        source="cloudshell-fog",
        body="cloudshell test event",
        thread_id="thread-1",
        metadata=metadata or {},
    )


def test_shell_session_requires_policy_decision():
    adapter = CloudShellFogAdapter(InMemoryCloudShellFogBackend())

    result = adapter.handle(make_event("shell_session", {"profile": "default"}))

    assert result.ok is False
    assert result.metadata["fail_closed"] is True
    assert result.metadata["deny_reason"] == "missing_policy_decision"


def test_shell_session_request_preserves_governed_metadata():
    adapter = CloudShellFogAdapter(InMemoryCloudShellFogBackend())
    event = make_event(
        "shell_session",
        {
            "profile": "default",
            "ttl_seconds": 1800,
            "placement_hint": "fog-first",
            "policy_decision_id": "decision-shell-1",
            "agent_id": "agent.codex",
            "workroom": "pi-demo",
            "topic_scope": "professional-intelligence",
            "matrix_room_id": "!room:example.org",
        },
    )

    result = adapter.handle(event)

    assert result.ok is True
    assert result.kind == "shell_session"
    assert result.metadata["cloudshell_status"] == "running"
    assert result.metadata["cloudshell_session_id"] == "shell-1"
    assert result.metadata["cloudshell_attach_ref"] == "cloudshell-fog://sessions/shell-1/pty"
    assert result.metadata["policy_decision_ref"] == "decision-shell-1"
    assert result.metadata["agent_id"] == "agent.codex"
    assert result.metadata["workroom"] == "pi-demo"


def test_attach_requires_policy_decision():
    adapter = CloudShellFogAdapter(InMemoryCloudShellFogBackend())

    result = adapter.handle(make_event("shell_attach", {"cloudshell_session_id": "shell-1"}))

    assert result.ok is False
    assert result.metadata["deny_reason"] == "missing_policy_decision"


def test_attach_prepares_known_session():
    backend = InMemoryCloudShellFogBackend()
    adapter = CloudShellFogAdapter(backend)
    created = adapter.handle(
        make_event(
            "shell_session",
            {"profile": "default", "policy_decision_ref": "decision-shell-create"},
        )
    )

    result = adapter.handle(
        make_event(
            "shell_attach",
            {
                "cloudshell_session_id": created.metadata["cloudshell_session_id"],
                "policy_decision_ref": "decision-shell-attach",
            },
        )
    )

    assert result.ok is True
    assert result.kind == "shell_attach"
    assert result.metadata["cloudshell_status"] == "running"
    assert result.metadata["policy_decision_ref"] == "decision-shell-attach"


def test_attach_unknown_session_fails_closed():
    adapter = CloudShellFogAdapter(InMemoryCloudShellFogBackend())

    result = adapter.handle(
        make_event(
            "shell_attach",
            {
                "cloudshell_session_id": "shell-missing",
                "policy_decision_ref": "decision-shell-attach",
            },
        )
    )

    assert result.ok is False
    assert result.metadata["fail_closed"] is True
    assert result.metadata["deny_reason"] == "unknown_session"
    assert result.metadata["cloudshell_session_id"] == "shell-missing"
