import json
import sqlite3
from pathlib import Path

SCHEMA = """CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY); CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, provider TEXT, status TEXT NOT NULL, started_at TEXT, ended_at TEXT, metadata_json TEXT NOT NULL); CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, sequence INTEGER NOT NULL, timestamp TEXT, type TEXT NOT NULL, payload_json TEXT NOT NULL, FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE, UNIQUE(session_id, sequence)); CREATE INDEX IF NOT EXISTS idx_events_session_seq ON events(session_id,sequence); CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);"""


def connect(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path, timeout=5)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA busy_timeout=5000")
    c.executescript(SCHEMA)
    return c


def rebuild(home: Path):
    c = connect(home / "database" / "aicr.sqlite3")
    count = 0
    for meta in home.glob("sessions/**/metadata.json"):
        try:
            m = json.loads(meta.read_text())
            sid = m.get("id", meta.parent.name)
            c.execute(
                "INSERT INTO sessions(id,provider,status,started_at,ended_at,metadata_json) VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,ended_at=excluded.ended_at,metadata_json=excluded.metadata_json",
                (
                    sid,
                    m.get("provider", "generic"),
                    m.get("status", "unknown"),
                    str(m.get("started_at", "")),
                    str(m.get("ended_at", "")),
                    json.dumps(m),
                ),
            )
        except (OSError, ValueError, TypeError):
            continue
        for line in meta.with_name("raw.jsonl").open("rb"):
            try:
                e = json.loads(line)
                c.execute(
                    "INSERT OR REPLACE INTO events(id,session_id,sequence,timestamp,type,payload_json) VALUES(?,?,?,?,?,?)",
                    (
                        e["id"],
                        sid,
                        e["sequence"],
                        str(e.get("timestamp", "")),
                        e["type"],
                        json.dumps(e.get("payload", {}), ensure_ascii=False),
                    ),
                )
                count += 1
            except (ValueError, TypeError, KeyError):
                continue
    c.commit()
    c.close()
    return count


def search(home: Path, query: str, limit: int = 20):
    c = connect(home / "database" / "aicr.sqlite3")
    try:
        c.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS event_fts USING fts5(event_id UNINDEXED, session_id UNINDEXED, content)"
        )
        c.execute("DELETE FROM event_fts")
        c.execute(
            "INSERT INTO event_fts SELECT id, session_id, type || ' ' || payload_json FROM events"
        )
        rows = c.execute(
            "SELECT session_id, event_id, snippet(event_fts, 2, '[', ']', '...', 12) FROM event_fts WHERE event_fts MATCH ? LIMIT ?",
            (query, limit),
        ).fetchall()
        return rows
    finally:
        c.close()
