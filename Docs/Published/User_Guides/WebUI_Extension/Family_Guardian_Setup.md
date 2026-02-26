# Family/Guardian Setup Guide

This guide is for parents or guardians who want to run tldw_server at home with separate accounts for each family member and practical guardrails (limits, filters, alerts).

> **Looking for the full walkthrough?** If you're starting from scratch, begin with [Household_Multi_User_Walkthrough.md](../WebUI_Extension/Household_Multi_User_Walkthrough.md) which covers installation, account creation, and verification end-to-end. This guide focuses on **guardrails and parental controls** to apply after setup.

## What You'll Set Up

- Multi-user accounts (one per person)
- Admin account for a parent/guardian
- Guardrails for sign-up, usage, and access
- Optional alerts and logging

This guide assumes a **local or home server**. For public/production deployments, use PostgreSQL and review `Docs/User_Guides/Server/Production_Hardening_Checklist.md`.

## Quick Glossary

- **AuthNZ DB**: Central database for users, sessions, roles, permissions, and API keys.
- **Per-user data**: Each user has their own media/notes/prompts databases under `USER_DB_BASE_DIR`.
- **JWT**: Login token used by the Web UI and API.
- **Virtual Key**: A per-user API key with allowlists and budgets (good for limits).

## Step 1: Configure Multi-User Mode

Start from the AuthNZ template:

```bash
cp tldw_Server_API/Config_Files/.env.example tldw_Server_API/Config_Files/.env
```

Set the essentials in `.env` (SQLite local example):

```bash
AUTH_MODE=multi_user
DATABASE_URL=sqlite:///./Databases/users.db
JWT_SECRET_KEY=<32+ char secret>
SESSION_ENCRYPTION_KEY=<Fernet key>
USER_DB_BASE_DIR=./Databases/user_databases

# Guardrails for sign-up
ENABLE_REGISTRATION=false
REQUIRE_REGISTRATION_CODE=true

# Recommended for local dev
TLDW_SQLITE_WAL_MODE=true
```

Notes:
- You can keep registration closed and only invite family members.
- `SESSION_ENCRYPTION_KEY` can be generated with:
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

## Step 2: Initialize AuthNZ and Create Admin

```bash
python -m tldw_Server_API.app.core.AuthNZ.initialize
```

Follow prompts to create the admin (parent/guardian) account.

## Step 3: Create Family Accounts

You have two safe options:

### Option A: Registration Codes (Recommended)

Create a registration code for each person:

```bash
python -m tldw_Server_API.app.core.AuthNZ.initialize --create-registration-code
```

Then each family member registers using the code:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username":"alex",
    "email":"alex@example.com",
    "password":"ChangeMe123!",
    "registration_code":"<CODE>"
  }'
```

### Option B: Admin Creates Accounts

1. Login as admin and get a JWT:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<admin password>"}'
```

2. Create a user via admin endpoint:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/admin/users \
  -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "username":"sam",
    "email":"sam@example.com",
    "password":"ChangeMe123!",
    "is_active": true
  }'
```

## Step 3b: Verify Account Setup

Before proceeding to guardrails, confirm each account works.

**Each user can log in and see their profile**:

```bash
# Log in as a family member
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alex","password":"ChangeMe123!"}' | python3 -m json.tool

# Use the returned token to check profile
curl -s http://127.0.0.1:8000/api/v1/auth/me \
  -H "Authorization: Bearer <USER_JWT>" | python3 -m json.tool
```

Expected: each user sees their own `username` and `"role": "user"`.

**Regular users cannot access admin endpoints**:

```bash
curl -s http://127.0.0.1:8000/api/v1/admin/users \
  -H "Authorization: Bearer <USER_JWT>"
```

Expected: `403 Forbidden`.

**Per-user data directories** (created lazily on first data access):

```bash
ls -la Databases/user_databases/
```

## Step 4: Set Guardrails (Practical Defaults)

### 1) Keep registration closed

```bash
ENABLE_REGISTRATION=false
REQUIRE_REGISTRATION_CODE=true
```

### 2) Limit providers and models via Virtual Keys

Virtual keys let you set **model/provider allowlists** and **usage budgets** per user. They are enforced when using `X-API-KEY` requests.

Create a virtual key for a user (example):

```bash
curl -X POST http://127.0.0.1:8000/api/v1/admin/users/<USER_ID>/virtual-keys \
  -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "name":"sam-kidsafe",
    "allowed_endpoints":["chat.completions"],
    "allowed_providers":["openai"],
    "allowed_models":["gpt-4o-mini"],
    "budget_day_tokens": 20000,
    "budget_month_usd": 10
  }'
```

Use that key for the child’s API clients:

```bash
curl -H "X-API-KEY: <VIRTUAL_KEY>" \
  -H "Content-Type: application/json" \
  http://127.0.0.1:8000/api/v1/chat/completions \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"hello"}]}'
```

Notes:
- Virtual keys enforce **provider/model allowlists** and **budgets** for API-key traffic.
- If you rely on the Web UI (JWT), use account permissions and global rate limits as your primary guardrails.

### 3) Global rate limits (all users)

```bash
RG_ENABLED=true
# Tune requests.rpm / requests.burst in Config_Files/resource_governor_policies.yaml
```

### 4) Disable BYOK for kids

If you don’t want users to add their own provider keys:

```bash
BYOK_ENABLED=false
```

Or allow only a small set of providers:

```bash
BYOK_ENABLED=true
BYOK_ALLOWED_PROVIDERS=openai,anthropic
```

### 5) Restrict web egress (optional)

For web search/scraping or workflows, you can allowlist domains:

```bash
EGRESS_ALLOWLIST=example.com,openai.com
WORKFLOWS_EGRESS_PROFILE=strict
WORKFLOWS_EGRESS_ALLOWLIST=example.com,openai.com
```

### 6) Enable security alerts

Send alerts to a file (and optionally webhook/email):

```bash
SECURITY_ALERTS_ENABLED=true
SECURITY_ALERT_FILE_PATH=./Databases/security_alerts.log
SECURITY_ALERT_MIN_SEVERITY=medium
```

## Step 5: Assign Roles and Permissions (Optional)

You can restrict access to specific features by using roles and permission overrides.

- List permissions:

```bash
curl -H "Authorization: Bearer <ADMIN_JWT>" \
  http://127.0.0.1:8000/api/v1/admin/permissions
```

- Deny a permission for a specific user:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/admin/users/<USER_ID>/overrides \
  -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{"permission_name":"<permission from list>","effect":"deny"}'
```

If you aren’t sure which permission names map to features, use the OpenAPI docs (`/docs`) to inspect the dependencies or start by denying the most sensitive endpoints (admin tools, web scraping, file uploads, etc.).

## Tips for Families

- Use a unique account per person (avoid shared accounts).
- Keep the admin account private and don't share the admin JWT.
- Start with conservative limits and loosen them over time.
- Review `Databases/security_alerts.log` occasionally.
- **Bookmark the WebUI** on each person's device so they don't need to remember the URL.
- **Password management**: Use a family password manager (1Password, Bitwarden) to store each person's credentials. Avoid writing passwords on sticky notes.
- **Token expiry**: JWTs expire after 24 hours by default. The WebUI handles refresh automatically. For API users, call `/api/v1/auth/refresh` before the token expires.
- **Periodic review**: Once a month, check the admin dashboard for unusual activity or budget overruns on virtual keys.

## Troubleshooting

### Reset a user's password

As admin, you can reset any user's password:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/admin/users/<USER_ID>/reset-password \
  -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{"new_password":"NewSecurePass123!"}'
```

### Deactivate / lock an account

If a family member should no longer have access:

```bash
curl -s -X PATCH http://127.0.0.1:8000/api/v1/admin/users/<USER_ID> \
  -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

The user will be unable to log in or use existing tokens.

### Revoke active sessions

To force a user to re-authenticate (e.g., if their token may be compromised):

```bash
curl -s -X DELETE http://127.0.0.1:8000/api/v1/admin/users/<USER_ID>/sessions \
  -H "Authorization: Bearer <ADMIN_JWT>"
```

### Server won't start / "JWT_SECRET_KEY not set"

Ensure `.env` contains all required secrets. See the [Household_Multi_User_Walkthrough.md](../WebUI_Extension/Household_Multi_User_Walkthrough.md) section 4b for the complete list.

### "Database is locked"

Set `TLDW_SQLITE_WAL_MODE=true` in `.env`. For persistent issues, consider switching to Postgres (see [Multi-User_Postgres_Setup.md](../Server/Multi-User_Postgres_Setup.md)).

## Related Docs

- **Full setup walkthrough**: [Household_Multi_User_Walkthrough.md](../WebUI_Extension/Household_Multi_User_Walkthrough.md) - Start-to-finish guide for a household of 3 users
- Multi-user SQLite setup: [Multi-User_SQLite_Setup.md](../Server/Multi-User_SQLite_Setup.md)
- Multi-user Postgres setup: [Multi-User_Postgres_Setup.md](../Server/Multi-User_Postgres_Setup.md)
- Authentication setup: [Authentication_Setup.md](../Server/Authentication_Setup.md)
- Multi-user production: [Multi-User_Deployment_Guide.md](../Server/Multi-User_Deployment_Guide.md)
- Production hardening: [Production_Hardening_Checklist.md](../Server/Production_Hardening_Checklist.md)
- BYOK configuration: [BYOK_User_Guide.md](../Server/BYOK_User_Guide.md)
- Backups with Litestream: [Backups_Using_Litestream.md](../Server/Backups_Using_Litestream.md)
- Environment variables: `Docs/Operations/Env_Vars.md`
