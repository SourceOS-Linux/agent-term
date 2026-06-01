"""Tests for opt-in Noetica interaction artifact import."""

from __future__ import annotations

import shutil
from pathlib import Path

from agent_term.noetica_import import (
    import_noetica_interaction_artifacts,
    iter_noetica_interaction_artifacts,
)
from agent_term.store import EventStore

FIXTURE = Path(__file__).parent / "fixtures" / "sourceos_interaction_event.json"


def test_iter_noetica_interaction_artifacts_accepts_single_file() -> None:
    assert iter_noetica_interaction_artifacts(FIXTURE) == [FIXTURE]


def test_iter_noetica_interaction_artifacts_returns_sorted_json_files(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    ignored = tmp_path / "ignored.txt"
    shutil.copyfile(FIXTURE, b)
    shutil.copyfile(FIXTURE, a)
    ignored.write_text("not-json", encoding="utf-8")

    assert iter_noetica_interaction_artifacts(tmp_path) == [a, b]


def test_import_noetica_interaction_artifacts_records_file(tmp_path: Path) -> None:
    db_path = tmp_path / "events.sqlite3"
    store = EventStore(db_path)
    try:
        result = import_noetica_interaction_artifacts(FIXTURE, store, channel="!demo")
        recorded = store.tail(channel="!demo", limit=5)
    finally:
        store.close()

    assert result.imported == 1
    assert len(result.event_ids) == 1
    assert len(recorded) == 1
    assert recorded[0].kind == "sourceos_interaction"
    assert recorded[0].source == "noetica"
    assert recorded[0].metadata["sourceos_interaction_event_id"] == "urn:srcos:interaction-event:noetica-standalone-complete-0001"


def test_import_noetica_interaction_artifacts_records_directory(tmp_path: Path) -> None:
    event_dir = tmp_path / "events"
    event_dir.mkdir()
    shutil.copyfile(FIXTURE, event_dir / "01.json")
    shutil.copyfile(FIXTURE, event_dir / "02.json")

    db_path = tmp_path / "events.sqlite3"
    store = EventStore(db_path)
    try:
        result = import_noetica_interaction_artifacts(event_dir, store, channel="!demo")
        recorded = store.tail(channel="!demo", limit=5)
    finally:
        store.close()

    assert result.imported == 2
    assert len(result.event_ids) == 2
    assert len(recorded) == 2
