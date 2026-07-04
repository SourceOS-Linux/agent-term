import json

from agent_term.dispatch_cli import main
from agent_term.store import EventStore


def test_dispatch_cli_uses_file_backed_policy_fabric(tmp_path, capsys):
    db_path = tmp_path / "configured-events.sqlite3"
    fixture_path = tmp_path / "policy-fabric.json"
    fixture_path.write_text(
        json.dumps(
            {
                "decisions": [
                    {
                        "decision_id": "decision.allow.memory",
                        "action": "memory-mesh.memory_recall",
                        "status": "allow",
                        "policy_ref": "fixture://policy/memory",
                        "obligations": ["record-audit"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "agent-term.json"
    config_path.write_text(
        json.dumps(
            {
                "eventStore": {"driver": "sqlite", "path": str(db_path)},
                "policyFabric": {"fixturePath": str(fixture_path)},
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "memory-mesh",
            "memory_recall",
            "!memory-mesh",
            "Recall workroom context",
            "--config",
            str(config_path),
            "--metadata-json",
            '{"query":"workroom context","policy_action":"memory-mesh.memory_recall"}',
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
    assert events[1].source == "policy-fabric"
    assert events[1].metadata["policy_decision_id"] == "decision.allow.memory"
    assert events[1].metadata["policy_obligations"] == ["record-audit"]
    assert events[-1].metadata["policy_decision_ref"] == "decision.allow.memory"


def test_dispatch_cli_blocks_file_backed_policy_denial(tmp_path, capsys):
    db_path = tmp_path / "configured-events.sqlite3"
    fixture_path = tmp_path / "policy-fabric.json"
    fixture_path.write_text(
        json.dumps(
            {
                "decisions": [
                    {
                        "decision_id": "decision.deny.memory",
                        "action": "memory-mesh.memory_recall",
                        "status": "deny",
                        "policy_ref": "fixture://policy/memory",
                        "reason": "memory recall denied",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "agent-term.json"
    config_path.write_text(
        json.dumps(
            {
                "eventStore": {"driver": "sqlite", "path": str(db_path)},
                "policyFabric": {"fixturePath": str(fixture_path)},
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "memory-mesh",
            "memory_recall",
            "!memory-mesh",
            "Recall workroom context",
            "--config",
            str(config_path),
            "--metadata-json",
            '{"query":"workroom context","policy_action":"memory-mesh.memory_recall"}',
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "dispatch_status=blocked" in captured.out
    assert "blocked_reason=memory recall denied" in captured.out

    store = EventStore(db_path)
    try:
        events = store.tail(limit=10)
    finally:
        store.close()
    assert events[-1].metadata["policy_decision_id"] == "decision.deny.memory"
    assert events[-1].metadata["deny_reason"] == "memory recall denied"
