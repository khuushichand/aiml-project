# Agent Client Protocol (ACP) Module

This document summarizes the ACP integration status, layout, and how to run the
current server + runner flow. It is intended as a snapshot of progress and a
quick reference for the ACP module.

## Status Summary (Progress So Far)
- Server-side ACP client + endpoints are wired and available behind `/api/v1/acp/*`.
- ACP runner exists in `../tldw-agent` and proxies to a downstream ACP agent.
- Session lifecycle is supported: `session/new`, `session/prompt`, `session/cancel`,
  and `_tldw/session/close`.
- Downstream capabilities are reflected in `initialize`.
- Terminal tooling is allowlisted by config; file read/write is scoped to workspace.
- Tests added for the ACP runner (Go) and server endpoints (pytest).
- Smoke test validated via stub agent.

## Module Layout

### Server (tldw_server2)
- Core client:
  - `tldw_Server_API/app/core/Agent_Client_Protocol/stdio_client.py`
  - `tldw_Server_API/app/core/Agent_Client_Protocol/runner_client.py`
  - `tldw_Server_API/app/core/Agent_Client_Protocol/config.py`
- API schemas:
  - `tldw_Server_API/app/api/v1/schemas/agent_client_protocol.py`
- API endpoints:
  - `tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py`

### Runner (tldw-agent)
- ACP protocol + runner:
  - `../tldw-agent/internal/acp/conn.go`
  - `../tldw-agent/internal/acp/runner.go`
  - `../tldw-agent/internal/acp/terminal.go`
  - `../tldw-agent/internal/acp/stdio.go`
  - `../tldw-agent/internal/acp/types.go`
- Runner entrypoint:
  - `../tldw-agent/cmd/tldw-agent-acp/main.go`

### Test Assets
- Stub agent used for smoke testing:
  - `Helper_Scripts/acp_stub_agent.py`
- ACP unit tests (server):
  - `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_endpoints.py`
- ACP tests (runner):
  - `../tldw-agent/internal/acp/runner_test.go`
  - `../tldw-agent/internal/acp/terminal_test.go`

## Behavior Summary

### Server ACP Client
- Spawns the ACP runner via stdio and JSON-RPC line framing.
- Maintains a per-process client and queues session updates.
- Default permission requests are auto-cancelled.
- Supports env/config overrides for runner command/args/env/cwd.

### ACP Runner
- One downstream process per ACP session.
- Validates workspace roots and keeps file ops inside workspace.
- Handles allowlisted `terminal/*` tools with command templates and argument
  guards.
- Forwards `session/request_permission` upstream; cancels if upstream is missing.
- Caches downstream capabilities and reflects them in `initialize`.

## Configuration

### Server config.txt
Enable ACP routes in `tldw_Server_API/Config_Files/config.txt`:

```
[API-Routes]
stable_only = true
enable = tools, jobs, acp

[ACP]
runner_command = go
runner_args = ["run", "./cmd/tldw-agent-acp"]
runner_cwd = ../tldw-agent
runner_env = HOME=/absolute/path/to/tldw_Server_API/Config_Files/acp_runner_home,PYTHONUNBUFFERED=1
startup_timeout_ms = 10000
```

Notes:
- `stable_only = true` blocks experimental routes unless explicitly enabled. ACP
  must be listed in `enable`.
- `runner_env` should use an absolute `HOME` to avoid Go module cache errors
  (relative `GOMODCACHE` is rejected by Go).

### Environment overrides
```
ACP_RUNNER_COMMAND=/path/to/runner
ACP_RUNNER_ARGS='["--flag","value"]'
ACP_RUNNER_ENV='HOME=/abs/path,PYTHONUNBUFFERED=1'
ACP_RUNNER_CWD=/abs/path/to/runner/dir
ACP_RUNNER_STARTUP_TIMEOUT_MS=10000
```

### Downstream agent selection
The runner launches the downstream ACP agent based on:
`tldw_Server_API/Config_Files/acp_runner_home/.tldw-agent/config.yaml`

Example (Codex):
```
agent:
  command: "codex"
  args: []
```

Example (Claude Code):
```
agent:
  command: "claude"
  args: ["code"]
```

## Endpoints (Server)
- `POST /api/v1/acp/sessions/new`
- `POST /api/v1/acp/sessions/prompt`
- `POST /api/v1/acp/sessions/cancel`
- `POST /api/v1/acp/sessions/close`
- `GET /api/v1/acp/sessions/{session_id}/updates`

## Testing
- Server endpoints:
  - `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_acp_endpoints.py -m unit`
- Runner:
  - `go test ./internal/acp` (from `../tldw-agent`)

## Known Constraints
- ACP routes are gated by `stable_only` unless explicitly enabled.
- ACP runner uses stdio; ensure the runner executable is available in PATH or
  configured explicitly.
- Permission requests are currently auto-cancelled by the server client.

## Next Steps (Short List)
- Implement richer permission handling (approve/deny from UI).
- Add server-side integration tests that exercise a real ACP runner and agent.
- Expand agent capability reflection (session/update formats or future ACP fields).
