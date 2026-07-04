"""CLI entry point for AgentTerm service health checks."""

from __future__ import annotations

import argparse
import json
import sys

from agent_term.config import load_config
from agent_term.health import HealthChecker, HealthCheckOptions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-term-check",
        description="Check configured AgentTerm service seams for Matrix, Agent Registry, and Policy Fabric.",
    )
    parser.add_argument("--config", help="Optional AgentTerm JSON config path.")
    parser.add_argument("--agent-id", help="Agent ID to resolve through Agent Registry.")
    parser.add_argument("--tool", help="Tool grant to resolve for --agent-id.")
    parser.add_argument("--policy-action", help="Policy action to resolve through Policy Fabric.")
    parser.add_argument("--json", action="store_true", help="Print health report as JSON.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero for warnings as well as blocked checks.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    report = HealthChecker(config).run(
        HealthCheckOptions(
            agent_id=args.agent_id,
            tool=args.tool,
            policy_action=args.policy_action,
        )
    )

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(report.render_text())

    if report.blocked:
        return 1
    if args.strict and not all(result.ok for result in report.results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
