"""CLI entry point for AgentTerm version and command-index output."""

from __future__ import annotations

import argparse
import sys

from agent_term.release import package_version, render_command_index


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-term-version",
        description="Print AgentTerm package version and command index.",
    )
    parser.add_argument("--short", action="store_true", help="Print only the package version.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.short:
        print(package_version())
    else:
        print(render_command_index())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
