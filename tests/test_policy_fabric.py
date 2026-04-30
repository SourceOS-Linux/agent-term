from agent_term.events import AgentTermEvent
from agent_term.policy_fabric import (
    ALLOW,
    DENY,
    PENDING,
    InMemoryPolicyFabricBackend,
    PolicyDecision,
    PolicyFabricAdapter,
    requires_admission,
)


def make_event(kind: str, source: str, metadata: dict[str, object] | None = None) -> AgentTermEvent:
    return AgentTermEvent(
        channel="!policyfabric",
        sender="@operator",
        kind=kind,
        source=source,
        body="policy test event",
        metadata=metadata or {},
    )


def test_non_sensitive_message_does_not_require_admission():
    event = make_event("message", "local")
    adapter = PolicyFabricAdapter(InMemoryPolicyFabricBackend())

    result = adapter.handle(event)

    assert requires_admission(event) is False
    assert result.ok is True
    assert result.metadata["admission_status"] == "not_required"


def test_side_effecting_event_without_decision_fails_closed():
    event = make_event("shell_session", "cloudshell-fog")
    adapter = PolicyFabricAdapter(InMemoryPolicyFabricBackend())

    result = adapter.handle(event)

    assert requires_admission(event) is True
    assert result.ok is False
    assert result.metadata["fail_closed"] is True
    assert result.metadata["deny_reason"] == "no_policy_decision"


def test_allow_decision_admits_event():
    decision = PolicyDecision(
        decision_id="decision-allow-shell",
        action="cloudshell-fog.shell_session",
        status=ALLOW,
        policy_ref="SocioProphet/policy-fabric#shell-session",
        obligations=("record-audit",),
    )
    adapter = PolicyFabricAdapter(InMemoryPolicyFabricBackend([decision]))

    result = adapter.handle(make_event("shell_session", "cloudshell-fog"))

    assert result.ok is True
    assert result.kind == "decision"
    assert result.metadata["admission_status"] == "admitted"
    assert result.metadata["policy_decision_id"] == "decision-allow-shell"
    assert result.metadata["policy_obligations"] == ["record-audit"]


def test_deny_decision_blocks_event():
    decision = PolicyDecision(
        decision_id="decision-deny-memory",
        action="memory-mesh.memory_recall",
        status=DENY,
        policy_ref="SocioProphet/policy-fabric#memory",
        reason="context release not authorized",
    )
    adapter = PolicyFabricAdapter(InMemoryPolicyFabricBackend([decision]))

    result = adapter.handle(make_event("memory_recall", "memory-mesh"))

    assert result.ok is False
    assert result.metadata["deny_reason"] == "context release not authorized"
    assert result.metadata["policy_status"] == DENY


def test_pending_decision_fails_closed():
    decision = PolicyDecision(
        decision_id="decision-pending-graph",
        action="meshrush.graph_view",
        status=PENDING,
        policy_ref="SocioProphet/policy-fabric#graph",
    )
    adapter = PolicyFabricAdapter(InMemoryPolicyFabricBackend([decision]))

    result = adapter.handle(make_event("graph_view", "meshrush"))

    assert result.ok is False
    assert result.metadata["deny_reason"] == "policy_decision_pending"
    assert result.metadata["policy_status"] == PENDING


def test_explicit_policy_action_is_used():
    decision = PolicyDecision(
        decision_id="decision-explicit",
        action="custom.context.release",
        status=ALLOW,
        policy_ref="SocioProphet/policy-fabric#custom",
    )
    adapter = PolicyFabricAdapter(InMemoryPolicyFabricBackend([decision]))
    event = make_event(
        "message",
        "local",
        {
            "policy_action": "custom.context.release",
            "requires_policy_admission": True,
        },
    )

    result = adapter.handle(event)

    assert result.ok is True
    assert result.metadata["policy_action"] == "custom.context.release"
    assert result.metadata["policy_decision_id"] == "decision-explicit"


def test_sensitive_context_flag_requires_admission():
    event = make_event("message", "local", {"sensitive_context": True})

    assert requires_admission(event) is True
