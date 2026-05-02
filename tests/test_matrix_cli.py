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
