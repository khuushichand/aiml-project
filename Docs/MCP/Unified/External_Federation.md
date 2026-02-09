# External MCP Federation

> Part of the MCP Unified documentation set. See `Docs/MCP/Unified/README.md` for the full guide index.

This guide shows how to enable external MCP server federation through the built-in `external_federation` module.

## What It Does

- Registers approved upstream MCP servers from local config.
- Discovers upstream tools and exposes them as virtual tool names:
  - `ext.<server_id>.<tool_name>`
- Routes execution through MCP Unified auth/RBAC/rate limits, then through local federation policy.

## Activation

### 1) Enable the Module

Edit `tldw_Server_API/Config_Files/mcp_modules.yaml` and enable the existing module entry:

```yaml
modules:
  - id: external_federation
    class: tldw_Server_API.app.core.MCP_unified.modules.implementations.external_federation_module:ExternalFederationModule
    enabled: true
    settings:
      external_servers_config_path: tldw_Server_API/Config_Files/mcp_external_servers.yaml
```

### 2) Create External Server Registry

Start from:

- `tldw_Server_API/Config_Files/mcp_external_servers.example.yaml`

Copy to:

- `tldw_Server_API/Config_Files/mcp_external_servers.yaml`

You can override path with:

- `MCP_EXTERNAL_SERVERS_CONFIG=/absolute/path/to/mcp_external_servers.yaml`

### 3) Set Up Upstream Auth Environment Variables

If a server uses env-indirected auth (`bearer_env` or `api_key_env`), define the referenced env vars in your deployment environment.

Example:

```bash
export EXTERNAL_MCP_DOCS_TOKEN="..."
```

## Minimal Working Example

```yaml
servers:
  - id: docs
    name: "Docs MCP"
    enabled: true
    transport: websocket
    websocket:
      url: "wss://mcp.example.com/ws"
    auth:
      mode: bearer_env
      token_env: "EXTERNAL_MCP_DOCS_TOKEN"
    policy:
      allow_tool_patterns: ["docs.*"]
      deny_tool_patterns: ["*.delete", "*.exec"]
      allow_writes: false
      require_write_confirmation: true
    timeouts:
      connect_seconds: 10
      request_seconds: 30
```

After restart:

1. `GET /api/v1/mcp/tools`
2. Find tools named like `ext.docs.docs.search`
3. Execute with `POST /api/v1/mcp/tools/execute`

## Stdio Operators Quickstart

Use `transport: stdio` when the upstream MCP server runs as a local process.

```yaml
servers:
  - id: local_ci
    name: "Local CI MCP"
    enabled: true
    transport: stdio
    stdio:
      command: "python"
      args: ["-u", "/opt/mcp/ci_server.py"]
      env:
        CI_MODE: "1"
      cwd: "/opt/mcp"
    auth:
      mode: none
    policy:
      allow_tool_patterns: ["ci.*"]
      deny_tool_patterns: ["*.delete", "*.exec"]
      allow_writes: true
      require_write_confirmation: true
    timeouts:
      connect_seconds: 5
      request_seconds: 20
```

Operator notes:

- Stdio federation expects newline-delimited JSON-RPC on stdout and reads JSON-RPC requests from stdin.
- Use unbuffered process output when possible (for Python, run with `-u`) to avoid delayed responses/timeouts.
- Keep `cwd` explicit so relative paths resolve deterministically in production.
- Use `env` only for non-secret runtime flags; put secrets in deployment environment variables.

## Write Safety Defaults

- `allow_writes` defaults to `false`.
- `require_write_confirmation` defaults to `true`.
- Federated tools classified as write operations are blocked unless explicitly allowed.
- If confirmation is required, include:
  - `__confirm_write: true`
  - This marker is consumed locally and is not forwarded upstream.

## Security Notes

- Use explicit `allow_tool_patterns` and `deny_tool_patterns`; avoid broad wildcards in production.
- Treat external MCP endpoints as privileged dependencies.
- Keep upstream credentials in env vars, not committed config files.
- External tools are still subject to local RBAC and MCP Unified enforcement.

## Operational Checks

- `external.servers.list` shows per-server status, connectivity, discovery state, tool count, last error, and telemetry counters.
- `external.tools.refresh` refreshes discovery for one server (`server_id`) or all servers.

### Telemetry fields in `external.servers.list`

Each server row includes a `telemetry` object with:

- Connect counters: `connect_attempts`, `connect_successes`, `connect_failures`.
- Discovery counters: `discovery_attempts`, `discovery_successes`, `discovery_failures`.
- Call counters: `call_attempts`, `call_successes`, `call_failures`, `call_timeouts`, `call_upstream_errors`.
- Policy counters: `policy_denials`.
- Latency snapshots: `last_*_latency_ms` and `avg_*_latency_ms` for connect/discovery/call.
- Most recent discovered tool count: `last_discovered_tool_count`.
- Most recent telemetry-captured error: `last_error`.

## Troubleshooting

- `Unknown external virtual tool`:
  - Tool not currently discovered (refresh failed or policy filtered it).
- `Write confirmation required`:
  - Add `__confirm_write: true` when policy requires confirmation.
- `External MCP request timed out`:
  - Increase `timeouts.request_seconds` for that server.
- `requires websocket/stdio config`:
  - Transport-specific section missing in `mcp_external_servers.yaml`.
- Stdio server appears connected but tools fail:
  - Verify upstream process writes newline-delimited JSON-RPC responses to stdout.
  - Confirm unbuffered stdout (`python -u`) and process permissions for `cwd` and executable path.
