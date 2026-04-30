from agent_term.events import AgentTermEvent
from agent_term.store import EventStore


def test_event_store_round_trips_events(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    try:
        event = AgentTermEvent(
            channel="!sourceos-build",
            sender="@operator",
            kind="search_packet",
            source="sherlock-search",
            body="Request scoped Sherlock packet",
            thread_id="thread-1",
            metadata={"workroom": "demo", "approval_required": True},
        )
        store.append(event)

        events = store.tail("!sourceos-build", limit=5)
    finally:
        store.close()

    assert len(events) == 1
    assert events[0].event_id == event.event_id
    assert events[0].metadata["approval_required"] is True
    assert events[0].source == "sherlock-search"
