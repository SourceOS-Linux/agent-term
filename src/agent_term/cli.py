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
APPROVAL_NEXT_AUTHORITY = "policy-fabric"
OFFICE_ARTIFACT_SCHEMA = "https://socioprophet.io/schemas/workspace/office-artifact.schema.json"
OFFICE_EVIDENCE_KIND = "OfficeArtifactEvidence"


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

    record = subparsers.add_parser(
        "record",
        help="Record a typed SourceOS plane event without invoking a network adapter.",
    )
    record.add_argument("plane", help="Registered plane key, e.g. memory-mesh or new-hope.")
    record.add_argument("kind", help="Event kind, e.g. workroom, topic_scope, memory_recall.")
    record.add_argument("channel")
    record.add_argument("body")
    record.add_argument("--sender", default="@operator")
    record.add_argument("--thread-id")
    record.add_argument("--requires-approval", action="store_true")
    record.add_argument("--metadata-json", default="{}")

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
    sherlock_packet.add_argument("--topic")
    sherlock_packet.add_argument("--thread-id")

    office = subparsers.add_parser(
        "office",
        help="Record governed Prophet Workspace Office Plane requests.",
    )
    office_sub = office.add_subparsers(dest="office_command", required=True)

    def add_office_create_common(parser_: argparse.ArgumentParser, artifact_type: str, fmt: str) -> None:
        parser_.add_argument("channel")
        parser_.add_argument("--sender", default="@operator")
        parser_.add_argument("--workroom", default="workroom-local-default")
        parser_.add_argument("--title", required=True)
        parser_.add_argument("--format", default=fmt)
        parser_.add_argument("--thread-id")
        parser_.set_defaults(artifact_type=artifact_type)

    create_doc = office_sub.add_parser("create-doc", help="Record an Office document generation request.")
    add_office_create_common(create_doc, "document", "docx")

    create_sheet = office_sub.add_parser("create-sheet", help="Record an Office spreadsheet generation request.")
    add_office_create_common(create_sheet, "spreadsheet", "xlsx")

    create_deck = office_sub.add_parser("create-deck", help="Record an Office slide deck generation request.")
    add_office_create_common(create_deck, "slide-deck", "pptx")

    convert = office_sub.add_parser("convert", help="Record an Office conversion request.")
    convert.add_argument("channel")
    convert.add_argument("input")
    convert.add_argument("--to", required=True)
    convert.add_argument("--sender", default="@operator")
    convert.add_argument("--workroom", default="workroom-local-default")
    convert.add_argument("--title", default="Office conversion")
    convert.add_argument("--thread-id")

    inspect = office_sub.add_parser("inspect", help="Record an Office artifact inspection request.")
    inspect.add_argument("channel")
    inspect.add_argument("path")
    inspect.add_argument("--sender", default="@operator")
    inspect.add_argument("--workroom", default="workroom-local-default")
    inspect.add_argument("--thread-id")

    evidence = office_sub.add_parser("evidence", help="Record an Office evidence inspection request.")
    evidence.add_argument("channel")
    evidence.add_argument("path")
    evidence.add_argument("--sender", default="@operator")
    evidence.add_argument("--workroom", default="workroom-local-default")
    evidence.add_argument("--thread-id")

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


def append_and_print(store: EventStore, event: AgentTermEvent) -> int:
    store.append(event)
    print(format_event(event))
    if event.metadata.get("approval_required"):
        print("status: pending Policy Fabric approval before side effects or sensitive context release")
    return 0


def make_plane_event(
    *,
    plane: str,
    kind: str,
    channel: str,
    sender: str,
    body: str,
    thread_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    approval_required: bool = False,
) -> AgentTermEvent:
    get_plane(plane)
    merged_metadata: dict[str, Any] = {
        "plane": plane,
        "approval_required": approval_required,
    }
    if approval_required:
        merged_metadata["next_authority"] = APPROVAL_NEXT_AUTHORITY
    if metadata:
        merged_metadata.update(metadata)
    return AgentTermEvent(
        channel=channel,
        sender=sender,
        kind=kind,
        source=plane,
        body=body,
        thread_id=thread_id,
        metadata=merged_metadata,
    )


def make_office_event(
    *,
    channel: str,
    sender: str,
    workroom: str,
    operation: str,
    body: str,
    thread_id: str | None,
    metadata: dict[str, Any],
    approval_required: bool,
) -> AgentTermEvent:
    merged = {
        "workroom": workroom,
        "office_operation": operation,
        "office_artifact_schema": OFFICE_ARTIFACT_SCHEMA,
        "agentplane_evidence_kind": OFFICE_EVIDENCE_KIND,
        "delegated_executor": "sourceosctl office",
        "policy_posture": "draft/review-first; send/publish requires approval",
    }
    merged.update(metadata)
    return make_plane_event(
        plane="prophet-workspace",
        kind="office_artifact_request",
        channel=channel,
        sender=sender,
        body=body,
        thread_id=thread_id,
        metadata=merged,
        approval_required=approval_required,
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
    return append_and_print(store, event)


def cmd_record(store: EventStore, args: argparse.Namespace) -> int:
    event = make_plane_event(
        plane=args.plane,
        kind=args.kind,
        channel=args.channel,
        sender=args.sender,
        body=args.body,
        thread_id=args.thread_id,
        metadata=parse_metadata(args.metadata_json),
        approval_required=args.requires_approval,
    )
    return append_and_print(store, event)


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
        "profile": args.profile,
        "ttl_seconds": args.ttl_seconds,
        "placement_hint": args.placement_hint,
    }
    event = make_plane_event(
        plane="cloudshell-fog",
        kind="shell_session",
        channel=args.channel,
        sender=args.sender,
        body=f"Request cloudshell-fog session profile={args.profile} placement={args.placement_hint}",
        thread_id=args.thread_id,
        metadata=metadata,
        approval_required=True,
    )
    return append_and_print(store, event)


def cmd_sherlock_packet(store: EventStore, args: argparse.Namespace) -> int:
    metadata = {
        "query": args.query,
        "workroom": args.workroom,
        "scope": args.scope,
        "topic": args.topic,
        "preferred_repo": "SocioProphet/sherlock-search",
    }
    event = make_plane_event(
        plane="sherlock-search",
        kind="search_packet",
        channel=args.channel,
        sender=args.sender,
        body=f"Request Sherlock search packet workroom={args.workroom} scope={args.scope}: {args.query}",
        thread_id=args.thread_id,
        metadata=metadata,
        approval_required=True,
    )
    return append_and_print(store, event)


def cmd_office(store: EventStore, args: argparse.Namespace) -> int:
    if args.office_command in {"create-doc", "create-sheet", "create-deck"}:
        sourceosctl_command = [
            "sourceosctl",
            "office",
            "generate",
            "--dry-run",
            "--workroom-id",
            args.workroom,
            "--artifact-type",
            args.artifact_type,
            "--format",
            args.format,
            "--title",
            args.title,
        ]
        metadata = {
            "artifact_type": args.artifact_type,
            "format": args.format,
            "title": args.title,
            "sourceosctl_command": sourceosctl_command,
        }
        event = make_office_event(
            channel=args.channel,
            sender=args.sender,
            workroom=args.workroom,
            operation="generate",
            body=f"Request Office {args.artifact_type} generation for workroom={args.workroom}: {args.title}",
            thread_id=args.thread_id,
            metadata=metadata,
            approval_required=True,
        )
        return append_and_print(store, event)

    if args.office_command == "convert":
        sourceosctl_command = [
            "sourceosctl",
            "office",
            "convert",
            args.input,
            "--to",
            args.to,
            "--dry-run",
            "--workroom-id",
            args.workroom,
            "--title",
            args.title,
        ]
        event = make_office_event(
            channel=args.channel,
            sender=args.sender,
            workroom=args.workroom,
            operation="convert",
            body=f"Request Office conversion to {args.to} for workroom={args.workroom}: {args.input}",
            thread_id=args.thread_id,
            metadata={"input": args.input, "to_format": args.to, "title": args.title, "sourceosctl_command": sourceosctl_command},
            approval_required=True,
        )
        return append_and_print(store, event)

    if args.office_command == "inspect":
        sourceosctl_command = ["sourceosctl", "office", "inspect", args.path]
        event = make_office_event(
            channel=args.channel,
            sender=args.sender,
            workroom=args.workroom,
            operation="inspect",
            body=f"Request Office artifact inspection for workroom={args.workroom}: {args.path}",
            thread_id=args.thread_id,
            metadata={"path": args.path, "sourceosctl_command": sourceosctl_command},
            approval_required=False,
        )
        return append_and_print(store, event)

    if args.office_command == "evidence":
        sourceosctl_command = ["sourceosctl", "office", "evidence", "inspect", args.path]
        event = make_office_event(
            channel=args.channel,
            sender=args.sender,
            workroom=args.workroom,
            operation="evidence_inspect",
            body=f"Request Office evidence inspection for workroom={args.workroom}: {args.path}",
            thread_id=args.thread_id,
            metadata={"path": args.path, "sourceosctl_command": sourceosctl_command},
            approval_required=False,
        )
        return append_and_print(store, event)

    raise SystemExit(f"unknown office command: {args.office_command}")


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
            print("/workroom <id-or-name>")
            print("/office create-doc <title>")
            print("/office create-sheet <title>")
            print("/office create-deck <title>")
            print("/office convert <path> <format>")
            print("/office inspect <path>")
            print("/topic <topic-scope>")
            print("/memory <query>")
            print("/newhope <thread-or-message-ref>")
            print("/holmes <investigation request>")
            print("/sherlock <query>")
            print("/meshrush <graph-view request>")
            print("/request-shell [profile]")
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
        if line.startswith("/workroom "):
            ref = line.split(maxsplit=1)[1]
            event = make_plane_event(
                plane="prophet-workspace",
                kind="workroom",
                channel=channel,
                sender=sender,
                body=f"Bind AgentTerm thread to Professional Workroom: {ref}",
                metadata={"workroom": ref},
            )
            append_and_print(store, event)
            continue
        if line.startswith("/office "):
            parts = shlex.split(line)
            if len(parts) >= 3 and parts[1] in {"create-doc", "create-sheet", "create-deck"}:
                artifact_map = {
                    "create-doc": ("document", "docx"),
                    "create-sheet": ("spreadsheet", "xlsx"),
                    "create-deck": ("slide-deck", "pptx"),
                }
                artifact_type, fmt = artifact_map[parts[1]]
                title = " ".join(parts[2:])
                event = make_office_event(
                    channel=channel,
                    sender=sender,
                    workroom="workroom-local-default",
                    operation="generate",
                    body=f"Request Office {artifact_type} generation: {title}",
                    thread_id=None,
                    metadata={"artifact_type": artifact_type, "format": fmt, "title": title},
                    approval_required=True,
                )
                append_and_print(store, event)
                continue
            if len(parts) == 4 and parts[1] == "convert":
                event = make_office_event(
                    channel=channel,
                    sender=sender,
                    workroom="workroom-local-default",
                    operation="convert",
                    body=f"Request Office conversion to {parts[3]}: {parts[2]}",
                    thread_id=None,
                    metadata={"input": parts[2], "to_format": parts[3]},
                    approval_required=True,
                )
                append_and_print(store, event)
                continue
            if len(parts) == 3 and parts[1] == "inspect":
                event = make_office_event(
                    channel=channel,
                    sender=sender,
                    workroom="workroom-local-default",
                    operation="inspect",
                    body=f"Request Office artifact inspection: {parts[2]}",
                    thread_id=None,
                    metadata={"path": parts[2]},
                    approval_required=False,
                )
                append_and_print(store, event)
                continue
            print("usage: /office create-doc|create-sheet|create-deck <title>; /office convert <path> <format>; /office inspect <path>")
            continue
        if line.startswith("/topic "):
            scope = line.split(maxsplit=1)[1]
            event = make_plane_event(
                plane="slash-topics",
                kind="topic_scope",
                channel=channel,
                sender=sender,
                body=f"Select slash-topic scope: {scope}",
                metadata={"topic_scope": scope},
            )
            append_and_print(store, event)
            continue
        if line.startswith("/memory "):
            query = line.split(maxsplit=1)[1]
            event = make_plane_event(
                plane="memory-mesh",
                kind="memory_recall",
                channel=channel,
                sender=sender,
                body=f"Request governed Memory Mesh recall: {query}",
                metadata={"query": query},
                approval_required=True,
            )
            append_and_print(store, event)
            continue
        if line.startswith("/newhope "):
            ref = line.split(maxsplit=1)[1]
            event = make_plane_event(
                plane="new-hope",
                kind="semantic_thread",
                channel=channel,
                sender=sender,
                body=f"Normalize semantic thread/message object: {ref}",
                metadata={"semantic_ref": ref},
            )
            append_and_print(store, event)
            continue
        if line.startswith("/holmes "):
            request = line.split(maxsplit=1)[1]
            event = make_plane_event(
                plane="holmes",
                kind="investigation",
                channel=channel,
                sender=sender,
                body=f"Request Holmes investigation: {request}",
                metadata={"request": request},
                approval_required=True,
            )
            append_and_print(store, event)
            continue
        if line.startswith("/sherlock "):
            query = line.split(maxsplit=1)[1]
            event = make_plane_event(
                plane="sherlock-search",
                kind="search_packet",
                channel=channel,
                sender=sender,
                body=f"Request Sherlock search packet: {query}",
                metadata={"query": query},
                approval_required=True,
            )
            append_and_print(store, event)
            continue
        if line.startswith("/meshrush "):
            request = line.split(maxsplit=1)[1]
            event = make_plane_event(
                plane="meshrush",
                kind="graph_view",
                channel=channel,
                sender=sender,
                body=f"Request MeshRush graph view: {request}",
                metadata={"request": request},
                approval_required=True,
            )
            append_and_print(store, event)
            continue
        if line.startswith("/request-shell"):
            parts = shlex.split(line)
            profile = parts[1] if len(parts) > 1 else "default"
            event = make_plane_event(
                plane="cloudshell-fog",
                kind="shell_session",
                channel=channel,
                sender=sender,
                body=f"Request cloudshell-fog session profile={profile}",
                metadata={"profile": profile},
                approval_required=True,
            )
            append_and_print(store, event)
            continue

        event = AgentTermEvent(channel=channel, sender=sender, kind="message", source="local", body=line)
        append_and_print(store, event)


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
        if args.command == "record":
            return cmd_record(store, args)
        if args.command == "tail":
            return cmd_tail(store, args)
        if args.command == "request-shell":
            return cmd_request_shell(store, args)
        if args.command == "sherlock-packet":
            return cmd_sherlock_packet(store, args)
        if args.command == "office":
            return cmd_office(store, args)
        if args.command == "shell":
            return cmd_shell(store)
    finally:
        store.close()

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
