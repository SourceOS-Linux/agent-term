import pytest

from agent_term.config import config_from_dict
from agent_term.events import AgentTermEvent
from agent_term.matrix_service import (
    InMemoryMatrixServiceBackend,
    MatrixSendRequest,
    MatrixServiceAdapter,
    MatrixServiceConfigError,
    MatrixSyncRequest,
    NioMatrixServiceBackend,
    build_matrix_service_backend,
    normalize_sync_payload,
)


def test_matrix_send_request_content_preserves_thread_root():
    request = MatrixSendRequest(
        room_id="!room:example.org",
        body="hello",
        thread_root_event_id="$root",
    )

    assert request.content() == {
        "msgtype": "m.text",
        "body": "hello",
        "m.relates_to": {"rel_type": "m.thread", "event_id": "$root"},
    }


def test_in_memory_matrix_backend_sends_text():
    backend = InMemoryMatrixServiceBackend()
    request = MatrixSendRequest(room_id="!room:example.org", body="hello", txn_id="txn-1")

    result = backend.send_text(request)

    assert result.ok is True
    assert result.room_id == "!room:example.org"
    assert result.event_id == "$local-1"
    assert result.metadata["txn_id"] == "txn-1"
    assert backend.sent == [request]


def test_in_memory_matrix_backend_incremental_sync_uses_since_token():
    backend = InMemoryMatrixServiceBackend(
        sync_payloads=[
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
        ]
    )

    batch = backend.sync(MatrixSyncRequest(since="batch-1", timeout_ms=1000))

    assert backend.sync_requests[0].since == "batch-1"
    assert backend.sync_requests[0].timeout_ms == 1000
    assert batch.next_batch == "batch-2"
    assert batch.events[0].event_id == "$event1"
    assert batch.metadata["since"] == "batch-1"


def test_normalize_sync_payload_preserves_room_event_metadata():
    batch = normalize_sync_payload(
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
                                    "content": {
                                        "body": "hello",
                                        "m.relates_to": {
                                            "rel_type": "m.thread",
                                            "event_id": "$root",
                                        },
                                    },
                                }
                            ]
                        }
                    }
                }
            },
        }
    )

    assert batch.next_batch == "batch-2"
    assert batch.metadata["matrix_sync_event_count"] == 1
    assert batch.events[0].room_id == "!room:example.org"
    assert batch.events[0].event_id == "$event1"
    assert batch.events[0].thread_root_event_id == "$root"


def test_matrix_service_adapter_send_uses_backend_and_preserves_metadata():
    backend = InMemoryMatrixServiceBackend()
    adapter = MatrixServiceAdapter(backend)
    event = AgentTermEvent(
        channel="!room:example.org",
        sender="@operator",
        kind="matrix_service_send",
        source="matrix-service",
        body="hello",
        thread_id="$root",
        metadata={"txn_id": "txn-1"},
    )

    result = adapter.handle(event)

    assert result.ok is True
    assert result.kind == "matrix_service_send"
    assert result.metadata["matrix_service_status"] == "sent"
    assert result.metadata["matrix_event_id"] == "$local-1"
    assert backend.sent[0].thread_root_event_id == "$root"
    assert backend.sent[0].txn_id == "txn-1"


def test_matrix_service_adapter_blocks_unverified_encrypted_sensitive_send():
    adapter = MatrixServiceAdapter(InMemoryMatrixServiceBackend())
    event = AgentTermEvent(
        channel="!room:example.org",
        sender="@operator",
        kind="matrix_service_send",
        source="matrix-service",
        body="sensitive",
        metadata={
            "sensitive_context": True,
            "matrix_encrypted": True,
            "matrix_e2ee_verified": False,
        },
    )

    result = adapter.handle(event)

    assert result.ok is False
    assert result.metadata["deny_reason"] == "matrix_posture_blocked"
    assert result.metadata["fail_closed"] is True


def test_matrix_service_adapter_sync_normalizes_payload():
    adapter = MatrixServiceAdapter(InMemoryMatrixServiceBackend())
    event = AgentTermEvent(
        channel="!room:example.org",
        sender="@operator",
        kind="matrix_sync",
        source="matrix-service",
        body="sync",
        metadata={
            "matrix_sync": {
                "next_batch": "batch-1",
                "rooms": {
                    "join": {
                        "!room:example.org": {
                            "timeline": {
                                "events": [
                                    {
                                        "event_id": "$event1",
                                        "sender": "@operator:example.org",
                                        "type": "m.room.member",
                                        "content": {"membership": "join"},
                                    }
                                ]
                            }
                        }
                    }
                },
            }
        },
    )

    result = adapter.handle(event)

    assert result.ok is True
    assert result.metadata["matrix_sync_event_count"] == 1
    assert result.metadata["matrix_next_batch"] == "batch-1"
    assert result.metadata["matrix_events"][0]["matrix_membership"] == "join"


def test_matrix_service_adapter_incremental_sync_uses_backend():
    backend = InMemoryMatrixServiceBackend(sync_payloads=[{"next_batch": "batch-2"}])
    adapter = MatrixServiceAdapter(backend)
    event = AgentTermEvent(
        channel="!matrix-sync",
        sender="@operator",
        kind="matrix_sync",
        source="matrix-service",
        body="sync",
        metadata={"since": "batch-1", "timeout_ms": 500, "full_state": True},
    )

    result = adapter.handle(event)

    assert result.ok is True
    assert backend.sync_requests[0].since == "batch-1"
    assert backend.sync_requests[0].timeout_ms == 500
    assert backend.sync_requests[0].full_state is True
    assert result.metadata["matrix_next_batch"] == "batch-2"


def test_build_matrix_backend_defaults_to_in_memory_when_disabled():
    config = config_from_dict({"matrix": {"enabled": False}})

    backend = build_matrix_service_backend(config)

    assert isinstance(backend, InMemoryMatrixServiceBackend)


def test_build_matrix_backend_requires_token_when_enabled(monkeypatch):
    monkeypatch.delenv("AGENT_TERM_MATRIX_ACCESS_TOKEN", raising=False)
    config = config_from_dict(
        {
            "matrix": {
                "enabled": True,
                "homeserverUrl": "https://matrix.example.org",
                "userId": "@agent-term:example.org",
            }
        }
    )

    with pytest.raises(MatrixServiceConfigError, match="missing Matrix access token"):
        build_matrix_service_backend(config)


def test_build_matrix_backend_returns_nio_backend_when_enabled_with_env(monkeypatch):
    monkeypatch.setenv("AGENT_TERM_MATRIX_ACCESS_TOKEN", "token-redacted")
    config = config_from_dict(
        {
            "matrix": {
                "enabled": True,
                "homeserverUrl": "https://matrix.example.org",
                "userId": "@agent-term:example.org",
                "deviceName": "agent-term-ci",
            }
        }
    )

    backend = build_matrix_service_backend(config)

    assert isinstance(backend, NioMatrixServiceBackend)
    assert backend.homeserver_url == "https://matrix.example.org"
    assert backend.user_id == "@agent-term:example.org"
    assert backend.access_token == "token-redacted"
    assert backend.device_name == "agent-term-ci"
