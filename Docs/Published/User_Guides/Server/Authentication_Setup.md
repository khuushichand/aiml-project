# Authentication Setup

tldw_server supports both single-user (personal) and multi-user (team) deployments via the AuthNZ module.

## Quick Setup (Single-User Mode)

For personal use, the simplest setup:

```bash
# 1. Copy the authentication template
cp tldw_Server_API/Config_Files/.env.example tldw_Server_API/Config_Files/.env

# 2. Generate a secure API key (new format)
python -m tldw_Server_API.app.core.AuthNZ.initialize
# Choose "Generate secure keys" and copy SINGLE_USER_API_KEY
# This also generates MCP_JWT_SECRET and MCP_API_KEY_SALT if missing.

# 3. Add the generated key to your .env file
# Edit .env and replace SINGLE_USER_API_KEY value

# 4. Set AUTH_MODE to single_user in .env
AUTH_MODE=single_user

# 5. Initialize the authentication system (if you haven't already)
python -m tldw_Server_API.app.core.AuthNZ.initialize

# 6. Start the server - your API key will be displayed in the console
python -m uvicorn tldw_Server_API.app.main:app --reload
```

When the server starts, you'll see:
```
INFO: 🔑 Single-user mode active
INFO: 📌 API Key: your-generated-api-key-here
INFO: Use header 'X-API-KEY: your-key' for authentication
```

Use this API key in all requests:
```bash
curl -H "X-API-KEY: your-api-key" http://localhost:8000/api/v1/media/search
```

## Multi-User Setup (Team/Production)

For team deployments with user management:

```bash
# 1. Copy and configure authentication
cp tldw_Server_API/Config_Files/.env.example tldw_Server_API/Config_Files/.env

# 2. Generate secure keys
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
python -c "from cryptography.fernet import Fernet; print('SESSION_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
# MCP Unified secrets (required in production; initializer can generate if missing)
python -c "import secrets; print('MCP_JWT_SECRET=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('MCP_API_KEY_SALT=' + secrets.token_urlsafe(32))"

# 3. Edit .env file:
#    - Set AUTH_MODE=multi_user
#    - Add generated JWT_SECRET_KEY
#    - Add generated SESSION_ENCRYPTION_KEY
#    - Add MCP_JWT_SECRET and MCP_API_KEY_SALT (required for MCP Unified in production)
#      (the server writes Config_Files/session_encryption.key with 0600 permissions; keep manual copies owner-readable only)
#    - Configure database settings

# 4. Initialize and create admin user
python -m tldw_Server_API.app.core.AuthNZ.initialize
# You'll be prompted to create an admin user

# 5. Start the server
python -m uvicorn tldw_Server_API.app.main:app --reload
```

Login to get JWT token:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'
```

Use the token in requests:
```bash
curl -H "Authorization: Bearer your-jwt-token" \
  http://localhost:8000/api/v1/media/search
```

## Configuration Options

Key settings in `.env`:

| Setting | Description | Default |
|---------|-------------|---------|
| `AUTH_MODE` | `single_user` or `multi_user` | `multi_user` |
| `JWT_SECRET_KEY` | Secret for JWT signing (multi-user) | Required for multi-user |
| `SINGLE_USER_API_KEY` | API key for single-user mode | Required for single-user |
| `MCP_JWT_SECRET` | MCP Unified JWT signing secret | Required for MCP in production |
| `MCP_API_KEY_SALT` | MCP API key hashing salt | Required for MCP in production |
| `ENABLE_REGISTRATION` | Allow new user registration | `false` |
| `DATABASE_URL` | User database location | `sqlite:///./Databases/users.db` |
| `ROTATE_REFRESH_TOKENS` | Rotate refresh tokens on use | `true` |
| `JWT_ISSUER` | Expected JWT `iss` claim (optional) | unset |
| `JWT_AUDIENCE` | Expected JWT `aud` claim (optional) | unset |
| `JWT_PRIVATE_KEY` | PEM-encoded private key (RS256/ES256) | unset |
| `JWT_PUBLIC_KEY` | PEM-encoded public key (RS256/ES256) | unset |
| `PII_REDACT_LOGS` | Redact usernames/IPs in auth logs | `false` |
| `CSRF_BIND_TO_USER` | Bind CSRF token to user context (HMAC) | `false` |

### Single-User API Key (How to obtain)

- Recommended: set `SINGLE_USER_API_KEY` explicitly in your `.env` (or environment). You know the key because you set it.
- Development logs: in dev mode (default), the server prints the full key at startup.
- Production logs: set `tldw_production=true` to mask the key in logs. To briefly show it once on startup (e.g., for initial bootstrap), also set `SHOW_API_KEY_ON_STARTUP=true`, then remove it.
- Programmatic retrieval:
  - Python (same env as server):
    ```bash
    python -c "from tldw_Server_API.app.core.AuthNZ.settings import get_settings; print(get_settings().SINGLE_USER_API_KEY)"
    ```
  - Docker Compose:
    ```bash
    docker compose exec app printenv SINGLE_USER_API_KEY
    ```
- Frontend clients: supply the API key via their own config (for the Next.js client, use `NEXT_PUBLIC_X_API_KEY` in `.env.local`).
- Important: Always set a secure `SINGLE_USER_API_KEY` in production. If unset, the server may use a deterministic test key for convenience during development/testing.
  - When `tldw_production=true`, the server refuses to start if `SINGLE_USER_API_KEY` is missing, a default/test value, or shorter than 24 characters.

### Multi-User JWT Secret (production)

- When `tldw_production=true` and `AUTH_MODE=multi_user`, the server refuses to start unless `JWT_SECRET_KEY` is set via environment, at least 32 characters, and not the default template value.

### Database (production, multi-user mode)

- When `tldw_production=true` and `AUTH_MODE=multi_user`, SQLite is not supported and startup will fail if `DATABASE_URL` points to SQLite.
- Configure PostgreSQL via `DATABASE_URL` (examples):
  - Local:
    ```bash
    export DATABASE_URL=postgresql://tldw_user:TestPassword123!@localhost:5432/tldw_users
    ```
  - With docker-compose (service name `postgres`):
    ```bash
    export DATABASE_URL=postgresql://tldw_user:TestPassword123!@postgres:5432/tldw_users
    ```
  - For a focused walkthrough, see `Docs/User_Guides/Server/Multi-User_Postgres_Setup.md`.
  - See Multi-User Deployment Guide for broader production guidance.

### Security Best Practices

1. **Never commit `.env` to version control** - Add to `.gitignore`
2. **Use strong, unique keys** - Generate with the provided commands
3. **Enable HTTPS in production** - Required for secure cookies
4. **Rotate keys periodically** - Use the API key rotation feature
5. **Monitor authentication failures** - Check logs for attacks
6. See the Production Hardening Checklist: `./Production_Hardening_Checklist.md`

JWT hardening (recommended):
- Set `JWT_ISSUER` to a stable service identifier (e.g., `tldw_server`).
- Set `JWT_AUDIENCE` to the intended audience (e.g., `tldw_api`).
- Clients should include the returned refresh token after each `/auth/refresh` when `ROTATE_REFRESH_TOKENS=true`.
- For multi-service deployments, prefer `RS256` and set `JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY`.

Rotation guidance: see `Docs/Operations/JWT_Rotation_Runbook.md`.

### Security Controls (env)

- `tldw_production`: Set to `true` in production to enable stricter guards (secrets validation, DB checks, masked logs).
- `ENABLE_OPENAPI`: Set `false` to hide docs/Redoc/OpenAPI; defaults to `false` in production when unspecified.
- `ALLOWED_ORIGINS`: Comma-separated list or JSON array to restrict CORS in production.
-, `ENABLE_SECURITY_HEADERS`: Enable/disable security headers middleware (defaults to `true` in production).

### Troubleshooting

"JWT_SECRET_KEY not set"
- Ensure JWT_SECRET_KEY is set in your .env file for multi-user mode

"API key not found"
- Check that X-API-KEY header is included in requests
- Verify the API key matches what's in .env (single-user) or displayed at startup

"Rate limit exceeded"
- Default: 60 requests/minute for authenticated users
- Adjust Resource Governor policy limits (`requests.rpm` / `requests.burst`) in `Config_Files/resource_governor_policies.yaml` if needed

### Documentation

- AuthNZ API Guide: `../API-related/AuthNZ-API-Guide.md`
- Family/Guardian setup: `Docs/User_Guides/WebUI_Extension/Family_Guardian_Setup.md`

## Quick Setup (Multi-User with SQLite - Dev)

For local/dev multi-user without Postgres:

```bash
# 1) Enable multi-user mode with SQLite AuthNZ DB
export AUTH_MODE=multi_user
export DATABASE_URL=sqlite:///./Databases/users.db

# 2) Initialize the AuthNZ database
python -m tldw_Server_API.app.core.AuthNZ.initialize

# 3) Start the server
uvicorn tldw_Server_API.app.main:app --reload

# 4) Open the Next.js WebUI login page to register/login and get a JWT
open http://localhost:8080/login   # macOS (run the Next.js client separately)
# xdg-open on Linux, or just paste the URL in a browser
```

Notes
- This is suitable for development and light testing. For production multi-user, use PostgreSQL for `DATABASE_URL`.
- The login flow posts to `/api/v1/auth/register` and `/api/v1/auth/login` and shows the access token.
- For a deeper explanation of how multi-user SQLite is wired (AuthNZ DB + per-user storage) and common limitations, see `Docs/User_Guides/Server/Multi-User_SQLite_Setup.md`.

## Using config.txt for AuthNZ

You can configure authentication and the AuthNZ database in `tldw_Server_API/Config_Files/config.txt` (env still overrides):

```
[AuthNZ]
auth_mode = multi_user
# Option A: full URL
database_url = postgresql://tldw_user:TestPassword123!@localhost:5432/tldw_users
# Option B: structured fields (used if DATABASE_URL not set)
db_type = postgresql
pg_host = localhost
pg_port = 5432
pg_db = tldw_users
pg_user = tldw_user
pg_password = TestPassword123!
pg_sslmode = prefer
enable_registration = true
require_registration_code = false
```

Environment precedence and a complete list of environment variables is in `Env_Vars.md`.
