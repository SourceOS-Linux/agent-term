"""CLI helpers for Matrix send and sync normalization workflows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from agent_term.config import load_config
from agent_term.dispatch_cli import build_pipeline
from agent_term.events import AgentTermEvent
from agent_term.matrix_service import MatrixServiceAdapter, build_matrix_service_backend
from agent_term.matrix_service import normalize_sync_payload
from agent_term.matrix_state import DEFAULT_STATE_PATH, MatrixStateStore, resolve_matrix_room
from agent_term.matrix_state import rooms_from_sync_payload
from agent_term.store import DEFAULT_DB_PATH, EventStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-term-matrix",
        description="Matrix helper workflows for AgentTerm send and sync normalization.",
    )
    parser.add_argument("--config", help="Optional AgentTerm JSON config path.")
    parser.add_argument("--db", help="Path to local AgentTerm SQLite event log.")
    parser.add_argument("--state", default=str(DEFAULT_STATE_PATH), help="Path to Matrix sync state JSON.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    send = subparsers.add_parser("send", help="Send a Matrix message through the AgentTerm dispatch pipeline.")
    send.add_argument("room")
    send.add_argument("body")
    send.add_argument("--sender", default="@operator")
    send.add_argument("--thread-id")
    send.add_argument("--txn-id")
    send.add_argument("--msgtype", default="m.text")
    send.add_argument("--policy-action", default="matrix-service.matrix_service_send")
    send.add_argument("--allow-policy", action="append", default=[])
    send.add_argument("--sensitive-context", action="store_true")
    send.add_argument("--matrix-encrypted", action="store_true")
    send.add_argument("--matrix-verified", action="store_true")
    send.add_argument("--show-snapshot", action="store_true")

    sync = subparsers.add_parser("normalize-sync", help="Normalize a Matrix /sync JSON payload.")
    sync.add_argument("payload", help="Path to a Matrix sync payload JSON file, or '-' for stdin.")
    sync.add_argument("--persist", action="store_true", help="Persist normalized events into EventStore.")
    sync.add_argument("--save-state", action="store_true", help="Persist next_batch and room IDs into Matrix state.")
    sync.add_argument("--sender", default="@agent-term")
    sync.add_argument("--channel", default="!matrix-sync")

    live_sync = subparsers.add_parser("sync", help="Run incremental Matrix sync through the configured backend.")
    live_sync.add_argument("--persist", action="store_true", help="Persist normalized events into EventStore.")
    live_sync.add_argument("--save-state", action="store_true", default=True, help="Persist next_batch and room IDs into Matrix state.")
    live_sync.add_argument("--no-save-state", dest="save_state", action="store_false")
    live_sync.add_argument("--timeout-ms", type=int, default=0)
    live_sync.add_argument("--full-state", action="store_true")

    state = subparsers.add_parser("state", help="Show durable Matrix sync state.")
    state.add_argument("--json", action="store_true", help="Print state as JSON.")

    return parser


def cmd_send(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    db_path = Path(args.db or config.event_store.path or DEFAULT_DB_PATH)
    state_store = MatrixStateStore(args.state)
    state = state_store.load()
    room_id = resolve_matrix_room(args.room, config, state)
    metadata: dict[str, object] = {
        "matrix_room_id": room_id,
        "matrix_room_alias": args.room if args.room != room_id else None,
        "msgtype": args.msgtype,
        "policy_action": args.policy_action,
    }
    if args.txn_id:
        metadata["txn_id"] = args.txn_id
    if args.sensitive_context:
        metadata["sensitive_context"] = True
    if args.matrix_encrypted:
        metadata["matrix_encrypted"] = True
        metadata["matrix_e2ee_verified"] = bool(args.matrix_verified)

    event = AgentTermEvent(
        channel=room_id,
        sender=args.sender,
        kind="matrix_service_send",
        source="matrix-service",
        body=args.body,
        thread_id=args.thread_id,
        metadata=metadata,
    )

    store = EventStore(db_path)
    try:
        dispatch_args = argparse.Namespace(
            source="matrix-service",
            agent_id=None,
            register_agent=[],
            grant=[],
            allow_policy=args.allow_policy,
            deny_policy=[],
            pending_policy=[],
            policy_action=args.policy_action,
            policy_ref="local://policy-fabric/matrix-cli",
            sensitive_context=args.sensitive_context,
        )
        outcome = build_pipeline(dispatch_args, event, store, config).dispatch(event)
        status = "ok" if outcome.ok else "blocked"
        print(f"matrix_send_status={status}")
        print(f"matrix_room_id={room_id}")
        if outcome.blocked_reason:
            print(f"blocked_reason={outcome.blocked_reason}")
        print(f"persisted_events={len(outcome.persisted_events)}")
        if args.show_snapshot:
            print(outcome.snapshot.render_text())
        return 0 if outcome.ok else 1
    finally:
        store.close()


def cmd_normalize_sync(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    db_path = Path(args.db or config.event_store.path or DEFAULT_DB_PATH)
    payload = _load_json_payload(args.payload)
    batch = normalize_sync_payload(payload)

    print_sync_batch(batch, db_path=db_path, state_path=Path(args.state), persist=args.persist, save_state=args.save_state, payload=payload)
    return 0


def cmd_incremental_sync(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    db_path = Path(args.db or config.event_store.path or DEFAULT_DB_PATH)
    state_store = MatrixStateStore(args.state)
    state = state_store.load()
    event = AgentTermEvent(
        channel="!matrix-sync",
        sender="@agent-term",
        kind="matrix_sync",
        source="matrix-service",
        body="Run Matrix incremental sync.",
        metadata={
            "since": state.next_batch,
            "timeout_ms": args.timeout_ms,
            "full_state": args.full_state,
        },
    )
    result = MatrixServiceAdapter(build_matrix_service_backend(config)).handle(event)
    if not result.ok:
        print("matrix_sync_status=blocked")
        if result.metadata.get("deny_reason"):
            print(f"blocked_reason={result.metadata['deny_reason']}")
        return 1

    events_metadata = result.metadata.get("matrix_events")
    events = []
    if isinstance(events_metadata, list):
        for metadata in events_metadata:
            if not isinstance(metadata, dict):
                continue
            events.append(
                AgentTermEvent(
                    channel=str(metadata.get("matrix_room_alias") or metadata.get("matrix_room_id") or "!matrix-sync"),
                    sender=str(metadata.get("matrix_sender_mxid") or "@agent-term"),
                    kind="matrix_room_event",
                    source="matrix",
                    body="",
                    thread_id=_optional_str(metadata.get("matrix_thread_root_event_id")),
                    metadata=metadata,
                )
            )

    print(f"matrix_sync_events={len(events)}")
    next_batch = _optional_str(result.metadata.get("matrix_next_batch"))
    if next_batch:
        print(f"matrix_next_batch={next_batch}")
    if args.persist:
        store = EventStore(db_path)
        try:
            for event in events:
                store.append(event)
        finally:
            store.close()
        print(f"persisted_events={len(events)}")
    if args.save_state:
        state = state_store.update_next_batch(next_batch)
        print(f"matrix_state_next_batch={state.next_batch}")
    return 0


def print_sync_batch(batch, *, db_path: Path, state_path: Path, persist: bool, save_state: bool, payload: dict[str, Any]) -> None:
    print(f"matrix_sync_events={len(batch.events)}")
    if batch.next_batch:
        print(f"matrix_next_batch={batch.next_batch}")

    events = [matrix_event.to_agentterm_event() for matrix_event in batch.events]
    if persist:
        store = EventStore(db_path)
        try:
            for event in events:
                store.append(event)
        finally:
            store.close()
        print(f"persisted_events={len(events)}")

    if save_state:
        state_store = MatrixStateStore(state_path)
        state = state_store.update_rooms(rooms_from_sync_payload(payload))
        state = state_store.save(state.with_next_batch(batch.next_batch))
        print(f"matrix_state_next_batch={state.next_batch}")
        print(f"matrix_state_rooms={len(state.rooms)}")

    for event in events:
        print(f"{event.channel}\t{event.sender}\t{event.kind}\t{event.body}")


def cmd_state(args: argparse.Namespace) -> int:
    state = MatrixStateStore(args.state).load()
    if args.json:
        print(json.dumps(state.to_dict(), indent=2, sort_keys=True))
        return 0
    print(f"matrix_state_next_batch={state.next_batch or ''}")
    print(f"matrix_state_rooms={len(state.rooms)}")
    for alias, room_id in sorted(state.rooms.items()):
        print(f"{alias}\t{room_id}")
    return 0


def _load_json_payload(path: str) -> dict[str, Any]:
    if path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise SystemExit("Matrix sync payload must be a JSON object")
    return value


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "send":
        return cmd_send(args)
    if args.command == "normalize-sync":
        return cmd_normalize_sync(args)
    if args.command == "sync":
        return cmd_incremental_sync(args)
    if args.command == "state":
        return cmd_state(args)
    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
