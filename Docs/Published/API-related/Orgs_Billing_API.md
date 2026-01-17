# Organizations, Invites, and Billing API Reference

Complete API reference for organizations, team management, invite codes, and billing endpoints.

## Authentication Context

### Standard Authentication

All endpoints require authentication via one of:
- **JWT Token**: `Authorization: Bearer <JWT>`
- **API Key**: `X-API-KEY: <key>` (single-user mode)

### Multi-Organization Context

Users can belong to multiple organizations. For org-scoped operations:

```http
X-TLDW-Org-Id: 1
```

If not provided, the first organization in the user's membership list is used.

Billing endpoints require explicit `org_id` parameter.

---

## Organizations API

Base Path: `/api/v1/orgs`

### List User's Organizations

```http
GET /api/v1/orgs
Authorization: Bearer <token>
```

**Response:**
```json
{
  "organizations": [
    {
      "id": 1,
      "name": "acme-corp",
      "display_name": "Acme Corporation",
      "role": "owner",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "count": 1
}
```

### Create Organization

```http
POST /api/v1/orgs
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "my-org",
  "display_name": "My Organization"
}
```

**Response:** `201 Created`
```json
{
  "id": 1,
  "name": "my-org",
  "display_name": "My Organization",
  "owner_user_id": 42,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Get Organization Details

```http
GET /api/v1/orgs/{org_id}
Authorization: Bearer <token>
```

**Response:**
```json
{
  "id": 1,
  "name": "my-org",
  "display_name": "My Organization",
  "owner_user_id": 42,
  "member_count": 5,
  "team_count": 2,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Update Organization

```http
PATCH /api/v1/orgs/{org_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "display_name": "New Display Name"
}
```

**Required Role:** owner or admin

### Delete Organization

```http
DELETE /api/v1/orgs/{org_id}
Authorization: Bearer <token>
```

**Required Role:** owner
**Prerequisites:** No active Stripe subscription

### Transfer Ownership

```http
POST /api/v1/orgs/{org_id}/transfer
Authorization: Bearer <token>
Content-Type: application/json

{
  "new_owner_id": 123
}
```

**Required Role:** owner
**Behavior:** Previous owner is demoted to admin

---

## Members API

Base Path: `/api/v1/orgs/{org_id}/members`

### List Members

```http
GET /api/v1/orgs/{org_id}/members
Authorization: Bearer <token>
```

**Response:**
```json
{
  "members": [
    {
      "user_id": 1,
      "username": "alice",
      "email": "alice@example.com",
      "role": "owner",
      "added_at": "2024-01-15T10:30:00Z"
    }
  ],
  "count": 1
}
```

### Add Member

```http
POST /api/v1/orgs/{org_id}/members
Authorization: Bearer <token>
Content-Type: application/json

{
  "user_id": 123,
  "role": "member"
}
```

**Required Role:** owner or admin
**Valid Roles:** `member`, `lead`, `admin`

### Update Member Role

```http
PATCH /api/v1/orgs/{org_id}/members/{user_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "role": "admin"
}
```

**Required Role:** owner or admin
**Note:** Cannot grant `owner` role (use transfer endpoint)

### Remove Member

```http
DELETE /api/v1/orgs/{org_id}/members/{user_id}
Authorization: Bearer <token>
```

**Required Role:** owner or admin
**Note:** Cannot remove the owner

---

## Teams API

Base Path: `/api/v1/orgs/{org_id}/teams`

### List Teams

```http
GET /api/v1/orgs/{org_id}/teams
Authorization: Bearer <token>
```

**Response:**
```json
{
  "teams": [
    {
      "id": 5,
      "name": "engineering",
      "description": "Engineering team",
      "member_count": 3,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "count": 1
}
```

### Create Team

```http
POST /api/v1/orgs/{org_id}/teams
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "dev-team",
  "description": "Development team"
}
```

**Required Role:** owner or admin

### Get Team

```http
GET /api/v1/orgs/{org_id}/teams/{team_id}
Authorization: Bearer <token>
```

### Update Team

```http
PATCH /api/v1/orgs/{org_id}/teams/{team_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "description": "Updated description"
}
```

**Required Role:** owner, admin, or team lead

### Delete Team

```http
DELETE /api/v1/orgs/{org_id}/teams/{team_id}
Authorization: Bearer <token>
```

**Required Role:** owner or admin

---

## Invites API

### Preview Invite (Public)

No authentication required.

```http
GET /api/v1/invites/preview?code=ABC123XYZ
```

**Response:**
```json
{
  "org_name": "Acme Corp",
  "org_slug": "acme-corp",
  "team_name": null,
  "role_to_grant": "member",
  "is_valid": true,
  "status": "valid"
}
```

**Possible Status Values:**

| Status | Description |
|--------|-------------|
| `valid` | Can be redeemed |
| `expired` | Past expiration date |
| `exhausted` | Reached max_uses |
| `revoked` | Manually deactivated |

### Redeem Invite

```http
POST /api/v1/invites/redeem
Authorization: Bearer <token>
Content-Type: application/json

{
  "code": "ABC123XYZ"
}
```

**Response:**
```json
{
  "success": true,
  "org_id": 1,
  "org_name": "Acme Corp",
  "team_id": null,
  "team_name": null,
  "role": "member",
  "was_already_member": false
}
```

**Idempotent:** If already a member, returns `success: true` with `was_already_member: true`.

### Create Invite

```http
POST /api/v1/orgs/{org_id}/invites
Authorization: Bearer <token>
Content-Type: application/json

{
  "max_uses": 10,
  "expiry_days": 7,
  "role_to_grant": "member",
  "team_id": null,
  "description": "Onboarding invite"
}
```

**Required Role:** owner or admin

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `max_uses` | int | No | 1 | Maximum redemptions (1-1000) |
| `expiry_days` | int | No | 7 | Days until expiration (1-365) |
| `role_to_grant` | string | No | member | Role: `member`, `lead`, `admin` |
| `team_id` | int | No | null | Also add to this team |
| `description` | string | No | null | Internal note |

**Response:**
```json
{
  "id": 1,
  "code": "ABC123XYZ",
  "org_id": 1,
  "team_id": null,
  "role_to_grant": "member",
  "max_uses": 10,
  "uses_count": 0,
  "expires_at": "2024-01-22T10:30:00Z",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### List Invites

```http
GET /api/v1/orgs/{org_id}/invites?include_expired=false
Authorization: Bearer <token>
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `include_expired` | bool | false | Include expired/exhausted invites |

### Revoke Invite

```http
DELETE /api/v1/orgs/{org_id}/invites/{invite_id}
Authorization: Bearer <token>
```

**Required Role:** owner or admin
**Response:** `204 No Content`

---

## Billing API

Base Path: `/api/v1/billing`

Stripe-backed billing operations (checkout, portal, subscription cancel/resume,
webhooks) require `BILLING_ENABLED=true`. Read-only endpoints (plans,
subscription status, usage, invoices) are available regardless of this flag.

### List Available Plans

```http
GET /api/v1/billing/plans
Authorization: Bearer <token>
```

**Response:**
```json
{
  "plans": [
    {
      "name": "free",
      "display_name": "Free",
      "price_usd_monthly": 0,
      "price_usd_yearly": 0,
      "limits": {
        "storage_mb": 1024,
        "api_calls_day": 100,
        "llm_tokens_month": 300000,
        "team_members": 1,
        "advanced_analytics": false
      }
    },
    {
      "name": "pro",
      "display_name": "Pro",
      "price_usd_monthly": 29,
      "price_usd_yearly": 290,
      "limits": {
        "storage_mb": 10240,
        "api_calls_day": 5000,
        "llm_tokens_month": 15000000,
        "team_members": 5,
        "advanced_analytics": true
      }
    }
  ]
}
```

### Get Subscription

```http
GET /api/v1/billing/subscription?org_id=1
Authorization: Bearer <token>
```

**Response:**
```json
{
  "org_id": 1,
  "plan_name": "pro",
  "status": "active",
  "billing_cycle": "monthly",
  "current_period_start": "2024-01-01T00:00:00Z",
  "current_period_end": "2024-02-01T00:00:00Z",
  "trial_end": null,
  "limits": {
    "storage_mb": 10240,
    "api_calls_day": 5000,
    "llm_tokens_month": 15000000,
    "team_members": 5
  }
}
```

### Create Checkout Session

```http
POST /api/v1/billing/checkout
Authorization: Bearer <token>
Content-Type: application/json

{
  "org_id": 1,
  "plan_name": "pro",
  "billing_cycle": "monthly"
}
```

**Response:**
```json
{
  "checkout_url": "https://checkout.stripe.com/c/pay/..."
}
```

Redirect the user to this URL to complete payment.

### Create Portal Session

```http
POST /api/v1/billing/portal
Authorization: Bearer <token>
Content-Type: application/json

{
  "org_id": 1
}
```

**Response:**
```json
{
  "portal_url": "https://billing.stripe.com/p/session/..."
}
```

### Cancel Subscription

```http
POST /api/v1/billing/subscription/cancel
Authorization: Bearer <token>
Content-Type: application/json

{
  "org_id": 1,
  "at_period_end": true
}
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `at_period_end` | bool | true | If true, access continues until period end |

### Resume Subscription

```http
POST /api/v1/billing/subscription/resume
Authorization: Bearer <token>
Content-Type: application/json

{
  "org_id": 1
}
```

### Get Usage

```http
GET /api/v1/billing/usage?org_id=1
Authorization: Bearer <token>
```

**Response:**
```json
{
  "api_calls_today": 50,
  "api_calls_limit": 100,
  "api_calls_percent": 50,
  "storage_used_gb": 0.5,
  "storage_limit_gb": 1,
  "storage_percent": 50,
  "llm_tokens_month": 150000,
  "llm_tokens_limit": 300000,
  "llm_tokens_percent": 50,
  "team_members_count": 3,
  "team_members_limit": 5
}
```

### List Invoices

```http
GET /api/v1/billing/invoices?org_id=1
Authorization: Bearer <token>
```

**Response:**
```json
{
  "invoices": [
    {
      "id": "inv_123",
      "amount_cents": 2900,
      "currency": "usd",
      "status": "paid",
      "created_at": "2024-01-01T00:00:00Z",
      "invoice_pdf_url": "https://..."
    }
  ]
}
```

### Stripe Webhook Handler

```http
POST /api/v1/billing/webhooks/stripe
Stripe-Signature: t=...,v1=...
Content-Type: application/json

{...stripe event...}
```

**Handled Events:**
- `checkout.session.completed` - New subscription
- `customer.subscription.updated` - Plan/status changes
- `customer.subscription.deleted` - Cancellation
- `invoice.paid` - Payment successful
- `invoice.payment_failed` - Payment failed

---

## Content Visibility API

### Share Content

```http
POST /api/v1/media/{id}/share
Authorization: Bearer <token>
Content-Type: application/json

{
  "visibility": "team",
  "team_id": 77
}
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `visibility` | string | Yes | `team` or `org` |
| `team_id` | int | If team | Required when visibility is `team` |

### Unshare Content

```http
DELETE /api/v1/media/{id}/share
Authorization: Bearer <token>
```

Reverts to personal visibility.

### Media Ingestion with Visibility

```http
POST /api/v1/media
Authorization: Bearer <token>
Content-Type: application/json

{
  "url": "https://...",
  "visibility": "org",
  "org_id": 1
}
```

### Search with Scope

```http
POST /api/v1/media/search
Authorization: Bearer <token>
Content-Type: application/json

{
  "query": "machine learning",
  "scope": "team"
}
```

**Scope Options:**

| Scope | Description |
|-------|-------------|
| `personal` | Only user's personal content |
| `team` | Content shared with user's teams |
| `org` | Content shared with user's organizations |
| `all` | All accessible content |

---

## Schemas

### InviteStatus Enum

| Value | Description |
|-------|-------------|
| `VALID` | Can be redeemed |
| `EXPIRED` | Past expiration date |
| `EXHAUSTED` | Reached max_uses |
| `REVOKED` | Manually deactivated |
| `NOT_FOUND` | Code doesn't exist |

### ContentVisibility Enum

| Value | Description |
|-------|-------------|
| `personal` | Only owner can access |
| `team` | Team members can access |
| `org` | All org members can access |

### OrgRole Enum

| Value | Description |
|-------|-------------|
| `owner` | Full control including billing and deletion |
| `admin` | Manage members, teams, invites |
| `lead` | Team leadership with limited org permissions |
| `member` | Basic access |

### EnforcementAction Enum

| Value | Description |
|-------|-------------|
| `ALLOW` | Request permitted |
| `WARN` | Request permitted with warning |
| `SOFT_BLOCK` | Request blocked (soft limit) |
| `HARD_BLOCK` | Request blocked (hard limit) |

---

## Error Responses

### 400 Bad Request

```json
{"detail": "max_uses must be between 1 and 1000"}
```

```json
{"detail": "role_to_grant cannot be 'owner'"}
```

```json
{"detail": "Team does not belong to this organization"}
```

### 402 Payment Required

```json
{
  "detail": "LLM token limit exceeded",
  "category": "llm_tokens_month",
  "limit": 300000,
  "current": 350000
}
```

### 403 Forbidden

```json
{"detail": "Insufficient permissions for this operation"}
```

```json
{"detail": "Must be organization owner to perform this action"}
```

### 404 Not Found

```json
{"detail": "Organization not found"}
```

```json
{"detail": "Invite code not found"}
```

### 409 Conflict

```json
{"detail": "Cannot delete organization with active subscription"}
```

### 429 Too Many Requests

```json
{
  "detail": "API call limit exceeded",
  "retry_after": 3600
}
```

---

## Response Headers

### Billing Warnings

```http
X-Billing-Warning: Approaching API call limit (85% used)
```

Returned when usage exceeds 80% of limit (soft limit).

### Rate Limits

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 15
X-RateLimit-Reset: 1702857600
```

---

## Environment Variables

```bash
# Billing
BILLING_ENABLED=true
LIMIT_ENFORCEMENT_ENABLED=true
STRIPE_API_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
BILLING_TRIAL_DAYS=14
BILLING_SOFT_LIMIT_PERCENT=80

# Stripe Products (optional, for seeding)
STRIPE_PRODUCT_PRO=prod_...
STRIPE_PRICE_PRO_MONTHLY=price_...
STRIPE_PRICE_PRO_YEARLY=price_...
```

---

## PostgreSQL RLS Notes

Team and organization content sharing requires PostgreSQL with Row-Level Security.

### Session Variables

Set per-request by the API:
```sql
SET app.current_user_id = '42';
SET app.team_ids = '5,7,12';
SET app.org_ids = '1,3';
```

### RLS Policies

Queries are automatically filtered by PostgreSQL based on:
- `visibility` column value
- User's org/team memberships

### SQLite Mode

- Personal content only (no team/org sharing)
- Application-layer filtering applied
- Recommended for single-user deployments

---

## Code Examples

### Creating an Organization and Inviting Members

```bash
# Create organization
ORG_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/orgs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-org", "display_name": "My Organization"}')

ORG_ID=$(echo $ORG_RESPONSE | jq -r '.id')

# Create invite code
INVITE_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v1/orgs/$ORG_ID/invites" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"max_uses": 10, "expiry_days": 7, "role_to_grant": "member"}')

INVITE_CODE=$(echo $INVITE_RESPONSE | jq -r '.code')
echo "Share this invite code: $INVITE_CODE"
```

### Python Client Example

```python
import json
from typing import Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

class TLDWClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}

    def _request_json(self, method, path, payload=None, params=None, headers=None):
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        hdrs = {"Content-Type": "application/json"}
        if headers:
            hdrs.update(headers)
        req = Request(url, data=data, headers=hdrs, method=method)
        with urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def preview_invite(self, code: str) -> dict:
        """Preview an invite without authentication."""
        return self._request_json(
            "GET",
            "/api/v1/invites/preview",
            params={"code": code},
        )

    def redeem_invite(self, code: str) -> dict:
        """Redeem an invite code."""
        return self._request_json(
            "POST",
            "/api/v1/invites/redeem",
            payload={"code": code},
            headers=self.headers,
        )

    def create_invite(
        self,
        org_id: int,
        max_uses: int = 1,
        expiry_days: int = 7,
        role: str = "member",
        team_id: Optional[int] = None
    ) -> dict:
        """Create an organization invite."""
        return self._request_json(
            "POST",
            f"/api/v1/orgs/{org_id}/invites",
            payload={
                "max_uses": max_uses,
                "expiry_days": expiry_days,
                "role_to_grant": role,
                "team_id": team_id,
            },
            headers=self.headers,
        )

    def get_usage(self, org_id: int) -> dict:
        """Get organization usage metrics."""
        return self._request_json(
            "GET",
            "/api/v1/billing/usage",
            params={"org_id": org_id},
            headers=self.headers,
        )

# Usage
def main():
    client = TLDWClient("http://localhost:8000", "your-token")

    # Preview before redeeming
    preview = client.preview_invite("ABC123XYZ")
    print(f"Joining: {preview['org_name']} as {preview['role_to_grant']}")

    if preview["is_valid"]:
        result = client.redeem_invite("ABC123XYZ")
        print(f"Joined org {result['org_name']}!")

if __name__ == "__main__":
    main()
```

---

## Related Documentation

- [Organizations and Sharing Guide](../User_Guides/Organizations_and_Sharing.md) - End user guide
- [Organization Administration Guide](../User_Guides/Organization_Administration.md) - Admin guide
- [API Design](API_Design.md) - General API design principles
- [Production Hardening Checklist](../User_Guides/Production_Hardening_Checklist.md) - Security best practices
