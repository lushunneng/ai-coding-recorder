import json

import pytest
from typer.testing import CliRunner

from aicr.cli import app
from aicr.database import rebuild, search
from aicr.exporter import find_session
from aicr.storage import recover_file

CLI = CliRunner()


# --- FTS: special characters must not crash, and search must not full-rebuild each call


@pytest.mark.parametrize(
    "query", ["\"", "AND", "a:b", "foo\"bar", "(", "*", "JWT token", "", "   "]
)
def test_search_quoting_does_not_crash(tmp_path, query):
    d = tmp_path / "sessions" / "x"
    d.mkdir(parents=True)
    (d / "metadata.json").write_text(
        json.dumps({"id": "sess_x", "status": "completed"})
    )
    (d / "raw.jsonl").write_text(
        json.dumps(
            {
                "id": "e1",
                "sequence": 1,
                "type": "terminal_output",
                "payload": {"text": "hello world"},
            }
        )
        + "\n"
    )
    rebuild(tmp_path)
    search(tmp_path, query)  # must not raise


def test_search_matches_across_tokens(tmp_path):
    d = tmp_path / "sessions" / "x"
    d.mkdir(parents=True)
    (d / "metadata.json").write_text(
        json.dumps({"id": "sess_x", "status": "completed"})
    )
    (d / "raw.jsonl").write_text(
        json.dumps(
            {
                "id": "e1",
                "sequence": 1,
                "type": "terminal_output",
                "payload": {"text": "deploy token xyz"},
            }
        )
        + "\n"
    )
    rebuild(tmp_path)
    rows = search(tmp_path, 'deploy "token"')
    assert rows and rows[0][0] == "sess_x"


# --- recover_file must merge, not clobber, and not crash on missing raw


def test_recover_merges_metadata_and_keeps_fields(tmp_path):
    m = tmp_path / "metadata.json"
    m.write_text(
        json.dumps(
            {"id": "sess_A", "status": "running", "command": ["ls"], "provider": "generic"}
        )
    )
    raw = tmp_path / "raw.jsonl"
    raw.write_text(
        json.dumps({"id": "e1", "sequence": 1, "type": "session_start"}) + "\n"
    )
    recover_file(raw, m)
    meta = json.loads(m.read_text())
    assert meta["id"] == "sess_A"
    assert meta["status"] == "running"
    assert meta["command"] == ["ls"]
    assert meta["recovery"]["last_valid_sequence"] == 1


def test_recover_missing_raw_does_not_crash(tmp_path):
    m = tmp_path / "metadata.json"
    m.write_text(json.dumps({"id": "sess_A", "status": "running"}))
    state = recover_file(tmp_path / "raw.jsonl", m, scan=True)
    assert state["recovery"]["last_valid_sequence"] == 0
    assert state["recovery"]["interrupted"] is True


# --- import must not reuse event ids and must produce a rebuildable session


def test_import_events_have_unique_ids_and_rebuild_keeps_output(tmp_path):
    src = tmp_path / "transcript.txt"
    src.write_text("line one\nline two\n")
    h = tmp_path / "home"
    res = CLI.invoke(
        app,
        ["import", "--provider", "generic", "--file", str(src)],
        env={"AICR_HOME": str(h)},
    )
    assert res.exit_code == 0, res.output
    m = find_session(h, "latest")
    assert m is not None
    events = [
        json.loads(line) for line in m.with_name("raw.jsonl").open().read().splitlines()
    ]
    ids = [e["id"] for e in events]
    assert len(ids) == len(set(ids))
    seq = [e["sequence"] for e in events]
    assert seq == [1, 2]
    # rebuild must keep both events, not REPLACE-overwrite the output event
    assert rebuild(h) == 2
    assert search(h, "line")[0][0] == m.parent.name


# --- CLI must not register the same command twice


def test_record_command_not_duplicated():
    registrations = [
        c
        for c in app.registered_commands
        if getattr(c.callback, "__name__", None) == "record_cmd"
    ]
    assert len(registrations) == 1
    assert registrations[0].name == "record"
    res = CLI.invoke(app, ["--help"])
    assert res.exit_code == 0
    assert "record-cmd" not in res.output
    assert "record" in res.output
