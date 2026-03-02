# Family/Guardian Setup Guide

This guide is for parents or guardians who want to run tldw_server at home with separate accounts for each family member and practical guardrails (limits, filters, alerts).

> **Looking for the full walkthrough?** If you're starting from scratch, begin with [Household_Multi_User_Walkthrough.md](../WebUI_Extension/Household_Multi_User_Walkthrough.md) which covers installation, account creation, and verification end-to-end. This guide focuses on **guardrails and parental controls** to apply after setup.

> **Wizard-first setup (recommended for most families):** Use [Family_Guardrails_Wizard_Guide.md](./Family_Guardrails_Wizard_Guide.md) for the guided flow in `Settings -> Family Guardrails Wizard` (WebUI and extension options).

## Prefer Wizard-First Setup

If you are onboarding a family now, start with the Family Guardrails Wizard first, then return to this guide for advanced hardening:

1. Run the wizard to create guardian/dependent mappings and template-based plans.
2. Confirm dependent acceptance in the wizard tracker.
3. Use this guide to apply additional server-level controls (registration, virtual keys, rate limits, BYOK restrictions).

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

1. Login as admin and capture a JWT:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "username=<admin username>" \
  --data-urlencode "password=<admin password>" | python3 -m json.tool
```

Save the returned `access_token` as `<ADMIN_JWT>` for the next command.

2. Create a registration code for each person:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/admin/registration-codes \
  -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "max_uses": 1,
    "expiry_days": 7,
    "role_to_grant": "user"
  }' | python3 -m json.tool
```

3. Temporarily allow self-registration while still requiring a code:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/admin/registration-settings \
  -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "enable_registration": true,
    "require_registration_code": true
  }' | python3 -m json.tool
```

4. Each family member registers using the returned `code`:

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

5. Lock registration down again after onboarding:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/admin/registration-settings \
  -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "enable_registration": false,
    "require_registration_code": true
  }' | python3 -m json.tool
```

### Option B: Admin Creates Accounts

1. Login as admin and get a JWT:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "username=<admin username>" \
  --data-urlencode "password=<admin password>"
```

Save the returned `access_token` and use it as `<ADMIN_JWT>`.

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
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "username=alex" \
  --data-urlencode "password=ChangeMe123!" | python3 -m json.tool

# Use the returned token to check profile
curl -s http://127.0.0.1:8000/api/v1/users/me/profile \
  -H "Authorization: Bearer <USER_JWT>" | python3 -m json.tool
```

Expected: each user sees their own `user.username` and `user.role = "user"`.

**Regular users cannot access admin endpoints**:

```bash
curl -s http://127.0.0.1:8000/api/v1/admin/users \
  -H "Authorization: Bearer <USER_JWT>"
```

Expected: `403 Forbidden`.

**Per-user data directories** (created lazily on first data access):

```bash
# Bare metal
ls -la Databases/user_databases/

# Docker
docker compose -f Dockerfiles/docker-compose.yml exec app ls -la /app/Databases/user_databases/
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
- **Token expiry**: Access JWTs expire after 30 minutes by default (`ACCESS_TOKEN_EXPIRE_MINUTES=30`). The WebUI handles refresh automatically. For API users, call `/api/v1/auth/refresh` with the refresh token.
- **Periodic review**: Once a month, check the admin dashboard for unusual activity or budget overruns on virtual keys.

## Troubleshooting

### Reset a user's password

Current AuthNZ endpoints do not expose a direct admin-only password reset route.
Use one of these supported flows:

1) User knows current password:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/users/change-password \
  -H "Authorization: Bearer <USER_JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "current_password":"OldSecurePass123!",
    "new_password":"NewSecurePass123!"
  }'
```

2) User forgot password (email-based recovery):

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email":"alex@example.com"}'
```

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "token":"<RESET_TOKEN_FROM_EMAIL>",
    "new_password":"NewSecurePass123!"
  }'
```

If email delivery is not configured, `forgot-password` still returns a generic success message but no reset email will be sent.

### Deactivate / lock an account

If a family member should no longer have access:

```bash
curl -s -X PUT http://127.0.0.1:8000/api/v1/admin/users/<USER_ID> \
  -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

The user will be unable to log in or use existing tokens.

### Revoke active sessions

To force a user to re-authenticate (e.g., if their token may be compromised):

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/admin/users/<USER_ID>/sessions/revoke-all \
  -H "Authorization: Bearer <ADMIN_JWT>"
```

### Server won't start / "JWT_SECRET_KEY not set"

Ensure `.env` contains all required secrets. See the [Household_Multi_User_Walkthrough.md](../WebUI_Extension/Household_Multi_User_Walkthrough.md) section 4b for the complete list.

### "Database is locked"

Set `TLDW_SQLITE_WAL_MODE=true` in `.env`. For persistent issues, consider switching to Postgres (see [Multi-User_Postgres_Setup.md](../Server/Multi-User_Postgres_Setup.md)).

## Validated Commands (AuthNZ API-Guide Style)

#### Login (Multi-User Mode)
`POST /api/v1/auth/login`

Request content type: `application/x-www-form-urlencoded`

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "username=<username>" \
  --data-urlencode "password=<password>" | python3 -m json.tool
```

#### Refresh Token
`POST /api/v1/auth/refresh`

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<REFRESH_TOKEN>"}' | python3 -m json.tool
```

#### Create User (Admin)
`POST /api/v1/admin/users`

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/admin/users \
  -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "username":"sam",
    "email":"sam@example.com",
    "password":"ChangeMe123!",
    "role":"user",
    "is_active": true
  }' | python3 -m json.tool
```

#### Create Registration Code (Admin)
`POST /api/v1/admin/registration-codes`

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/admin/registration-codes \
  -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{"max_uses":1,"expiry_days":7,"role_to_grant":"user"}' | python3 -m json.tool
```

#### Revoke All Sessions for a User (Admin)
`POST /api/v1/admin/users/<USER_ID>/sessions/revoke-all`

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/admin/users/<USER_ID>/sessions/revoke-all \
  -H "Authorization: Bearer <ADMIN_JWT>" | python3 -m json.tool
```

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
