# Agent participant authority

AgentTerm is not the authority for non-human agent identity. It is the terminal operator console and event surface.

`SocioProphet/agent-registry` is the authority for:

- agent specs
- agent identities
- runtime sessions
- tool grants
- memory authority
- revocation
- runtime authority

## Hard invariant

Every non-human AgentTerm participant must resolve through Agent Registry before enablement.

This includes:

- Hermes
- Codex
- Claude Code
- OpenCLAW
- Matrix bots
- GitHub bots acting as agents
- CI bots acting as agents
- MCP-backed tool participants
- local process agents
- future SourceOS agents

Local config may express desired bindings. It is not runtime authority.

## Dispatch sequence

```text
/operator addresses @agent
  -> AgentTerm records agent_identity lookup event
  -> Agent Registry resolves identity, spec, grants, session, and revocation state
  -> Policy Fabric evaluates action/context admission when required
  -> AgentTerm dispatches only if registry and policy posture are valid
  -> adapter result records agent_id, grant_id, session_id, policy ref, and evidence ref
```

## Failure posture

AgentTerm must fail closed when registry status is:

- unknown
- missing
- revoked
- expired
- incompatible with requested tool/capability
- unavailable outside explicitly marked local development mode

Local development mode must not operate on sensitive context or side-effecting commands unless Agent Registry and Policy Fabric checks pass.

## Relationship to other planes

Agent Registry does not replace Policy Fabric. Agent Registry answers: “Who is this agent, what session/grants does it hold, and is it still authorized as an agent participant?”

Policy Fabric answers: “Is this action or context release allowed under current policy?”

Both gates are required for side-effecting agent work.
