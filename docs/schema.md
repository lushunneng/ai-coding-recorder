# AICR Event Schema

## Raw Event

`raw.jsonl` is the append-only source of truth. Each line is one JSON object with `id`, `session_id`, `sequence` (integer, unique per session), `timestamp` (UTC ISO-8601), `monotonic_ns` (integer), `type`, and `payload`. Payload preserves bytes: UTF-8 uses `{encoding: utf-8, text: ...}`; invalid bytes use `{encoding: base64, data: ...}`.

Raw types: `session_start`, `terminal_input`, `terminal_output`, `process_exit`, `session_end`, `error`, `warning`.

## Semantic Event

`events.jsonl` is derived from Raw and may be rebuilt. It adds `schema_version`, `actor`, `provider`, `capture_mode`, `stream`, `confidence`, `provider_data`, `is_partial`, `content_ref`, and `metadata`. Generic PTY uses `stream=merged`; semantic confidence cannot exceed `observed`.

Confidence values: `confirmed` (source and fixture verified), `observed` (directly observed with limited semantics), `inferred` (explicit deterministic rule), `unknown` (cannot determine).

## Assets and chunks

Inline payload threshold is 256 KiB. Larger content is stored under `assets/`. A single asset is limited to 64 MiB; larger content is split. Each chunk records `content_ref`, `chunk_of`, zero-based `chunk_index`, `chunk_total`, byte count, and SHA-256. Readers group by `chunk_of`, sort by `chunk_index`, verify count/size/hash, then concatenate.

## Session states

`running` transitions once to `completed`, `failed`, or `interrupted`. Recovery never rewrites `raw.jsonl`; it records the last valid sequence and skipped sequences in metadata.

Schema and adapter versions are independent. Unknown fields must be preserved by importers.
