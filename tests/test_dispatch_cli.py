from agent_term.dispatch_cli import main
from agent_term.store import EventStore


def test_dispatch_cli_success_persists_events_and_snapshot(tmp_path, capsys):
    db_path = tmp_path / "events.sqlite3"

    exit_code = main(
        [
            "memory-mesh",
            "memory_recall",
            "!memory-mesh",
            "Recall workroom context",
            "--db",
            str(db_path),
            "--metadata-json",
            '{"query":"workroom context","policy_action":"memory-mesh.memory_recall"}',
            "--allow-policy",
            "memory-mesh.memory_recall",
            "--show-snapshot",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "dispatch_status=ok" in captured.out
    assert "adapter=memory-mesh" in captured.out
    assert "persisted_events=3" in captured.out
    assert "[Memory / Context]" in captured.out
    assert "Recall workroom context" in captured.out

    store = EventStore(db_path)
    try:
        events = store.tail(limit=10)
    finally:
        store.close()
    assert [event.source for event in events] == ["memory-mesh", "policy-fabric", "memory-mesh"]


def test_dispatch_cli_blocks_unknown_agent(tmp_path, capsys):
    db_path = tmp_path / "events.sqlite3"

    exit_code = main(["codex", "agent_message", "!codex", "Do work", "--db", str(db_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "dispatch_status=blocked" in captured.out
    assert "blocked_reason=unknown_agent" in captured.out

    store = EventStore(db_path)
    try:
        events = store.tail(limit=10)
    finally:
        store.close()
    assert events[-1].source == "agent-registry"
    assert events[-1].metadata["deny_reason"] == "unknown_agent"


def test_dispatch_cli_registered_agent_with_policy_and_grant_invokes(tmp_path, capsys):
    db_path = tmp_path / "events.sqlite3"

    exit_code = main(
        [
            "github",
            "github_mutation",
            "!github",
            "Create PR",
            "--db",
            str(db_path),
            "--agent-id",
            "agent.github",
            "--register-agent",
            "agent.github",
            "--tool",
            "repo-write",
            "--grant",
            "agent.github:repo-write:grant.repo-write",
            "--policy-action",
            "github.pr.create",
            "--allow-policy",
            "github.pr.create",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "dispatch_status=ok" in captured.out
    assert "adapter=github" in captured.out

    store = EventStore(db_path)
    try:
        events = store.tail(limit=10)
    finally:
        store.close()
    assert [event.source for event in events] == [
        "github",
        "agent-registry",
        "agent-registry",
        "policy-fabric",
        "github",
    ]
    assert events[-1].metadata["dispatch_status"] == "invoked"
    assert events[-1].metadata["grant_id"] == "grant.repo-write"


def test_dispatch_cli_blocks_unverified_encrypted_sensitive_context(tmp_path, capsys):
    db_path = tmp_path / "events.sqlite3"

    exit_code = main(
        [
            "memory-mesh",
            "memory_recall",
            "!memory-mesh",
            "Recall workroom context",
            "--db",
            str(db_path),
            "--metadata-json",
            '{"query":"workroom context"}',
            "--sensitive-context",
            "--matrix-encrypted",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "dispatch_status=blocked" in captured.out
    assert "blocked_reason=matrix_posture_blocked" in captured.out

    store = EventStore(db_path)
    try:
        events = store.tail(limit=10)
    finally:
        store.close()
    assert events[-1].source == "matrix"
    assert events[-1].metadata["matrix_status"] == "blocked"
