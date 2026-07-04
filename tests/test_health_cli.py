import json

from agent_term.health_cli import main


def test_health_cli_prints_default_warnings(capsys):
    exit_code = main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "matrix\twarn\tMatrix is using the offline/in-memory backend." in captured.out
    assert "agent-registry\twarn\tAgent Registry is using local fallback fixtures." in captured.out
    assert "policy-fabric\twarn\tPolicy Fabric is using local fallback fixtures." in captured.out


def test_health_cli_strict_returns_nonzero_for_warnings(capsys):
    exit_code = main(["--strict"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "matrix\twarn" in captured.out


def test_health_cli_json_output(capsys):
    exit_code = main(["--json"])

    captured = capsys.readouterr()
    value = json.loads(captured.out)
    assert exit_code == 0
    assert value["ok"] is True
    assert value["blocked"] is False
    assert {item["name"] for item in value["results"]} == {
        "matrix",
        "agent-registry",
        "policy-fabric",
    }


def test_health_cli_blocks_missing_fixture(tmp_path, capsys):
    config_path = tmp_path / "agent-term.json"
    config_path.write_text(
        json.dumps({"agentRegistration": {"fixturePath": str(tmp_path / "missing.json")}}),
        encoding="utf-8",
    )

    exit_code = main(["--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "agent-registry\tblocked\tAgent Registry fixture path does not exist." in captured.out


def test_health_cli_resolves_fixture_agent_tool_and_policy(tmp_path, capsys):
    agent_fixture = tmp_path / "agent-registry.json"
    agent_fixture.write_text(
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
    policy_fixture = tmp_path / "policy-fabric.json"
    policy_fixture.write_text(
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
    config_path = tmp_path / "agent-term.json"
    config_path.write_text(
        json.dumps(
            {
                "agentRegistration": {"fixturePath": str(agent_fixture)},
                "policyFabric": {"fixturePath": str(policy_fixture)},
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--config",
            str(config_path),
            "--agent-id",
            "agent.github",
            "--tool",
            "repo-write",
            "--policy-action",
            "github.pr.create",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "agent-registry\tok\tAgent and tool grant resolved: agent.github:repo-write" in captured.out
    assert "policy-fabric\tok\tPolicy decision resolved: github.pr.create -> allow" in captured.out
