# AgentTerm

AgentTerm is a terminal-native ChatOps console for coordinating human operators, LLM agents, GitHub bots, CI systems, MCP tools, Matrix rooms, and local SourceOS services from one channel/thread workspace.

The design target is not another single-agent CLI. AgentTerm is the Slack-term class interface for agent operations: rooms, channels, threads, slash commands, approvals, event logs, adapters, and terminal-first operator flow. For SourceOS, Matrix is the canonical network ChatOps substrate. Slack and Discord should be treated as bridge targets, not the source of truth.

## What this repo seeds

- A Python CLI package named `agent-term`.
- A local SQLite event log for durable operator history.
- A minimal interactive shell for immediate use.
- A Textual TUI entry point for richer terminal UX.
- First-class Matrix adapter boundaries for rooms, events, redactions, membership, E2EE posture, and bridges.
- Adapter contracts for Hermes, Codex, Claude Code, OpenCLAW, GitHub, CI, MCP, and local process agents.
- Configuration examples and operating-model docs for building AgentTerm into the SourceOS operator console.

## Core concept

```text
┌──────────────────────────┬─────────────────────────────────────────────┐
│ Matrix Rooms / Channels  │ Thread / Conversation                       │
│ !sourceos-build          │ @codex: opened branch fix-ci-gate           │
│ !agentplane              │ @claude-code: proposes patch plan           │
│ !policyfabric            │ @github: PR #42 checks failing              │
│ !ci-failures             │ @operator: /approve retry                   │
├──────────────────────────┴─────────────────────────────────────────────┤
│ /ask claude-code ...  /assign codex ...  /run ci  /approve  /summarize │
└────────────────────────────────────────────────────────────────────────┘
```

AgentTerm treats every meaningful action as an event:

- human chat messages
- slash commands
- agent replies
- GitHub issue and PR updates
- CI status transitions
- MCP tool calls
- approval decisions
- handoffs between agents
- Matrix room events and bridge events

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
agent-term post '!sourceos-build' '@operator' 'AgentTerm is online.'
agent-term tail '!sourceos-build'
agent-term shell
```

The first implementation stores events in SQLite and executes process-backed adapters locally. Matrix network I/O is intentionally isolated behind an adapter boundary so the terminal, policy, event log, and agent registry can be hardened independently.

## Adapter targets

| Target | Role |
| --- | --- |
| Matrix | Canonical ChatOps transport and room substrate |
| Hermes | Personal/multi-channel agent gateway participant |
| Codex | Code-writing and repo mutation participant |
| Claude Code | Codebase reasoning and patch participant |
| OpenCLAW | Local/open agent runtime participant |
| GitHub | Issues, PRs, reviews, checks, branch events |
| CI | Workflow status, logs, retry/approve gates |
| MCP | Tool plane for files, docs, search, memory, calendar, etc. |
| Local process | Escape hatch for any CLI-driven agent or bot |

## Repository status

This is the seed implementation. The next step is to land a Matrix-room MVP, then bind Codex, Claude Code, Hermes, and OpenCLAW as participants under explicit operator permissions.
