import json

from aicr.exporter import render


def test_html_escapes(tmp_path):
    m = tmp_path / "metadata.json"
    m.write_text(json.dumps({"id": "sess_test"}))
    (tmp_path / "raw.jsonl").write_text(
        json.dumps(
            {
                "sequence": 1,
                "type": "terminal_output",
                "payload": {"text": "<script>alert(1)</script>"},
            }
        )
        + "\n"
    )
    out = render(m, "html")
    assert "<script>alert" not in out and "&lt;script&gt;" in out


def test_empty_terminal_events_are_not_exported(tmp_path):
    m = tmp_path / "metadata.json"
    m.write_text(json.dumps({"id": "sess_empty"}))
    (tmp_path / "raw.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "sequence": 1,
                        "type": "terminal_output",
                        "payload": {"text": " \n\t"},
                    }
                ),
                json.dumps(
                    {
                        "sequence": 2,
                        "type": "terminal_output",
                        "payload": {"text": "visible"},
                    }
                ),
            ]
        )
        + "\n"
    )
    out = render(m, "markdown")
    assert "## 1. terminal_output" not in out
    assert "## 2. terminal_output" in out
    assert "visible" in out
