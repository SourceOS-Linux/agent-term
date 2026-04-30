# Copilot instructions for SourceOS AgentTerm

AgentTerm is the Matrix-first terminal ChatOps console for SourceOS. Do not implement it as a generic chatbot wrapper.

Read these before making changes:

- `AGENTS.md`
- `docs/architecture/sourceos-control-surface.md`
- `docs/integration/agent-registry-boundary.md`
- `docs/integration/holmes-boundary.md`

## Architecture guardrails

- Matrix is the canonical transport. Slack and Discord integrations are bridges.
- AgentTerm owns terminal UX, normalized local events, slash-command parsing, and adapter boundaries.
- Agent Registry owns agent specs, identities, sessions, memories, tool grants, revocation, and runtime authority. Every non-human participant must resolve through Agent Registry before enablement.
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
- Local config may reference participants, but it is not runtime authority.

## Validation commands

```bash
python -m pip install -e '.[dev]'
ruff check .
pytest
```

## Current priority order

1. Matrix adapter with room/event/E2EE posture preservation.
2. Agent Registry adapter for participant identity, grants, sessions, and revocation.
3. Policy Fabric admission stub for side-effecting commands and sensitive context release.
4. Sociosphere workspace state adapter.
5. Prophet Workspace workroom binding and receipt adapter.
6. Slash Topics scope/membrane adapter.
7. Memory Mesh recall/writeback/context-pack adapter.
8. New Hope semantic event adapter.
9. Sherlock Search packet validation/hydration adapter.
10. Holmes request/status/artifact correlation adapter, respecting `docs/integration/holmes-boundary.md`.
11. MeshRush graph operation adapter.
12. cloudshell-fog session lifecycle adapter.
13. AgentPlane validate/place/run/evidence adapter.
14. GitHub/CI bridge adapters.
15. Hermes, Codex, Claude Code, and OpenCLAW participant adapters gated by Agent Registry.
16. Textual TUI for rooms, threads, agents, grants, workrooms, topics, memory, semantic objects, investigations, graphs, approvals, and evidence.
