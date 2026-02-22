# Multi-User SQLite Setup (Local/Dev)

This guide explains how **multi-user mode** works when you keep the AuthNZ database in **SQLite**. This is intended for local development, small-scale testing, and demos. For production, use PostgreSQL (see `Docs/User_Guides/Server/Multi-User_Deployment_Guide.md`).

## When to Use This

Use multi-user + SQLite when you want:
- Local/CI testing of JWT flows, user management, and RBAC.
- A lightweight team demo without running Postgres.

Do **not** use SQLite for production multi-user. When `tldw_production=true` and `AUTH_MODE=multi_user`, the server blocks SQLite by design.

## How Multi-User SQLite Works

Multi-user mode has two storage layers:

1. **AuthNZ DB (central)**
   - Controlled by `DATABASE_URL`.
   - Stores users, sessions, API keys, orgs/teams, RBAC, and security events.
   - In this guide, it is a **single SQLite file** (e.g., `Databases/users.db`).

2. **Per-user data (isolated)**
   - All user content (media, notes, prompts, vector stores, outputs, etc.) is stored under `USER_DB_BASE_DIR`.
   - Each user gets a **separate directory** keyed by their `user_id` from AuthNZ.
   - The API always resolves DB paths using the authenticated user’s ID; in multi-user mode there is **no default user**.

### Default Layout

```
Databases/
  users.db
  user_databases/
    <user_id>/
      Media_DB_v2.db
      ChaChaNotes.db
      Personalization.db
      prompts_user_dbs/
        user_prompts_v2.sqlite
      evaluations/
        evaluations.db
      audit/
        unified_audit.db
      workflows/
        workflows.db
      vector_store/
        vector_store_meta.db
      chroma_storage/
      outputs/
      voices/
```

Notes:
- `USER_DB_BASE_DIR` defaults to `Databases/user_databases`.
- The directory and DB files are created lazily on first access.

## Configuration (Recommended for Dev)

Start from the AuthNZ template:

```bash
cp tldw_Server_API/Config_Files/.env.authnz.template .env
```

Then update `.env` (or export in your shell):

```bash
# Required
AUTH_MODE=multi_user
DATABASE_URL=sqlite:///./Databases/users.db
JWT_SECRET_KEY=<32+ char secret>
SESSION_ENCRYPTION_KEY=<Fernet key>

# Allow self-registration for local dev
ENABLE_REGISTRATION=true
REQUIRE_REGISTRATION_CODE=false

# Optional but helpful
USER_DB_BASE_DIR=./Databases/user_databases
TLDW_SQLITE_WAL_MODE=true
```

Notes:
- `SESSION_ENCRYPTION_KEY` is used to encrypt session tokens at rest. If omitted, the server will persist a key under `Config_Files/session_encryption.key` (0600 permissions).
- `TLDW_SQLITE_WAL_MODE=true` improves concurrency for the AuthNZ SQLite DB.
- If you keep `REQUIRE_REGISTRATION_CODE=true`, you must create registration codes (see below).

## Setup Steps

1. **Initialize AuthNZ** (creates schema, prompts for admin user, and can generate missing keys):

```bash
python -m tldw_Server_API.app.core.AuthNZ.initialize
```

2. **Start the API server**:

```bash
python -m uvicorn tldw_Server_API.app.main:app --reload
```

3. **Register or login**

- If registration is enabled:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"ChangeMe123!","email":"alice@example.com"}'
```

- Login to get a JWT:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"ChangeMe123!"}'
```

- Use the JWT for API calls:

```bash
curl -H "Authorization: Bearer <access_token>" \
  http://127.0.0.1:8000/api/v1/media/search
```

4. **Web UI (optional)**

If you use `apps/tldw-frontend`, leave `NEXT_PUBLIC_X_API_KEY` unset and login via the UI. Add your UI origin to `ALLOWED_ORIGINS` if needed.

## Registration Codes (Optional)

If you want to require registration codes, run:

```bash
python -m tldw_Server_API.app.core.AuthNZ.initialize --create-registration-code
```

Then pass the code in the register request as `registration_code` (see `/api/v1/auth/register`).

## Limitations (SQLite in Multi-User Mode)

- **Concurrency**: SQLite allows many readers but limited concurrent writers. With multiple users, expect contention on the AuthNZ DB.
- **Multi-process servers**: Avoid running multiple Uvicorn workers against the same SQLite file. Use `--workers 1` for dev.
- **Production guard**: With `tldw_production=true`, SQLite is blocked for multi-user.

If you need higher concurrency or stability, switch the AuthNZ DB to PostgreSQL.

## Troubleshooting

- **Startup error: SQLite not supported in production**
  - Ensure `tldw_production` is unset/false for dev, or switch to PostgreSQL.

- **`sqlite3.OperationalError: database is locked`**
  - Reduce concurrent writers (single worker), enable WAL, or move AuthNZ to PostgreSQL.

- **`user_id is required in multi-user mode`**
  - Ensure endpoints are called with a valid JWT (Authorization header).

## Next Steps

- For production: `Docs/User_Guides/Server/Multi-User_Deployment_Guide.md`
- Database layout details: `Docs/Code_Documentation/Database.md`
- AuthNZ config reference: `Docs/AuthNZ/AUTHNZ_DATABASE_CONFIG.md`
