from agent_term.agent_registry import AgentRegistration, InMemoryAgentRegistryBackend, ToolGrant
from agent_term.events import AgentTermEvent
from agent_term.participants import InMemoryParticipantBackend, RegisteredParticipantAdapter
from agent_term.policy_fabric import ALLOW, DENY, PENDING, InMemoryPolicyFabricBackend, PolicyDecision


def make_event(
    source: str,
    kind: str = "agent_message",
    metadata: dict[str, object] | None = None,
) -> AgentTermEvent:
    return AgentTermEvent(
        channel="!agents",
        sender="@operator",
        kind=kind,
        source=source,
        body="participant test event",
        thread_id="thread-1",
        metadata=metadata or {},
    )


def make_adapter(
    agents: list[AgentRegistration] | None = None,
    grants: list[ToolGrant] | None = None,
    decisions: list[PolicyDecision] | None = None,
) -> tuple[RegisteredParticipantAdapter, InMemoryParticipantBackend]:
    participant_backend = InMemoryParticipantBackend()
    adapter = RegisteredParticipantAdapter(
        registry_backend=InMemoryAgentRegistryBackend(agents=agents, grants=grants),
        policy_backend=InMemoryPolicyFabricBackend(decisions=decisions),
        participant_backend=participant_backend,
    )
    return adapter, participant_backend


def test_registered_participant_invokes_without_policy_for_non_side_effecting_message():
    adapter, participant_backend = make_adapter(
        agents=[
            AgentRegistration(
                agent_id="agent.hermes",
                registry_ref="SocioProphet/agent-registry#agent.hermes",
                spec_version="v0.1",
                session_id="session-hermes",
            )
        ]
    )

    result = adapter.handle(make_event("hermes"))

    assert result.ok is True
    assert result.metadata["agent_id"] == "agent.hermes"
    assert result.metadata["session_id"] == "session-hermes"
    assert result.metadata["dispatch_status"] == "invoked"
    assert len(participant_backend.invocations) == 1


def test_unknown_agent_fails_closed():
    adapter, participant_backend = make_adapter()

    result = adapter.handle(make_event("codex"))

    assert result.ok is False
    assert result.metadata["fail_closed"] is True
    assert result.metadata["deny_reason"] == "unknown_agent"
    assert participant_backend.invocations == []


def test_revoked_agent_fails_closed():
    adapter, participant_backend = make_adapter(
        agents=[
            AgentRegistration(
                agent_id="agent.openclaw",
                registry_ref="SocioProphet/agent-registry#agent.openclaw",
                spec_version="v0.1",
                revoked=True,
            )
        ]
    )

    result = adapter.handle(make_event("openclaw"))

    assert result.ok is False
    assert result.metadata["deny_reason"] == "agent_not_enabled"
    assert result.metadata["revoked"] is True
    assert participant_backend.invocations == []


def test_tool_grant_is_required_when_tool_is_requested():
    adapter, participant_backend = make_adapter(
        agents=[
            AgentRegistration(
                agent_id="agent.mcp",
                registry_ref="SocioProphet/agent-registry#agent.mcp",
                spec_version="v0.1",
            )
        ]
    )

    result = adapter.handle(make_event("mcp", "mcp_tool_call", {"tool": "memory-write"}))

    assert result.ok is False
    assert result.metadata["deny_reason"] == "tool_grant_not_active"
    assert result.metadata["tool"] == "memory-write"
    assert participant_backend.invocations == []


def test_side_effecting_registered_participant_requires_policy_decision():
    adapter, participant_backend = make_adapter(
        agents=[
            AgentRegistration(
                agent_id="agent.github",
                registry_ref="SocioProphet/agent-registry#agent.github",
                spec_version="v0.1",
            )
        ],
        grants=[ToolGrant(grant_id="grant.repo-write", agent_id="agent.github", tool="repo-write")],
    )

    result = adapter.handle(
        make_event("github", "github_mutation", {"tool": "repo-write", "action": "github.pr.create"})
    )

    assert result.ok is False
    assert result.metadata["deny_reason"] == "no_policy_decision"
    assert participant_backend.invocations == []


def test_side_effecting_registered_participant_with_grant_and_policy_invokes():
    adapter, participant_backend = make_adapter(
        agents=[
            AgentRegistration(
                agent_id="agent.github",
                registry_ref="SocioProphet/agent-registry#agent.github",
                spec_version="v0.1",
                session_id="session-github",
            )
        ],
        grants=[ToolGrant(grant_id="grant.repo-write", agent_id="agent.github", tool="repo-write")],
        decisions=[
            PolicyDecision(
                decision_id="decision-pr-create",
                action="github.pr.create",
                status=ALLOW,
                policy_ref="SocioProphet/policy-fabric#github-pr-create",
            )
        ],
    )

    result = adapter.handle(
        make_event("github", "github_mutation", {"tool": "repo-write", "action": "github.pr.create"})
    )

    assert result.ok is True
    assert result.metadata["dispatch_status"] == "invoked"
    assert result.metadata["agent_id"] == "agent.github"
    assert result.metadata["grant_id"] == "grant.repo-write"
    assert result.metadata["policy_decision_id"] == "decision-pr-create"
    assert len(participant_backend.invocations) == 1


def test_policy_denial_blocks_registered_participant():
    adapter, participant_backend = make_adapter(
        agents=[
            AgentRegistration(
                agent_id="agent.codex",
                registry_ref="SocioProphet/agent-registry#agent.codex",
                spec_version="v0.1",
            )
        ],
        decisions=[
            PolicyDecision(
                decision_id="decision-deny",
                action="codex.repo.mutate",
                status=DENY,
                policy_ref="SocioProphet/policy-fabric#codex",
                reason="repo mutation not approved",
            )
        ],
    )

    result = adapter.handle(
        make_event(
            "codex",
            "github_mutation",
            {"agent_id": "agent.codex", "action": "codex.repo.mutate"},
        )
    )

    assert result.ok is False
    assert result.metadata["deny_reason"] == "repo mutation not approved"
    assert result.metadata["policy_decision_id"] == "decision-deny"
    assert participant_backend.invocations == []


def test_pending_policy_decision_blocks_registered_participant():
    adapter, participant_backend = make_adapter(
        agents=[
            AgentRegistration(
                agent_id="agent.ci",
                registry_ref="SocioProphet/agent-registry#agent.ci",
                spec_version="v0.1",
            )
        ],
        decisions=[
            PolicyDecision(
                decision_id="decision-pending",
                action="ci.retry",
                status=PENDING,
                policy_ref="SocioProphet/policy-fabric#ci-retry",
            )
        ],
    )

    result = adapter.handle(make_event("ci", "ci_retry", {"action": "ci.retry"}))

    assert result.ok is False
    assert result.metadata["deny_reason"] == "policy_decision_pending"
    assert result.metadata["policy_decision_id"] == "decision-pending"
    assert participant_backend.invocations == []
