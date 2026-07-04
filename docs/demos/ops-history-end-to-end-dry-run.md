# OpsHistory End-to-End Dry-Run Demo

Status: deterministic dry-run demo plan.

This demo proves the OpsHistory contract capture can be exercised across the estate without enabling live services.

## Run

```bash
python scripts/ops_history_dry_run_demo.py
```

The script emits JSON with:

- AgentTerm policy explanation plan;
- AgentTerm replay plan;
- AgentTerm context-pack plan;
- AgentTerm redaction posture;
- external validation commands for sourceos-spec, Policy Fabric, Agent Registry, Memory Mesh, AgentPlane, BearBrowser, and sourceos-shell;
- explicit no-live-side-effect safety boundary.

## Safety boundary

The demo must keep all of these disabled:

- live sync;
- live Matrix;
- browser profile reads;
- browser credential access;
- browser cookie access;
- operational content capture;
- Memory Mesh writeback;
- AgentPlane execution;
- external bridge/export.

## Estate validation commands

```bash
# SourceOS-Linux/agent-term
ruff check .
pytest
python scripts/ops_history_dry_run_demo.py

# SourceOS-Linux/sourceos-spec
make validate-ops-history-examples

# SocioProphet/policy-fabric
make ops-history-policy-validate

# SocioProphet/agent-registry
make ops-history-grants-validate

# SocioProphet/memory-mesh
python scripts/validate_ops_history_context_pack.py

# SocioProphet/agentplane
make validate-ops-history-contracts

# SourceOS-Linux/BearBrowser
bearbrowser-history export explain --session demo --profile agent-runtime --dry-run

# SourceOS-Linux/sourceos-shell
python scripts/validate_ops_history_receipts.py
```

## Non-goals

This demo does not implement `ops-historyd`, `bearhistoryd`, live receipt adapters, Memory Mesh writeback, AgentPlane execution, or bridge/export runtime behavior.
