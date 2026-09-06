import json

from aicr.database import connect, rebuild


def test_rebuild_idempotent(tmp_path):
    d = tmp_path / "sessions" / "x"
    d.mkdir(parents=True)
    (d / "metadata.json").write_text(
        json.dumps({"id": "sess_x", "status": "completed"})
    )
    (d / "raw.jsonl").write_text(
        json.dumps({"id": "e1", "sequence": 1, "type": "session_start", "payload": {}})
        + "\n"
    )
    assert rebuild(tmp_path) == 1
    assert rebuild(tmp_path) == 1
    c = connect(tmp_path / "database/aicr.sqlite3")
    assert c.execute("select count(*) from events").fetchone()[0] == 1
