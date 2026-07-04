"""CLI helper for rendering SourceOSInteractionEvent payloads."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent_term.interaction import (
    interaction_to_agent_term_event,
    load_interaction_event,
    render_interaction_event,
)
from agent_term.noetica_import import import_noetica_interaction_artifacts
from agent_term.store import DEFAULT_DB_PATH, EventStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-term-interaction",
        description="Render or record SourceOSInteractionEvent governance traces.",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help="Path to the local AgentTerm SQLite event log.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    render = subparsers.add_parser("render", help="Render an interaction event JSON file.")
    render.add_argument("path", type=Path)

    record = subparsers.add_parser(
        "record",
        help="Record an interaction event JSON file in the AgentTerm event log.",
    )
    record.add_argument("path", type=Path)
    record.add_argument("--channel", default="!sourceos-interaction")
    record.add_argument("--sender", default="@agent-term")

    import_noetica = subparsers.add_parser(
        "import-noetica",
        help="Import Noetica-exported SourceOSInteractionEvent JSON artifacts from a file or directory.",
    )
    import_noetica.add_argument("path", type=Path)
    import_noetica.add_argument("--channel", default="!sourceos-interaction")
    import_noetica.add_argument("--sender", default="@agent-term")
    import_noetica.add_argument("--render", action="store_true")

    return parser


def cmd_render(path: Path) -> int:
    event = load_interaction_event(path)
    print(render_interaction_event(event))
    return 0


def cmd_record(path: Path, db_path: Path, channel: str, sender: str) -> int:
    event = load_interaction_event(path)
    agent_term_event = interaction_to_agent_term_event(
        event,
        channel=channel,
        sender=sender,
    )
    store = EventStore(db_path)
    try:
        store.append(agent_term_event)
    finally:
        store.close()
    print(render_interaction_event(event))
    print(f"recorded: {agent_term_event.event_id}")
    return 0


def cmd_import_noetica(
    path: Path,
    db_path: Path,
    channel: str,
    sender: str,
    render: bool,
) -> int:
    store = EventStore(db_path)
    try:
        result = import_noetica_interaction_artifacts(
            path,
            store,
            channel=channel,
            sender=sender,
            render=render,
        )
    finally:
        store.close()
    print(f"imported: {result.imported}")
    for event_id in result.event_ids:
        print(f"recorded: {event_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "render":
        return cmd_render(args.path)

    if args.command == "record":
        return cmd_record(args.path, Path(args.db), args.channel, args.sender)

    if args.command == "import-noetica":
        return cmd_import_noetica(args.path, Path(args.db), args.channel, args.sender, args.render)

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
