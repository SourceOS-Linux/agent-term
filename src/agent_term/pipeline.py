"""Operator dispatch pipeline.

The pipeline wires existing AgentTerm scaffolds together without becoming a new
authority plane. It records every input, gate, decision, adapter result, and TUI
snapshot source event in the local event log.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from agent_term.adapters import AdapterResult, AgentTermAdapter
from agent_term.agent_registry import AgentRegistryAdapter
from agent_term.events import AgentTermEvent
from agent_term.matrix_adapter import MatrixAdapter
from agent_term.participants import PARTICIPANT_AGENT_IDS
from agent_term.policy_fabric import PolicyFabricAdapter, requires_admission
from agent_term.store import EventStore
from agent_term.tui_model import TuiSnapshot, TuiSnapshotBuilder


@dataclass(frozen=True)
class DispatchOutcome:
    """Result of dispatching a single operator event."""

    ok: bool
    input_event: AgentTermEvent
    persisted_events: tuple[AgentTermEvent, ...]
    snapshot: TuiSnapshot
    blocked_reason: str | None = None
    adapter_key: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class DispatchPipelineConfig:
    """Pipeline policy switches."""

    require_matrix_posture_for_sensitive_context: bool = True
    require_agent_registry_for_participants: bool = True
    require_policy_for_admitted_events: bool = True


class OperatorDispatchPipeline:
    """Dispatches events through Matrix, Agent Registry, Policy Fabric, and adapters."""

    def __init__(
        self,
        *,
        store: EventStore,
        matrix_adapter: MatrixAdapter | None = None,
        agent_registry_adapter: AgentRegistryAdapter | None = None,
        policy_fabric_adapter: PolicyFabricAdapter | None = None,
        adapters: Iterable[AgentTermAdapter] = (),
        snapshot_builder: TuiSnapshotBuilder | None = None,
        config: DispatchPipelineConfig | None = None,
    ) -> None:
        self.store = store
        self.matrix_adapter = matrix_adapter
        self.agent_registry_adapter = agent_registry_adapter
        self.policy_fabric_adapter = policy_fabric_adapter
        self.adapters = tuple(adapters)
        self.snapshot_builder = snapshot_builder or TuiSnapshotBuilder()
        self.config = config or DispatchPipelineConfig()

    def dispatch(self, event: AgentTermEvent) -> DispatchOutcome:
        persisted: list[AgentTermEvent] = [self.store.append(event)]

        matrix_event = self._matrix_gate(event)
        if matrix_event is not None:
            persisted.append(self.store.append(matrix_event))
            if _is_blocked(matrix_event):
                return self._outcome(False, event, persisted, "matrix_posture_blocked")

        registry_events = self._agent_registry_gates(event)
        for registry_event in registry_events:
            persisted.append(self.store.append(registry_event))
            if _is_blocked(registry_event):
                return self._outcome(False, event, persisted, _deny_reason(registry_event))

        policy_event = self._policy_gate(event)
        if policy_event is not None:
            persisted.append(self.store.append(policy_event))
            if _is_blocked(policy_event):
                return self._outcome(False, event, persisted, _deny_reason(policy_event))

        adapter = self._select_adapter(event)
        if adapter is None:
            no_adapter = _result_event(
                event,
                AdapterResult(
                    ok=False,
                    source="pipeline",
                    kind="adapter_result",
                    body=f"No adapter found for {event.source}.{event.kind}",
                    metadata={"deny_reason": "no_adapter", "fail_closed": True},
                ),
            )
            persisted.append(self.store.append(no_adapter))
            return self._outcome(False, event, persisted, "no_adapter")

        result_event = _result_event(event, adapter.handle(event))
        persisted.append(self.store.append(result_event))
        return self._outcome(
            not _is_blocked(result_event),
            event,
            persisted,
            _deny_reason(result_event) if _is_blocked(result_event) else None,
            adapter_key=getattr(adapter, "key", None),
        )

    def _matrix_gate(self, event: AgentTermEvent) -> AgentTermEvent | None:
        if not self.config.require_matrix_posture_for_sensitive_context:
            return None
        if self.matrix_adapter is None:
            return None
        if not event.metadata.get("sensitive_context"):
            return None
        if event.source == "matrix" and event.kind == "matrix_e2ee_posture_check":
            return None

        gate_event = AgentTermEvent(
            channel=event.channel,
            sender="@agent-term",
            kind="matrix_e2ee_posture_check",
            source="matrix",
            body="Check Matrix E2EE posture before sensitive context release.",
            thread_id=event.thread_id,
            metadata={
                "request_event_id": event.event_id,
                "matrix_room_id": event.metadata.get("matrix_room_id"),
                "matrix_room_alias": event.metadata.get("matrix_room_alias"),
                "matrix_encrypted": event.metadata.get("matrix_encrypted"),
                "matrix_e2ee_verified": event.metadata.get("matrix_e2ee_verified"),
                "sensitive_context": True,
            },
        )
        return _result_event(gate_event, self.matrix_adapter.handle(gate_event))

    def _agent_registry_gates(self, event: AgentTermEvent) -> tuple[AgentTermEvent, ...]:
        if not self.config.require_agent_registry_for_participants:
            return ()
        if self.agent_registry_adapter is None:
            return ()

        agent_id = _agent_id(event)
        if not agent_id:
            return ()

        identity_request = AgentTermEvent(
            channel=event.channel,
            sender="@agent-term",
            kind="agent_identity",
            source="agent-registry",
            body=f"Resolve participant identity: {agent_id}",
            thread_id=event.thread_id,
            metadata={"request_event_id": event.event_id, "agent_id": agent_id},
        )
        identity_event = _result_event(
            identity_request,
            self.agent_registry_adapter.handle(identity_request),
        )
        if _is_blocked(identity_event):
            return (identity_event,)

        events = [identity_event]
        tool = event.metadata.get("tool") or event.metadata.get("tool_name")
        if tool:
            grant_request = AgentTermEvent(
                channel=event.channel,
                sender="@agent-term",
                kind="tool_grant",
                source="agent-registry",
                body=f"Resolve participant tool grant: {agent_id} -> {tool}",
                thread_id=event.thread_id,
                metadata={
                    "request_event_id": event.event_id,
                    "agent_id": agent_id,
                    "tool": tool,
                },
            )
            events.append(
                _result_event(grant_request, self.agent_registry_adapter.handle(grant_request))
            )
        return tuple(events)

    def _policy_gate(self, event: AgentTermEvent) -> AgentTermEvent | None:
        if not self.config.require_policy_for_admitted_events:
            return None
        if self.policy_fabric_adapter is None:
            return None
        if not requires_admission(event):
            return None
        if event.source == "policy-fabric":
            return None
        return _result_event(event, self.policy_fabric_adapter.handle(event))

    def _select_adapter(self, event: AgentTermEvent) -> AgentTermAdapter | None:
        for adapter in self.adapters:
            if adapter.supports(event):
                return adapter
        return None

    def _outcome(
        self,
        ok: bool,
        input_event: AgentTermEvent,
        persisted: list[AgentTermEvent],
        blocked_reason: str | None,
        *,
        adapter_key: str | None = None,
    ) -> DispatchOutcome:
        snapshot = self.snapshot_builder.build(self.store.tail(limit=500))
        return DispatchOutcome(
            ok=ok,
            input_event=input_event,
            persisted_events=tuple(persisted),
            snapshot=snapshot,
            blocked_reason=blocked_reason,
            adapter_key=adapter_key,
        )


def _result_event(request: AgentTermEvent, result: AdapterResult) -> AgentTermEvent:
    return result.to_event(request)


def _agent_id(event: AgentTermEvent) -> str | None:
    value = (
        event.metadata.get("agent_id")
        or event.metadata.get("agentRegistryId")
        or event.metadata.get("agent_registry_id")
        or PARTICIPANT_AGENT_IDS.get(event.source)
    )
    return str(value) if value else None


def _is_blocked(event: AgentTermEvent) -> bool:
    metadata = event.metadata
    if metadata.get("deny_reason"):
        return True
    if metadata.get("admission_status") == "denied":
        return True
    if metadata.get("registry_status") == "denied":
        return True
    if metadata.get("matrix_status") == "blocked":
        return True
    if metadata.get("fail_closed") and metadata.get("deny_reason"):
        return True
    return False


def _deny_reason(event: AgentTermEvent) -> str | None:
    value = event.metadata.get("deny_reason") or event.metadata.get("matrix_status")
    return str(value) if value else None
