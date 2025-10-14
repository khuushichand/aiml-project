# MCP Unified – PRD Snapshot (v0.1)

Goal: Production-ready Model Context Protocol (MCP) server with secure multi‑tenant auth, modular tools, reliable retrieval, and full observability.

## Scope (Phase 1)
- Protocol: JSON‑RPC 2.0 over WebSocket and HTTP
- Security: AuthNZ JWT, MCP JWT (back‑compat), API key, RBAC (AuthNZ DB)
- Rate limits: Per user/client with Redis optional
- Modules: Media, Notes, Prompts, Chats, Characters, Knowledge aggregator
- Retrieval: FTS‑first with normalized schema and safe_config session params
- Observability: Health endpoints, Prometheus metrics, OTEL spans

## Not in Scope (Phase 1)
- Tool sandboxing/isolation beyond RBAC
- Cross‑instance distributed session state
- Token refresh endpoint (future)
- Full semantic/vector retrieval in Knowledge (FTS‑only for now)

## Current Status
- Server, Protocol, Auth, RBAC (AuthNZ‑backed), Rate limiting: Implemented
- WebSocket caps (global/per‑IP) + metrics: Implemented
- Modules:
  - Media: Implemented; health check completed (connectivity/writable).
  - Notes, Prompts, Chats, Characters: Implemented (FTS‑only)
  - Knowledge: search across sources; get() supports notes/media (others WIP)
- Metrics: JSON and Prometheus endpoints (admin‑gated by default)
- Tests: Unit + integration present; MCP tests gated by `RUN_MCP_TESTS`

## Gaps / TODO
- Knowledge.get support for chats/characters/prompts
- Robust module health checks (beyond Media)
- Token refresh endpoint (`/api/v1/mcp/auth/refresh`)
- Hardening docs for production (network placement, TLS, WAF)
- CI: Enable `RUN_MCP_TESTS=1` in a targeted workflow stage

## Success Criteria
- AuthZ: Denied tool exec returns 403 with actionable hint (covered by tests)
- Stability: WebSocket caps enforced; ping loop keeps idle connections healthy
- Metrics: Prometheus scrape returns without errors; p95 request latency tracked
- Security: No hardcoded secrets; secrets via env; RBAC pulls from AuthNZ DB
- Docs: README accurate; developer guide links; PRD snapshot in repo

## Rollout Plan
1) Finalize gaps (above), add tests
2) Soak in staging with Prometheus/Grafana alerts (see Docs/Deployment/Monitoring)
3) Enable MCP in production behind auth proxy; keep Prometheus gated unless required

