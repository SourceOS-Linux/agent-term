"""Command-line entry point for AgentTerm."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any

from agent_term.events import AgentTermEvent
from agent_term.planes import get_plane, iter_planes
from agent_term.store import DEFAULT_DB_PATH, EventStore


DEFAULT_CHANNEL = "!sourceos-ops"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-term",
        description="Matrix-first terminal ChatOps console for SourceOS multi-agent operations.",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help="Path to the local AgentTerm SQLite event log.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Initialize the local AgentTerm event log.")

    post = subparsers.add_parser("post", help="Append a message/event to the local event log.")
    post.add_argument("channel")
    post.add_argument("sender")
    post.add_argument("body")
    post.add_argument("--kind", default="message")
    post.add_argument("--source", default="local")
    post.add_argument("--thread-id")
    post.add_argument("--metadata-json", default="{}")

    tail = subparsers.add_parser("tail", help="Show recent events.")
    tail.add_argument("channel", nargs="?")
    tail.add_argument("--limit", type=int, default=25)

    planes = subparsers.add_parser("planes", help="List or inspect first-class SourceOS planes.")
    planes_sub = planes.add_subparsers(dest="planes_command", required=True)
    planes_sub.add_parser("list", help="List registered SourceOS planes.")
    show_plane = planes_sub.add_parser("show", help="Show one registered SourceOS plane.")
    show_plane.add_argument("plane")

    request_shell = subparsers.add_parser(
        "request-shell",
        help="Record a governed cloudshell-fog shell-session request event.",
    )
    request_shell.add_argument("channel")
    request_shell.add_argument("profile", nargs="?", default="default")
    request_shell.add_argument("--sender", default="@operator")
    request_shell.add_argument("--ttl-seconds", type=int, default=3600)
    request_shell.add_argument("--placement-hint", default="fog-first")
    request_shell.add_argument("--thread-id")

    sherlock_packet = subparsers.add_parser(
        "sherlock-packet",
        help="Record a governed Sherlock search-packet request event.",
    )
    sherlock_packet.add_argument("channel")
    sherlock_packet.add_argument("query")
    sherlock_packet.add_argument("--sender", default="@operator")
    sherlock_packet.add_argument("--workroom", default="default")
    sherlock_packet.add_argument("--scope", default="workroom")
    sherlock_packet.add_argument("--thread-id")

    subparsers.add_parser("shell", help="Open the minimal AgentTerm interactive shell.")

    return parser


def parse_metadata(metadata_json: str) -> dict[str, Any]:
    try:
        value = json.loads(metadata_json)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"metadata must be valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit("metadata must decode to a JSON object")
    return value


def format_event(event: AgentTermEvent) -> str:
    thread = f" thread={event.thread_id}" if event.thread_id else ""
    return (
        f"{event.created_at.isoformat()} [{event.channel}] "
        f"{event.sender} kind={event.kind} source={event.source}{thread}: {event.body}"
    )


def cmd_init(store: EventStore) -> int:
    event = AgentTermEvent(
        channel=DEFAULT_CHANNEL,
        sender="@agent-term",
        kind="system",
        source="local",
        body="AgentTerm local event log initialized.",
    )
    store.append(event)
    print(f"initialized: {store.path}")
    return 0


def cmd_post(store: EventStore, args: argparse.Namespace) -> int:
    event = AgentTermEvent(
        channel=args.channel,
        sender=args.sender,
        kind=args.kind,
        source=args.source,
        body=args.body,
        thread_id=args.thread_id,
        metadata=parse_metadata(args.metadata_json),
    )
    store.append(event)
    print(format_event(event))
    return 0


def cmd_tail(store: EventStore, args: argparse.Namespace) -> int:
    for event in store.tail(channel=args.channel, limit=args.limit):
        print(format_event(event))
    return 0


def cmd_planes(args: argparse.Namespace) -> int:
    if args.planes_command == "list":
        for plane in iter_planes():
            print(f"{plane.key}\t{plane.display_name}\t{plane.repository}")
        return 0

    if args.planes_command == "show":
        plane = get_plane(args.plane)
        print(f"{plane.display_name} ({plane.key})")
        print(f"repo: {plane.repository}")
        print(f"source: {plane.source}")
        print(f"role: {plane.role}")
        print("capabilities:")
        for capability in plane.capabilities:
            approval = "approval-required" if capability.requires_approval else "no-approval"
            kinds = ",".join(capability.event_kinds) or "none"
            print(f"  - {capability.name} [{approval}; events={kinds}]")
            print(f"    {capability.description}")
        if plane.notes:
            print("notes:")
            for note in plane.notes:
                print(f"  - {note}")
        return 0

    raise SystemExit(f"unknown planes command: {args.planes_command}")


def cmd_request_shell(store: EventStore, args: argparse.Namespace) -> int:
    metadata = {
        "plane": "cloudshell-fog",
        "profile": args.profile,
        "ttl_seconds": args.ttl_seconds,
        "placement_hint": args.placement_hint,
        "approval_required": True,
        "next_authority": "policy-fabric",
    }
    event = AgentTermEvent(
        channel=args.channel,
        sender=args.sender,
        kind="shell_session",
        source="cloudshell-fog",
        body=f"Request cloudshell-fog session profile={args.profile} placement={args.placement_hint}",
        thread_id=args.thread_id,
        metadata=metadata,
    )
    store.append(event)
    print(format_event(event))
    print("status: pending Policy Fabric approval before shell attach")
    return 0


def cmd_sherlock_packet(store: EventStore, args: argparse.Namespace) -> int:
    metadata = {
        "plane": "sherlock-search",
        "query": args.query,
        "workroom": args.workroom,
        "scope": args.scope,
        "approval_required": True,
        "next_authority": "policy-fabric",
        "preferred_repo": "SocioProphet/sherlock-search",
    }
    event = AgentTermEvent(
        channel=args.channel,
        sender=args.sender,
        kind="search_packet",
        source="sherlock-search",
        body=f"Request Sherlock search packet workroom={args.workroom} scope={args.scope}: {args.query}",
        thread_id=args.thread_id,
        metadata=metadata,
    )
    store.append(event)
    print(format_event(event))
    print("status: pending Policy Fabric approval before context hydration or legacy OSINT tools")
    return 0


def cmd_shell(store: EventStore) -> int:
    print("AgentTerm shell. Type /help for commands, /quit to exit.")
    channel = DEFAULT_CHANNEL
    sender = "@operator"
    while True:
        try:
            line = input(f"{channel} {sender}> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        if line in {"/quit", "/exit"}:
            return 0
        if line == "/help":
            print("/channel <room-or-channel>")
            print("/sender <principal>")
            print("/tail [limit]")
            print("/planes")
            print("/request-shell [profile]")
            print("/sherlock <query>")
            print("/quit")
            print("Anything else is posted as a message event.")
            continue
        if line.startswith("/channel "):
            channel = line.split(maxsplit=1)[1]
            continue
        if line.startswith("/sender "):
            sender = line.split(maxsplit=1)[1]
            continue
        if line.startswith("/tail"):
            parts = shlex.split(line)
            limit = int(parts[1]) if len(parts) > 1 else 10
            for event in store.tail(channel=channel, limit=limit):
                print(format_event(event))
            continue
        if line == "/planes":
            for plane in iter_planes():
                print(f"{plane.key}\t{plane.display_name}\t{plane.repository}")
            continue
        if line.startswith("/request-shell"):
            parts = shlex.split(line)
            profile = parts[1] if len(parts) > 1 else "default"
            event = AgentTermEvent(
                channel=channel,
                sender=sender,
                kind="shell_session",
                source="cloudshell-fog",
                body=f"Request cloudshell-fog session profile={profile}",
                metadata={
                    "plane": "cloudshell-fog",
                    "profile": profile,
                    "approval_required": True,
                    "next_authority": "policy-fabric",
                },
            )
            store.append(event)
            print(format_event(event))
            continue
        if line.startswith("/sherlock "):
            query = line.split(maxsplit=1)[1]
            event = AgentTermEvent(
                channel=channel,
                sender=sender,
                kind="search_packet",
                source="sherlock-search",
                body=f"Request Sherlock search packet: {query}",
                metadata={
                    "plane": "sherlock-search",
                    "query": query,
                    "approval_required": True,
                    "next_authority": "policy-fabric",
                },
            )
            store.append(event)
            print(format_event(event))
            continue

        event = AgentTermEvent(channel=channel, sender=sender, kind="message", source="local", body=line)
        store.append(event)
        print(format_event(event))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    db_path = Path(args.db)

    if args.command == "planes":
        return cmd_planes(args)

    store = EventStore(db_path)
    try:
        if args.command == "init":
            return cmd_init(store)
        if args.command == "post":
            return cmd_post(store, args)
        if args.command == "tail":
            return cmd_tail(store, args)
        if args.command == "request-shell":
            return cmd_request_shell(store, args)
        if args.command == "sherlock-packet":
            return cmd_sherlock_packet(store, args)
        if args.command == "shell":
            return cmd_shell(store)
    finally:
        store.close()

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
