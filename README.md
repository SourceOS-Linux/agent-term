# AgentTerm

AgentTerm is a terminal-native ChatOps console for coordinating human operators, Matrix rooms, LLM agents, GitHub bots, CI systems, MCP tools, cloudshell-fog sessions, AgentPlane runs, Policy Fabric decisions, Sherlock search packets, and local SourceOS services from one channel/thread workspace.

The design target is not another single-agent CLI. AgentTerm is the Slack-term class interface for agent operations: rooms, channels, threads, slash commands, approvals, event logs, adapters, and terminal-first operator flow. For SourceOS, Matrix is the canonical network ChatOps substrate. Slack and Discord should be treated as bridge targets, not the source of truth.

## What this repo seeds

- A Python CLI package named `agent-term`.
- A local SQLite event log for durable operator history.
- A minimal interactive shell for immediate use.
- First-class SourceOS plane registry for Matrix, cloudshell-fog, AgentPlane, Policy Fabric, Sherlock Search, legacy Sherlock, GitHub, CI, MCP, Hermes, Codex, Claude Code, and OpenCLAW.
- Adapter contracts for Matrix and process-backed participants.
- Governance-preserving command shapes for shell-session and Sherlock search-packet requests.
- Configuration examples, tests, CI, and operating-model docs for building AgentTerm into the SourceOS operator console.

## Core concept

```text
┌──────────────────────────┬─────────────────────────────────────────────┐
│ Matrix Rooms / Channels  │ Thread / Conversation                       │
│ !sourceos-build          │ @codex: opened branch fix-ci-gate           │
│ !agentplane              │ @claude-code: proposes patch plan           │
│ !policyfabric            │ @github: PR #42 checks failing              │
│ !sherlock-search         │ @operator: /sherlock scoped context packet  │
│ !ci-failures             │ @operator: /approve retry                   │
├──────────────────────────┴─────────────────────────────────────────────┤
│ /ask claude-code ...  /assign codex ...  /run ci  /approve  /summarize │
└────────────────────────────────────────────────────────────────────────┘
```

AgentTerm treats every meaningful action as an event:

- human chat messages
- slash commands
- agent replies
- Matrix room events, redactions, membership changes, and bridge events
- GitHub issue and PR updates
- CI status transitions
- MCP tool calls
- Policy Fabric decisions
- AgentPlane validation, placement, run, replay, and evidence artifacts
- cloudshell-fog session and shell-attach events
- Sherlock search-packet and context-hydration events
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

## MVP commands

After cloning locally:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
agent-term init
agent-term planes list
agent-term planes show cloudshell-fog
agent-term post '!sourceos-build' '@operator' 'AgentTerm is online.'
agent-term request-shell '!sourceos-build' default --thread-id demo-shell
agent-term sherlock-packet '!sherlock-search' 'hydrate AgentTerm workroom context' --workroom agent-term --thread-id demo-search
agent-term tail
agent-term shell
```

The first implementation stores events in SQLite and records governance-preserving events locally. Matrix network I/O, cloudshell-fog session attach, AgentPlane bundle execution, Policy Fabric admission, and Sherlock Search hydration are intentionally isolated behind adapter boundaries so the terminal, policy, event log, and agent registry can be hardened independently.

## First-class SourceOS planes

| Target | Role |
| --- | --- |
| Matrix | Canonical ChatOps transport and room substrate |
| cloudshell-fog | Fog-first shell/session substrate; AgentTerm requests sessions but does not bypass OIDC, placement, TTL, or audit |
| AgentPlane | Execution authority for bundle validation, placement, runs, replay, and evidence artifacts |
| Policy Fabric | Policy decision and evidence authority for side-effecting commands and sensitive context release |
| Sherlock Search | Preferred Sherlock integration for scoped search packets and context hydration |
| Legacy Sherlock | High-friction policy-gated OSINT wrapper only; never a default ambient tool |
| Hermes | Personal/multi-channel agent gateway participant |
| Codex | Code-writing participant under branch/PR/evidence gates |
| Claude Code | Codebase reasoning and patch participant under branch/PR/evidence gates |
| OpenCLAW | Local/open agent runtime inside SourceOS policy envelopes |
| GitHub | Issues, PRs, reviews, checks, branch events |
| CI | Workflow status, logs, retry/approve gates |
| MCP | Tool plane for files, docs, search, memory, calendar, etc. |
| Local process | Escape hatch for any CLI-driven agent or bot |

## Docs

- [SourceOS control surface architecture](docs/architecture/sourceos-control-surface.md)
- [Agent instructions](AGENTS.md)
- [Example configuration](configs/agent-term.example.json)

## Repository status

This is the seed implementation. It is intentionally small but runnable. The next step is to land the Matrix-room MVP, then bind Policy Fabric admission, cloudshell-fog session lifecycle, Sherlock Search packets, AgentPlane evidence flow, and Hermes/Codex/Claude Code/OpenCLAW participants under explicit operator permissions.
