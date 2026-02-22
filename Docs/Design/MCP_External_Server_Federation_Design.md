# MCP External Server Federation Design

## Status
- Drafted: 2026-02-09
- Scope: MCP Unified extension for external MCP server federation

## Problem Statement
MCP Unified currently treats in-process modules as the single source of tools. This is intentional and hardened, but it limits integration with external MCP servers that already expose useful tools.

The goal is to add a safe, explicit federation layer so operators can register approved external MCP servers and make selected tools available through the existing `/api/v1/mcp/*` surface.

## Current Constraints
- MCP docs explicitly define MCP Unified as the supported production stack (`Docs/MCP/README.md`).
- Module autoload is restricted to local `modules.implementations` classes for safety (`tldw_Server_API/app/core/MCP_unified/server.py`).
- ACP sessions already accept `mcp_servers` and pass them downstream, but this is separate from MCP Unified tool federation.

## Goals
- Add external MCP server support without relaxing module autoload hardening.
- Keep the server-side contract stable: clients still call `/api/v1/mcp/tools` and `/api/v1/mcp/tools/execute`.
- Apply local policy and RBAC before forwarding calls to external servers.
- Provide clear observability and failure isolation per external server.
- Ship in phases: read-only first, write tools later.

## Non-Goals
- No direct, unfiltered proxying from public API to arbitrary remote MCP endpoints.
- No dynamic runtime registration from untrusted callers.
- No bypass of existing MCP Unified auth/RBAC/rate-limit layers.

## High-Level Architecture
1. **External Server Registry**
   - New config file (`mcp_external_servers.yaml`) declares approved servers and policies.
   - Parsed/validated at module initialization.

2. **External Federation Module**
   - New local MCP module (`external_federation_module.py`) loaded like any other module.
   - Exposes virtual tool names in a namespaced format:
     - `ext.<server_id>.<tool_name>`
   - Handles discovery cache + execute routing.

3. **Transport Adapters**
   - Adapter contracts for `websocket` and `stdio` backends.
   - Concrete adapters normalize external tool definitions/results into MCP Unified-compatible payloads.

4. **Policy Enforcement Layer**
   - Tool allowlist/denylist and write-policy checks.
   - Optional per-server limits (timeout/retries/circuit-breaker).
   - Local RBAC authorization uses namespaced virtual tool names.

5. **Observability + Audit**
   - Metrics labels include `source="external"` and `server_id`.
   - Audit includes caller identity, server_id, tool_name, duration, outcome.

## Request Flow
1. Client requests tool list (`GET /api/v1/mcp/tools`).
2. MCP Unified queries modules; federation module returns virtual external tools from cache/discovery.
3. Client executes tool (`POST /api/v1/mcp/tools/execute`).
4. MCP Unified resolves RBAC on `ext.<server_id>.<tool_name>`.
5. Federation module validates local policy and input.
6. Module routes to adapter (`websocket`/`stdio`) and forwards tool call.
7. Adapter normalizes response and returns module-safe result.
8. Metrics/audit emitted with external source tags.

## Config Schema (Proposed)
Top-level:
- `servers`: list of external server definitions.

Per server:
- `id`: stable identifier (used in tool namespace).
- `name`: display name.
- `enabled`: bool.
- `transport`: `websocket` or `stdio`.
- `websocket`: websocket transport options (required when `transport=websocket`).
- `stdio`: stdio transport options (required when `transport=stdio`).
- `auth`: optional auth material indirection via env refs.
- `policy`: local safety policy (allowlist/denylist/write controls).
- `timeouts`: connect/request timeouts.
- `retries`: retry controls.
- `circuit_breaker`: thresholds and recovery timing.

## Example Config
```yaml
servers:
  - id: docs
    name: Documentation MCP
    enabled: true
    transport: websocket
    websocket:
      url: "wss://mcp.example.com/ws"
      subprotocols: ["bearer"]
      headers:
        x-client: "tldw"
    auth:
      mode: bearer_env
      token_env: "EXTERNAL_MCP_DOCS_TOKEN"
    policy:
      allow_tool_patterns: ["docs.*", "search.*"]
      deny_tool_patterns: ["*.delete", "*.exec"]
      allow_writes: false
    timeouts:
      connect_seconds: 10
      request_seconds: 30

  - id: local_ci
    name: Local CI MCP
    enabled: false
    transport: stdio
    stdio:
      command: "/usr/bin/node"
      args: ["/opt/mcp/ci-server.js"]
      env:
        CI_MODE: "1"
      cwd: "/opt/mcp"
    policy:
      allow_tool_patterns: ["ci.*"]
      allow_writes: true
      require_write_confirmation: true
```

## Stdio Transport Security Requirements (Mandatory)
**Security Note (Critical):** `stdio.command`, `stdio.args`, `stdio.env`, and
`stdio.cwd` must be pre-vetted static operator configuration and must never be
derived from or influenced by external/user input.

- Command path validation:
  - `stdio.command` must resolve to an absolute canonical path (`realpath`) and
    match an allowlist of permitted executables.
  - Reject relative paths, traversal segments (`..`), and shell-style command
    strings.
  - Prevent symlink race attacks by validating the resolved target at config
    load and again immediately before process spawn; fail closed on mismatch.
- Args/env injection prevention:
  - Launch stdio processes with direct exec APIs (`shell=false`) only.
  - Validate `stdio.args` as structured tokens (no shell interpolation) and
    reject arguments that fail per-server policy/schema.
  - `stdio.env` must be key-whitelisted/sanitized; start from a minimal
    inherited environment and allow only approved keys/values.
- Working-directory constraints:
  - `stdio.cwd` must be an absolute canonical path under an operator-defined
    allowlisted root.
  - Reject `cwd` values that escape allowed roots after canonicalization, or
    point to unsafe writable locations.
- Process isolation/sandboxing:
  - Run stdio backends as a dedicated unprivileged service account.
  - Strongly prefer container/chroot isolation plus kernel policy controls
    (for example seccomp and SELinux/AppArmor profiles).
  - Apply resource and privilege restrictions (CPU/memory/file limits,
    no-new-privileges) to reduce blast radius.
- Runtime enforcement and audit checks:
  - Enforce all stdio validation checks at startup and at each execution
    attempt; reject on any policy violation.
  - Emit audit records for validation decisions and executions (server_id,
    resolved executable path, cwd, allowed env key set, caller, outcome).
  - Include periodic operational checks to detect config drift (allowlist,
    ownership/permissions, path target changes) and alert on violations.

## RBAC and Permission Model
- External tool permissions map to namespaced tool ids:
  - `tools.execute:ext.<server_id>.<tool_name>`
- Optional wildcard use for admins:
  - `tools.execute:ext.<server_id>.*`
- Discovery still respects catalogs and caller RBAC.
- Federation module never grants permissions; it only applies additional restrictions.

## Security Model
- Default deny for write tools unless explicitly enabled in server policy.
- Enforce allowlist/denylist before transport invocation.
- Validate arguments locally against discovered tool schemas when present.
- Store secrets in env vars; config references env variable names only.
- Require fail-closed stdio preflight validation for command path, args/env, and cwd.
- Add outbound host allowlist support (future hardening extension).

## Failure and Resilience
- Discovery failures do not crash MCP server startup; they mark server as degraded.
- Per-server circuit breaker opens after consecutive failures.
- Timeouts and retries are per server, not global.
- Partial availability: one broken external server does not disable others.

## Observability
- Metrics:
  - `mcp_external_requests_total{server_id,tool,status}`
  - `mcp_external_request_duration_seconds{server_id,tool}`
  - `mcp_external_discovery_failures_total{server_id}`
  - `mcp_external_circuit_state{server_id,state}`
- Audit fields:
  - `user_id`, `client_id`, `server_id`, `tool_name`, `request_id`, `outcome`, `duration_ms`
  - `transport`, `resolved_command_path`, `cwd`, `env_keys`, `policy_decision`

## Rollout Plan
1. **Phase 1 (Read-only federation MVP)**
   - Config loader + adapter contracts + federation module skeleton.
   - Tool discovery + execution only for tools classified as read.
2. **Phase 2 (Policy + RBAC hardening)**
   - Full allowlist/denylist enforcement + schema validation + richer audit.
3. **Phase 3 (Write support)**
   - Explicit write enablement, confirmation gates, idempotency integration.
4. **Phase 4 (Ops maturity)**
   - Admin APIs/UI for registry management and health visibility.

## Testing Strategy
- Unit tests:
  - Config parsing/validation (transport requirements, ID format, policy defaults).
  - Tool namespace mapping and routing.
- Integration tests:
  - Stub websocket and stdio adapters for discovery/execute flows.
  - RBAC denial and policy denial paths.
- Regression tests:
  - Ensure existing native MCP modules are unaffected when external module disabled.

## Initial Deliverables in This Draft
- Config schema models + loader helper.
- Transport adapter contracts (base interfaces + skeleton adapters).
- External federation module skeleton wired for future expansion.
