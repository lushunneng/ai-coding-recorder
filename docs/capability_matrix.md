# AICR Capability Matrix

| Field/capability | pty | native | import |
|---|---|---|---|
| Terminal input/output bytes | observed | observed/confirmed | confirmed from source |
| stdout/stderr separation | unavailable (`merged`) | confirmed when source provides it | confirmed when source provides it |
| User/assistant messages | unavailable | confirmed only with verified mapping | confirmed only with verified mapping |
| Tool calls/results | unavailable | confirmed only with verified mapping | confirmed only with verified mapping |
| File edits and diffs | unavailable | confirmed only with verified mapping | confirmed only with verified mapping |
| Exit status/lifecycle | confirmed | confirmed | source-dependent |
| Provider-specific fields | unavailable | confirmed with fixture | preserved in provider_data |

Generic PTY semantic events have a maximum confidence of `observed`. Native support requires a provider version range, real or sanitized fixtures, event mapping tests, malformed-input behavior, duplicate-import behavior, and end-to-end export verification. Unsupported native formats remain `unsupported`; PTY remains available.
