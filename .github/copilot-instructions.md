# Copilot instructions for SourceOS AgentTerm

AgentTerm is the Matrix-first terminal ChatOps console for SourceOS. Do not implement it as a generic chatbot wrapper.

Read these before making changes:

- `AGENTS.md`
- `docs/architecture/sourceos-control-surface.md`
- `docs/integration/holmes-boundary.md`

## Architecture guardrails

- Matrix is the canonical transport. Slack and Discord integrations are bridges.
- AgentTerm owns terminal UX, normalized local events, slash-command parsing, and adapter boundaries.
- Sociosphere owns workspace manifest, lock, topology, registry, validation lanes, and release-readiness orchestration.
- Prophet Workspace owns Professional Workrooms and workspace product semantics.
- Slash Topics owns topic scopes and policy membranes.
- Memory Mesh owns governed recall/writeback and context packs.
- New Hope owns message/thread/claim/citation semantic runtime semantics.
- Holmes must not be redefined here. AgentTerm may only request, display, correlate, and audit Holmes-owned work.
- Sherlock Search owns search packets and retrieval-evidence surfaces. Legacy Sherlock OSINT remains disabled by default and policy-gated.
- MeshRush owns graph-view/diffusion/crystallization semantics.
- cloudshell-fog owns shell placement, OIDC, TTL, PTY attach, and audit.
- AgentPlane owns validation, placement, runs, replay, and evidence artifacts.
- Policy Fabric owns command admission and sensitive context-release decisions.
- Side-effecting operations require explicit approval paths.
- Avoid adding SDK-specific logic directly to `cli.py`. Keep adapters narrow and testable.

## Validation commands

```bash
python -m pip install -e '.[dev]'
ruff check .
pytest
```

## Current priority order

1. Matrix adapter with room/event/E2EE posture preservation.
2. Policy Fabric admission stub for side-effecting commands and sensitive context release.
3. Sociosphere workspace state adapter.
4. Prophet Workspace workroom binding and receipt adapter.
5. Slash Topics scope/membrane adapter.
6. Memory Mesh recall/writeback/context-pack adapter.
7. New Hope semantic event adapter.
8. Sherlock Search packet validation/hydration adapter.
9. Holmes request/status/artifact correlation adapter, respecting `docs/integration/holmes-boundary.md`.
10. MeshRush graph operation adapter.
11. cloudshell-fog session lifecycle adapter.
12. AgentPlane validate/place/run/evidence adapter.
13. GitHub/CI bridge adapters.
14. Hermes, Codex, Claude Code, and OpenCLAW participant adapters.
15. Textual TUI for rooms, threads, workrooms, topics, memory, semantic objects, investigations, graphs, approvals, and evidence.
