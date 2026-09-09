import json
import sqlite3
from pathlib import Path

SCHEMA = """CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY); CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, provider TEXT, status TEXT NOT NULL, started_at TEXT, ended_at TEXT, metadata_json TEXT NOT NULL); CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, sequence INTEGER NOT NULL, timestamp TEXT, type TEXT NOT NULL, payload_json TEXT NOT NULL, FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE, UNIQUE(session_id, sequence)); CREATE INDEX IF NOT EXISTS idx_events_session_seq ON events(session_id,sequence); CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);"""

FTS_SCHEMA = """CREATE VIRTUAL TABLE IF NOT EXISTS event_fts USING fts5(event_id UNINDEXED, session_id UNINDEXED, content);"""


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
    # Rebuild the FTS index in the same pass so search never does a full scan.
    populate_fts(c)
    c.commit()
    c.close()
    return count


def populate_fts(c: sqlite3.Connection):
    c.execute(FTS_SCHEMA)
    c.execute("DELETE FROM event_fts")
    for rowid, (eid, sid, _type, content) in enumerate(
        c.execute(
            "SELECT id, session_id, type, type || ' ' || payload_json FROM events"
        ),
        start=1,
    ):
        c.execute(
            "INSERT INTO event_fts(rowid, event_id, session_id, content) VALUES(?,?,?,?)",
            (rowid, eid, sid, content),
        )


def _quote_fts(query: str) -> str:
    """Escape a user query as a safe FTS5 string-literal phrase match."""
    tokens = [t for t in query.split() if t]
    return " ".join(f'"{t.replace(chr(34), chr(34) * 2)}"' for t in tokens)


def search(home: Path, query: str, limit: int = 20):
    if not query.strip():
        return []
    c = connect(home / "database" / "aicr.sqlite3")
    try:
        c.execute(FTS_SCHEMA)
        # Keep the FTS index in sync with the events table on demand, without a
        # full rebuild on every search. An empty or stale index (created by an
        # older version, or events added since the last rebuild) is rebuilt once.
        fts_rows = c.execute("SELECT COUNT(*) FROM event_fts").fetchone()[0]
        event_rows = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        if fts_rows != event_rows:
            populate_fts(c)
        rows = c.execute(
            "SELECT session_id, event_id, snippet(event_fts, 2, '[', ']', '...', 12) "
            "FROM event_fts WHERE event_fts MATCH ? LIMIT ?",
            (_quote_fts(query), limit),
        ).fetchall()
        return rows
    finally:
        c.close()
