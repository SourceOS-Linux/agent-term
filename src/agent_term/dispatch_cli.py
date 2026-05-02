"""CLI entry point for dispatching an event through the operator pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent_term.agent_registry import AgentRegistration, AgentRegistryAdapter
from agent_term.agent_registry import InMemoryAgentRegistryBackend, ToolGrant
from agent_term.agentplane import AgentPlaneAdapter, InMemoryAgentPlaneBackend
from agent_term.cloudshell_fog import CloudShellFogAdapter, InMemoryCloudShellFogBackend
from agent_term.events import AgentTermEvent
from agent_term.knowledge import (
    HolmesAdapter,
    InMemoryHolmesBackend,
    InMemoryMemoryMeshBackend,
    InMemoryMeshRushBackend,
    InMemoryNewHopeBackend,
    InMemorySherlockSearchBackend,
    InMemorySlashTopicsBackend,
    MemoryMeshAdapter,
    MeshRushAdapter,
    NewHopeAdapter,
    SherlockSearchAdapter,
    SlashTopicsAdapter,
)
from agent_term.matrix_adapter import MatrixAdapter
from agent_term.participants import InMemoryParticipantBackend, RegisteredParticipantAdapter
from agent_term.pipeline import OperatorDispatchPipeline
from agent_term.policy_fabric import ALLOW, DENY, PENDING, InMemoryPolicyFabricBackend, PolicyDecision
from agent_term.policy_fabric import action_for_event
from agent_term.store import DEFAULT_DB_PATH, EventStore
from agent_term.workspace import (
    InMemoryProphetWorkspaceBackend,
    InMemorySociosphereBackend,
    ProphetWorkspaceAdapter,
    SociosphereAdapter,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-term-dispatch",
        description="Dispatch one AgentTerm event through Matrix, Agent Registry, Policy Fabric, adapters, EventStore, and snapshot generation.",
    )
    parser.add_argument("source", help="Event source/adapter key, e.g. memory-mesh, codex, matrix.")
    parser.add_argument("kind", help="Event kind, e.g. memory_recall, agent_message, context_pack.")
    parser.add_argument("channel", help="Logical channel or Matrix room alias/ID.")
    parser.add_argument("body", help="Event body.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to local AgentTerm SQLite event log.")
    parser.add_argument("--sender", default="@operator")
    parser.add_argument("--thread-id")
    parser.add_argument("--metadata-json", default="{}")
    parser.add_argument("--agent-id", help="Agent Registry ID to include on the event and pre-register locally.")
    parser.add_argument("--register-agent", action="append", default=[], help="Register an agent ID in the local in-memory registry. Repeatable.")
    parser.add_argument("--grant", action="append", default=[], help="Grant in form agent_id:tool[:grant_id]. Repeatable.")
    parser.add_argument("--tool", help="Tool name requested by this event.")
    parser.add_argument("--allow-policy", action="append", default=[], help="Allow policy action. Repeatable.")
    parser.add_argument("--deny-policy", action="append", default=[], help="Deny policy action. Repeatable.")
    parser.add_argument("--pending-policy", action="append", default=[], help="Pending policy action. Repeatable.")
    parser.add_argument("--policy-action", help="Explicit policy action for this event.")
    parser.add_argument("--policy-ref", default="local://policy-fabric/dispatch-cli")
    parser.add_argument("--sensitive-context", action="store_true")
    parser.add_argument("--matrix-encrypted", action="store_true")
    parser.add_argument("--matrix-verified", action="store_true")
    parser.add_argument("--show-snapshot", action="store_true", help="Print the generated operator snapshot after dispatch.")
    return parser


def parse_metadata(metadata_json: str) -> dict[str, object]:
    try:
        value = json.loads(metadata_json)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"metadata must be valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit("metadata must decode to a JSON object")
    return value


def build_event(args: argparse.Namespace) -> AgentTermEvent:
    metadata = parse_metadata(args.metadata_json)
    if args.agent_id:
        metadata["agent_id"] = args.agent_id
    if args.tool:
        metadata["tool"] = args.tool
    if args.policy_action:
        metadata["policy_action"] = args.policy_action
    if args.sensitive_context:
        metadata["sensitive_context"] = True
    if args.matrix_encrypted:
        metadata["matrix_encrypted"] = True
        metadata["matrix_e2ee_verified"] = bool(args.matrix_verified)

    return AgentTermEvent(
        channel=args.channel,
        sender=args.sender,
        kind=args.kind,
        source=args.source,
        body=args.body,
        thread_id=args.thread_id,
        metadata=metadata,
    )


def build_registry_backend(args: argparse.Namespace) -> InMemoryAgentRegistryBackend:
    agent_ids = set(args.register_agent)
    if args.agent_id:
        agent_ids.add(args.agent_id)

    agents = [
        AgentRegistration(
            agent_id=agent_id,
            registry_ref=f"local://agent-registry/{agent_id}",
            spec_version="local-dev",
            session_id=f"session-{agent_id.replace('.', '-')}",
        )
        for agent_id in sorted(agent_ids)
    ]
    grants = [_parse_grant(raw) for raw in args.grant]
    return InMemoryAgentRegistryBackend(agents=agents, grants=grants)


def _parse_grant(raw: str) -> ToolGrant:
    parts = raw.split(":")
    if len(parts) not in {2, 3}:
        raise SystemExit("--grant must use form agent_id:tool[:grant_id]")
    agent_id, tool = parts[0], parts[1]
    grant_id = parts[2] if len(parts) == 3 else f"grant.{agent_id}.{tool}"
    return ToolGrant(grant_id=grant_id, agent_id=agent_id, tool=tool)


def build_policy_backend(args: argparse.Namespace, event: AgentTermEvent) -> InMemoryPolicyFabricBackend:
    decisions: list[PolicyDecision] = []
    for action in args.allow_policy:
        decisions.append(_decision(action, ALLOW, args.policy_ref))
    for action in args.deny_policy:
        decisions.append(_decision(action, DENY, args.policy_ref, reason="denied by dispatch CLI"))
    for action in args.pending_policy:
        decisions.append(_decision(action, PENDING, args.policy_ref))

    if args.policy_action and args.policy_action not in {decision.action for decision in decisions}:
        decisions.append(_decision(args.policy_action, ALLOW, args.policy_ref))
    elif args.sensitive_context and not decisions:
        decisions.append(_decision(action_for_event(event), ALLOW, args.policy_ref))

    return InMemoryPolicyFabricBackend(decisions)


def _decision(action: str, status: str, policy_ref: str, reason: str | None = None) -> PolicyDecision:
    return PolicyDecision(
        decision_id=f"decision.{status}.{action}",
        action=action,
        status=status,
        policy_ref=policy_ref,
        reason=reason,
    )


def build_pipeline(args: argparse.Namespace, event: AgentTermEvent, store: EventStore) -> OperatorDispatchPipeline:
    registry_backend = build_registry_backend(args)
    policy_backend = build_policy_backend(args, event)
    participant_backend = InMemoryParticipantBackend()

    adapters = (
        MatrixAdapter(),
        CloudShellFogAdapter(InMemoryCloudShellFogBackend()),
        AgentPlaneAdapter(InMemoryAgentPlaneBackend()),
        SociosphereAdapter(InMemorySociosphereBackend()),
        ProphetWorkspaceAdapter(InMemoryProphetWorkspaceBackend()),
        SlashTopicsAdapter(InMemorySlashTopicsBackend()),
        MemoryMeshAdapter(InMemoryMemoryMeshBackend()),
        NewHopeAdapter(InMemoryNewHopeBackend()),
        SherlockSearchAdapter(InMemorySherlockSearchBackend()),
        HolmesAdapter(InMemoryHolmesBackend()),
        MeshRushAdapter(InMemoryMeshRushBackend()),
        RegisteredParticipantAdapter(registry_backend, policy_backend, participant_backend),
    )

    return OperatorDispatchPipeline(
        store=store,
        matrix_adapter=MatrixAdapter(),
        agent_registry_adapter=AgentRegistryAdapter(registry_backend),
        policy_fabric_adapter=PolicyFabricAdapter(policy_backend),
        adapters=adapters,
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    event = build_event(args)
    store = EventStore(Path(args.db))
    try:
        outcome = build_pipeline(args, event, store).dispatch(event)
        status = "ok" if outcome.ok else "blocked"
        print(f"dispatch_status={status}")
        if outcome.adapter_key:
            print(f"adapter={outcome.adapter_key}")
        if outcome.blocked_reason:
            print(f"blocked_reason={outcome.blocked_reason}")
        print(f"persisted_events={len(outcome.persisted_events)}")
        print(f"input_event_id={outcome.input_event.event_id}")
        if args.show_snapshot:
            print(outcome.snapshot.render_text())
        return 0 if outcome.ok else 1
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
