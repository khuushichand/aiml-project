# Organization Administration Guide

This guide covers organization management for owners, administrators, team leads, and platform operators.

## Introduction

### Organization Hierarchy

```
Organization (e.g., "Acme Corp")
├── Members (owner, admins, leads, members)
├── Teams
│   ├── Team A (e.g., "Engineering")
│   │   └── Team Members
│   └── Team B (e.g., "Research")
│       └── Team Members
├── Invites
└── Subscription (billing plan)
```

### Role-Based Access Control

Organizations use a hierarchical role system:
- **Owner**: Full control, including billing and deletion
- **Admin**: Can manage members, teams, and invites
- **Lead**: Team leadership with limited org-level permissions
- **Member**: Basic access to view org and shared content

## Creating and Managing Organizations

### Creating a New Organization

**API Request:**
```bash
curl -X POST http://localhost:8000/api/v1/orgs \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-company",
    "display_name": "My Company Inc."
  }'
```

The creator automatically becomes the organization owner.

### Updating Organization Settings

**API Request:**
```bash
curl -X PATCH http://localhost:8000/api/v1/orgs/1 \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "display_name": "My Company International"
  }'
```

Requires: owner or admin role.

### Transferring Ownership

Transfer ownership to another existing member:

**API Request:**
```bash
curl -X POST http://localhost:8000/api/v1/orgs/1/transfer \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"new_owner_id": 42}'
```

Requires: owner role. The previous owner is demoted to admin.

### Deleting an Organization

**API Request:**
```bash
curl -X DELETE http://localhost:8000/api/v1/orgs/1 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Prerequisites:**
- Must be the owner
- Must cancel any active Stripe subscription first
- All invites will be automatically revoked

## Managing Members

### Viewing Organization Members

**API Request:**
```bash
curl http://localhost:8000/api/v1/orgs/1/members \
  -H "Authorization: Bearer YOUR_TOKEN"
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
    },
    {
      "user_id": 2,
      "username": "bob",
      "email": "bob@example.com",
      "role": "member",
      "added_at": "2024-01-20T14:00:00Z"
    }
  ],
  "count": 2
}
```

### Adding Members Directly

Add a user by their user ID (alternative to invite codes):

**API Request:**
```bash
curl -X POST http://localhost:8000/api/v1/orgs/1/members \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 42, "role": "member"}'
```

Requires: owner or admin role.

### Updating Member Roles

**API Request:**
```bash
curl -X PATCH http://localhost:8000/api/v1/orgs/1/members/42 \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role": "admin"}'
```

**Valid roles:** `member`, `lead`, `admin`

Note: You cannot grant the `owner` role via this endpoint; use ownership transfer instead.

### Removing Members

**API Request:**
```bash
curl -X DELETE http://localhost:8000/api/v1/orgs/1/members/42 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Note: You cannot remove the owner. Transfer ownership first if needed.

## Teams

### Creating Teams

**API Request:**
```bash
curl -X POST http://localhost:8000/api/v1/orgs/1/teams \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "engineering",
    "description": "Engineering team"
  }'
```

Requires: owner or admin role.

### Listing Teams

**API Request:**
```bash
curl http://localhost:8000/api/v1/orgs/1/teams \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Managing Team Settings

**API Request:**
```bash
curl -X PATCH http://localhost:8000/api/v1/orgs/1/teams/5 \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"description": "Core Engineering team"}'
```

### Deleting Teams

**API Request:**
```bash
curl -X DELETE http://localhost:8000/api/v1/orgs/1/teams/5 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Requires: owner or admin role.

## Invite Codes

Invite codes allow you to onboard new members without knowing their user IDs.

### Creating Invite Codes

**API Request:**
```bash
curl -X POST http://localhost:8000/api/v1/orgs/1/invites \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "max_uses": 10,
    "expiry_days": 7,
    "role_to_grant": "member",
    "team_id": null,
    "description": "Q1 onboarding invites"
  }'
```

**Parameters:**

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `max_uses` | No | 1 | Maximum redemptions (1-1000) |
| `expiry_days` | No | 7 | Days until expiration (1-365) |
| `role_to_grant` | No | member | Role to assign: `member`, `lead`, or `admin` |
| `team_id` | No | null | Also add to this team |
| `description` | No | null | Internal note about this invite |

**Response:**
```json
{
  "id": 1,
  "code": "ABC123XYZ",
  "org_id": 1,
  "role_to_grant": "member",
  "max_uses": 10,
  "uses_count": 0,
  "expires_at": "2024-01-22T10:30:00Z",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Team-Specific Invites

To add users to both the org and a specific team:

**API Request:**
```bash
curl -X POST http://localhost:8000/api/v1/orgs/1/invites \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "max_uses": 5,
    "expiry_days": 14,
    "role_to_grant": "member",
    "team_id": 5
  }'
```

### Listing Active Invites

**API Request:**
```bash
curl "http://localhost:8000/api/v1/orgs/1/invites?include_expired=false" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Monitoring Invite Usage

The response includes `uses_count` showing how many times the invite has been redeemed.

### Revoking Invites

**API Request:**
```bash
curl -X DELETE http://localhost:8000/api/v1/orgs/1/invites/1 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Revoked invites cannot be redeemed even if they haven't expired.

## Role Permissions Matrix

### Organization Roles

| Action | owner | admin | lead | member |
|--------|:-----:|:-----:|:----:|:------:|
| View org | Y | Y | Y | Y |
| Update org settings | Y | Y | - | - |
| Delete org | Y | - | - | - |
| Create/delete teams | Y | Y | - | - |
| Manage org members | Y | Y | - | - |
| Create invite codes | Y | Y | - | - |
| View billing | Y | Y | - | - |
| Manage billing | Y | - | - | - |
| Transfer ownership | Y | - | - | - |

### Team Roles

| Action | org_owner | org_admin | team_lead | team_member |
|--------|:---------:|:---------:|:---------:|:-----------:|
| View team | Y | Y | Y | Y |
| Update team settings | Y | Y | Y | - |
| Delete team | Y | Y | - | - |
| Manage team members | Y | Y | Y | - |

## Billing and Subscriptions

Billing features are available when `BILLING_ENABLED=true`.

### Viewing Your Current Plan

**API Request:**
```bash
curl "http://localhost:8000/api/v1/billing/subscription?org_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN"
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
  "limits": {
    "storage_gb": 10,
    "api_calls_day": 5000,
    "llm_tokens_month": 15000000,
    "team_members": 5,
    "advanced_analytics": true
  }
}
```

### Subscription Plans

| Plan | Price/mo | Storage | API/day | LLM tokens/mo | Team members |
|------|----------|---------|---------|---------------|--------------|
| Free | $0 | 1 GB | 100 | 300K | 1 |
| Pro | $29 | 10 GB | 5,000 | 15M | 5 |
| Enterprise | $199 | 100 GB | 50,000 | 150M | Unlimited |

### Upgrading Your Plan

**API Request:**
```bash
curl -X POST http://localhost:8000/api/v1/billing/checkout \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "org_id": 1,
    "plan_name": "pro",
    "billing_cycle": "monthly"
  }'
```

**Response:**
```json
{
  "checkout_url": "https://checkout.stripe.com/c/pay/..."
}
```

Redirect users to this URL to complete payment.

### Accessing the Billing Portal

For managing payment methods, viewing invoices, and canceling:

**API Request:**
```bash
curl -X POST http://localhost:8000/api/v1/billing/portal \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"org_id": 1}'
```

**Response:**
```json
{
  "portal_url": "https://billing.stripe.com/p/session/..."
}
```

### Viewing Usage

**API Request:**
```bash
curl "http://localhost:8000/api/v1/billing/usage?org_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{
  "api_calls_today": 45,
  "api_calls_limit": 100,
  "storage_used_gb": 0.5,
  "storage_limit_gb": 1,
  "llm_tokens_month": 150000,
  "llm_tokens_limit": 300000,
  "team_members_count": 3,
  "team_members_limit": 5
}
```

### Canceling a Subscription

**API Request:**
```bash
curl -X POST http://localhost:8000/api/v1/billing/subscription/cancel \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "org_id": 1,
    "at_period_end": true
  }'
```

With `at_period_end: true`, access continues until the current billing period ends.

## Limit Enforcement

### Soft Limits (80%)

When usage reaches 80% of a limit:
- API responses include `X-Billing-Warning` header
- Usage dashboard shows warnings
- No functionality is restricted

### Hard Limits (100%)

When limits are exceeded:

| Resource | Behavior |
|----------|----------|
| API calls/day | HTTP 429 with `Retry-After` header |
| LLM tokens/month | HTTP 402 Payment Required |
| Storage | HTTP 413 (uploads blocked) |
| Team members | Invite creation blocked |

### Grace Periods

- **Payment failure**: 3-day grace period before downgrade to Free
- **Subscription canceled**: Access until period end, then Free

### What Happens When Limits Are Exceeded

1. **API calls**: Requests are blocked with 429 status until the daily limit resets
2. **LLM tokens**: Token-consuming operations fail with 402 status
3. **Storage**: New uploads are blocked; existing content remains accessible
4. **Team members**: Cannot add new members or create invites until under limit

## Platform Admin Features

Platform administrators (separate from org admins) have additional capabilities.

### Admin Endpoints

Platform admin endpoints at `/admin/organizations/*`:
- List all organizations
- View any organization's details
- Modify any organization's settings
- Override subscription limits

### Managing All Organizations

**API Request:**
```bash
curl http://localhost:8000/admin/organizations \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

### Overriding Plan Limits

Platform admins can set custom limits that override the plan defaults:

**API Request:**
```bash
curl -X PATCH http://localhost:8000/admin/organizations/1/limits \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "custom_limits_json": {
      "api_calls_day": 10000,
      "storage_gb": 50
    }
  }'
```

## Best Practices

### Invite Management

1. **Use descriptive names**: Add descriptions to invites for tracking
2. **Set reasonable expiry**: 7-14 days is typical for onboarding
3. **Monitor usage**: Check `uses_count` to track adoption
4. **Revoke unused invites**: Clean up old invites regularly

### Team Structure

1. **Logical grouping**: Organize teams by function or project
2. **Appropriate roles**: Grant minimum necessary permissions
3. **Regular audits**: Review memberships periodically

### Billing Management

1. **Monitor usage**: Check usage regularly to avoid surprises
2. **Upgrade proactively**: Upgrade before hitting limits
3. **Use soft limit warnings**: Act on warning headers

## Related Documentation

- [Organizations and Sharing Guide](Organizations_and_Sharing.md) - For end users
- [Orgs and Billing API Reference](../Published/API-related/Orgs_Billing_API.md) - Full API documentation
- [Production Hardening Checklist](Production_Hardening_Checklist.md) - Security best practices
