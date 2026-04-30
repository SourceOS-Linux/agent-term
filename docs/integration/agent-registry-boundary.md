# Agent Registry integration boundary

AgentTerm must not invent, hardcode, or locally bless non-human agent participants. Agent identity and runtime authority belong to `SocioProphet/agent-registry`.

Agent Registry is the governed registry for SocioProphet agent specs, identities, sessions, memories, tool grants, revocation, and runtime authority.

## AgentTerm may own

- terminal UX for selecting, viewing, and addressing registered agents
- local event records that reference agent identities and sessions
- Matrix room/thread correlation metadata for agent messages
- request events for tool grants, capability use, and session activation
- display of Agent Registry status, grants, revocations, and denials
- adapter plumbing that resolves registered agents before dispatch

## AgentTerm must not own

- canonical agent specs
- agent identity authority
- runtime session authority
- tool grant authority
- revocation authority
- memory ownership authority
- capability-policy decisions
- a hidden allowlist that bypasses Agent Registry

## Required invariant

Every non-human AgentTerm participant must be registered and resolved through Agent Registry before enablement. This includes:

- Hermes participants
- Codex participants
- Claude Code participants
- OpenCLAW participants
- Matrix bots
- GitHub bots acting as agents
- CI bots acting as agents
- MCP-backed tool participants
- local process agents
- future custom SourceOS agents

Local config may reference agents, but config is not authority. Config only expresses desired local bindings. Agent Registry decides whether the participant exists, what it may do, which tools it may use, which sessions are live, and whether any grants have been revoked.

## Expected flow

```text
/operator addresses @agent
  -> AgentTerm records agent_identity lookup event
  -> Agent Registry resolves identity, spec, runtime authority, grants, and session state
  -> Policy Fabric evaluates requested action/context release where required
  -> AgentTerm dispatches through the appropriate adapter only if identity and grants are valid
  -> adapter result is recorded with agent ID, grant ID, session ID, and policy/evidence references
  -> Matrix room and local event log receive visible status
```

## Minimum metadata on agent events

- `agent_id`
- `agent_registry_ref`
- `agent_spec_version`
- `session_id`, when active
- `tool_grant_ids`, when tools are requested
- `revocation_check_at`
- `policy_decision_ref`, when the action is side-effecting or context-sensitive
- `adapter_key`
- `runtime_authority`
- `workroom`, `topic_scope`, and `thread_id`, when applicable

## Adapter posture

Agent adapters should fail closed when Agent Registry is unavailable or returns unknown/revoked status. The only acceptable exception is a clearly marked local development mode that cannot operate on sensitive context or side-effecting commands.
