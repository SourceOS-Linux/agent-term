import json

from agent_term.cli import main
from agent_term.ops_history import context_pack_plan, policy_explain, redactions_pending, replay_plan


def test_policy_explain_active_multi_agent_room():
    plan = policy_explain("active-multi-agent-room")

    assert plan["dryRun"] is True
    assert plan["profile"] == "active-multi-agent-room"
    assert any(lane["lane"] == "redaction" for lane in plan["lanes"])
    assert plan["redactionPriority"]["invalidateContextPacks"] is True


def test_replay_plan_is_dry_run():
    plan = replay_plan("demo-search")

    assert plan["dryRun"] is True
    assert plan["threadId"] == "demo-search"
    assert plan["policyDecisionRefs"]
    assert "emit replay plan without side effects" in plan["steps"]


def test_context_pack_plan_disables_writeback():
    plan = context_pack_plan("pi-demo", topic="urn:srcos:topic:professional-intelligence")

    assert plan["dryRun"] is True
    assert plan["contextPackRef"] == "urn:srcos:context-pack:pi-demo-ops-history-demo"
    assert plan["retention"]["writebackAllowed"] is False
    assert "memory-mesh" in plan["targetConsumers"]
    assert "agentplane" in plan["targetConsumers"]


def test_redactions_pending_is_empty_but_configured():
    plan = redactions_pending()

    assert plan["dryRun"] is True
    assert plan["pending"] == []
    assert plan["policy"]["redactionPriority"] == "critical"


def test_cli_ops_history_policy(capsys):
    exit_code = main(["ops-history", "policy", "--profile", "active-multi-agent-room"])

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["planKind"] == "ops-history-policy-explain"
    assert payload["dryRun"] is True


def test_cli_ops_history_context_pack(capsys):
    exit_code = main(["ops-history", "context-pack", "--workroom", "pi-demo"])

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["planKind"] == "ops-history-context-pack"
    assert payload["retention"]["writebackAllowed"] is False
