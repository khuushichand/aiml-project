# ACP Runner (tldw-agent)

## Overview
The ACP runner allows the tldw server to work with any ACP-compatible agent by hosting the agent locally and proxying ACP traffic. The runner behaves as:
- An ACP **agent** to the server (upstream).
- An ACP **client** to a downstream ACP agent (spawned locally, one process per session).

This keeps ACP stdio compatibility intact for third-party agents while enabling server control.

## Goals
- Support any ACP agent that uses stdio transport.
- Spawn exactly one downstream agent process per ACP session.
- Provide client-side `fs/*` and `terminal/*` capabilities locally (allowlisted terminals).
- Keep configuration file driven (no CLI flags required for agent selection).

## Non-Goals (MVP)
- Streaming HTTP transport.
- Multi-session reuse of a single downstream agent process.
- Full ACP schema enforcement (beyond basic validation and required fields).

## Architecture
```
Server (ACP client)
  |  stdio or custom transport (future)
  v
ACP Runner (tldw-agent)
  |  stdio (ACP)
  v
Downstream ACP Agent (Codex, Claude Code, etc.)
```

## Message Flow
1. **initialize (upstream)**
   - Runner responds with protocolVersion=1 and minimal agentCapabilities.
2. **session/new (upstream)**
   - Runner validates absolute `cwd`.
   - Runner spawns downstream agent process and runs ACP `initialize` as client.
   - Runner calls downstream `session/new` and returns its sessionId upstream.
3. **session/prompt (upstream)**
   - Runner forwards to downstream.
   - Downstream `session/update` notifications are forwarded upstream.
   - Downstream `session/prompt` response is returned upstream.
4. **session/cancel (upstream)**
   - Runner forwards to downstream as notification.
5. **session/request_permission (downstream)**
   - Runner forwards to server and returns the decision to downstream.
   - If upstream is unavailable, runner may auto-allow or reject based on config.

## Capabilities
### Upstream (runner as agent)
- `session/new`, `session/prompt`, `session/cancel` supported.
- `session/load` disabled (loadSession=false) for MVP.
- `promptCapabilities`: text + resource link only (image/audio disabled).

### Downstream (runner as client)
- `fs.readTextFile`, `fs.writeTextFile` supported.
- `terminal` supported if execution is enabled and allowlist permits.

## File System Handling
- All ACP file paths must be absolute.
- Runner validates paths against workspace root and blocked patterns.
- `fs/read_text_file` returns `content` only (per ACP spec).
- `fs/write_text_file` returns `result: null` on success.

## Terminal Handling
- `terminal/*` commands use the existing allowlist (no arbitrary shell execution).
- `terminal/create` only allows commands whose argv prefix matches an allowlisted template.
- Output buffering respects ACP `outputByteLimit`, capped by config `max_output_bytes`.

## Configuration
New config fields in `~/.tldw-agent/config.yaml`:
```yaml
agent:
  command: "/path/to/agent"
  args: ["--stdio"]
  env: ["ENV_VAR=value"]
```

## Error Handling
- JSON-RPC errors follow standard codes (e.g., -32601 for unknown method).
- Downstream errors are passed upstream unchanged when possible.

## Security
- Workspace root is enforced per session.
- Blocked paths are denied even if absolute.
- Terminal execution remains allowlisted.

## Testing
- Framing tests for newline-delimited ACP stdio.
- Session mapping tests (sessionId -> downstream process).
- Terminal allowlist matching and output truncation tests.

## Future Work
- Dynamic capability reflection from downstream agent at initialize.
- Streamable HTTP transport (ACP draft) and WebSocket for server-controlled sessions.
- Session persistence and loadSession support.
