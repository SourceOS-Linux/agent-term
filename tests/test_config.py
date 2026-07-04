import json

from agent_term.config import config_from_dict, load_config


def test_loads_example_config_shape(tmp_path):
    config_path = tmp_path / "agent-term.json"
    config_path.write_text(
        json.dumps(
            {
                "workspace": "sourceos",
                "defaultChannel": "!sourceos-ops",
                "eventStore": {"driver": "sqlite", "path": ".agent-term/events.sqlite3"},
                "matrix": {
                    "enabled": False,
                    "homeserverUrl": "https://matrix.example.org",
                    "userId": "@agent-term:example.org",
                    "deviceName": "agent-term-operator-console",
                    "rooms": {"sourceosOps": "!sourceos-ops:example.org"},
                    "requireEncryptedRoomPostureForSensitiveContext": True,
                },
                "agentRegistration": {
                    "requireRegisteredParticipants": True,
                    "failClosedWhenRegistryUnavailable": True,
                    "repository": "SocioProphet/agent-registry",
                    "requiredFor": ["codex", "githubBots"],
                    "fixturePath": "fixtures/agent-registry.json",
                    "endpointUrl": "https://agent-registry.example.org",
                    "tokenEnv": "AGENT_TERM_AGENT_REGISTRY_TOKEN",
                    "timeoutSeconds": 2.5,
                },
                "policyFabric": {
                    "repository": "SocioProphet/policy-fabric",
                    "fixturePath": "fixtures/policy-fabric.json",
                    "endpointUrl": "https://policy-fabric.example.org",
                    "tokenEnv": "AGENT_TERM_POLICY_FABRIC_TOKEN",
                    "timeoutSeconds": 3.5,
                },
                "participants": {
                    "codex": {
                        "enabled": False,
                        "mode": "repo-branch-pr",
                        "requireAgentRegistryResolution": True,
                        "agentRegistryId": "agent.codex",
                        "requirePolicyApprovalForMutation": True,
                    }
                },
                "planes": {
                    "policyFabric": {
                        "enabled": True,
                        "repository": "SocioProphet/policy-fabric",
                        "role": "decision-authority",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.workspace == "sourceos"
    assert config.default_channel == "!sourceos-ops"
    assert config.event_store.path == ".agent-term/events.sqlite3"
    assert config.matrix.homeserver_url == "https://matrix.example.org"
    assert config.matrix.rooms["sourceosOps"] == "!sourceos-ops:example.org"
    assert config.agent_registration.repository == "SocioProphet/agent-registry"
    assert config.agent_registration.required_for == ("codex", "githubBots")
    assert config.agent_registration.fixture_path == "fixtures/agent-registry.json"
    assert config.agent_registration.endpoint_url == "https://agent-registry.example.org"
    assert config.agent_registration.token_env == "AGENT_TERM_AGENT_REGISTRY_TOKEN"
    assert config.agent_registration.timeout_seconds == 2.5
    assert config.policy_fabric.repository == "SocioProphet/policy-fabric"
    assert config.policy_fabric.fixture_path == "fixtures/policy-fabric.json"
    assert config.policy_fabric.endpoint_url == "https://policy-fabric.example.org"
    assert config.policy_fabric.token_env == "AGENT_TERM_POLICY_FABRIC_TOKEN"
    assert config.policy_fabric.timeout_seconds == 3.5
    assert config.participant_agent_id("codex") == "agent.codex"
    assert config.participants["codex"].require_policy_approval_for_mutation is True
    assert config.planes["policyFabric"].repository == "SocioProphet/policy-fabric"


def test_defaults_are_safe_without_config_file():
    config = load_config(None)

    assert config.workspace == "sourceos"
    assert config.agent_registration.require_registered_participants is True
    assert config.agent_registration.token_env == "AGENT_TERM_AGENT_REGISTRY_TOKEN"
    assert config.agent_registration.timeout_seconds == 5.0
    assert config.policy_fabric.repository == "SocioProphet/policy-fabric"
    assert config.policy_fabric.token_env == "AGENT_TERM_POLICY_FABRIC_TOKEN"
    assert config.policy_fabric.timeout_seconds == 5.0
    assert config.matrix.require_encrypted_room_posture_for_sensitive_context is True
    assert config.pipeline_config().require_agent_registry_for_participants is True
    assert config.pipeline_config().require_matrix_posture_for_sensitive_context is True


def test_local_runtime_fixtures_are_parsed():
    config = config_from_dict(
        {
            "localRuntime": {
                "registeredAgents": ["agent.github"],
                "toolGrants": ["agent.github:repo-write:grant.repo-write"],
                "allowPolicies": ["github.pr.create"],
                "denyPolicies": ["github.repo.delete"],
                "pendingPolicies": ["ci.retry"],
            }
        }
    )

    assert config.local_runtime.registered_agents == ("agent.github",)
    assert config.local_runtime.tool_grants == ("agent.github:repo-write:grant.repo-write",)
    assert config.local_runtime.allow_policies == ("github.pr.create",)
    assert config.local_runtime.deny_policies == ("github.repo.delete",)
    assert config.local_runtime.pending_policies == ("ci.retry",)


def test_pipeline_config_reflects_matrix_and_registry_posture():
    config = config_from_dict(
        {
            "matrix": {"requireEncryptedRoomPostureForSensitiveContext": False},
            "agentRegistration": {"requireRegisteredParticipants": False},
        }
    )

    pipeline_config = config.pipeline_config()

    assert pipeline_config.require_matrix_posture_for_sensitive_context is False
    assert pipeline_config.require_agent_registry_for_participants is False
    assert pipeline_config.require_policy_for_admitted_events is True
