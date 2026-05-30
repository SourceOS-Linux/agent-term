# SourceOS Interaction Reference Flow

Status: downstream reference pointer  
Canonical packet: `SourceOS-Linux/sourceos-spec#118`  
Canonical manifest: `examples/interaction-flow/noetica-superconscious-agentplane-agentterm.flow.json`

## AgentTerm role

AgentTerm is the terminal-facing consumer of `SourceOSInteractionEvent` governance traces.

The canonical reference flow is:

```text
Noetica creates SourceOSInteractionEvent
  -> Superconscious records task-boundary refs
  -> AgentPlane records evidence refs
  -> AgentTerm displays the governance trace
```

## Local references

- Generated contract: `src/agent_term/contracts/sourceos/generated/sourceos_interaction_event.py`
- Sync check: `python tools/sync_sourceos_contracts.py --check`
- Sync refresh: `python tools/sync_sourceos_contracts.py --write`

## Boundary

AgentTerm owns terminal display of the trace. The schema remains owned by `SourceOS-Linux/sourceos-spec`; task coordination, evidence records, policy decisions, identity grants, and memory context remain in their respective planes.
