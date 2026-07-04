# AgentTerm operator quickstart

This quickstart exercises the current local AgentTerm control loop without requiring live Matrix, Agent Registry, or Policy Fabric services.

It demonstrates the intended operator path:

```text
agent-term-check
  -> agent-term-matrix normalize-sync
  -> agent-term-dispatch
  -> agent-term-snapshot
```

The fixtures in `configs/fixtures/` are local examples only. They are not authority. In production, Agent Registry and Policy Fabric remain the authority for agent identity, grants, sessions, revocation, and policy admission.

## 1. Install for local development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

## 2. Check configured service seams

```bash
agent-term-check \
  --config configs/agent-term.local.example.json \
  --agent-id agent.github \
  --tool repo-write \
  --policy-action github.pr.create
```

Expected posture:

- Matrix reports `warn` because the local example uses the offline/in-memory backend.
- Agent Registry reports `ok` because `agent.github` and the `repo-write` grant resolve from the local fixture.
- Policy Fabric reports `ok` because `github.pr.create` resolves from the local fixture.

Use strict mode when warnings should fail an operator preflight:

```bash
agent-term-check \
  --config configs/agent-term.local.example.json \
  --strict
```

## 3. Normalize a Matrix sync payload

```bash
agent-term-matrix \
  --config configs/agent-term.local.example.json \
  normalize-sync configs/fixtures/matrix-sync.local.example.json \
  --persist \
  --save-state
```

This persists normalized Matrix events into `.agent-term/events.sqlite3` and saves `next_batch` plus joined room IDs into `.agent-term/matrix-state.json`.

Show current Matrix state:

```bash
agent-term-matrix \
  --config configs/agent-term.local.example.json \
  state
```

## 4. Dispatch a policy-gated Matrix send

```bash
agent-term-matrix \
  --config configs/agent-term.local.example.json \
  send sourceosOps "AgentTerm dispatch pipeline is online."
```

The send goes through the AgentTerm dispatch pipeline. It is admitted by the local Policy Fabric fixture and sent through the offline Matrix backend unless live Matrix config is enabled.

## 5. Dispatch a registered GitHub participant action

```bash
agent-term-dispatch \
  --config configs/agent-term.local.example.json \
  --tool repo-write \
  --policy-action github.pr.create \
  github github_mutation '!github' 'Create PR for AgentTerm operator quickstart'
```

Expected event flow:

1. Original `github.github_mutation` event is recorded.
2. Agent Registry resolves `agent.github`.
3. Agent Registry resolves `repo-write` grant.
4. Policy Fabric admits `github.pr.create`.
5. Registered participant adapter records the invocation.

## 6. Dispatch a governed Memory Mesh recall

```bash
agent-term-dispatch \
  --config configs/agent-term.local.example.json \
  --metadata-json '{"query":"operator quickstart context","policy_action":"memory-mesh.memory_recall","workroom":"operator-quickstart","topic_scope":"sourceos-agentterm"}' \
  memory-mesh memory_recall '!memory-mesh' 'Recall operator quickstart context'
```

Expected event flow:

1. Original `memory-mesh.memory_recall` event is recorded.
2. Policy Fabric admits `memory-mesh.memory_recall`.
3. Memory Mesh adapter records a context-pack reference.

## 7. Render the operator snapshot

```bash
agent-term-snapshot \
  --db .agent-term/events.sqlite3 \
  --limit 100
```

The snapshot groups events into operator panes such as Matrix rooms, agents, approvals, context, runs, shells, and evidence.

## 8. Clean local state

```bash
rm -rf .agent-term
```

## Notes on live services

Live Matrix requires `matrix.enabled=true` in config and `AGENT_TERM_MATRIX_ACCESS_TOKEN` in the environment. Do not place access tokens in JSON config.

Live Agent Registry and Policy Fabric endpoints can be configured with `agentRegistration.endpointUrl` and `policyFabric.endpointUrl`. The local examples use fixtures so the flow remains runnable in CI and on developer machines without service credentials.
