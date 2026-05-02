"""CLI entry point for rendering an AgentTerm operator snapshot."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent_term.store import DEFAULT_DB_PATH, EventStore
from agent_term.tui_model import TuiSnapshotBuilder


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-term-snapshot",
        description="Render a dependency-light AgentTerm operator snapshot from the local event log.",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help="Path to the local AgentTerm SQLite event log.",
    )
    parser.add_argument("channel", nargs="?", help="Optional channel/room to render.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum events to render.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = EventStore(Path(args.db))
    try:
        events = store.tail(channel=args.channel, limit=args.limit)
        snapshot = TuiSnapshotBuilder().build(events)
        print(snapshot.render_text())
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
