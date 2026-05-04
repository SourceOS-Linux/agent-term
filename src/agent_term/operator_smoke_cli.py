"""CLI entry point for AgentTerm local operator smoke tests."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent_term.operator_smoke import DEFAULT_CONFIG, DEFAULT_MATRIX_SYNC, run_local_operator_smoke


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-term-smoke",
        description="Run the local AgentTerm operator smoke path using offline fixtures.",
    )
    parser.add_argument(
        "--workdir",
        default=".agent-term/smoke",
        help="Directory for isolated smoke state.",
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="AgentTerm config path.")
    parser.add_argument(
        "--matrix-sync-fixture",
        default=str(DEFAULT_MATRIX_SYNC),
        help="Matrix sync fixture path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_local_operator_smoke(
        workdir=Path(args.workdir),
        config_path=Path(args.config),
        matrix_sync_fixture=Path(args.matrix_sync_fixture),
    )
    print(result.render_text())
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
