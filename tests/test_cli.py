from agent_term.cli import main


def test_record_memory_mesh_event(tmp_path, capsys):
    db_path = tmp_path / "events.sqlite3"

    exit_code = main(
        [
            "--db",
            str(db_path),
            "record",
            "memory-mesh",
            "memory_recall",
            "!memory-mesh",
            "Recall workroom context",
            "--requires-approval",
            "--metadata-json",
            '{"workroom":"pi-demo"}',
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "source=memory-mesh" in captured.out
    assert "pending Policy Fabric approval" in captured.out


def test_planes_show_new_hope(capsys):
    exit_code = main(["planes", "show", "new-hope"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "New Hope" in captured.out
    assert "semantic runtime" in captured.out.lower()
