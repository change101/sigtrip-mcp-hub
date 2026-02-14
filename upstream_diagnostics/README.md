# Upstream Diagnostics

This folder stores capability snapshots and scenario results for each upstream MCP.

Naming rule for provider folders:
- Start from upstream URL from env (e.g. `MCP_PROVIDER_SIGTRIP_URL`)
- Remove `https://` (and `http://` if present)
- Replace `/` with `-`
- Replace `.` with `_`

Example:
- `https://hotel.sigtrip.ai/mcp` -> `hotel_sigtrip_ai-mcp`

Each provider folder contains:
- `tools_list.raw.json` (raw upstream tools/list result)
- `tools_list.names.json` (extracted tool names)
- `scenarios/*.json` (request + response snapshots)
- `SUMMARY.md` (human-readable support/debug notes)
