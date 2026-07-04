import json

from agent_term.config import config_from_dict
from agent_term.health import BLOCKED, OK, WARN, HealthChecker, HealthCheckOptions


def test_health_checker_defaults_to_warning_for_local_fallbacks():
    report = HealthChecker(config_from_dict({})).run()

    statuses = {result.name: result.status for result in report.results}
    assert statuses == {
        "matrix": WARN,
        "agent-registry": WARN,
        "policy-fabric": WARN,
    }
    assert report.ok is True
    assert report.blocked is False


def test_health_checker_blocks_missing_agent_registry_fixture():
    config = config_from_dict({"agentRegistration": {"fixturePath": "/missing/agent-registry.json"}})

    result = HealthChecker(config).check_agent_registry(HealthCheckOptions())

    assert result.status == BLOCKED
    assert "fixture path does not exist" in result.message


def test_health_checker_resolves_agent_and_tool_from_fixture(tmp_path):
    fixture = tmp_path / "agent-registry.json"
    fixture.write_text(
        json.dumps(
            {
                "agents": [{"agent_id": "agent.github", "spec_version": "v1"}],
                "tool_grants": [
                    {"grant_id": "grant.repo-write", "agent_id": "agent.github", "tool": "repo-write"}
                ],
            }
        ),
        encoding="utf-8",
    )
    config = config_from_dict({"agentRegistration": {"fixturePath": str(fixture)}})

    result = HealthChecker(config).check_agent_registry(
        HealthCheckOptions(agent_id="agent.github", tool="repo-write")
    )

    assert result.status == OK
    assert result.metadata["agent_id"] == "agent.github"
    assert result.metadata["grant_id"] == "grant.repo-write"


def test_health_checker_blocks_missing_policy_fabric_fixture():
    config = config_from_dict({"policyFabric": {"fixturePath": "/missing/policy-fabric.json"}})

    result = HealthChecker(config).check_policy_fabric(HealthCheckOptions())

    assert result.status == BLOCKED
    assert "fixture path does not exist" in result.message


def test_health_checker_resolves_policy_from_fixture(tmp_path):
    fixture = tmp_path / "policy-fabric.json"
    fixture.write_text(
        json.dumps(
            {
                "decisions": [
                    {
                        "decision_id": "decision.allow.github.pr.create",
                        "action": "github.pr.create",
                        "status": "allow",
                        "policy_ref": "fixture://policy/github-pr-create",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    config = config_from_dict({"policyFabric": {"fixturePath": str(fixture)}})

    result = HealthChecker(config).check_policy_fabric(
        HealthCheckOptions(policy_action="github.pr.create")
    )

    assert result.status == OK
    assert result.metadata["policy_decision_id"] == "decision.allow.github.pr.create"


def test_health_report_json_shape():
    report = HealthChecker(config_from_dict({})).run()

    value = report.to_dict()

    assert value["ok"] is True
    assert value["blocked"] is False
    assert len(value["results"]) == 3
