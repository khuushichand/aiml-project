# AuthNZ Code Guide (Developers)

This guide orients project developers to the AuthNZ module: what’s in it, how it works, and how to work with it when building or extending the server.

See also: `tldw_Server_API/app/core/AuthNZ/README.md` and `Docs/Code_Documentation/AuthNZ-Developer-Guide.md` for complementary overviews.

## Scope & Goals
- Dual-mode authentication: single-user (API key) and multi-user (JWT) with a unified dependency pattern for endpoints.
- Authorization via roles/permissions (RBAC) with org/team context.
- Sessions, token rotation/blacklist, API keys and virtual keys, rate limits/quotas, CSRF, and security headers.
- Works with SQLite (default) and PostgreSQL (production); optional Redis acceleration for sessions/rate limits.

## Quick Map
- Core settings: `tldw_Server_API/app/core/AuthNZ/settings.py`
- DB pool + migrations glue: `tldw_Server_API/app/core/AuthNZ/database.py`
- JWT service: `tldw_Server_API/app/core/AuthNZ/jwt_service.py`
- Sessions + blacklist: `tldw_Server_API/app/core/AuthNZ/session_manager.py`, `tldw_Server_API/app/core/AuthNZ/token_blacklist.py`
- API keys + Virtual keys: `tldw_Server_API/app/core/AuthNZ/api_key_manager.py`, `tldw_Server_API/app/core/AuthNZ/virtual_keys.py`
- RBAC/orgs/teams/permissions: `tldw_Server_API/app/core/AuthNZ/permissions.py`, `tldw_Server_API/app/core/AuthNZ/rbac.py`, `tldw_Server_API/app/core/AuthNZ/orgs_teams.py`, `tldw_Server_API/app/core/AuthNZ/privilege_catalog.py`
- Guardrails/middleware: `tldw_Server_API/app/core/AuthNZ/rate_limiter.py`, `tldw_Server_API/app/core/AuthNZ/llm_budget_middleware.py`, `tldw_Server_API/app/core/AuthNZ/csrf_protection.py`, `tldw_Server_API/app/core/AuthNZ/security_headers.py`, `tldw_Server_API/app/core/AuthNZ/usage_logging_middleware.py`
- Guardrails/middleware: `tldw_Server_API/app/core/AuthNZ/rate_limiter.py`, `tldw_Server_API/app/core/AuthNZ/llm_budget_middleware.py`, `tldw_Server_API/app/core/AuthNZ/llm_budget_guard.py`, `tldw_Server_API/app/core/AuthNZ/csrf_protection.py`, `tldw_Server_API/app/core/AuthNZ/security_headers.py`, `tldw_Server_API/app/core/AuthNZ/usage_logging_middleware.py`
- Endpoint DI (use these): `tldw_Server_API/app/api/v1/API_Deps/auth_deps.py`
- Auth endpoints: `tldw_Server_API/app/api/v1/endpoints/auth.py`, `tldw_Server_API/app/api/v1/endpoints/auth_enhanced.py`
- Admin + RBAC mgmt: `tldw_Server_API/app/api/v1/endpoints/admin.py`, `.../users.py`, `.../privileges.py`, `.../register.py`

## Modes & Request Flow

### Single-User Mode (X-API-KEY)
- Configure `AUTH_MODE=single_user` and `SINGLE_USER_API_KEY`.
- `get_current_user` accepts either `X-API-KEY: <key>` header or `Authorization: Bearer <key>`.
- Optional IP allowlist via `SINGLE_USER_ALLOWED_IPS`.
- JWT/session/blacklist are bypassed; user is treated as admin with full permissions.

### Multi-User Mode (JWT)
- Configure `AUTH_MODE=multi_user` and `JWT_SECRET_KEY` (or RS/ES keys).
- Login issues `access` and `refresh` tokens; sessions persisted; refresh rotation enabled by default.
- Bearer `Authorization` is required for protected endpoints unless an API key is used as an alternative path.
- Token revocation checks the blacklist; sessions track activity, IP, UA.

### API Keys & Virtual Keys
- API keys provide non-JWT authentication; can be scoped, rotated, expire, and audited.
- Virtual keys are short-lived scoped JWTs minted by authenticated users for automation/integrations.
  - Virtual key authentication requires multi-user mode; in single-user mode, bearer JWTs are not accepted by `get_current_user`.

## Using Dependencies in Endpoints

Prefer the shared dependencies from `tldw_Server_API/app/api/v1/API_Deps/auth_deps.py`.

Typical patterns:

```python
from fastapi import APIRouter, Depends
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    get_current_user,           # Resolves single-user, API-key, or JWT
    get_current_active_user,    # Adds active status check
    check_rate_limit,           # General rate limit helper
)
from tldw_Server_API.app.core.AuthNZ.permissions import PermissionChecker

router = APIRouter(prefix="/example", tags=["examples"])

@router.get("/protected")
async def protected_route(user=Depends(get_current_user)):
    return {"hello": user.get("username")}

@router.post("/write", dependencies=[Depends(PermissionChecker("media.update"))])
async def write_route(user=Depends(get_current_active_user)):
    return {"ok": True}

@router.get("/limited", dependencies=[Depends(check_rate_limit)])
async def limited_route(user=Depends(get_current_user)):
    return {"ok": True}
```

Notes:
- `get_current_user` handles single-user mode first, then API key, then JWT.
- `PermissionChecker` honors soft-enforce via `RBAC_SOFT_ENFORCE` and never logs secrets.
- `check_rate_limit` uses a token bucket; see Rate Limiting below.

## Sessions, Tokens, Revocation

- `session_manager.py` encrypts token material at rest using Fernet.
- Encryption key precedence: explicit `SESSION_ENCRYPTION_KEY` → persisted file (secure 0600) → derived keys from configured secrets (fallback) → generated in TEST_MODE.
  - Persisted key preferred path: project root `Config_Files/session_encryption.key`; back-compat fallback: `tldw_Server_API/Config_Files/session_encryption.key`. Set `SESSION_KEY_STORAGE=api` to prefer the API component path. Symlinks are handled safely and file ownership/permissions are validated.
- Blacklist checks (by JTI) protect against replay after logout/rotation; see `token_blacklist.py`.
- Redis (optional via `REDIS_URL`) accelerates lookups and counters.

Key calls you’ll see in endpoints/services:
- `JWTService.create_access_token(...)`, `create_refresh_token(...)`, `decode_access_token(...)`.
- `SessionManager.create_session(...)`, `update_session_tokens(...)`, `revoke_session(...)`.

## API Keys & Virtual Keys

- `api_key_manager.py` creates, rotates, revokes, and validates keys; stores HMAC-SHA256 hash of the presented key.
- Keys support: expiry, usage counts, IP allowlists, rate limits, audit log, and optional LLM usage budgets and allowlists.
- `auth_deps.get_current_user` can authenticate via `X-API-KEY` when no Bearer token is present.
- Virtual keys: use `POST /api/v1/auth/virtual-key` or programmatically via `JWTService.create_virtual_access_token(...)`.
  - Virtual keys are enforced via scoped claims (e.g., `scope`, allowed endpoints/methods/paths) with helpers in `auth_deps.require_token_scope` and budget checks in `llm_budget_guard.py`.

Example: create and validate an API key
```python
from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager

mgr = await get_api_key_manager()
rec = await mgr.create_api_key(user_id=1, name="integration", scope="write", expires_in_days=30)
# Persist the cleartext key somewhere safe on the client side
assert await mgr.validate_api_key(api_key=rec["api_key"])  # returns user context
```

## RBAC, Roles, Permissions, Orgs/Teams

- Permissions helpers: `tldw_Server_API/app/core/AuthNZ/permissions.py`.
- Org/team context: DI attaches `request.state.user_id`, plus memberships from `orgs_teams.list_memberships_for_user` and a content scope token via `scope_context.set_scope` for downstream DB access.
- Use `PermissionChecker`, `RoleChecker`, `AnyPermissionChecker`, `AllPermissionsChecker` in route dependencies to enforce access.
- Admin routes use stricter checks and separate admin endpoints (see `.../endpoints/admin.py`).

## Rate Limiting & Quotas

- General limiter: `rate_limiter.py` implements a token bucket; DI provides `get_rate_limiter_dep`.
- Endpoint helper: `check_rate_limit` extracts a stable client identity (IP or user) and enforces limits; authentication routes use `check_auth_rate_limit` with stricter defaults.
- LLM budgets: `llm_budget_middleware.py` and `llm_budget_guard.py` enforce endpoint/provider/model quotas when configured. Settings are `LLM_BUDGET_ENFORCE` (on/off) and `LLM_BUDGET_ENDPOINTS` (paths).

Example: custom rate limit per endpoint
```python
from fastapi import Depends, Request, HTTPException, status
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_rate_limiter_dep

async def limit_10rpm(req: Request, limiter=Depends(get_rate_limiter_dep)):
    allowed, meta = await limiter.check_rate_limit(req.client.host, "example", limit=10, window_minutes=1)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Slow down")

@router.get("/tight", dependencies=[Depends(limit_10rpm)])
async def tight_route(user=Depends(get_current_user)):
    return {"ok": True}
```

## Settings & Initialization

- Central source: `settings.py` (via `get_settings()`), with env + optional project config overrides.
- Single-user requires `SINGLE_USER_API_KEY`; multi-user requires `JWT_SECRET_KEY` or asymmetric keys.
- Asymmetric JWT is supported via `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY` (e.g., RS256/ES256); otherwise use `JWT_SECRET_KEY` for HS*.
- Initialize or migrate DB:
  - `python -m tldw_Server_API.app.core.AuthNZ.run_migrations`
  - `python -m tldw_Server_API.app.core.AuthNZ.initialize`
- DB detection: `database.py` chooses Postgres in multi-user when `DATABASE_URL` is `postgres*`; else SQLite.

## Database Backends

- SQLite is the default; WAL mode enabled; migrations harmonized via `migrations.py` on startup.
- PostgreSQL is recommended for multi-user deployments; pool managed by `asyncpg`.
- `get_db_pool()` yields a singleton `DatabasePool`; use `transaction()` for writes, `acquire()` for reads.
  - `DatabasePool.execute/fetch*` normalize SQL placeholders across backends (`?` → `$1,$2,...` on Postgres). Inside explicit transactions where you work with the raw connection, prefer Postgres-style placeholders (`$1,$2,...`) for portability; SQLite shims convert `$N` to `?` automatically.

## Gotchas

- Cross-backend SQL placeholders
  - When using `get_db_transaction` (raw connections), Postgres requires `$1,$2,...` placeholders. SQLite adapter shims translate `$N` to `?`, so `$N` works on both.
  - If you aren’t in a transaction, prefer `DatabasePool.execute/fetch*` which normalizes placeholders automatically in either direction.

## Common Recipes

1) Protect a new endpoint
```python
@router.get("/secure")
async def secure(user=Depends(get_current_user)):
    return {"user_id": user["id"]}
```

2) Require a permission
```python
from tldw_Server_API.app.core.AuthNZ.permissions import PermissionChecker

@router.post("/media/update", dependencies=[Depends(PermissionChecker("media.update"))])
async def update_media(user=Depends(get_current_user)):
    ...
```

3) Use a DB transaction in a handler
```python
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_db_transaction

@router.post("/do-write")
async def do_write(conn=Depends(get_db_transaction), user=Depends(get_current_user)):
    # Prefer Postgres-style placeholders for cross-backend portability
    await conn.execute("INSERT INTO example(col) VALUES($1)", "value")
    return {"ok": True}
```

4) Mint a virtual key (from an authenticated route)
```python
from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
from tldw_Server_API.app.core.AuthNZ.settings import get_settings

@router.post("/vk")
async def mint_vk(user=Depends(get_current_user)):
    svc = JWTService(get_settings())
    token = svc.create_virtual_access_token(
        user_id=user["id"], username=user.get("username", ""), role=user.get("role", "user"),
        scope="workflows", ttl_minutes=30, additional_claims={"allowed_endpoints": ["chat.completions"]}
    )
    return {"token": token}
```

## Testing Notes

- TEST_MODE (`TEST_MODE=1`) disables rate limiting by default and enables deterministic secrets/keys. Some DI dependencies return lightweight stubs to keep tests fast and deterministic.
- Postgres-dependent tests use a provisioned container unless `TLDW_TEST_NO_DOCKER=1`; see `tldw_Server_API/tests/AuthNZ_Postgres/` and project test README.
- Many endpoint utilities add test-only diagnostics headers for clarity (e.g., `X-TLDW-DB`, `X-TLDW-CSRF-Enabled`).

## Extending AuthNZ

- Add new permissions in `permissions.py` and seed mapping in RBAC migrations/seeders.
- New admin surfaces belong under `.../endpoints/admin.py` or feature-specific admin routes guarded by `RoleChecker("admin")` and permission checks.
- For new guardrails, prefer middleware with settings gating, and expose DI helpers to keep endpoints simple.
- Keep both SQLite and Postgres code paths working; use `DatabasePool` helpers to normalize placeholders across backends when needed.

## Troubleshooting & Pitfalls

- JWT misconfig in multi-user: ensure `JWT_SECRET_KEY` length >= 32 (HS*) or set RSA/EC keys for (RS*/ES*).
- Single-user without key: set `SINGLE_USER_API_KEY` (a deterministic test key is used under TEST_MODE).
- Session key persistence failures: ensure `Config_Files/session_encryption.key` is writable and not a symlink to an invalid location.
- Virtual keys require multi-user mode.
- LLM budget enforcement depends on `LLM_BUDGET_*` settings and middleware placement.
- When using `get_db_transaction` with Postgres connections, `?` placeholders are not supported. Use `$1,$2,...` or route SQL through `DatabasePool.execute`/`fetch*` for automatic normalization (outside explicit transactions).

---

If you need a deeper conceptual overview, read `tldw_Server_API/app/core/AuthNZ/README.md`. For a broader project context, see `Docs/Code_Documentation/AuthNZ-Developer-Guide.md`.
