from pathlib import Path

from agent_term.agent_registry_service import JsonFileAgentRegistryBackend
from agent_term.config import load_config
from agent_term.matrix_service import normalize_sync_payload
from agent_term.policy_fabric_service import JsonFilePolicyFabricBackend
from agent_term.events import AgentTermEvent


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "configs" / "agent-term.local.example.json"
AGENT_FIXTURE_PATH = REPO_ROOT / "configs" / "fixtures" / "agent-registry.local.example.json"
POLICY_FIXTURE_PATH = REPO_ROOT / "configs" / "fixtures" / "policy-fabric.local.example.json"
MATRIX_SYNC_FIXTURE_PATH = REPO_ROOT / "configs" / "fixtures" / "matrix-sync.local.example.json"


def test_local_example_config_loads_and_points_to_fixtures():
    config = load_config(CONFIG_PATH)

    assert config.workspace == "sourceos-local"
    assert config.agent_registration.fixture_path == "configs/fixtures/agent-registry.local.example.json"
    assert config.policy_fabric.fixture_path == "configs/fixtures/policy-fabric.local.example.json"
    assert config.participant_agent_id("github") == "agent.github"
    assert config.matrix.rooms["sourceosOps"] == "!sourceos-ops:example.org"


def test_agent_registry_fixture_resolves_quickstart_agent_and_grant():
    backend = JsonFileAgentRegistryBackend(AGENT_FIXTURE_PATH)

    agent = backend.resolve_agent("agent.github")
    grant = backend.resolve_tool_grant("agent.github", "repo-write")

    assert agent is not None
    assert agent.session_id == "session-agent-github-local"
    assert grant is not None
    assert grant.grant_id == "grant.repo-write"


def test_policy_fabric_fixture_resolves_quickstart_decisions():
    backend = JsonFilePolicyFabricBackend(POLICY_FIXTURE_PATH)

    allow = backend.evaluate(
        AgentTermEvent(
            channel="!github",
            sender="@operator",
            kind="github_mutation",
            source="github",
            body="Create PR",
            metadata={"policy_action": "github.pr.create"},
        )
    )
    deny = backend.evaluate(
        AgentTermEvent(
            channel="!github",
            sender="@operator",
            kind="github_mutation",
            source="github",
            body="Delete repo",
            metadata={"policy_action": "github.repo.delete"},
        )
    )

    assert allow is not None
    assert allow.is_allowed is True
    assert deny is not None
    assert deny.is_allowed is False
    assert deny.reason == "Repository deletion is not allowed from AgentTerm local operator flow."


def test_matrix_sync_fixture_normalizes_to_events():
    import json

    payload = json.loads(MATRIX_SYNC_FIXTURE_PATH.read_text(encoding="utf-8"))
    batch = normalize_sync_payload(payload)

    assert batch.next_batch == "local-batch-2"
    assert len(batch.events) == 2
    assert batch.events[0].event_id == "$local-message-1"
    assert batch.events[0].thread_root_event_id == "$local-thread-root"
    assert batch.events[1].membership == "join"
