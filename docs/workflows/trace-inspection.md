# Trace inspection (v1.5)

Trace config is in `configs/mcp.yaml` under `mcp.trace`:
- `enabled`
- `path`
- `include_query_text`
- `include_source_ids`

Default trace file:
- `data/traces/mcp_traces.jsonl`

Each line is a JSON event containing fields such as:
- `timestamp`
- `tool`
- `ok`
- `trace_id`
- `mode_used`
- `elapsed_ms`
- optional `query` and `source_ids` depending on config

Notes:
- Trace logging is fail-safe and should not break tool execution.
- For privacy-sensitive contexts, set `include_query_text: false`.
