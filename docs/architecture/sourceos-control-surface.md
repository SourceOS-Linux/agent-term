# AgentTerm as the SourceOS control surface

AgentTerm is the terminal-native operator surface for the SourceOS multi-agent stack. It does not replace Matrix, cloudshell-fog, AgentPlane, Policy Fabric, Sherlock, GitHub, CI, MCP, Hermes, Codex, Claude Code, or OpenCLAW. It normalizes those systems into an auditable ChatOps event plane with terminal UX.

## Boundary statement

AgentTerm owns:

- terminal-native room/thread UX
- normalized local event log
- slash-command parsing
- operator approval capture
- adapter dispatch boundaries
- integration visibility across SourceOS planes

AgentTerm does not own:

- Matrix homeserver semantics
- cloudshell-fog placement, OIDC, TTL, or PTY enforcement
- AgentPlane bundle execution or replay authority
- Policy Fabric policy authoring, validation, packaging, or release authority
- Sherlock search-packet schema authority
- legacy Sherlock OSINT behavior
- GitHub repository state
- CI workflow execution

This keeps AgentTerm as an operator console rather than a new monolith.

## First-class SourceOS planes

| Plane | Canonical repo/surface | AgentTerm role |
| --- | --- | --- |
| Matrix | Matrix homeserver and bridge topology | canonical ChatOps transport for rooms, events, membership, redactions, bridge metadata, and E2EE posture |
| cloudshell-fog | `SocioProphet/cloudshell-fog` | fog-first secure shell/session substrate for governed terminal and browser shells |
| AgentPlane | `SocioProphet/agentplane` | execution authority for validate/place/run/evidence/replay flows |
| Policy Fabric | `SocioProphet/policy-fabric` | policy decision point for command dispatch, sensitive context release, and evidence capture |
| Sherlock Search | `SocioProphet/sherlock-search` | preferred Sherlock integration for search packets and workroom-scoped retrieval context |
| Legacy Sherlock | `SocioProphet/sherlock` | high-friction, policy-gated OSINT adapter only |
| GitHub | GitHub app/CLI/API | issue, PR, branch, review, and check state |
| CI | GitHub Actions and other runners | workflow status, logs, artifacts, retry gates |
| MCP | MCP servers/tools | governed capability plane for external tools and context sources |
| Hermes | Hermes-compatible agent gateway | multi-channel/personal agent participant |
| Codex | Codex CLI/cloud agent | code-writing participant under branch/PR/evidence gates |
| Claude Code | Claude Code CLI | codebase reasoning and patch participant under branch/PR/evidence gates |
| OpenCLAW | OpenCLAW/local open runtime | local/open agent runtime inside SourceOS policy envelopes |

## Control loop

```text
Matrix room event or local terminal command
  -> AgentTerm normalized event
  -> Policy Fabric decision point
  -> Adapter dispatch
  -> cloudshell-fog / AgentPlane / Sherlock / GitHub / CI / MCP / agent runtime
  -> evidence event
  -> Matrix room and local event log
```

Side-effecting operations must pass through a decision event before execution. Examples include shell attach, repo mutation, CI retry, search-packet hydration with sensitive context, legacy Sherlock OSINT lookup, and AgentPlane bundle execution.

## Cloud-fog shell integration

AgentTerm should request cloudshell-fog sessions instead of directly spawning privileged shells for SourceOS operator work. The minimum session request event needs:

- operator identity
- Matrix room/channel
- thread/work-order ID
- requested profile
- TTL
- placement hint
- policy decision reference
- resulting session ID and attach URL reference when approved
- audit event correlation ID

AgentTerm may still provide local development shell commands, but those are not a substitute for SourceOS-governed cloud-fog shell sessions.

## AgentPlane integration

AgentTerm should call AgentPlane for execution, not reimplement execution. The minimum event mapping is:

| AgentPlane concept | AgentTerm event kind |
| --- | --- |
| `ValidationArtifact` | `validation` |
| `PlacementDecision` | `placement` |
| `PlacementReceipt` | `placement` / `evidence` |
| `RunArtifact` | `run` / `evidence` |
| `ReplayArtifact` | `replay` / `evidence` |
| `SessionArtifact` | `session` / `evidence` |

AgentTerm threads should preserve artifact paths, content hashes, executor identity, bundle ID, policy IDs, and replay inputs.

## Policy Fabric integration

Policy Fabric is the decision authority for AgentTerm operations. AgentTerm should emit policy-check events before adapter dispatch and decision/evidence events after validation.

Minimum policy hooks:

- command admission
- capability admission
- context-release admission
- shell-session admission
- legacy OSINT admission
- GitHub mutation admission
- CI retry admission
- AgentPlane run admission

Policy denials must be displayed in-channel with enough metadata for review.

## Sherlock integration

AgentTerm should prefer `sherlock-search` search packets over direct legacy Sherlock invocation.

Preferred path:

```text
/operator asks for investigation or retrieval
  -> AgentTerm creates `search_packet` event
  -> Policy Fabric evaluates scope
  -> sherlock-search validates packet schema
  -> retrieval/context hydration happens under workroom/thread scope
  -> AgentTerm records provenance and packet ID
```

Legacy Sherlock username/social-network lookup is not a default ambient tool. It should require explicit scope, authorization, terms-of-use posture, and audit metadata.

## Matrix integration

Matrix room metadata is security-relevant. AgentTerm should preserve:

- room ID and alias
- event ID
- sender MXID
- thread/root event when available
- membership changes
- redactions
- bridge metadata
- encryption state and verification posture

Agents should not receive sensitive room history from an encrypted room unless AgentTerm can establish an acceptable E2EE posture.

## Implementation order

1. Local event log and CLI shell.
2. SourceOS plane registry.
3. Matrix read/write adapter with E2EE posture surfaced.
4. Policy Fabric command-admission stub.
5. cloudshell-fog session request and attach flow.
6. Sherlock Search packet validation and hydration flow.
7. AgentPlane validate/place/run/evidence flow.
8. GitHub/CI bridge events.
9. Hermes, Codex, Claude Code, and OpenCLAW participant adapters.
10. Textual TUI with rooms, threads, events, approvals, and evidence panes.
