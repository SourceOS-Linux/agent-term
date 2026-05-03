import json

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


def test_dispatch_cli_matrix_service_send_is_policy_gated_and_persisted(tmp_path, capsys):
    db_path = tmp_path / "events.sqlite3"

    exit_code = main(
        [
            "matrix-service",
            "matrix_service_send",
            "!room:example.org",
            "Hello Matrix",
            "--db",
            str(db_path),
            "--policy-action",
            "matrix-service.matrix_service_send",
            "--allow-policy",
            "matrix-service.matrix_service_send",
            "--metadata-json",
            '{"txn_id":"txn-1"}',
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "dispatch_status=ok" in captured.out
    assert "adapter=matrix-service" in captured.out

    store = EventStore(db_path)
    try:
        events = store.tail(limit=10)
    finally:
        store.close()
    assert [event.source for event in events] == [
        "matrix-service",
        "policy-fabric",
        "matrix-service",
    ]
    assert events[-1].metadata["matrix_service_status"] == "sent"
    assert events[-1].metadata["matrix_event_id"] == "$local-1"


def test_dispatch_cli_uses_config_event_store_and_local_runtime_fixtures(tmp_path, capsys):
    db_path = tmp_path / "configured-events.sqlite3"
    config_path = tmp_path / "agent-term.json"
    config_path.write_text(
        json.dumps(
            {
                "eventStore": {"driver": "sqlite", "path": str(db_path)},
                "participants": {
                    "github": {
                        "enabled": True,
                        "agentRegistryId": "agent.github",
                        "requireAgentRegistryResolution": True,
                    }
                },
                "localRuntime": {
                    "registeredAgents": ["agent.github"],
                    "toolGrants": ["agent.github:repo-write:grant.repo-write"],
                    "allowPolicies": ["github.pr.create"],
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "github",
            "github_mutation",
            "!github",
            "Create PR",
            "--config",
            str(config_path),
            "--tool",
            "repo-write",
            "--policy-action",
            "github.pr.create",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "dispatch_status=ok" in captured.out
    assert db_path.exists()

    store = EventStore(db_path)
    try:
        events = store.tail(limit=10)
    finally:
        store.close()
    assert events[0].metadata["agent_id"] == "agent.github"
    assert events[-1].metadata["grant_id"] == "grant.repo-write"
    assert events[-1].metadata["policy_decision_id"] == "decision.allow.github.pr.create"


def test_dispatch_cli_uses_file_backed_agent_registry(tmp_path, capsys):
    db_path = tmp_path / "configured-events.sqlite3"
    fixture_path = tmp_path / "agent-registry.json"
    fixture_path.write_text(
        json.dumps(
            {
                "agents": [
                    {
                        "agent_id": "agent.github",
                        "registry_ref": "fixture://agent.github",
                        "spec_version": "v1",
                        "session_id": "session-github",
                    }
                ],
                "tool_grants": [
                    {
                        "grant_id": "grant.repo-write",
                        "agent_id": "agent.github",
                        "tool": "repo-write",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "agent-term.json"
    config_path.write_text(
        json.dumps(
            {
                "eventStore": {"driver": "sqlite", "path": str(db_path)},
                "agentRegistration": {"fixturePath": str(fixture_path)},
                "participants": {"github": {"agentRegistryId": "agent.github"}},
                "localRuntime": {"allowPolicies": ["github.pr.create"]},
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "github",
            "github_mutation",
            "!github",
            "Create PR",
            "--config",
            str(config_path),
            "--tool",
            "repo-write",
            "--policy-action",
            "github.pr.create",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "dispatch_status=ok" in captured.out

    store = EventStore(db_path)
    try:
        events = store.tail(limit=10)
    finally:
        store.close()
    assert events[1].metadata["agent_registry_ref"] == "fixture://agent.github"
    assert events[-1].metadata["grant_id"] == "grant.repo-write"
    assert events[-1].metadata["session_id"] == "session-github"


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
    assert "adapter=registered-participant" in captured.out

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
