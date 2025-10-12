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
pip install fastapi uvicorn loguru pydantic python-jose passlib bcrypt aiosqlite
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
```

### HTTP Endpoints
- `POST /api/v1/mcp/request` - Process MCP request
- `GET /api/v1/mcp/status` - Server status
- `GET /api/v1/mcp/metrics` - Server metrics (admin only)
- `GET /api/v1/mcp/tools` - List available tools
- `POST /api/v1/mcp/tools/execute` - Execute tool (auth required)
- `GET /api/v1/mcp/health` - Health check

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
      db_path: ./Databases/Media_DB_v2.db
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

See `Docs/Development/MCP_Modules.md` for a complete guide.

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
MCP_METRICS_ENABLED=true
MCP_LOG_LEVEL=INFO
```

### Docker Deployment
```bash
docker build -f docker/Dockerfile -t mcp-unified .
docker run -d \
  -e MCP_JWT_SECRET=$MCP_JWT_SECRET \
  -e MCP_API_KEY_SALT=$MCP_API_KEY_SALT \
  -p 8000:8000 \
  -p 9090:9090 \
  mcp-unified
```

## 📈 Monitoring

### Prometheus Metrics
Available at `/metrics` endpoint (port 9090):
- Request rates and latencies
- Module health status
- Connection statistics
- Cache hit/miss rates
- System resource usage

### Health Checks
- `/api/v1/mcp/health` - Overall health
- `/api/v1/mcp/modules/health` - Module-specific health

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

- `DESIGN.md` - Architecture and design decisions
- `IMPLEMENTATION_STATUS.md` - Development progress
- `MIGRATION_GUIDE.md` - Migration from old modules (if needed)
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

MCP Unified now uses the project's AuthNZ RBAC (roles, permissions, overrides). Tool execution uses fine‑grained permissions:

- Per‑tool permission: `tools.execute:<tool_name>`
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
