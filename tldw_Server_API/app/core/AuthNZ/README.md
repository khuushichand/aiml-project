# AuthNZ Module

Developer guide for the authentication and authorization subsystem that powers both single-user and multi-user deployments of **tldw_server**.

---

## Responsibilities at a Glance
- Starters: single-user API key auth (legacy/self-host) and multi-user JWT flows.
- Account security: Argon2 password hashing, MFA/TOTP, password reset/verification email pipelines.
- Session management: refresh tokens, blacklist-backed revocation, session metadata.
- Authorization: role-based access control, org/team hierarchies, fine-grained permission checks.
- API Keys: issuance, rotation, virtual keys with per-endpoint/LLM budgets.
- Guardrails: rate limiting, lockout, quotas, CSRF protection, security headers.
- Observability: audit hooks, alerting, usage logging, metrics instrumentation.

---

## Architecture & Modes
```
FastAPI Endpoints (auth.py, auth_enhanced.py, admin.py)
        │
        ▼
AuthNZ Services  ──┬── Credential Services (password_service, mfa_service, email_service)
                   ├── Token Stack (jwt_service, session_manager, token_blacklist)
                   ├── API Keys & Virtual Keys (api_key_manager, virtual_keys, quotas)
                   ├── Authorization & RBAC (permissions, rbac, orgs_teams)
                   ├── Rate/Usage/Middleware (rate_limiter, llm_budget_middleware, csrf_protection,
                   │                            security_headers, usage_logging_middleware)
                   └── Support Utilities (settings, database, migrations, monitoring, alerting)
        │
        ▼
Datastores ── Users/Auth metadata (SQLite/PostgreSQL) + optional Redis cache
```

- **Single-user mode** (`AUTH_MODE=single_user`): requests authenticate via `X-API-KEY`; user identity is a fixed singleton.
- **Multi-user mode** (`AUTH_MODE=multi_user`): users authenticate with username/password + optional MFA, receive JWT access/refresh tokens, and interact through RBAC, teams, quotas, API keys, etc.

---

## Data Stores & Migrations
- Default DB: `sqlite:///./Databases/users.db`; production-ready paths point to PostgreSQL.
- Migration runners: `migrations.py`, `pg_migrations_extra.py`, and `run_migrations.py`.
- First-time provisioning: `python -m tldw_Server_API.app.core.AuthNZ.initialize` creates users, seeds roles, and emits API keys when requested.
- `migrate_to_multiuser.py` upgrades legacy single-user installs to multi-user schema (roles, orgs, sessions, keys).

All schema operations honor asyncpg (Postgres) and aiosqlite code paths.

---

## Core Components
| Module | Purpose |
| --- | --- |
| `settings.py` | Pydantic settings facade; unifies env/file overrides, secret persistence, and helper accessors (`get_settings`, `is_single_user_mode`). |
| `database.py` | Async database pool abstraction (asyncpg or aiosqlite) with transaction helpers and connection lifecycle. |
| `jwt_service.py` | HS/RS JWT issuance & validation, secondary key rotation support, enforced claims, async verification. |
| `session_manager.py` | Session metadata store (refresh tokens, device info, logout handling, rotation). |
| `token_blacklist.py` | Revocation store with Redis acceleration, LRU cache, background cleanup. |
| `password_service.py` | Argon2id hashing, strength validation, reuse detection, password history enforcement. |
| `mfa_service.py` | TOTP secret provisioning, QR/backup codes, verification, lifecycle binding. |
| `api_key_manager.py` | User-owned API keys with rotation, audit log, IP allowlists, expiry. |
| `virtual_keys.py` | Derived keys for delegating LLM access; budgets, provider/model allowlists. |
| `quotas.py` | DB-backed quota counters (per JWT JTI and API key) for virtual key enforcement. |
| `rate_limiter.py` | Token-bucket limiter with Redis acceleration, lockout tracking, burst support. |
| `csrf_protection.py` | Double-submit cookie middleware with optional user binding and configurable exclusions. |
| `security_headers.py` | Standard HTTP security headers and optional CSP directives for the WebUI/login flows. |
| `orgs_teams.py`, `rbac.py`, `permissions.py` | Org/team hierarchy, role definitions, and permission evaluation helpers. |
| `alerting.py`, `monitoring.py`, `usage_logging_middleware.py` | Metrics, Prometheus/counter integration, anomaly alerts. |
| `llm_budget_middleware.py` | Enforces virtual key endpoint allowlists & budget ceilings on LLM routes. |

---

## Authentication Flows
### Single-User API Key
- `verify_single_user_api_key` dependency checks `X-API-KEY` against config.
- `SINGLE_USER_API_KEY` printed during `initialize.py` run if unset.
- CSRF middleware bypassed when API key auth present.

### Multi-User JWT
1. Credentials validated (`input_validation.py`, `password_service.py`).
2. MFA (if enabled) via `mfa_service` and backup codes.
3. Access token + refresh token minted by `jwt_service`.
4. Session entry created, refresh token stored with metadata.
5. Access tokens verified by `verify_jwt_and_fetch_user`; integrates blacklist and RBAC lookups.
6. Token revocation uses `session_manager` + `token_blacklist` (JWT ID + expiry).

Refresh tokens rotate on use; session manager ensures stale tokens are invalidated.

---

## Authorization & RBAC
- Roles defined in the DB (`roles`, `permissions`, `role_permissions` tables). `rbac.py` loads and caches.
- `permissions.py` exposes helpers for guard decorators/dependencies.
- `orgs_teams.py` manages organizational hierarchies, team membership, invites, and cross-org boundaries.
- Admin endpoints enforce `require_admin` / `require_token_scope`.
- Virtual keys inherit org/team ownership for budget attribution.

---

## Credentials & Account Security
- **Passwords**: Argon2id hashing, complexity rules, breached password detection hooks.
- **Lockout & rate limits**: `rate_limiter.record_failed_attempt` with Redis fallback; `MAX_LOGIN_ATTEMPTS`, `LOCKOUT_DURATION_MINUTES`.
- **MFA/TOTP**: Setup, verification, backup codes, recovery flows. Data persisted encrypted in the auth DB.
- **Email flows**: `email_service` sends password reset, verification, MFA notifications. Development mode falls back to file logging.
- **Input validation**: Centralized sanitizers for username/email/password to prevent injection and format errors.

---

## API Keys & Virtual Keys
- **API Keys**: Created per user, hashed + peppered, rotation/expiry, audit log, IP allowlists, per-key rate limits.
- **Virtual Keys**: Sub-keys that inherit user/org context but enforce:
  - Allowed endpoints/providers/models (JSON allowlists).
  - LLM usage budgets (daily/monthly tokens + USD).
  - Quotas tracked by `llm_budget_middleware` and `quotas.py`.
- **LLM Budget enforcement**: Middleware pre-validates key ID, rejects forbidden endpoint/model/provider, returns `402 budget_exceeded` with usage summary.

---

## Sessions, CSRF & Headers
- `session_manager.py` stores refresh metadata, device info, IP, and handles rotation.
- `token_blacklist.py` ensures revocations propagate across workers (DB + optional Redis).
- `CSRFProtectionMiddleware` applies to cookie-authenticated WebUI flows; supports binding tokens to user IDs.
- `security_headers.py` attaches HSTS, X-Frame-Options, CSP, etc., configurable via settings.

---

## Rate Limiting & Quotas
- `RateLimiter` token-bucket enforces per-identifier limits (IP, API key, user). Optional service account override.
- Lockout state stored via Redis or SQLite tables.
- `quotas.py` increments DB counters for JWT/API key quotas (supports fallback when DB unavailable).
- `usage_logging_middleware` records per-request metrics, including identifying API keys/JWT claims for analytics.

---

## Configuration Reference
Key settings (all surfaced via `Settings` in `settings.py`):

| Setting | Description |
| --- | --- |
| `AUTH_MODE` | `single_user` or `multi_user`. Drives dependencies and migrations. |
| `DATABASE_URL` | Users/Auth database connection string. Use Postgres in production. |
| `JWT_SECRET_KEY` / `JWT_PRIVATE_KEY` | Required for token signing (HS or RS/ES algorithms). Support secondary keys for rotation. |
| `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` | Token lifetimes. |
| `PASSWORD_MIN_LENGTH`, `ARGON2_*` | Password policy + hashing costs. |
| `RATE_LIMIT_ENABLED`, `RATE_LIMIT_PER_MINUTE`, `RATE_LIMIT_BURST` | Default rate limiter configuration. |
| `MAX_LOGIN_ATTEMPTS`, `LOCKOUT_DURATION_MINUTES` | Lockout thresholds. |
| `ENABLE_REGISTRATION`, `REQUIRE_REGISTRATION_CODE` | Control self-service sign-up. |
| `DEFAULT_STORAGE_QUOTA_MB`, `USER_DATA_BASE_PATH`, `CHROMADB_BASE_PATH` | Per-user storage settings passed to downstream modules. |
| `REDIS_URL` | Enables Redis-backed session cache, rate limiter, blacklist. |
| `VIRTUAL_KEYS_ENABLED`, `LLM_BUDGET_ENFORCE`, `LLM_BUDGET_ENDPOINTS` | Toggle virtual-key enforcement and set monitored endpoints. |
| `SERVICE_ACCOUNT_RATE_LIMIT`, `SESSION_COOKIE_SECURE`, `CSRF_BIND_TO_USER` | Advanced guardrails for service accounts/cookie flows. |

Settings merge environment variables, `.env.authnz` files, and global project config (via `load_comprehensive_config`).

---

## Initialization & Maintenance
1. **Install dependencies**: `pip install -e .[multiplayer]`.
2. **Run migrations**:
   ```bash
   python -m tldw_Server_API.app.core.AuthNZ.run_migrations
   ```
3. **Initialize** (creates admin user, API key, optional demo data):
   ```bash
   python -m tldw_Server_API.app.core.AuthNZ.initialize
   ```
4. **Switching modes**: Update `AUTH_MODE` and rerun migrations (`migrate_to_multiuser.py` if upgrading).
5. **Postgres extras**: `pg_migrations_extra.py` adds indices/constraints for high concurrency deployments.

---

## Observability & Alerting
- `monitoring.py` exports Prometheus metrics for auth flows (login success/failure, MFA usage, token issuance).
- `alerting.py` integrates with on-call channels (Slack/email) for lockouts, suspicious activity, quota breaches.
- Hooks emit events into the Audit subsystem (see `tldw_Server_API/app/core/Audit/unified_audit_service.py`).

---

## Testing
- Unit/integration suites live under:
  - `tldw_Server_API/tests/AuthNZ/`
  - `tldw_Server_API/tests/AuthNZ_SQLite/`
  - `tldw_Server_API/tests/Security/` (cross-cutting)
- Run focused tests:
  ```bash
  python -m pytest tldw_Server_API/tests/AuthNZ -v
  python -m pytest tldw_Server_API/tests/Security/test_websearch_egress_guard.py -k auth
  ```
- Many tests rely on `TEST_MODE=1` to disable background loops and use in-memory fixtures. Respect that flag when adding new async tasks.

---

## Extension Guidelines
1. **Follow existing dependency patterns**: route dependencies come from `User_DB_Handling` and `API_Deps`; reuse them rather than re-parsing headers yourself.
2. **Keep storage dual-compatible**: implement both asyncpg and aiosqlite paths (`if hasattr(conn, "fetchval")`).
3. **Update migrations**: schema changes require bumps in `migrations.py` (and Postgres extras if relevant). Include downgrade-safe defaults.
4. **Wire audits & metrics**: new auth-sensitive actions should log via the Audit service and increment appropriate counters.
5. **Document new settings**: extend this README and `Docs/AuthNZ` when adding configuration knobs.
6. **Write tests**: ensure both SQLite and Postgres (if applicable) code paths are covered; add fixtures when new dependencies are introduced.

---

## Integration Touchpoints
- **FastAPI dependencies**: used in `app/api/v1/api.py` routers; any new endpoints should depend on `verify_api_key`, `verify_jwt_and_fetch_user`, or higher-level scopes.
- **Budget middleware**: attach `LLMBudgetMiddleware` early in the ASGI stack if adding new LLM endpoints that should honor virtual key constraints.
- **Audit**: `auth_enhanced.py` and services emit events; use `UnifiedAuditService` helpers for new flows.
- **Scheduler & background jobs**: `scheduler.py` handles cleanup tasks (expired tokens, pending invites). Register new periodic jobs there.

---

## Useful Commands
```bash
# Generate a registration code (multi-use, 30 days)
python -m tldw_Server_API.app.core.AuthNZ.initialize --create-registration-code --max-uses 10 --expires 30

# Rotate JWT secrets (HS)
python -m tldw_Server_API.app.core.AuthNZ.initialize --rotate-jwt

# Inspect active sessions
python -m tldw_Server_API.app.core.AuthNZ.initialize --list-sessions --user alice@example.com

# Create virtual key with budgets
python -m tldw_Server_API.app.core.AuthNZ.initialize --create-virtual-key --user-id 3 \
       --day-tokens 100000 --month-usd 50 --allow-endpoints chat.completions embeddings
```

---

Keeping this README current helps contributors understand how authentication, authorization, and usage enforcement interact across the stack. Update it whenever you introduce major flows, schema changes, or new guardrails.***
