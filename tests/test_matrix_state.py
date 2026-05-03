import json

from agent_term.config import config_from_dict
from agent_term.matrix_state import MatrixStateStore, MatrixSyncState, resolve_matrix_room
from agent_term.matrix_state import rooms_from_sync_payload


def test_matrix_state_store_round_trips_next_batch_and_rooms(tmp_path):
    state_path = tmp_path / "matrix-state.json"
    store = MatrixStateStore(state_path)

    saved = store.save(
        MatrixSyncState(next_batch="batch-1", rooms={"sourceosOps": "!room:example.org"})
    )
    loaded = store.load()

    assert saved.next_batch == "batch-1"
    assert loaded.next_batch == "batch-1"
    assert loaded.rooms == {"sourceosOps": "!room:example.org"}
    assert state_path.exists()


def test_matrix_state_updates_next_batch_without_dropping_rooms(tmp_path):
    store = MatrixStateStore(tmp_path / "matrix-state.json")
    store.save(MatrixSyncState(next_batch="batch-1", rooms={"sourceosOps": "!room"}))

    updated = store.update_next_batch("batch-2")

    assert updated.next_batch == "batch-2"
    assert updated.rooms == {"sourceosOps": "!room"}
    assert updated.updated_at is not None


def test_resolve_matrix_room_prefers_state_then_config_then_literal():
    config = config_from_dict({"matrix": {"rooms": {"sourceosOps": "!config:example.org"}}})
    state = MatrixSyncState(rooms={"sourceosOps": "!state:example.org"})

    assert resolve_matrix_room("sourceosOps", config, state) == "!state:example.org"
    assert resolve_matrix_room("!config:example.org", config, MatrixSyncState()) == "!config:example.org"
    assert resolve_matrix_room("unknown", config, state) == "unknown"


def test_rooms_from_sync_payload_extracts_joined_room_ids():
    rooms = rooms_from_sync_payload(
        {
            "rooms": {
                "join": {
                    "!one:example.org": {"timeline": {"events": []}},
                    "!two:example.org": {"timeline": {"events": []}},
                }
            }
        }
    )

    assert rooms == {
        "!one:example.org": "!one:example.org",
        "!two:example.org": "!two:example.org",
    }


def test_state_file_is_json_object(tmp_path):
    state_path = tmp_path / "matrix-state.json"
    store = MatrixStateStore(state_path)
    store.save(MatrixSyncState(next_batch="batch-1", rooms={"!room": "!room"}))

    raw = json.loads(state_path.read_text(encoding="utf-8"))

    assert raw["next_batch"] == "batch-1"
    assert raw["rooms"] == {"!room": "!room"}
