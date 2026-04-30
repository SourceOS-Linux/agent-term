# AgentTerm

AgentTerm is a terminal-native ChatOps console for coordinating human operators, Matrix rooms, LLM agents, GitHub bots, CI systems, MCP tools, Sociosphere workspace materialization, Prophet Workspace workrooms, Slash Topics scopes, Memory Mesh context, New Hope semantic threads, Holmes investigations, Sherlock search packets, MeshRush graph operations, cloudshell-fog sessions, AgentPlane runs, Policy Fabric decisions, and local SourceOS services from one channel/thread workspace.

The design target is not another single-agent CLI. AgentTerm is the Slack-term class interface for agent operations: rooms, channels, threads, slash commands, approvals, event logs, adapters, and terminal-first operator flow. For SourceOS, Matrix is the canonical network ChatOps substrate. Slack and Discord should be treated as bridge targets, not the source of truth.

## What this repo seeds

- A Python CLI package named `agent-term`.
- A local SQLite event log for durable operator history.
- A minimal interactive shell for immediate use.
- A first-class SourceOS plane registry for Matrix, Sociosphere, Prophet Workspace, Slash Topics, Memory Mesh, New Hope, Holmes, Sherlock Search, legacy Sherlock, MeshRush, cloudshell-fog, AgentPlane, Policy Fabric, GitHub, CI, MCP, Hermes, Codex, Claude Code, and OpenCLAW.
- Adapter contracts for Matrix, SourceOS planes, and process-backed participants.
- Governance-preserving command shapes for workroom, topic, memory, semantic-thread, investigation, search-packet, graph-view, and shell-session requests.
- Configuration examples, tests, CI, and operating-model docs for building AgentTerm into the SourceOS operator console.

## Core concept

```text
┌──────────────────────────┬─────────────────────────────────────────────┐
│ Matrix Rooms / Channels  │ Thread / Conversation                       │
│ !prophet-workspace       │ @operator: /workroom pi-demo                │
│ !slash-topics            │ @operator: /topic professional-intelligence │
│ !memory-mesh             │ @operator: /memory recall workroom context  │
│ !new-hope                │ @agent-term: semantic thread normalized     │
│ !holmes                  │ @operator: /holmes investigate evidence gap │
│ !sherlock-search         │ @operator: /sherlock scoped search packet   │
│ !meshrush                │ @operator: /meshrush enter graph view       │
│ !agentplane              │ @claude-code: proposes patch plan           │
│ !policyfabric            │ @github: PR #42 checks failing              │
│ !cloudshell-fog          │ @operator: /request-shell default           │
├──────────────────────────┴─────────────────────────────────────────────┤
│ /workroom  /topic  /memory  /newhope  /holmes  /sherlock  /meshrush    │
└────────────────────────────────────────────────────────────────────────┘
```

AgentTerm treats every meaningful action as an event:

- human chat messages
- slash commands
- agent replies
- Matrix room events, redactions, membership changes, and bridge events
- Sociosphere workspace manifest, lock, topology, and validation events
- Prophet Workspace workroom, audit, policy-aware UX, and receipt events
- Slash Topics topic-scope, policy-membrane, and receipt events
- Memory Mesh recall, writeback, and context-pack events
- New Hope message, thread, claim, citation, receptor, membrane, and moderation events
- Holmes request/status/artifact correlation events, without redefining Holmes behavior
- Sherlock Search search-packet and context-hydration events
- MeshRush graph-view, diffusion, crystallization, trace, and graph-evidence events
- GitHub issue and PR updates
- CI status transitions
- MCP tool calls
- Policy Fabric decisions
- AgentPlane validation, placement, run, replay, and evidence artifacts
- cloudshell-fog session and shell-attach events
- handoffs between agents

The event log is the control plane. The terminal UI is only the operator surface.

## Why Matrix first

Matrix gives us a federated, open ChatOps substrate instead of binding the system to a vendor workspace. AgentTerm should be able to operate inside Matrix rooms, bridge to Slack/Discord where required, and preserve enough event metadata to audit agent actions.

Initial Matrix requirements:

- map AgentTerm channels to Matrix room IDs or aliases
- preserve Matrix event IDs for auditability
- support threaded replies where homeserver/client support exists
- model redactions as first-class governance events
- expose membership changes as security-relevant events
- support encrypted-room posture checks before agents receive sensitive context
- keep bridge metadata when Matrix rooms bridge to Slack, Discord, GitHub, or CI systems

## Authority split

AgentTerm should not collapse the SourceOS stack into one generic search agent.

| Plane | Authority |
| --- | --- |
| Sociosphere | Meta-workspace controller, canonical workspace manifest, lock, topology, governance registry, validation lanes |
| Prophet Workspace | Workspace product semantics, Professional Workrooms, mail/calendar/drive/docs/chat/meeting surfaces, policy-aware UX |
| Slash Topics | Governed signed topic scopes, policy membranes, search/knowledge scoping, replayable receipts |
| Memory Mesh | Governed recall, writeback, context packs, memoryd runtime, LiteLLM/OpenCLAW memory integrations |
| New Hope | Semantic runtime for messages, threads, claims, citations, entities, lenses, receptors, membranes, and moderation events |
| Holmes | External language-intelligence fabric; AgentTerm may request, display, correlate, and audit Holmes-owned work, but must not define it |
| Sherlock Search | Discovery/search-packet surface and retrieval evidence engine |
| Legacy Sherlock | Explicitly authorized, policy-gated username/social-network OSINT only |
| MeshRush | Graph-native autonomous-agent runtime over typed hypergraph world-model views |
| cloudshell-fog | Governed fog/cloud shell session placement, OIDC, TTL, PTY attach, and audit |
| AgentPlane | Validated bundle execution, executor placement, run/replay artifacts, and evidence |
| Policy Fabric | Policy decision/evidence authority for side effects and sensitive context release |

New Hope is not “handled by” Sherlock or Holmes. Holmes investigates, Sherlock retrieves, and New Hope normalizes the semantic commons objects they operate over.

## MVP commands

After cloning locally:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
agent-term init
agent-term planes list
agent-term planes show new-hope
agent-term post '!sourceos-build' '@operator' 'AgentTerm is online.'
agent-term record prophet-workspace workroom '!prophet-workspace' 'Bind PI demo workroom' --metadata-json '{"workroom":"pi-demo"}'
agent-term record slash-topics topic_scope '!slash-topics' 'Select /professional-intelligence topic scope'
agent-term record memory-mesh memory_recall '!memory-mesh' 'Recall workroom context' --requires-approval
agent-term record new-hope semantic_thread '!new-hope' 'Normalize Matrix thread into New Hope objects'
agent-term record holmes investigation '!holmes' 'Investigate evidence gap' --requires-approval
agent-term sherlock-packet '!sherlock-search' 'hydrate AgentTerm workroom context' --workroom agent-term --topic professional-intelligence --thread-id demo-search
agent-term record meshrush graph_view '!meshrush' 'Enter professional intelligence graph view' --requires-approval
agent-term request-shell '!cloudshell-fog' default --thread-id demo-shell
agent-term tail
agent-term shell
```

The first implementation stores events in SQLite and records governance-preserving events locally. Matrix network I/O, Sociosphere materialization, Prophet Workspace workroom APIs, Slash Topics membranes, Memory Mesh recall/writeback, New Hope semantic normalization, Holmes request/status/artifact correlation, Sherlock Search hydration, MeshRush graph execution, cloudshell-fog session attach, AgentPlane bundle execution, and Policy Fabric admission are intentionally isolated behind adapter boundaries so the terminal, policy, event log, and registry can be hardened independently.

## Docs

- [SourceOS control surface architecture](docs/architecture/sourceos-control-surface.md)
- [Holmes integration boundary](docs/integration/holmes-boundary.md)
- [Agent instructions](AGENTS.md)
- [Example configuration](configs/agent-term.example.json)

## Repository status

This is the seed implementation. It is intentionally small but runnable. The next step is to land the Matrix-room MVP, then bind Policy Fabric admission, Sociosphere workspace state, Prophet Workspace workrooms, Slash Topics scopes, Memory Mesh recall/writeback, New Hope semantic events, Holmes request/status/artifact correlation, Sherlock Search packets, MeshRush graph events, cloudshell-fog session lifecycle, AgentPlane evidence flow, and Hermes/Codex/Claude Code/OpenCLAW participants under explicit operator permissions.
