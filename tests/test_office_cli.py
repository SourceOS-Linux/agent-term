from agent_term.cli import main


def test_office_create_deck_records_governed_event(tmp_path, capsys):
    db_path = tmp_path / "events.sqlite3"

    exit_code = main(
        [
            "--db",
            str(db_path),
            "office",
            "create-deck",
            "!prophet-workspace",
            "--workroom",
            "workroom-demo-0001",
            "--title",
            "Demo Briefing Deck",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "source=prophet-workspace" in captured.out
    assert "kind=office_artifact_request" in captured.out
    assert "Request Office slide-deck generation" in captured.out
    assert "pending Policy Fabric approval" in captured.out


def test_office_inspect_records_non_approval_event(tmp_path, capsys):
    db_path = tmp_path / "events.sqlite3"

    exit_code = main(
        [
            "--db",
            str(db_path),
            "office",
            "inspect",
            "!prophet-workspace",
            "/workspace/output/demo.pptx",
            "--workroom",
            "workroom-demo-0001",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "source=prophet-workspace" in captured.out
    assert "Office artifact inspection" in captured.out
    assert "pending Policy Fabric approval" not in captured.out


def test_office_convert_records_governed_event(tmp_path, capsys):
    db_path = tmp_path / "events.sqlite3"

    exit_code = main(
        [
            "--db",
            str(db_path),
            "office",
            "convert",
            "!prophet-workspace",
            "/workspace/output/demo.docx",
            "--to",
            "pdf",
            "--workroom",
            "workroom-demo-0001",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "source=prophet-workspace" in captured.out
    assert "Request Office conversion to pdf" in captured.out
    assert "pending Policy Fabric approval" in captured.out
