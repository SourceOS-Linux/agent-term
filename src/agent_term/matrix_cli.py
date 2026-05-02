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
from agent_term.matrix_service import normalize_sync_payload
from agent_term.store import DEFAULT_DB_PATH, EventStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-term-matrix",
        description="Matrix helper workflows for AgentTerm send and sync normalization.",
    )
    parser.add_argument("--config", help="Optional AgentTerm JSON config path.")
    parser.add_argument("--db", help="Path to local AgentTerm SQLite event log.")
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
    sync.add_argument("--sender", default="@agent-term")
    sync.add_argument("--channel", default="!matrix-sync")

    return parser


def cmd_send(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    db_path = Path(args.db or config.event_store.path or DEFAULT_DB_PATH)
    metadata: dict[str, object] = {
        "matrix_room_id": args.room,
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
        channel=args.room,
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
        )
        outcome = build_pipeline(dispatch_args, event, store, config).dispatch(event)
        status = "ok" if outcome.ok else "blocked"
        print(f"matrix_send_status={status}")
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

    print(f"matrix_sync_events={len(batch.events)}")
    if batch.next_batch:
        print(f"matrix_next_batch={batch.next_batch}")

    events = [matrix_event.to_agentterm_event() for matrix_event in batch.events]
    if args.persist:
        store = EventStore(db_path)
        try:
            for event in events:
                store.append(event)
        finally:
            store.close()
        print(f"persisted_events={len(events)}")

    for event in events:
        print(f"{event.channel}\t{event.sender}\t{event.kind}\t{event.body}")
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "send":
        return cmd_send(args)
    if args.command == "normalize-sync":
        return cmd_normalize_sync(args)
    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
