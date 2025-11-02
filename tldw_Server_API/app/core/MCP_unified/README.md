# MCP Unified Module - Production Ready

## Overview
A secure, production-ready Model Context Protocol implementation that consolidates MCP v1 and v2 with enterprise-grade features.

## ✅ What's Been Built

### Core Components
- **Secure Configuration** (`config.py`) - All secrets from environment variables
- **MCP Server** (`server.py`) - WebSocket and HTTP support with connection management
- **Protocol Handler** (`protocol.py`) - Full JSON-RPC 2.0 implementation
- **Module System** (`modules/`) - Extensible module architecture with health checks

### Security Layer (All vulnerabilities fixed!)
- **JWT Authentication** (`auth/jwt_manager.py`) - No hardcoded secrets, token rotation
- **RBAC** (`auth/rbac.py`) - Fine-grained permissions with role inheritance
- **Rate Limiting** (`auth/rate_limiter.py`) - Token bucket and sliding window algorithms

### Production Features
- **Health Monitoring** - Automatic health checks with circuit breakers
- **Metrics Collection** (`monitoring/metrics.py`) - Prometheus-compatible metrics
- **Connection Pooling** - Efficient resource management
- **Graceful Degradation** - Circuit breaker pattern for resilience

## 🚀 Quick Start

### 1. Set Required Environment Variables

```bash
# Generate secure secrets
export MCP_JWT_SECRET=$(openssl rand -base64 32)
export MCP_API_KEY_SALT=$(openssl rand -base64 32)

# Optional configuration
export MCP_LOG_LEVEL=INFO
export MCP_RATE_LIMIT_RPM=60
export MCP_DATABASE_URL=sqlite+aiosqlite:///./Databases/mcp_unified.db
```

### 2. Install Dependencies

```bash
pip install fastapi uvicorn loguru pydantic PyJWT passlib bcrypt aiosqlite
```

### 3. Run Tests

```bash
python -m pytest tldw_Server_API/app/core/MCP_unified/tests/ -v
```

### 4. Start Server

```python
from tldw_Server_API.app.core.MCP_unified import get_mcp_server

server = get_mcp_server()
await server.initialize()
```

## 📁 Directory Structure

```
MCP_unified/
├── __init__.py              # Main exports
├── config.py                # Secure configuration
├── server.py                # MCP server
├── protocol.py              # Protocol handler
├── auth/                    # Authentication & authorization
│   ├── jwt_manager.py       # JWT management (no hardcoded secrets!)
│   ├── rbac.py             # Role-based access control
│   └── rate_limiter.py    # Rate limiting
├── modules/                 # Module system
│   ├── base.py             # Base module interface
│   ├── registry.py         # Module registry
│   └── implementations/    # Module implementations
├── monitoring/              # Observability
│   └── metrics.py          # Metrics collection
└── tests/                   # Test suite
    └── test_basic_functionality.py

```

## 🔒 Security Features

### No Hardcoded Secrets
- All sensitive configuration from environment variables
- Validation on startup to prevent use of default values
- Secure random generation if not provided (with warnings)

### Authentication & Authorization
- JWT with access and refresh tokens
- Token rotation for enhanced security
- Fine-grained RBAC with permission inheritance
- API key management with PBKDF2 hashing

### WebSocket Hardening
- Require WS authentication in production (`MCP_WS_AUTH_REQUIRED=true`)
- Explicitly set allowed origins (`MCP_WS_ALLOWED_ORIGINS=http://your-ui:port`)

### Client Certificate (mTLS) via Reverse Proxy
- Enforce client certs by enabling `MCP_CLIENT_CERT_REQUIRED=true`
- Configure the header asserted by your proxy (default `x-ssl-client-verify`)
- Set `MCP_CLIENT_CERT_HEADER_VALUE` to the exact success sentinel (e.g., `SUCCESS`)
- Only trusted proxies may assert this header - set `MCP_TRUSTED_PROXY_IPS` to your proxy CIDRs
- X-Forwarded-For is honored only from trusted proxies (`MCP_TRUST_X_FORWARDED=true` if desired)

Note: In test mode (`TEST_MODE=true`) the harness peer is treated as trusted for convenience.

### Rate Limiting
- Multiple algorithms (Token Bucket, Sliding Window)
- Per-user and per-endpoint limits
- Redis support for distributed deployments
- Automatic cleanup of old entries

### Input Validation
- Pydantic models for all inputs
- SQL injection prevention
- XSS protection
- Request size limits

### SSRF Protection (Media Ingestion)
- Media module only accepts `http/https` URLs
- Rejects `.local` and hosts resolving to loopback/private/link-local/reserved/multicast IPs
- Enforce allowed ports (`80,443` by default)
- Optional allowlist per deployment via module settings:
  - `allowed_domains`: ["example.com", "cdn.example.com"]
  - `allowed_ports`: [80, 443]
  - `blocked_domains`: ["unwanted.tld"]

## 🎯 Key Improvements Over Original

| Feature | Original MCP v1/v2 | Unified MCP |
|---------|-------------------|-------------|
| JWT Secret | Hardcoded in code | Environment variable |
| Rate Limiting | Basic/None | Advanced with Redis support |
| Health Checks | None | Automatic with caching |
| Circuit Breakers | None | Built-in with configurable thresholds |
| Metrics | None | Prometheus-compatible |
| Input Validation | Basic | Comprehensive with Pydantic |
| Error Handling | Generic | Detailed with proper codes |
| Testing | Minimal | Comprehensive test suite |

## 📊 API Endpoints

### Authentication

MCP Unified supports multiple authentication methods:

- AuthNZ JWT (preferred): `Authorization: Bearer <AuthNZ access token>`
- MCP JWT (back-compat): `Authorization: Bearer <MCP JWT>`
- API Key (HTTP): `X-API-KEY: <api_key>`
- API Key (WebSocket): query param `api_key=<api_key>`

When using API keys, RequestContext.metadata includes `org_id` and `team_id` (if present on the key) so modules can scope behavior.

### WebSocket
```
ws://localhost:8000/api/v1/mcp/ws?client_id=<id>&token=<jwt>
# or
ws://localhost:8000/api/v1/mcp/ws?client_id=<id>&api_key=<api_key>
# Recommended (headers/subprotocol):
#   Authorization: Bearer <token>
#   Sec-WebSocket-Protocol: bearer,<token>
```

### HTTP Endpoints
- `POST /api/v1/mcp/request` - Process MCP request
- `GET /api/v1/mcp/status` - Server status
- `GET /api/v1/mcp/metrics` - Server metrics (admin only)
- `GET /api/v1/mcp/tools` - List available tools (auth required; RBAC-filtered)
- `POST /api/v1/mcp/tools/execute` - Execute tool (auth required)
- `GET /api/v1/mcp/health` - Health check

#### Tool Discovery & Catalogs
- Reduce discovery size by grouping tools into catalogs (global, org, team).
- Filtering:
  - HTTP: `GET /api/v1/mcp/tools?catalog=<name>` or `?catalog_id=<id>`
  - JSON-RPC: `tools/list` with `{ catalog?: string, catalog_id?: number }`
- Name resolution respects caller context with precedence `team > org > global`; `catalog_id` takes precedence.
- Responses include `canExecute` per tool; catalog membership does not grant execution rights.
- See `Docs/MCP/mcp_tool_catalogs.md` for admin/manager APIs to create/manage catalogs.

## 🛡️ Production Checklist

- Set secure secrets: `MCP_JWT_SECRET`, `MCP_API_KEY_SALT`
- Enforce WS auth: `MCP_WS_AUTH_REQUIRED=true`
- Configure `MCP_WS_ALLOWED_ORIGINS`
- Keep WS query-parameter auth disabled (default): `MCP_WS_ALLOW_QUERY_AUTH=0`; use headers/subprotocol instead
- If using mTLS via proxy: set `MCP_CLIENT_CERT_REQUIRED=true`, `MCP_CLIENT_CERT_HEADER_VALUE`, and `MCP_TRUSTED_PROXY_IPS`
- Keep rate limiting enabled; configure Redis for multi-instance
- Do not use wildcard CORS in production

## 🧪 Testing

Run the comprehensive test suite:

```bash
# All tests
pytest tldw_Server_API/app/core/MCP_unified/tests/ -v

# Specific test categories
pytest -m unit        # Unit tests
pytest -m integration # Integration tests
pytest -m security    # Security tests
```

## 📝 Module Development

Create a new module by extending `BaseModule`:

```python
from tldw_Server_API.app.core.MCP_unified.modules import BaseModule

class MyModule(BaseModule):
    async def on_initialize(self):
        # Initialize resources
        pass

    async def check_health(self) -> Dict[str, bool]:
        return {"service": True}

    async def get_tools(self) -> List[Dict[str, Any]]:
        return [...]

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]):
        # Execute tool with circuit breaker
        return await self.execute_with_circuit_breaker(
            self._do_work, arguments
        )
```

## ➕ Adding Modules (Autoload)

Modules can be autoloaded via YAML or environment variables:

- YAML (default path `tldw_Server_API/Config_Files/mcp_modules.yaml`):
```
modules:
  - id: media
    class: tldw_Server_API.app.core.MCP_unified.modules.implementations.media_module:MediaModule
    enabled: true
    name: Media
    settings:
      # Per-user default (single-user mode example): Databases/user_databases/1/Media_DB_v2.db
      # For multi-user setups, run a module instance per user or pass user-specific db_path at runtime.
      db_path: Databases/user_databases/1/Media_DB_v2.db
    # Optional runtime controls
    # Limit concurrent operations per module instance
    max_concurrent: 16
    # Circuit breaker tuning
    circuit_breaker_threshold: 3
    circuit_breaker_timeout: 30
    circuit_breaker_backoff_factor: 2.0
    circuit_breaker_max_timeout: 180
```

- Environment variable (comma-separated list):
```
export MCP_MODULES="example=tldw_Server_API.app.core.MCP_unified.modules.implementations.template_module:TemplateModule"
```

- Optional quick-start flag:
```
export MCP_ENABLE_MEDIA_MODULE=true
```

Tool results include the serving module:
```
{"content": [...], "module": "Media", "tool": "search_media"}
```

See `Docs/MCP/Unified/Modules.md` for a complete guide.

## 🚢 Production Deployment

### Environment Variables (Required)
```bash
MCP_JWT_SECRET=<strong-random-secret>
MCP_API_KEY_SALT=<strong-random-secret>
```

### Environment Variables (Optional)
```bash
MCP_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/mcp
MCP_REDIS_URL=redis://localhost:6379/0
MCP_RATE_LIMIT_ENABLED=true
MCP_RATE_LIMIT_USE_REDIS=1               # Use Redis-backed limiter (multi-node)
MCP_RATE_LIMIT_RPM_INGESTION=30         # Optional per-category rate; default = RPM
MCP_RATE_LIMIT_BURST_INGESTION=5
MCP_RATE_LIMIT_RPM_READ=120
MCP_METRICS_ENABLED=true
MCP_LOG_LEVEL=INFO
MCP_WS_AUTH_REQUIRED=1                  # Require authenticated WS (prod hardening)
MCP_WS_ALLOWED_ORIGINS=https://your-ui.example.com  # Enforce WS Origin; comma-separated list
MCP_WS_ALLOW_QUERY_AUTH=0               # Disable ?token= / ?api_key= query auth (use headers/subprotocol)
```

## 🔐 Production Hardening

Recommended hardening steps for Internet-exposed deployments:

- Require WS auth and enforce allowed origins
  - Set `MCP_WS_AUTH_REQUIRED=1`
  - Set `MCP_WS_ALLOWED_ORIGINS=https://your-ui.example.com` (comma-separated if multiple)
  - Prefer header-based auth for WS: `Authorization: Bearer <token>` or `X-API-KEY`
  - Optional: Subprotocol auth: `Sec-WebSocket-Protocol: bearer,<token>`
- Disable query-string authentication for WS
  - `MCP_WS_ALLOW_QUERY_AUTH=0` (default). If a client passes `?token=` or `?api_key=`, the server ignores it and logs a warning.
- Rate limiting
  - Enable Redis limiter for multi-node and avoid fail-open: `MCP_RATE_LIMIT_USE_REDIS=1`
  - The server falls back to an in-memory token bucket if Redis is unavailable.
- Restrict module autoloads
  - Only classes under `tldw_Server_API.app.core.MCP_unified.modules.implementations` are allowed when auto-loading.
- Write tools safety & validation (Security knobs)
  - `MCP_DISABLE_WRITE_TOOLS=0|1` - If set to `1`, the protocol blocks all write-capable tools (category `ingestion`/`management`).
  - `MCP_VALIDATE_INPUT_SCHEMA=0|1` - Validate tool `inputSchema` at the protocol layer (required fields, primitive types, unknown fields).
  - `MCP_IDEMPOTENCY_TTL_SECONDS` - TTL for protocol-level idempotency cache for write tools (default: 300s).
  - `MCP_IDEMPOTENCY_CACHE_SIZE` - Max entries for idempotency cache (LRU, default: 512).
  - Client hint: pass `idempotencyKey` in JSON-RPC `tools/call` params to dedupe writes.
- Demo auth (dev only)
  - `MCP_ENABLE_DEMO_AUTH` is for development/testing. If enabled in non-debug environments, the server logs a loud warning.
  - `MCP_DEMO_AUTH_SECRET` must be set to a strong value; the token endpoint also requires loopback/private clients and debug/test mode.

### Security Knobs (Quick Reference)

| Knob | Env/Config | Default | Purpose |
|---|---|---|---|
| WebSocket auth required | `MCP_WS_AUTH_REQUIRED` | `1` | Enforce `Authorization`/`X-API-KEY` headers for WS clients |
| WebSocket allowed origins | `MCP_WS_ALLOWED_ORIGINS` | *(empty)* | Comma-separated Origin allowlist to prevent UI spoofing |
| WebSocket query auth | `MCP_WS_ALLOW_QUERY_AUTH` | `0` | Reject `?token=`/`?api_key=` query parameters (set `1` only for legacy clients) |
| WebSocket idle timeout | `MCP_WS_IDLE_TIMEOUT_SECONDS` | `300` | Close idle WS sessions after N seconds |
| WebSocket session rate cap | `MCP_WS_SESSION_RATE_COUNT` / `MCP_WS_SESSION_RATE_WINDOW_SECONDS` | `120 / 60` | Sliding-window JSON-RPC rate limits per session |
| Disable write tools | `MCP_DISABLE_WRITE_TOOLS` | `0` | Hard block write-capable tools (ingestion/management categories) |
| Input schema validation | `MCP_VALIDATE_INPUT_SCHEMA` | `1` | Enforce required fields, primitive types, unknown-field rejection |
| Request size guard | `MCP_HTTP_MAX_BODY_BYTES` | `524288` | Reject oversized HTTP payloads (bytes) |
| IP allow/deny lists | `MCP_ALLOWED_IPS` / `MCP_BLOCKED_IPS` / `MCP_TRUSTED_PROXY_IPS` | *(empty)* | Defense-in-depth for client networks and the proxies whose X-Forwarded-For headers are trusted |
| Client certificates | `MCP_CLIENT_CERT_REQUIRED`, `MCP_CLIENT_CERT_HEADER`, `MCP_CLIENT_CERT_HEADER_VALUE` | `0`, `x-ssl-client-verify`, *(empty)* | Require mTLS headers from reverse proxy (e.g., NGINX, ALB) |
| Idempotency cache TTL | `MCP_IDEMPOTENCY_TTL_SECONDS` | `300` | Time window for write-tool dedupe |
| Idempotency cache size | `MCP_IDEMPOTENCY_CACHE_SIZE` | `512` | LRU size for idempotency cache entries |

### WebSocket Session Policy Knobs

Configure WS behavior to protect the server from idle and bursty sessions:

- `MCP_WS_IDLE_TIMEOUT_SECONDS` (default: 300) - If no activity for this many seconds, the server closes the WS with code 1001 (Idle timeout).
- `MCP_WS_SESSION_RATE_COUNT` (default: 120) - Max JSON-RPC requests allowed per session over the configured window.
- `MCP_WS_SESSION_RATE_WINDOW_SECONDS` (default: 60) - Sliding window in seconds used for per-session rate counting.

Notes
- When the session rate is exceeded, the server sends a JSON-RPC error (-32002) and closes the connection with code 1013 (session rate limit exceeded).
- The server emits Prometheus counters for WS session closures by reason (idle/session_rate): `mcp_ws_session_closures_total{reason="..."}`.

## 🔧 Rate Limits

MCP supports global and per-category (tool-driven) rate limits.

- Global limiter: configured via MCP_RATE_LIMIT_ENABLED, MCP_RATE_LIMIT_RPM, MCP_RATE_LIMIT_BURST.
- Distributed deployments: enable Redis with MCP_RATE_LIMIT_USE_REDIS=1 and MCP_REDIS_URL.
- Per-category limiters:
  - Categories: free-form labels; project recognizes at least ‘ingestion’ and ‘read’.
  - Category RPM/bursts via env:
    - MCP_RATE_LIMIT_RPM_INGESTION, MCP_RATE_LIMIT_BURST_INGESTION
    - MCP_RATE_LIMIT_RPM_READ (burst falls back to global burst)
  - Tool → category mapping:
    - JSON env (MCP_TOOL_CATEGORY_MAP)
    - YAML file (MCP_TOOL_CATEGORY_MAP_FILE)

Examples

- JSON env mapping:
```bash
export MCP_TOOL_CATEGORY_MAP='{"ingest_media":"ingestion","media.search":"read","mock_ingest":"ingestion"}'
```

- YAML mapping file (recommended):
```yaml
# tldw_Server_API/Config_Files/mcp_tool_categories.yaml
ingest_media: ingestion
update_media: ingestion
delete_media: ingestion

media.search: read
knowledge.search: read
notes.search: read
```
Use with:
```bash
export MCP_TOOL_CATEGORY_MAP_FILE=tldw_Server_API/Config_Files/mcp_tool_categories.yaml
```

Notes
- Config mapping takes precedence over the heuristic fallback (which classifies ingest_media/update_media/delete_media as ‘ingestion’).
- If Redis is enabled, per-category limiters also use Redis; otherwise in-memory token buckets are used.

See also: Ops tuning guide at Docs/Deployment/Operations/MCP_Rate_Limits_Tuning.md

### Docker Deployment
```bash
docker build -f docker/Dockerfile -t mcp-unified .
docker run -d \
  -e MCP_JWT_SECRET=$MCP_JWT_SECRET \
  -e MCP_API_KEY_SALT=$MCP_API_KEY_SALT \
  -p 8000:8000 \
  mcp-unified
```

## 📈 Monitoring

### Prometheus Metrics
Scrape MCP metrics at `GET /api/v1/mcp/metrics/prometheus` (text exposition format):
- Request rates and latencies (per MCP method)
- Module operation metrics (per module)
- Connection statistics (WebSocket)
- Rate limit hits
- Cache hit/miss rates
- System resource usage
 - Validation metrics:
   - `mcp_tool_invalid_params_total{module,tool}` - schema/validator failures
   - `mcp_tool_validator_missing_total{module,tool}` - write tools missing custom validators
 - Idempotency metrics:
   - `mcp_idempotency_hits_total{module,tool}` - protocol-level idempotency cache hits
   - `mcp_idempotency_misses_total{module,tool}` - protocol-level idempotency cache misses

Security: The Prometheus endpoint is gated by default (admin required). Only set `MCP_PROMETHEUS_PUBLIC=1` behind an internal network or ingress with auth.

### Health Checks
- `/api/v1/mcp/health` - Overall health
- `/api/v1/mcp/modules/health` - Module-specific health

## ⚙️ Module Runtime Controls

Tune module behavior and resilience without changing code.

- Concurrency guard (per module)
  - `ModuleConfig.max_concurrent` - Maximum concurrent operations per module (default: 20). Set to 0 to disable the guard.
- Circuit breaker backoff (per module)
  - `ModuleConfig.circuit_breaker_threshold` - Failures before opening (default: 5)
  - `ModuleConfig.circuit_breaker_timeout` - Initial open window in seconds (default: 60)
  - `ModuleConfig.circuit_breaker_backoff_factor` - Multiplier applied when re-opening after half-open failure (default: 2.0)
  - `ModuleConfig.circuit_breaker_max_timeout` - Cap for backoff window (default: 300)

How it works
- When the breaker opens and the timeout elapses, the next call enters half-open state (one probe).
- If the probe succeeds, the breaker heals and the timeout resets to baseline.
- If the probe fails, the breaker re-opens with an exponentially increased timeout (capped).

## 🛡️ Security Checklist

- ✅ No hardcoded secrets
- ✅ JWT authentication with rotation
- ✅ RBAC with fine-grained permissions
- ✅ Rate limiting protection
- ✅ Input validation and sanitization
- ✅ SQL injection prevention
- ✅ XSS protection
- ✅ CORS configuration
- ✅ Audit logging
- ✅ Secure password hashing (bcrypt)

## 📚 Documentation

- Developer Guide: `Docs/MCP/Unified/Developer_Guide.md`
- System Admin Guide: `Docs/MCP/Unified/System_Admin_Guide.md`
- User Guide: `Docs/MCP/Unified/User_Guide.md`
- Module Authoring: `Docs/MCP/Unified/Modules.md`
- Documentation Ingestion Playbook: `Docs/MCP/Unified/Documentation_Ingestion_Playbook.md`
- Context search design (FTS-first): `Docs/Design/context_mcp_search.md`
- API documentation available at `/docs` when server is running

## 🤝 Contributing

1. Follow existing patterns and conventions
2. Add tests for new features
3. Update documentation
4. Ensure all tests pass
5. No hardcoded secrets or credentials

## 📄 License

Part of tldw_server project - see main LICENSE file.
### Authorization (RBAC)

MCP Unified now uses the project's AuthNZ RBAC (roles, permissions, overrides). Tool execution uses fine-grained permissions:

- Per-tool permission: `tools.execute:<tool_name>`
- Wildcard permission: `tools.execute:*`

Admin endpoints for managing tool permissions:

- List: `GET /api/v1/admin/permissions/tools`
- Create: `POST /api/v1/admin/permissions/tools` with `{ "tool_name": "*" | "<name>", "description": "..." }`
- Delete: `DELETE /api/v1/admin/permissions/tools/{perm_name}`

Grant/revoke tool permissions to roles:

- Grant: `POST /api/v1/admin/roles/{role_id}/permissions/tools` with `{ "tool_name": "*" | "<name>" }`
- Revoke: `DELETE /api/v1/admin/roles/{role_id}/permissions/tools/{tool_name}`

Example: seed wildcard and grant to a role

```bash
# Create wildcard permission (if not present)
curl -X POST http://127.0.0.1:8000/api/v1/admin/permissions/tools \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"tool_name":"*","description":"Allow executing all tools"}'

# Grant wildcard to role (replace 1 with your role id)
curl -X POST http://127.0.0.1:8000/api/v1/admin/roles/1/permissions/tools \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"tool_name":"*"}'
```
