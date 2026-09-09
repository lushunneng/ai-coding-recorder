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
    "query", ['"', "AND", "a:b", 'foo"bar', "(", "*", "JWT token", "", "   "]
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
            {
                "id": "sess_A",
                "status": "running",
                "command": ["ls"],
                "provider": "generic",
            }
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


def test_event_ids_are_unique_across_sessions(tmp_path):
    from aicr.storage import RawWriter

    first = RawWriter(tmp_path / "one" / "raw.jsonl")
    second = RawWriter(tmp_path / "two" / "raw.jsonl")
    first.write("terminal_output", {})
    second.write("terminal_output", {})
    first.close()
    second.close()
    ids = []
    for path in (tmp_path / "one" / "raw.jsonl", tmp_path / "two" / "raw.jsonl"):
        ids.append(json.loads(path.read_text())["id"])
    assert len(set(ids)) == 2


def test_rebuild_removes_deleted_events(tmp_path):
    d = tmp_path / "sessions" / "x"
    d.mkdir(parents=True)
    (d / "metadata.json").write_text(
        json.dumps({"id": "sess_x", "status": "completed"})
    )
    raw = d / "raw.jsonl"
    raw.write_text(
        json.dumps(
            {
                "id": "e1",
                "sequence": 1,
                "type": "terminal_output",
                "payload": {"text": "old"},
            }
        )
        + "\n"
        + json.dumps(
            {
                "id": "e2",
                "sequence": 2,
                "type": "terminal_output",
                "payload": {"text": "gone"},
            }
        )
        + "\n"
    )
    rebuild(tmp_path)
    raw.write_text(raw.read_text().splitlines()[0] + "\n")
    assert rebuild(tmp_path) == 1
    assert search(tmp_path, "gone") == []


def test_json_export_redacts_payload(tmp_path):
    m = tmp_path / "metadata.json"
    m.write_text(json.dumps({"id": "sess_safe"}))
    (tmp_path / "raw.jsonl").write_text(
        json.dumps(
            {
                "sequence": 1,
                "type": "terminal_output",
                "payload": {"text": "AKIA1234567890ABCDEF"},
            }
        )
        + "\n"
    )
    rendered = __import__("aicr.exporter", fromlist=["render"]).render(m, "json")
    assert "AKIA1234567890ABCDEF" not in rendered
    assert "REDACTED:AWS_ACCESS_KEY" in rendered


def test_stale_lock_can_be_taken_over(tmp_path):
    import time

    from aicr.storage import SessionLock

    path = tmp_path / "lock"
    path.write_text(json.dumps({"pid": 99999999, "heartbeat_at": time.time() - 60}))
    lock = SessionLock(path, "sess_x")
    assert lock.takeover(timeout=30) is True
    lock.release()


def test_default_config_is_valid_toml(tmp_path):
    from aicr.config import ensure, load

    ensure(tmp_path)
    config = load(tmp_path, create=False)
    assert config.retention_days is None
    assert config.max_sessions is None
    assert config.max_total_bytes > 0


def test_record_propagates_wrapped_exit_code(monkeypatch, tmp_path):
    from aicr import cli

    monkeypatch.setattr(cli, "record", lambda command, root: 7)
    result = CLI.invoke(app, ["record", "bash"], env={"AICR_HOME": str(tmp_path)})
    assert result.exit_code == 7
