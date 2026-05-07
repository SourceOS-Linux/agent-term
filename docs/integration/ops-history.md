# OpsHistory Integration

Status: initial dry-run implementation slice.

AgentTerm is the operator surface for OpsHistory. This integration makes OpsHistory visible before any live local service, Matrix sync, Memory Mesh writeback, or AgentPlane run behavior is enabled.

## Commands

```bash
agent-term ops-history policy --profile active-multi-agent-room
agent-term ops-history replay --thread demo-search
agent-term ops-history context-pack --workroom pi-demo --topic urn:srcos:topic:professional-intelligence
agent-term ops-history redactions
```

All commands are dry-run only in this implementation slice. They emit deterministic JSON plans.

## Boundaries

- No live sync.
- No live Matrix access.
- No live Memory Mesh writeback.
- No AgentPlane execution.
- No browser or operational receipt export.

## Contract role

AgentTerm produces operator-visible plans for:

- OpsHistory sync-policy explanation;
- bounded replay planning;
- context-pack planning for Memory Mesh and AgentPlane;
- redaction posture.

Policy Fabric and Agent Registry references are represented as refs only. Runtime checks land in a later slice.
