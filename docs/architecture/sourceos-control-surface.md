# AgentTerm as the SourceOS control surface

AgentTerm is the terminal-native operator surface for the SourceOS multi-agent stack. It does not replace Matrix, Sociosphere, Prophet Workspace, Slash Topics, Memory Mesh, New Hope, Holmes, Sherlock Search, MeshRush, cloudshell-fog, AgentPlane, Policy Fabric, GitHub, CI, MCP, Hermes, Codex, Claude Code, or OpenCLAW. It normalizes those systems into an auditable ChatOps event plane with terminal UX.

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
- Sociosphere workspace manifest, lock, topology, or governance registry authority
- Prophet Workspace product/workroom semantics
- Slash Topics topic-pack or membrane schema authority
- Memory Mesh recall/writeback runtime authority
- New Hope semantic runtime authority
- Holmes language intelligence, casefile, retrieval, eval, or guardrail authority
- Sherlock Search search-packet schema authority
- MeshRush graph runtime authority
- cloudshell-fog placement, OIDC, TTL, or PTY enforcement
- AgentPlane bundle execution or replay authority
- Policy Fabric policy authoring, validation, packaging, or release authority
- legacy Sherlock OSINT behavior
- GitHub repository state
- CI workflow execution

This keeps AgentTerm as an operator console rather than a new monolith.

## First-class SourceOS planes

| Plane | Canonical repo/surface | AgentTerm role |
| --- | --- | --- |
| Matrix | Matrix homeserver and bridge topology | canonical ChatOps transport for rooms, events, membership, redactions, bridge metadata, and E2EE posture |
| Sociosphere | `SocioProphet/sociosphere` | meta-workspace controller for manifests, locks, topology, governance registry, validation lanes, and release-readiness orchestration |
| Prophet Workspace | `SocioProphet/prophet-workspace` | Professional Workrooms and workspace product surface for policy-aware workrooms, audit, receipts, and user-facing collaboration surfaces |
| Slash Topics | `SocioProphet/slash-topics` | governed, signed, replayable topic scopes and policy membranes for search/knowledge operations |
| Memory Mesh | `SocioProphet/memory-mesh` | governed recall, writeback, context packs, memoryd runtime, and memory adapters |
| New Hope | `SocioProphet/new-hope` | higher-order semantic runtime for messages, threads, claims, citations, entities, lenses, receptors, membranes, and moderation events |
| Holmes | `SocioProphet/holmes` | language intelligence fabric for casefiles, retrieval, semantic graphs, synthesis, guardrails, evals, and investigative discovery |
| Sherlock Search | `SocioProphet/sherlock-search` | preferred Sherlock integration for search packets and workroom-scoped retrieval context |
| Legacy Sherlock | `SocioProphet/sherlock` | high-friction, policy-gated OSINT adapter only |
| MeshRush | `SocioProphet/meshrush` | graph-native agent runtime for graph views, diffusion, crystallization, traces, and graph evidence |
| cloudshell-fog | `SocioProphet/cloudshell-fog` | fog-first secure shell/session substrate for governed terminal and browser shells |
| AgentPlane | `SocioProphet/agentplane` | execution authority for validate/place/run/evidence/replay flows |
| Policy Fabric | `SocioProphet/policy-fabric` | policy decision point for command dispatch, sensitive context release, and evidence capture |
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
  -> Slash Topics scope and New Hope semantic normalization, when applicable
  -> Policy Fabric decision point
  -> Adapter dispatch
  -> Sociosphere / Prophet Workspace / Memory Mesh / Holmes / Sherlock Search / MeshRush
     / cloudshell-fog / AgentPlane / GitHub / CI / MCP / agent runtime
  -> evidence event
  -> Matrix room and local event log
```

Side-effecting operations must pass through a decision event before execution. Examples include workspace materialization, sensitive workroom context hydration, memory recall/writeback, semantic membrane application, Holmes investigation, search-packet hydration, graph diffusion/crystallization, shell attach, repo mutation, CI retry, legacy Sherlock OSINT lookup, and AgentPlane bundle execution.

## Workspace and workroom integration

Sociosphere and Prophet Workspace are separate authorities:

- Sociosphere owns canonical multi-repo workspace state: manifest, lock, topology, governance registry, validation lanes, and release readiness.
- Prophet Workspace owns product semantics: Professional Workrooms, workspace capabilities, policy-aware UX, audit, receipts, and collaboration surfaces.

AgentTerm should bind Matrix rooms and local terminal threads to Professional Workrooms when available, but use Sociosphere when the operator needs workspace materialization, topology, repo roles, or governance status.

Minimum workroom event metadata:

- workroom ID or alias
- Matrix room ID and thread/root event
- operator identity
- Slash Topics scope, when selected
- Policy Fabric decision reference for context release
- Memory Mesh context-pack reference, when hydrated
- Sherlock Search packet reference, when retrieval is requested
- Holmes casefile reference, when investigation begins
- AgentPlane bundle/evidence reference, when execution occurs

## Slash Topics integration

Slash Topics supplies governed scopes for knowledge and search surfaces. AgentTerm slash commands should preserve:

- topic-pack ID
- signature or validation state
- policy membrane decision
- room/thread/workroom binding
- deterministic receipt reference
- downstream search, memory, Holmes, Sherlock, or New Hope correlation IDs

Topic scopes should constrain Memory Mesh recall, Sherlock Search packets, Holmes investigations, New Hope semantic routing, and MeshRush graph view selection.

## Memory Mesh integration

Memory Mesh should supply governed recall and writeback. AgentTerm should not treat memory as generic hidden prompt history.

Minimum memory event metadata:

- recall or writeback operation
- workroom/thread binding
- topic scope
- policy decision reference
- memory entry IDs or context-pack ID
- source/evidence/provenance references
- downstream agent or investigation recipient

## New Hope integration

New Hope is not covered by Sherlock or Holmes. It is the semantic runtime underneath message/thread/claim/citation operations.

AgentTerm should use New Hope to normalize operator and agent conversations into semantic commons objects before routing to investigation, retrieval, ranking, moderation, or graph operations.

Minimum New Hope event metadata:

- source Matrix event/thread/workroom reference
- Message/Thread/Claim/Citation/Entity/Lens/ModerationEvent IDs, when available
- receptor/membrane decision reference
- provenance and replay references
- ranking/moderation output, when applicable

## Holmes and Sherlock integration

Holmes and Sherlock Search are complementary:

- Holmes is the language-intelligence fabric for casefiles, retrieval, semantic graphs, synthesis, guardrails, evals, and investigative discovery.
- Sherlock Search is the discovery/search-packet surface and retrieval-evidence engine.
- Legacy Sherlock is an explicitly authorized, policy-gated OSINT adapter only.

Preferred investigation path:

```text
/operator asks for investigation or retrieval
  -> AgentTerm binds workroom/topic/thread
  -> New Hope normalizes semantic thread objects
  -> Policy Fabric evaluates context release and action scope
  -> Sherlock Search creates/validates search packet
  -> Memory Mesh hydrates approved context pack
  -> Holmes opens casefile or investigation workflow
  -> AgentTerm records findings, claims, citations, provenance, and evidence
```

## MeshRush integration

MeshRush is the graph-operating runtime. It does not replace the workspace controller, execution control plane, or learning/evaluation plane.

AgentTerm should expose graph operations as visible events:

- graph view selection
- diffusion/exploration request
- stop/crystallization decision
- graph artifact persistence
- trace/evidence emission
- downstream AgentPlane or Holmes handoff

Graph operations should carry provenance, reversibility, policy decision, and workroom/topic/memory bindings.

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
- workroom context admission
- topic membrane admission
- memory recall/writeback admission
- semantic membrane admission
- investigation admission
- search-packet hydration admission
- graph-operation admission
- shell-session admission
- legacy OSINT admission
- GitHub mutation admission
- CI retry admission
- AgentPlane run admission

Policy denials must be displayed in-channel with enough metadata for review.

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
2. Full SourceOS plane registry and CLI shortcuts.
3. Matrix read/write adapter with E2EE posture surfaced.
4. Policy Fabric command-admission stub.
5. Sociosphere workspace state and topology adapter.
6. Prophet Workspace workroom binding and receipt adapter.
7. Slash Topics scope/membrane adapter.
8. Memory Mesh recall/writeback/context-pack adapter.
9. New Hope semantic-thread/message/claim/citation adapter.
10. Sherlock Search packet validation and hydration flow.
11. Holmes casefile/investigation/synthesis/eval flow.
12. MeshRush graph-view/diffusion/crystallization flow.
13. cloudshell-fog session request and attach flow.
14. AgentPlane validate/place/run/evidence flow.
15. GitHub/CI bridge events.
16. Hermes, Codex, Claude Code, and OpenCLAW participant adapters.
17. Textual TUI with rooms, threads, events, approvals, workrooms, context, graph, and evidence panes.
