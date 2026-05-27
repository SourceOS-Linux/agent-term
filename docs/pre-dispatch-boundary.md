# AgentTerm Pre-Dispatch Boundary

## Purpose

`AgentTermPreDispatchDecision` is the decision-only boundary between an operator or interaction event and any later runtime dispatch.

AgentTerm is the terminal-native / Matrix-first operator console. It is not the authority plane for non-human identity, grants, policy admission, sensitive context release, or side-effecting execution.

This object exists so later participant adapters for Hermes, Codex, Claude Code, OpenCLAW, GitHub, CI, MCP, terminal, Matrix, and AgentPlane cannot dispatch from local config alone.

## Required chain

```text
operator / interaction event = evidence input
Agent Registry lookup = identity / session / grant / revocation evidence
Policy Fabric decision = action/context policy evaluation
AgentTerm pre-dispatch decision = local runtime readiness decision
AgentPlane / terminal / Matrix adapter = downstream execution surface
OpsHistory / SourceOSInteractionEvent = record/render path only
```

## Boundary rules

A pre-dispatch decision is not execution.

It must record:

- participant ref and kind;
- Agent Registry ref for non-human participants;
- grant refs and session ref for non-human participants;
- revocation state;
- Policy Fabric decision refs for side-effecting actions;
- policy status;
- dispatch decision;
- target adapter;
- side-effect posture;
- sensitive-context posture;
- evidence refs;
- `performed_dispatch = false`.

## Fail-closed cases

The validator rejects:

- non-human participant dispatch from local config alone;
- non-human participant without grants or session ref;
- revoked or unknown revocation state allowing dispatch;
- side-effecting action without Policy Fabric decision refs;
- sensitive context without policy admission;
- pre-dispatch record claiming dispatch already occurred.

## Related issues

- #8 registered non-human participants and pre-dispatch Agent Registry / Policy Fabric checks.
- #18 SourceOS Agent Machine workspace integration and governed execution handoff.
- #43 SourceOSInteractionEvent governance trace rendering.
- #44 pre-dispatch boundary issue.

## Non-goals

This tranche does not add live provider calls, terminal execution, Matrix sends, MCP execution, AgentPlane calls, or Agent Registry network access.

It only defines and validates the decision object that must exist before those surfaces are wired.
