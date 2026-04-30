from agent_term.agent_registry import (
    AgentRegistration,
    AgentRegistryAdapter,
    InMemoryAgentRegistryBackend,
    ToolGrant,
)
from agent_term.events import AgentTermEvent


def make_event(kind: str, metadata: dict[str, object]) -> AgentTermEvent:
    return AgentTermEvent(
        channel="!agent-registry",
        sender="@operator",
        kind=kind,
        source="agent-registry",
        body="registry test event",
        metadata=metadata,
    )


def test_resolves_registered_agent_identity():
    backend = InMemoryAgentRegistryBackend(
        agents=[
            AgentRegistration(
                agent_id="agent.codex",
                registry_ref="SocioProphet/agent-registry#agent.codex",
                spec_version="v0.1",
                session_id="session-1",
            )
        ]
    )
    adapter = AgentRegistryAdapter(backend)

    result = adapter.handle(make_event("agent_identity", {"agent_id": "agent.codex"}))

    assert result.ok is True
    assert result.metadata["agent_id"] == "agent.codex"
    assert result.metadata["registry_status"] == "resolved"
    assert result.metadata["session_id"] == "session-1"


def test_unknown_agent_fails_closed():
    adapter = AgentRegistryAdapter(InMemoryAgentRegistryBackend())

    result = adapter.handle(make_event("agent_identity", {"agent_id": "agent.unknown"}))

    assert result.ok is False
    assert result.metadata["fail_closed"] is True
    assert result.metadata["deny_reason"] == "unknown_agent"


def test_revoked_agent_fails_closed():
    backend = InMemoryAgentRegistryBackend(
        agents=[
            AgentRegistration(
                agent_id="agent.revoked",
                registry_ref="SocioProphet/agent-registry#agent.revoked",
                spec_version="v0.1",
                revoked=True,
            )
        ]
    )
    adapter = AgentRegistryAdapter(backend)

    result = adapter.handle(make_event("agent_identity", {"agent_id": "agent.revoked"}))

    assert result.ok is False
    assert result.metadata["deny_reason"] == "agent_not_enabled"
    assert result.metadata["revoked"] is True


def test_active_tool_grant_passes():
    backend = InMemoryAgentRegistryBackend(
        agents=[
            AgentRegistration(
                agent_id="agent.claude-code",
                registry_ref="SocioProphet/agent-registry#agent.claude-code",
                spec_version="v0.1",
                tool_grants=frozenset({"grant.repo-write"}),
            )
        ],
        grants=[
            ToolGrant(
                grant_id="grant.repo-write",
                agent_id="agent.claude-code",
                tool="repo-write",
            )
        ],
    )
    adapter = AgentRegistryAdapter(backend)

    result = adapter.handle(
        make_event("tool_grant", {"agent_id": "agent.claude-code", "tool": "repo-write"})
    )

    assert result.ok is True
    assert result.metadata["registry_status"] == "tool_granted"
    assert result.metadata["grant_id"] == "grant.repo-write"
    assert result.metadata["tool"] == "repo-write"


def test_missing_tool_grant_fails_closed():
    backend = InMemoryAgentRegistryBackend(
        agents=[
            AgentRegistration(
                agent_id="agent.openclaw",
                registry_ref="SocioProphet/agent-registry#agent.openclaw",
                spec_version="v0.1",
            )
        ]
    )
    adapter = AgentRegistryAdapter(backend)

    result = adapter.handle(
        make_event("tool_grant", {"agent_id": "agent.openclaw", "tool": "memory-write"})
    )

    assert result.ok is False
    assert result.metadata["deny_reason"] == "tool_grant_not_active"
    assert result.metadata["tool"] == "memory-write"


def test_result_can_be_converted_to_agentterm_event():
    backend = InMemoryAgentRegistryBackend(
        agents=[
            AgentRegistration(
                agent_id="agent.hermes",
                registry_ref="SocioProphet/agent-registry#agent.hermes",
                spec_version="v0.1",
            )
        ]
    )
    adapter = AgentRegistryAdapter(backend)
    request = make_event("agent_identity", {"agent_id": "agent.hermes"})

    result_event = adapter.handle(request).to_event(request)

    assert result_event.source == "agent-registry"
    assert result_event.metadata["request_event_id"] == request.event_id
    assert result_event.metadata["agent_id"] == "agent.hermes"
