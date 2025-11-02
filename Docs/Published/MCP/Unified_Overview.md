# MCP Unified - Overview

The MCP Unified module provides a production-grade Model Context Protocol surface in tldw_server. It exposes a secure JSON-RPC API over HTTP and WebSocket, an extensible module system for tools/resources/prompts, and operational endpoints for status, health, and metrics.

See also:
- Full User Guide: source tree at `Docs/MCP/Unified/User_Guide.md`
- Developer Guide: `Docs/MCP/Unified/Developer_Guide.md`
- Client Snippets (published): `MCP/Unified_Client_Snippets.md`

## Endpoints

- HTTP JSON-RPC
  - `POST /api/v1/mcp/request` - Process JSON-RPC (supports batch)
  - `POST /api/v1/mcp/tools/execute` - Convenience tool execution (auth required)

- Discovery & Modules
  - `GET /api/v1/mcp/tools` - List tools (auth required; RBAC-filtered)
    - Filters: `catalog` (name), `catalog_id` (id). `catalog_id` takes precedence.
  - `GET /api/v1/mcp/modules` - List registered modules (auth required)
  - `GET /api/v1/mcp/modules/health` - Module health (admin)

- Health & Metrics
  - `GET /api/v1/mcp/health` - Returns `{ "status": "healthy" }` (503 when unhealthy)
  - `GET /api/v1/mcp/status` - Server status summary
  - `GET /api/v1/mcp/metrics/prometheus` - Prometheus text exposition (admin unless `MCP_PROMETHEUS_PUBLIC=1`)

- WebSocket
  - `WS /api/v1/mcp/ws` - Full JSON-RPC over WS
    - Preferred auth: `Authorization: Bearer <token>` header or `Sec-WebSocket-Protocol: bearer,<token>`
    - Query tokens (`?token=` / `?api_key=`) are disabled by default (`MCP_WS_ALLOW_QUERY_AUTH=0`)

## Tool Catalogs (Discovery)

To avoid dumping very large catalogs, tools can be organized into named catalogs with team/org/global scopes. Discovery accepts a catalog filter, while RBAC still gates execution.

- HTTP: `GET /api/v1/mcp/tools?catalog=<name>` or `?catalog_id=<id>`
- JSON-RPC: `tools/list` with `{ "catalog": "name" }` or `{ "catalog_id": 42 }`
- Name resolution precedence: team > org > global; `catalog_id` takes precedence.
- Responses include `canExecute` on each tool; catalog membership does not grant permissions.

For a short copy-paste demo, see `MCP/Unified_Client_Snippets.md`.
