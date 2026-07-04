import json
from pathlib import Path

from agent_term.operator_smoke import run_local_operator_smoke
from agent_term.operator_smoke_cli import main
from agent_term.store import EventStore


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "configs" / "agent-term.local.example.json"
MATRIX_SYNC_FIXTURE = REPO_ROOT / "configs" / "fixtures" / "matrix-sync.local.example.json"


def test_local_operator_smoke_runner_executes_quickstart_flow(tmp_path):
    result = run_local_operator_smoke(
        workdir=tmp_path,
        config_path=CONFIG_PATH,
        matrix_sync_fixture=MATRIX_SYNC_FIXTURE,
    )

    assert result.ok is True
    assert [step.name for step in result.steps] == [
        "check",
        "matrix-normalize-sync",
        "matrix-send",
        "github-dispatch",
        "memory-dispatch",
        "snapshot",
    ]
    assert (tmp_path / "events.sqlite3").exists()
    assert (tmp_path / "matrix-state.json").exists()

    state = json.loads((tmp_path / "matrix-state.json").read_text(encoding="utf-8"))
    assert state["next_batch"] == "local-batch-2"

    store = EventStore(tmp_path / "events.sqlite3")
    try:
        events = store.tail(limit=100)
    finally:
        store.close()

    sources = [event.source for event in events]
    assert "matrix" in sources
    assert "matrix-service" in sources
    assert "agent-registry" in sources
    assert "policy-fabric" in sources
    assert "github" in sources
    assert "memory-mesh" in sources


def test_operator_smoke_cli_reports_success(tmp_path, capsys):
    exit_code = main(
        [
            "--workdir",
            str(tmp_path),
            "--config",
            str(CONFIG_PATH),
            "--matrix-sync-fixture",
            str(MATRIX_SYNC_FIXTURE),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "smoke_status=ok" in captured.out
    assert "check\tok\texit=0" in captured.out
    assert "snapshot\tok\texit=0" in captured.out
