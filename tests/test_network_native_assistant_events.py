from agent_term.cli import main


def test_record_network_door_plan_event(tmp_path, capsys):
    db_path = tmp_path / "events.sqlite3"

    exit_code = main(
        [
            "--db",
            str(db_path),
            "record",
            "agentplane",
            "network_door_plan",
            "!sourceos-network",
            "Plan enterprise/user network route",
            "--requires-approval",
            "--metadata-json",
            '{"evidenceKind":"NetworkDoorPlanEvidence","delegatedExecutor":"sourceosctl network plan"}',
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "source=agentplane" in captured.out
    assert "kind=network_door_plan" in captured.out
    assert "pending Policy Fabric approval" in captured.out


def test_record_byom_provider_route_event(tmp_path, capsys):
    db_path = tmp_path / "events.sqlite3"

    exit_code = main(
        [
            "--db",
            str(db_path),
            "record",
            "agentplane",
            "external_model_provider_route",
            "!sourceos-network",
            "Plan BYOM provider route",
            "--requires-approval",
            "--metadata-json",
            '{"evidenceKind":"ExternalModelProviderRouteEvidence","delegatedExecutor":"sourceosctl network provider"}',
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "source=agentplane" in captured.out
    assert "kind=external_model_provider_route" in captured.out
    assert "pending Policy Fabric approval" in captured.out


def test_record_native_assistant_bridge_event(tmp_path, capsys):
    db_path = tmp_path / "events.sqlite3"

    exit_code = main(
        [
            "--db",
            str(db_path),
            "record",
            "agentplane",
            "native_assistant_bridge",
            "!sourceos-native",
            "Plan native assistant bridge",
            "--requires-approval",
            "--metadata-json",
            '{"evidenceKind":"NativeAssistantBridgeEvidence","delegatedExecutor":"sourceosctl native-assistant plan"}',
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "source=agentplane" in captured.out
    assert "kind=native_assistant_bridge" in captured.out
    assert "pending Policy Fabric approval" in captured.out
