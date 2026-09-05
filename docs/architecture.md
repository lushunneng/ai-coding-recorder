# AICR Architecture

## Boundaries

- `capture/`: PTY allocation, terminal forwarding, process groups, signals and resize.
- `core/`: event models, Session state machine and normalization contracts.
- `storage/`: append-only Raw JSONL, derived Semantic JSONL, SQLite migrations and repositories.
- `renderers/`: streaming Markdown/HTML/JSON/Bundle exporters and redaction.
- `adapters/`: Generic, Native and Import adapters with capability declarations.
- `cli/`: Typer commands and exit-code mapping.

## Data flow

PTY recorder -> `raw.jsonl` -> normalization -> `events.jsonl` -> post-session SQLite index/renderers. The PTY hot path never writes SQLite, performs FTS, or renders documents. Derived outputs are disposable and rebuildable.

## Reliability

One Raw writer owns per-session sequence generation. JSON lines are flushed in chunks and fsynced for lifecycle/error checkpoints. Session locks use PID, process start time, heartbeat and takeover ID; stale takeover uses atomic CAS rename and read-back verification. Export writes a snapshot to a temporary file and atomically renames it.

## Security

AICR_HOME defaults to `~/.aicr`, directory mode 0700 and file mode 0600. Environment variables are not recorded wholesale. Export redaction is separate from Raw storage. HTML escapes all recorded content and uses a restrictive CSP; no CDN or network access is required.

## Concurrency and recovery

Multiple sessions write separate JSONL files. SQLite uses WAL, foreign keys and busy timeout; indexing occurs after session_end or in a background worker. `recover` validates complete lines without modifying Raw; `recover --scan` records skipped sequences. `rebuild-index` skips active sessions and is idempotent.
