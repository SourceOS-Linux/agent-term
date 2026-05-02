from agent_term.agent_registry import AgentRegistration, AgentRegistryAdapter, InMemoryAgentRegistryBackend
from agent_term.adapters import AdapterResult
from agent_term.events import AgentTermEvent
from agent_term.matrix_adapter import MatrixAdapter
from agent_term.pipeline import OperatorDispatchPipeline
from agent_term.policy_fabric import ALLOW, DENY, InMemoryPolicyFabricBackend, PolicyDecision
from agent_term.policy_fabric import PolicyFabricAdapter
from agent_term.store import EventStore


class EchoAdapter:
    key = "echo"

    def supports(self, event: AgentTermEvent) -> bool:
        return event.source == self.key

    def handle(self, event: AgentTermEvent) -> AdapterResult:
        return AdapterResult(
            ok=True,
            source=self.key,
            kind="adapter_result",
            body=f"echo: {event.body}",
            metadata={"echoed": True},
        )


def make_store(tmp_path) -> EventStore:
    return EventStore(tmp_path / "events.sqlite3")


def make_pipeline(
    tmp_path,
    *,
    agents=None,
    decisions=None,
    adapters=None,
) -> tuple[OperatorDispatchPipeline, EventStore]:
    store = make_store(tmp_path)
    pipeline = OperatorDispatchPipeline(
        store=store,
        matrix_adapter=MatrixAdapter(),
        agent_registry_adapter=AgentRegistryAdapter(InMemoryAgentRegistryBackend(agents=agents or [])),
        policy_fabric_adapter=PolicyFabricAdapter(InMemoryPolicyFabricBackend(decisions=decisions or [])),
        adapters=adapters or (EchoAdapter(),),
    )
    return pipeline, store


def test_pipeline_dispatches_successful_event_and_records_snapshot(tmp_path):
    pipeline, store = make_pipeline(tmp_path)
    try:
        event = AgentTermEvent(
            channel="!echo",
            sender="@operator",
            kind="message",
            source="echo",
            body="hello",
        )

        outcome = pipeline.dispatch(event)
    finally:
        store.close()

    assert outcome.ok is True
    assert outcome.adapter_key == "echo"
    assert len(outcome.persisted_events) == 2
    assert outcome.persisted_events[-1].metadata["echoed"] is True
    assert "echo: hello" in outcome.snapshot.render_text()


def test_pipeline_blocks_unknown_registered_participant(tmp_path):
    pipeline, store = make_pipeline(tmp_path)
    try:
        event = AgentTermEvent(
            channel="!codex",
            sender="@operator",
            kind="agent_message",
            source="codex",
            body="do work",
        )

        outcome = pipeline.dispatch(event)
    finally:
        store.close()

    assert outcome.ok is False
    assert outcome.blocked_reason == "unknown_agent"
    assert len(outcome.persisted_events) == 2
    assert outcome.persisted_events[-1].source == "agent-registry"
    assert outcome.persisted_events[-1].metadata["deny_reason"] == "unknown_agent"


def test_pipeline_allows_registered_participant_after_registry_gate(tmp_path):
    pipeline, store = make_pipeline(
        tmp_path,
        agents=[
            AgentRegistration(
                agent_id="agent.codex",
                registry_ref="SocioProphet/agent-registry#agent.codex",
                spec_version="v0.1",
            )
        ],
        adapters=(EchoAdapter(),),
    )
    try:
        event = AgentTermEvent(
            channel="!codex",
            sender="@operator",
            kind="agent_message",
            source="echo",
            body="do work",
            metadata={"agent_id": "agent.codex"},
        )

        outcome = pipeline.dispatch(event)
    finally:
        store.close()

    assert outcome.ok is True
    assert [item.source for item in outcome.persisted_events] == ["echo", "agent-registry", "echo"]
    assert outcome.persisted_events[1].metadata["registry_status"] == "resolved"


def test_pipeline_blocks_policy_denial_before_adapter_dispatch(tmp_path):
    pipeline, store = make_pipeline(
        tmp_path,
        decisions=[
            PolicyDecision(
                decision_id="decision-deny",
                action="echo.context_pack",
                status=DENY,
                policy_ref="SocioProphet/policy-fabric#deny",
                reason="not authorized",
            )
        ],
    )
    try:
        event = AgentTermEvent(
            channel="!echo",
            sender="@operator",
            kind="context_pack",
            source="echo",
            body="sensitive",
            metadata={"sensitive_context": True, "matrix_encrypted": False},
        )

        outcome = pipeline.dispatch(event)
    finally:
        store.close()

    assert outcome.ok is False
    assert outcome.blocked_reason == "not authorized"
    assert outcome.persisted_events[-1].source == "policy-fabric"
    assert outcome.persisted_events[-1].metadata["policy_decision_id"] == "decision-deny"


def test_pipeline_blocks_unverified_encrypted_matrix_context_before_policy(tmp_path):
    pipeline, store = make_pipeline(tmp_path)
    try:
        event = AgentTermEvent(
            channel="!echo",
            sender="@operator",
            kind="context_pack",
            source="echo",
            body="sensitive",
            metadata={
                "sensitive_context": True,
                "matrix_encrypted": True,
                "matrix_e2ee_verified": False,
            },
        )

        outcome = pipeline.dispatch(event)
    finally:
        store.close()

    assert outcome.ok is False
    assert outcome.blocked_reason == "matrix_posture_blocked"
    assert outcome.persisted_events[-1].source == "matrix"
    assert outcome.persisted_events[-1].metadata["matrix_status"] == "blocked"


def test_pipeline_fails_closed_when_no_adapter_matches(tmp_path):
    pipeline, store = make_pipeline(tmp_path, adapters=())
    try:
        event = AgentTermEvent(
            channel="!unknown",
            sender="@operator",
            kind="message",
            source="unknown",
            body="hello",
        )

        outcome = pipeline.dispatch(event)
    finally:
        store.close()

    assert outcome.ok is False
    assert outcome.blocked_reason == "no_adapter"
    assert outcome.persisted_events[-1].source == "pipeline"
    assert outcome.persisted_events[-1].metadata["deny_reason"] == "no_adapter"


def test_pipeline_allows_sensitive_context_when_matrix_and_policy_allow(tmp_path):
    pipeline, store = make_pipeline(
        tmp_path,
        decisions=[
            PolicyDecision(
                decision_id="decision-allow",
                action="echo.context_pack",
                status=ALLOW,
                policy_ref="SocioProphet/policy-fabric#allow",
            )
        ],
    )
    try:
        event = AgentTermEvent(
            channel="!echo",
            sender="@operator",
            kind="context_pack",
            source="echo",
            body="sensitive",
            metadata={
                "sensitive_context": True,
                "matrix_encrypted": True,
                "matrix_e2ee_verified": True,
            },
        )

        outcome = pipeline.dispatch(event)
    finally:
        store.close()

    assert outcome.ok is True
    assert [item.source for item in outcome.persisted_events] == [
        "echo",
        "matrix",
        "policy-fabric",
        "echo",
    ]
    assert outcome.persisted_events[1].metadata["matrix_status"] == "allowed"
    assert outcome.persisted_events[2].metadata["admission_status"] == "admitted"
    assert outcome.persisted_events[3].metadata["echoed"] is True
