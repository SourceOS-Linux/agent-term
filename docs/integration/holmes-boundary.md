# Holmes integration boundary

AgentTerm must integrate with Holmes without redefining Holmes.

Holmes is the SocioProphet language-intelligence fabric. AgentTerm is only the terminal-native ChatOps/operator surface that can display, request, correlate, and audit Holmes-related work.

## AgentTerm may own

- terminal commands that request a Holmes investigation or casefile operation
- local event records that reference Holmes work
- Matrix room/thread correlation metadata
- Policy Fabric admission records before sensitive context release or side-effecting investigation actions
- links to Holmes artifacts, casefiles, evals, guardrails, retrieval traces, or synthesis outputs
- operator-visible status and evidence summaries

## AgentTerm must not own

- Holmes product semantics
- Holmes service implementation
- Holmes casefile schema authority
- Holmes retrieval, NLP, guardrail, eval, or synthesis internals
- Holmes model-routing policy
- Holmes release/deployment topology
- any migration or refactor inside `SocioProphet/holmes`

## Integration posture

Holmes integration in AgentTerm should be conservative until the Holmes repo exposes stable contracts. The current AgentTerm registry entry is only an operator-visible integration placeholder based on the public Holmes product boundary. It should not be treated as a normative Holmes specification.

## Expected flow

```text
Matrix room / AgentTerm thread
  -> optional Prophet Workspace workroom binding
  -> optional Slash Topics scope
  -> optional New Hope semantic normalization
  -> Policy Fabric admission for sensitive context or side effects
  -> Sherlock Search packet or Memory Mesh context pack, when needed
  -> Holmes casefile/investigation request
  -> Holmes-owned artifacts/status/evidence references
  -> AgentTerm event log + Matrix-visible summary
```

AgentTerm should call or observe Holmes through adapters once Holmes contracts are stable. Until then, AgentTerm should record governed request events and preserve references rather than simulating Holmes behavior.
