from agent_term.events import AgentTermEvent
from agent_term.matrix_adapter import MatrixAdapter, normalize_matrix_payload, posture_from_metadata


def test_normalizes_matrix_thread_and_bridge_metadata():
    payload = {
        "room_id": "!room:example.org",
        "room_alias": "#sourceos-ops:example.org",
        "event_id": "$event1",
        "sender": "@operator:example.org",
        "type": "m.room.message",
        "content": {
            "body": "hello matrix",
            "m.relates_to": {"rel_type": "m.thread", "event_id": "$root"},
        },
        "unsigned": {"bridge": {"network": "slack", "channel": "sourceos-ops"}},
    }

    normalized = normalize_matrix_payload(payload)
    event = normalized.to_agentterm_event()

    assert normalized.channel == "#sourceos-ops:example.org"
    assert normalized.thread_root_event_id == "$root"
    assert normalized.bridge_metadata == {"network": "slack", "channel": "sourceos-ops"}
    assert event.channel == "#sourceos-ops:example.org"
    assert event.thread_id == "$root"
    assert event.metadata["matrix_event_id"] == "$event1"


def test_normalizes_redaction_as_governance_event():
    normalized = normalize_matrix_payload(
        {
            "room_id": "!room:example.org",
            "event_id": "$redaction",
            "sender": "@mod:example.org",
            "type": "m.room.redaction",
            "content": {},
        }
    )

    event = normalized.to_agentterm_event()

    assert normalized.redacted is True
    assert event.kind == "matrix_redaction"
    assert event.body == "<redacted>"
    assert event.metadata["matrix_redacted"] is True


def test_normalizes_membership_event():
    normalized = normalize_matrix_payload(
        {
            "room_id": "!room:example.org",
            "event_id": "$member",
            "sender": "@user:example.org",
            "type": "m.room.member",
            "content": {"membership": "join"},
        }
    )

    event = normalized.to_agentterm_event()

    assert normalized.membership == "join"
    assert event.kind == "matrix_membership"
    assert event.metadata["matrix_membership"] == "join"


def test_e2ee_posture_blocks_unverified_encrypted_sensitive_context():
    adapter = MatrixAdapter()
    event = AgentTermEvent(
        channel="!room:example.org",
        sender="@agent-term:example.org",
        kind="matrix_e2ee_posture_check",
        source="matrix",
        body="check posture",
        metadata={"matrix_encrypted": True, "matrix_e2ee_verified": False},
    )

    result = adapter.handle(event)

    assert result.ok is False
    assert result.metadata["fail_closed"] is True
    assert result.metadata["matrix_status"] == "blocked"
    assert result.metadata["matrix_sensitive_context_allowed"] is False


def test_e2ee_posture_allows_verified_encrypted_room():
    posture = posture_from_metadata({"matrix_encrypted": True, "matrix_e2ee_verified": True})

    assert posture.encrypted is True
    assert posture.verified is True
    assert posture.can_release_sensitive_context is True


def test_matrix_emit_blocks_sensitive_context_when_unverified():
    adapter = MatrixAdapter()
    event = AgentTermEvent(
        channel="!room:example.org",
        sender="@agent-term:example.org",
        kind="matrix_emit",
        source="matrix",
        body="sensitive context",
        metadata={
            "sensitive_context": True,
            "matrix_room_id": "!room:example.org",
            "matrix_encrypted": True,
            "matrix_e2ee_verified": False,
        },
    )

    result = adapter.handle(event)

    assert result.ok is False
    assert result.kind == "matrix_emit"
    assert result.metadata["matrix_status"] == "blocked"


def test_matrix_emit_prepares_non_sensitive_event():
    adapter = MatrixAdapter()
    event = AgentTermEvent(
        channel="!room:example.org",
        sender="@agent-term:example.org",
        kind="matrix_emit",
        source="matrix",
        body="status update",
        metadata={"matrix_room_id": "!room:example.org"},
    )

    result = adapter.handle(event)

    assert result.ok is True
    assert result.metadata["matrix_status"] == "prepared"
    assert result.metadata["matrix_room_id"] == "!room:example.org"
