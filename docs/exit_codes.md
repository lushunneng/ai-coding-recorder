# AICR Exit Codes

| Code | Meaning |
|---:|---|
| 0 | AICR and wrapped command completed successfully |
| 1 | Wrapped command exited non-zero; AICR recorded the exit |
| 2 | CLI usage or argument error |
| 3 | Configuration invalid or cannot be read |
| 4 | Data directory or permission error |
| 5 | PTY unavailable or command cannot start |
| 6 | Recording degraded; raw data exists but content may be incomplete |
| 7 | Recovery or JSONL validation error |
| 8 | Export/render error; raw data remains intact |
| 9 | Lock held by a live session |
| 10 | Unsupported Provider history/format |
| 11 | Storage quota prevents starting a new session |
| 12 | Internal Recorder error |

When the wrapped process exits non-zero, AICR returns code 1 unless a more severe Recorder error occurred. The terminal output must include session ID and paths for every recording outcome.
