# Agent instructions for AgentTerm

AgentTerm is the terminal-native Matrix-first ChatOps console for SourceOS. It is not a single-agent chat wrapper.

## Mandatory architecture boundaries

- Matrix is the canonical ChatOps transport. Slack and Discord are bridge targets, not the source of truth.
- AgentTerm is the operator surface and normalized event log. It does not own agent identity authority, workspace topology, workroom semantics, topic scopes, memory runtime, semantic runtime, investigation runtime, search-packet schemas, graph runtime, shell placement, bundle execution, policy release, or CI execution.
- Agent Registry owns agent specs, identities, sessions, memories, tool grants, revocation, and runtime authority. Every non-human AgentTerm participant must resolve through Agent Registry before enablement.
- Sociosphere owns canonical workspace manifests, locks, topology, registry metadata, validation lanes, and release-readiness orchestration.
- Prophet Workspace owns workspace product semantics, Professional Workrooms, workspace app surfaces, policy-aware UX, audit, and receipts.
- Slash Topics owns governed, signed, replayable topic scopes and policy membranes for search/knowledge operations.
- Memory Mesh owns governed recall, writeback, context packs, memoryd runtime, LiteLLM hooks, and OpenCLAW memory tools.
- New Hope owns semantic runtime semantics for messages, threads, claims, citations, entities, lenses, receptors, membranes, and moderation events.
- Holmes owns language intelligence: casefiles, retrieval, semantic graphs, synthesis, guardrails, evals, and investigative discovery. AgentTerm may request/status/correlate Holmes work but must not redefine Holmes.
- Sherlock Search owns discovery/search-packet and retrieval-evidence surfaces. Legacy Sherlock username/social-network lookup is high-friction and policy-gated only.
- MeshRush owns graph-native autonomous-agent runtime semantics over graph views, diffusion, crystallization, traces, and graph evidence.
- cloudshell-fog owns governed shell/session placement, OIDC, TTL, PTY attach, and audit semantics.
- AgentPlane owns bundle validation, executor placement, runs, evidence artifacts, and replay.
- Policy Fabric owns policy decision/evidence surfaces for side-effecting operations and sensitive context release.

## Required invariants

1. Every non-human participant requires Agent Registry identity resolution before enablement.
2. Tool use, capability grants, runtime sessions, memory authority, and revocation checks must resolve through Agent Registry.
3. Side-effecting commands require an approval path.
4. Sensitive context release requires Policy Fabric admission.
5. Matrix room IDs, event IDs, membership changes, redactions, bridge metadata, and E2EE posture must be preserved when available.
6. Workroom, topic, memory, semantic-thread, investigation, search-packet, graph, execution, and shell events must remain explicit and auditable.
7. Slash Topics scopes should constrain Memory Mesh recall, Sherlock Search packets, Holmes investigations, New Hope semantic routing, and MeshRush graph view selection.
8. Memory Mesh must not be treated as hidden prompt history; recall/writeback requires explicit event metadata and policy posture.
9. New Hope is not handled by Sherlock or Holmes; it is the semantic commons runtime underneath message/thread/claim/citation operations.
10. Holmes investigates; Sherlock retrieves; New Hope normalizes semantic objects; Memory Mesh supplies governed context; Slash Topics scopes the operation.
11. AgentPlane evidence artifacts must remain visible in AgentTerm events.
12. cloudshell-fog shell attach must not bypass OIDC, placement, TTL, or audit semantics.
13. Legacy Sherlock OSINT must never become an ambient default tool.
14. Adapter code must be behind narrow contracts; do not hardwire vendor SDKs into the terminal shell.
15. Local event-log data must not be committed.

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
agent-term planes show agent-registry
agent-term planes show new-hope
agent-term record agent-registry agent_identity '!agent-registry' 'Resolve agent.codex before dispatch'
agent-term record prophet-workspace workroom '!prophet-workspace' 'Bind PI demo workroom' --metadata-json '{"workroom":"pi-demo"}'
agent-term record slash-topics topic_scope '!slash-topics' 'Select /professional-intelligence topic scope'
agent-term record memory-mesh memory_recall '!memory-mesh' 'Recall workroom context' --requires-approval
agent-term record new-hope semantic_thread '!new-hope' 'Normalize Matrix thread into semantic commons objects'
agent-term record holmes investigation '!holmes' 'Investigate evidence gap' --requires-approval
agent-term sherlock-packet '!sourceos-intel' 'find workroom context for AgentTerm Sherlock integration' --workroom agent-term --topic professional-intelligence
agent-term record meshrush graph_view '!meshrush' 'Enter professional intelligence graph view' --requires-approval
agent-term request-shell '!sourceos-build' default --thread-id demo-shell
agent-term tail
```

## Preferred implementation order

1. Keep the local event model and SourceOS plane registry stable.
2. Add Matrix adapter read/write with E2EE posture surfaced.
3. Add Agent Registry participant identity, grant, session, and revocation adapter.
4. Add Policy Fabric command admission stub before side-effecting adapter execution.
5. Add Sociosphere workspace manifest/topology adapter.
6. Add Prophet Workspace workroom binding and receipt adapter.
7. Add Slash Topics topic-pack and membrane adapter.
8. Add Memory Mesh recall/writeback/context-pack adapter.
9. Add New Hope semantic-thread/message/claim/citation adapter.
10. Add Sherlock Search packet validation/hydration flow.
11. Add Holmes request/status/artifact correlation flow without redefining Holmes.
12. Add MeshRush graph-view/diffusion/crystallization flow.
13. Add cloudshell-fog session request/attach flow.
14. Add AgentPlane validate/place/run/evidence flow.
15. Add GitHub and CI bridge events.
16. Add Hermes, Codex, Claude Code, and OpenCLAW participant adapters gated by Agent Registry.
17. Add richer Textual TUI views for rooms, threads, agents, grants, workrooms, topics, memory, semantic objects, investigations, graphs, approvals, and evidence.
