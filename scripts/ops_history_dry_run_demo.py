#!/usr/bin/env python3
"""Assemble the OpsHistory end-to-end dry-run demo plan.

This script is intentionally contract-only. It does not connect to Matrix, read browser
profiles, export receipts, write Memory Mesh entries, run AgentPlane bundles, or call
external services. It emits a JSON plan that points at the validation commands in the
other repos participating in the dry-run demo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agent_term.ops_history import (  # noqa: E402
    context_pack_plan,
    policy_explain,
    redactions_pending,
    replay_plan,
)


def build_demo() -> dict[str, Any]:
    """Return the cross-repo OpsHistory dry-run demo envelope."""

    agent_term_policy = policy_explain("active-multi-agent-room")
    agent_term_replay = replay_plan("demo-search")
    agent_term_context_pack = context_pack_plan(
        "pi-demo",
        topic="urn:srcos:topic:professional-intelligence",
    )
    agent_term_redactions = redactions_pending()

    return {
        "demoId": "urn:srcos:ops-history-demo:end-to-end-dry-run-0001",
        "demoKind": "ops-history-end-to-end-dry-run",
        "dryRun": True,
        "operatorSurface": "SourceOS-Linux/agent-term",
        "plans": {
            "agentTermPolicy": agent_term_policy,
            "agentTermReplay": agent_term_replay,
            "agentTermContextPack": agent_term_context_pack,
            "agentTermRedactions": agent_term_redactions,
        },
        "externalValidation": [
            {
                "repo": "SourceOS-Linux/sourceos-spec",
                "command": "make validate-ops-history-examples",
                "purpose": "Validate shared OpsHistory typed contracts.",
            },
            {
                "repo": "SocioProphet/policy-fabric",
                "command": "make ops-history-policy-validate",
                "purpose": "Validate Policy Fabric OpsHistory decision families.",
            },
            {
                "repo": "SocioProphet/agent-registry",
                "command": "make ops-history-grants-validate",
                "purpose": "Validate Agent Registry dry-run authority grant examples.",
            },
            {
                "repo": "SocioProphet/memory-mesh",
                "command": "python scripts/validate_ops_history_context_pack.py",
                "purpose": "Validate bounded Memory Mesh context-pack references.",
            },
            {
                "repo": "SocioProphet/agentplane",
                "command": "make validate-ops-history-contracts",
                "purpose": "Validate AgentPlane context/evidence references.",
            },
            {
                "repo": "SourceOS-Linux/BearBrowser",
                "command": "bearbrowser-history export explain --session demo --profile agent-runtime --dry-run",
                "purpose": "Validate BearHistory metadata-only export posture.",
            },
            {
                "repo": "SourceOS-Linux/sourceos-shell",
                "command": "python scripts/validate_ops_history_receipts.py",
                "purpose": "Validate operational receipt metadata with content capture disabled.",
            },
        ],
        "safetyBoundary": {
            "liveSync": False,
            "liveMatrix": False,
            "browserProfileRead": False,
            "browserCredentialAccess": False,
            "browserCookieAccess": False,
            "receiptContentCapture": False,
            "memoryWriteback": False,
            "agentplaneExecution": False,
            "externalBridgeExport": False,
        },
        "expectedOutcomes": [
            "AgentTerm emits policy/replay/context-pack/redaction plans.",
            "Policy Fabric admits summary-only or ref-only decisions where appropriate.",
            "Agent Registry grants are dry-run scoped and deny sensitive payload access by default.",
            "Memory Mesh accepts bounded context-pack references without writeback.",
            "AgentPlane accepts context/evidence references without execution behavior changes.",
            "BearBrowser denies human-secure export and admits agent-runtime metadata-only posture.",
            "sourceos-shell receipts keep content capture disabled by default.",
            "Redaction/tombstone posture invalidates downstream derived refs in dry-run.",
        ],
    }


def main() -> int:
    print(json.dumps(build_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
