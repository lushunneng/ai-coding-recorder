import json

from aicr.database import rebuild, search


def test_search(tmp_path):
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
                "payload": {"text": "JWT token"},
            }
        )
        + "\n"
    )
    rebuild(tmp_path)
    assert search(tmp_path, "JWT")[0][0] == "sess_x"
