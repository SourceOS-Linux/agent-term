import json

from agent_term.matrix_cli import main
from agent_term.store import EventStore


def test_matrix_cli_send_dispatches_policy_admitted_message(tmp_path, capsys):
    db_path = tmp_path / "events.sqlite3"

    exit_code = main(
        [
            "--db",
            str(db_path),
            "send",
            "!room:example.org",
            "Hello Matrix",
            "--allow-policy",
            "matrix-service.matrix_service_send",
            "--txn-id",
            "txn-1",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "matrix_send_status=ok" in captured.out
    assert "matrix_room_id=!room:example.org" in captured.out
    assert "persisted_events=3" in captured.out

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
    assert events[-1].metadata["matrix_send_status"] == "sent"
    assert events[-1].metadata["matrix_event_id"] == "$local-1"


def test_matrix_cli_send_resolves_room_from_config(tmp_path, capsys):
    db_path = tmp_path / "events.sqlite3"
    config_path = tmp_path / "agent-term.json"
    config_path.write_text(
        json.dumps(
            {
                "eventStore": {"driver": "sqlite", "path": str(db_path)},
                "matrix": {"rooms": {"sourceosOps": "!sourceos-ops:example.org"}},
                "localRuntime": {"allowPolicies": ["matrix-service.matrix_service_send"]},
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["--config", str(config_path), "send", "sourceosOps", "Hello"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "matrix_room_id=!sourceos-ops:example.org" in captured.out

    store = EventStore(db_path)
    try:
        events = store.tail(limit=10)
    finally:
        store.close()
    assert events[0].channel == "!sourceos-ops:example.org"
    assert events[0].metadata["matrix_room_alias"] == "sourceosOps"


def test_matrix_cli_send_blocks_unverified_encrypted_sensitive_context(tmp_path, capsys):
    db_path = tmp_path / "events.sqlite3"

    exit_code = main(
        [
            "--db",
            str(db_path),
            "send",
            "!room:example.org",
            "Sensitive Matrix",
            "--sensitive-context",
            "--matrix-encrypted",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "matrix_send_status=blocked" in captured.out
    assert "blocked_reason=matrix_posture_blocked" in captured.out

    store = EventStore(db_path)
    try:
        events = store.tail(limit=10)
    finally:
        store.close()
    assert events[-1].source == "matrix"
    assert events[-1].metadata["matrix_status"] == "blocked"


def test_matrix_cli_normalize_sync_prints_events(tmp_path, capsys):
    payload_path = tmp_path / "sync.json"
    payload_path.write_text(
        json.dumps(
            {
                "next_batch": "batch-2",
                "rooms": {
                    "join": {
                        "!room:example.org": {
                            "timeline": {
                                "events": [
                                    {
                                        "event_id": "$event1",
                                        "sender": "@operator:example.org",
                                        "type": "m.room.message",
                                        "content": {"body": "hello"},
                                    }
                                ]
                            }
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["normalize-sync", str(payload_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "matrix_sync_events=1" in captured.out
    assert "matrix_next_batch=batch-2" in captured.out
    assert "!room:example.org\t@operator:example.org\tmatrix_room_event\thello" in captured.out


def test_matrix_cli_normalize_sync_persists_events(tmp_path, capsys):
    db_path = tmp_path / "events.sqlite3"
    payload_path = tmp_path / "sync.json"
    payload_path.write_text(
        json.dumps(
            {
                "rooms": {
                    "join": {
                        "!room:example.org": {
                            "timeline": {
                                "events": [
                                    {
                                        "event_id": "$member",
                                        "sender": "@user:example.org",
                                        "type": "m.room.member",
                                        "content": {"membership": "join"},
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["--db", str(db_path), "normalize-sync", str(payload_path), "--persist"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "persisted_events=1" in captured.out

    store = EventStore(db_path)
    try:
        events = store.tail(limit=10)
    finally:
        store.close()
    assert len(events) == 1
    assert events[0].kind == "matrix_membership"
    assert events[0].metadata["matrix_membership"] == "join"


def test_matrix_cli_normalize_sync_saves_state(tmp_path, capsys):
    db_path = tmp_path / "events.sqlite3"
    state_path = tmp_path / "matrix-state.json"
    payload_path = tmp_path / "sync.json"
    payload_path.write_text(
        json.dumps(
            {
                "next_batch": "batch-3",
                "rooms": {
                    "join": {
                        "!room:example.org": {
                            "timeline": {
                                "events": [
                                    {
                                        "event_id": "$event1",
                                        "sender": "@operator:example.org",
                                        "type": "m.room.message",
                                        "content": {"body": "hello"},
                                    }
                                ]
                            }
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--db",
            str(db_path),
            "--state",
            str(state_path),
            "normalize-sync",
            str(payload_path),
            "--save-state",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "matrix_state_next_batch=batch-3" in captured.out
    assert "matrix_state_rooms=1" in captured.out
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["next_batch"] == "batch-3"
    assert state["rooms"] == {"!room:example.org": "!room:example.org"}


def test_matrix_cli_state_prints_state(tmp_path, capsys):
    state_path = tmp_path / "matrix-state.json"
    state_path.write_text(
        json.dumps({"next_batch": "batch-4", "rooms": {"sourceosOps": "!room"}}),
        encoding="utf-8",
    )

    exit_code = main(["--state", str(state_path), "state"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "matrix_state_next_batch=batch-4" in captured.out
    assert "matrix_state_rooms=1" in captured.out
    assert "sourceosOps\t!room" in captured.out
