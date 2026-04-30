# Agent instructions for AgentTerm

AgentTerm is the terminal-native Matrix-first ChatOps console for SourceOS. It is not a single-agent chat wrapper.

## Mandatory architecture boundaries

- Matrix is the canonical ChatOps transport. Slack and Discord are bridge targets, not the source of truth.
- AgentTerm is the operator surface and normalized event log. It does not own shell placement, bundle execution, policy release, search-packet schemas, or CI execution.
- cloudshell-fog owns governed shell/session placement, OIDC, TTL, PTY attach, and audit semantics.
- AgentPlane owns bundle validation, executor placement, runs, evidence artifacts, and replay.
- Policy Fabric owns policy decision/evidence surfaces for side-effecting operations and sensitive context release.
- Sherlock Search is the preferred Sherlock integration path. Legacy Sherlock username/social-network lookup is high-friction and policy-gated only.

## Required invariants

1. Side-effecting commands require an approval path.
2. Sensitive context release requires Policy Fabric admission.
3. Matrix room IDs, event IDs, membership changes, redactions, bridge metadata, and E2EE posture must be preserved when available.
4. AgentPlane evidence artifacts must remain visible in AgentTerm events.
5. cloudshell-fog shell attach must not bypass OIDC, placement, TTL, or audit semantics.
6. Legacy Sherlock OSINT must never become an ambient default tool.
7. Adapter code must be behind narrow contracts; do not hardwire vendor SDKs into the terminal shell.
8. Local event-log data must not be committed.

## Development commands

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
ruff check .
pytest
```

## Useful smoke commands

```bash
agent-term init
agent-term planes list
agent-term planes show cloudshell-fog
agent-term request-shell '!sourceos-build' default --thread-id demo-shell
agent-term sherlock-packet '!sourceos-intel' 'find workroom context for AgentTerm Sherlock integration' --workroom agent-term
agent-term tail
```

## Preferred implementation order

1. Keep the local event model and SourceOS plane registry stable.
2. Add Matrix adapter read/write with E2EE posture surfaced.
3. Add Policy Fabric command admission stub before side-effecting adapter execution.
4. Add cloudshell-fog session request/attach flow.
5. Add Sherlock Search packet validation/hydration flow.
6. Add AgentPlane validate/place/run/evidence flow.
7. Add GitHub and CI bridge events.
8. Add Hermes, Codex, Claude Code, and OpenCLAW participant adapters.
9. Add richer Textual TUI views for rooms, threads, approvals, and evidence.
