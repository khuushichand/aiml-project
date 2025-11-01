# Authentication Setup

tldw_server supports both single-user (personal) and multi-user (team) deployments via the AuthNZ module.

## Quick Setup (Single-User Mode)

For personal use, the simplest setup:

```bash
# 1. Copy the authentication template
cp .env.authnz.template .env

# 2. Generate a secure API key
python -c "import secrets; print('SINGLE_USER_API_KEY=' + secrets.token_urlsafe(32))"

# 3. Add the generated key to your .env file
# Edit .env and replace SINGLE_USER_API_KEY value

# 4. Set AUTH_MODE to single_user in .env
AUTH_MODE=single_user

# 5. Initialize the authentication system
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

Note on tokens in single-user mode
- Login endpoints are disabled/hidden; there are no JWTs. Authenticate with the `X-API-KEY` header only.
- Bearer tokens are ignored in single-user mode. Some OpenAI-compatible clients send `Authorization: Bearer ...` - set the same value in `X-API-KEY` to authenticate.

## Multi-User Setup (Team/Production)

For team deployments with user management:

```bash
# 1. Copy and configure authentication
cp .env.authnz.template .env

# 2. Generate secure keys
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
python -c "from cryptography.fernet import Fernet; print('SESSION_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"

# 3. Edit .env file:
#    - Set AUTH_MODE=multi_user
#    - Add generated JWT_SECRET_KEY
#    - Add generated SESSION_ENCRYPTION_KEY
#      (the server will persist this to Config_Files/session_encryption.key with 0600 permissions;
#       if you manage the file manually, keep it owner-readable only)
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
| `ENABLE_REGISTRATION` | Allow new user registration | `false` |
| `DATABASE_URL` | User database location | `sqlite:///./Databases/users.db` |

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
- WebUI convenience (dev): `GET /webui/config.json` returns the key in single-user mode so the WebUI can auto-configure. Avoid relying on this in production.
  - In production (`tldw_production=true`), `/webui/config.json` omits the `apiKey` field for security.
- Important: Always set a secure `SINGLE_USER_API_KEY` in production. If unset, the server may use a deterministic test key for convenience during development/testing.
  - When `tldw_production=true`, the server refuses to start if `SINGLE_USER_API_KEY` is missing, a default/test value, or shorter than 24 characters.

### Multi-User JWT Secret (production)

- When `tldw_production=true` and `AUTH_MODE=multi_user`, the server refuses to start unless `JWT_SECRET_KEY` is set via environment, at least 32 characters, and not the default template value.

### Database (production, multi-user mode)

- When `tldw_production=true` and `AUTH_MODE=multi_user`, SQLite is not supported and startup will fail if `DATABASE_URL` points to SQLite.
- Configure PostgreSQL via `DATABASE_URL` (examples):
  - Local:
    ```bash
    export DATABASE_URL=postgresql://tldw_user:ChangeMeStrong123!@localhost:5432/tldw_users
    ```
  - With docker-compose (service name `postgres`):
    ```bash
    export DATABASE_URL=postgresql://tldw_user:ChangeMeStrong123!@postgres:5432/tldw_users
    ```
  - See Multi-User Deployment Guide for more details.

### Security Best Practices

1. **Never commit `.env` to version control** - Add to `.gitignore`
2. **Use strong, unique keys** - Generate with the provided commands
3. **Enable HTTPS in production** - Required for secure cookies
4. **Rotate keys periodically** - Use the API key rotation feature
5. **Monitor authentication failures** - Check logs for attacks
6. See the Production Hardening Checklist: `./Production_Hardening_Checklist.md`

### Security Controls (env)

- `tldw_production`: Set to `true` in production to enable stricter guards (secrets validation, DB checks, masked logs, WebUI config hardening).
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
- Adjust RATE_LIMIT_PER_MINUTE in .env if needed

### Documentation

- AuthNZ API Guide: `../API-related/AuthNZ-API-Guide.md`

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

# 4) Open the simple auth page to register/login and get a JWT
open http://127.0.0.1:8000/webui/auth.html   # macOS
# xdg-open on Linux, or just paste the URL in a browser
```

Notes
- This is suitable for development and light testing. For production multi-user, use PostgreSQL for `DATABASE_URL`.
- The auth page posts to `/api/v1/auth/register` and `/api/v1/auth/login` and shows the access token.

## Using config.txt for AuthNZ

You can configure authentication and the AuthNZ database in `tldw_Server_API/Config_Files/config.txt` (env still overrides):

```
[AuthNZ]
auth_mode = multi_user
# Option A: full URL
database_url = postgresql://tldw_user:ChangeMeStrong123!@localhost:5432/tldw_users
# Option B: structured fields (used if DATABASE_URL not set)
db_type = postgresql
pg_host = localhost
pg_port = 5432
pg_db = tldw_users
pg_user = tldw_user
pg_password = ChangeMeStrong123!
pg_sslmode = prefer
enable_registration = true
require_registration_code = false
```

Environment precedence and a complete list of environment variables is in `Env_Vars.md`.
