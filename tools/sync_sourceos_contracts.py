#!/usr/bin/env python3
"""Sync vendored SourceOS contract artifacts from sourceos-spec."""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

SOURCEOS_SPEC_REF = "c7f8c2d9e42a56e1127c2f9b85649cbea0f0a9fa"
SOURCE_PATH = "generated/python/sourceos_interaction_event.py"
TARGET_PATH = Path("src/agent_term/contracts/sourceos/generated/sourceos_interaction_event.py")
SOURCE_URL = (
    "https://raw.githubusercontent.com/SourceOS-Linux/sourceos-spec/"
    f"{SOURCEOS_SPEC_REF}/{SOURCE_PATH}"
)
HEADER = (
    "# Generated from schemas/SourceOSInteractionEvent.json.\n"
    f"# Do not edit by hand. Source: SourceOS-Linux/sourceos-spec {SOURCE_PATH}\n"
    f"# Pinned sourceos-spec commit: {SOURCEOS_SPEC_REF}\n\n"
)
UPSTREAM_HEADER = (
    "# Generated from schemas/SourceOSInteractionEvent.json.\n"
    "# Do not edit by hand. Run: python tools/generate_sourceos_interaction_types.py\n\n"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if vendored contracts are stale.")
    parser.add_argument("--write", action="store_true", help="Write vendored contracts from upstream.")
    args = parser.parse_args(argv)

    if args.check == args.write:
        parser.error("choose exactly one of --check or --write")

    expected = normalize(fetch_text(SOURCE_URL))

    if args.write:
        TARGET_PATH.parent.mkdir(parents=True, exist_ok=True)
        TARGET_PATH.write_text(expected, encoding="utf-8")
        print(f"synced {TARGET_PATH} from {SOURCE_URL}")
        return 0

    if not TARGET_PATH.exists():
        print(f"missing vendored contract: {TARGET_PATH}", file=sys.stderr)
        return 1

    current = TARGET_PATH.read_text(encoding="utf-8")
    if current != expected:
        print(f"vendored SourceOS contract is stale: {TARGET_PATH}", file=sys.stderr)
        print(f"source: {SOURCE_URL}", file=sys.stderr)
        print("run: python tools/sync_sourceos_contracts.py --write", file=sys.stderr)
        return 1

    print(f"SourceOS contracts are current at {SOURCEOS_SPEC_REF}")
    return 0


def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - pinned public source file
        return response.read().decode("utf-8")


def normalize(content: str) -> str:
    return HEADER + content.removeprefix(UPSTREAM_HEADER)


if __name__ == "__main__":
    raise SystemExit(main())
