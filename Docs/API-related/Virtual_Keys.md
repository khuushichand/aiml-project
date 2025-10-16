# Virtual Keys API

Virtual Keys are API keys with scoped access and LLM usage budgets. They can be associated with Organizations and Teams.

Base path: `/api/v1/admin`

## Create Virtual Key

POST `/api/v1/admin/users/{user_id}/virtual-keys`

Request body (application/json):
```json
{
  "name": "lab-chat-key",
  "description": "Ephemeral key for lab UI",
  "expires_in_days": 30,
  "org_id": 1,
  "team_id": 5,
  "allowed_endpoints": ["chat.completions", "embeddings"],
  "allowed_providers": ["openai"],
  "allowed_models": ["gpt-4o-mini", "text-embedding-3-small"],
  "budget_day_tokens": 100000,
  "budget_month_tokens": 2000000,
  "budget_day_usd": 5.0,
  "budget_month_usd": 100.0
}
```

Response 200 (application/json):
```json
{
  "id": 42,
  "key": "tldw_R4nd0mlyG3n3rat3d...",
  "key_prefix": "tldw_R4nd0...",
  "name": "lab-chat-key",
  "scope": "read",
  "expires_at": "2025-12-01T00:00:00Z",
  "created_at": "2025-11-01T00:00:00Z",
  "message": "Store this key securely - it will not be shown again"
}
```

Notes:
- The `key` value is only returned once at creation/rotation time.
- `allowed_endpoints` supports: `chat.completions`, `embeddings` (more may be added later).

Example (cURL):
```bash
curl -X POST http://127.0.0.1:8000/api/v1/admin/users/123/virtual-keys \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -d '{
    "name": "lab-chat-key",
    "allowed_endpoints": ["chat.completions", "embeddings"],
    "allowed_providers": ["openai"],
    "allowed_models": ["gpt-4o-mini"],
    "budget_day_tokens": 100000,
    "budget_month_usd": 50.0
  }'
```

## List Virtual Keys for a User

GET `/api/v1/admin/users/{user_id}/virtual-keys`

Response 200 (application/json):
```json
[
  {
    "id": 42,
    "key_prefix": "tldw_R4nd0...",
    "name": "lab-chat-key",
    "description": "Ephemeral key for lab UI",
    "scope": "read",
    "status": "active",
    "created_at": "2025-11-01T00:00:00Z",
    "expires_at": "2025-12-01T00:00:00Z",
    "usage_count": 3,
    "last_used_at": "2025-11-02T10:00:00Z",
    "last_used_ip": "203.0.113.10"
  }
]
```

## Enforcement

- Endpoint allowlists: enforced for LLM endpoints (`/api/v1/chat/completions`, `/api/v1/embeddings`). Requests to disallowed endpoints receive 403.
- Budgets: evaluated from `llm_usage_log` daily/monthly. Exceeding a budget returns 402 with details.
- Optional allowlists: set `llm_allowed_providers` and/or `llm_allowed_models` (on the key via admin SQL for now). If present, middleware enforces provider via `X-LLM-Provider` header and model parsed from JSON request body when available.

```http
HTTP/1.1 402 Payment Required
Content-Type: application/json

{
  "error": "budget_exceeded",
  "message": "Virtual key budget exceeded",
  "details": {
    "over": true,
    "reasons": ["day_tokens_exceeded:1200/1000"],
    "day": {"tokens": 1200, "usd": 0.55},
    "month": {"tokens": 20000, "usd": 12.34}
  }
}
```

### Using the virtual key

- Use `X-API-KEY: <virtual_key>` header for API-key auth.
- Optional provider header: `X-LLM-Provider: <provider>` when provider allowlists are enabled.

Chat example (cURL):
```bash
curl -X POST http://127.0.0.1:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: <VIRTUAL_KEY>" \
  -H "X-LLM-Provider: openai" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

Embeddings example (cURL):
```bash
curl -X POST http://127.0.0.1:8000/api/v1/embeddings \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: <VIRTUAL_KEY>" \
  -d '{
    "model": "text-embedding-3-small",
    "input": ["test phrase"]
  }'
```

## Admin: Orgs and Teams (selected)

- POST `/api/v1/admin/orgs` — create organization
- GET `/api/v1/admin/orgs` — list
- POST `/api/v1/admin/orgs/{org_id}/teams` — create team
- GET `/api/v1/admin/orgs/{org_id}/teams` — list
- POST `/api/v1/admin/teams/{team_id}/members` — add member
- GET `/api/v1/admin/teams/{team_id}/members` — list

These endpoints assist grouping users and associating Virtual Keys with org/team scopes.
Example (cURL):
```bash
curl -X GET http://127.0.0.1:8000/api/v1/admin/users/123/virtual-keys \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```
