# Billing Module

This module provides subscription lifecycle, usage enforcement, and Stripe webhook handling for organization billing.

Related documents:
- `Docs/Operations/Hosted_Stripe_Test_Mode_Runbook.md`
- `Docs/Published/Deployment/Hosted_Staging_Runbook.md`

## Key Environment Variables

- `BILLING_ENABLED`
  - Enables billing endpoints and Stripe-backed billing behavior when set to `true`.
- `LIMIT_ENFORCEMENT_ENABLED`
  - Enables limit enforcement checks independent of Stripe checkout.
- `STRIPE_API_KEY`
  - Stripe API key used for checkout/portal/subscription operations.
- `STRIPE_WEBHOOK_SECRET`
  - Secret used to verify `Stripe-Signature` on webhook requests.
- `BILLING_WEBHOOK_PROCESSING_TIMEOUT_SECONDS`
  - Timeout (seconds) after which stale `processing` webhook claims may be reclaimed.
  - Default: `300`.
- `BILLING_ENFORCEMENT_FAILURE_MODE`
  - Enforcement fallback mode when limits/usage data sources fail.
  - Allowed values: `open` (default), `closed`.
  - `open`: permissive limits and allow-on-error behavior.
  - `closed`: restrictive limits and deny-on-error behavior.

### Redirect Host Allowlist

- `BILLING_ALLOWED_REDIRECT_HOSTS`
  - Comma-separated host allowlist for billing redirect URLs used by:
    - `POST /api/v1/billing/checkout` (`success_url`, `cancel_url`)
    - `POST /api/v1/billing/portal` (`return_url`)
  - When configured: request URLs must match one of the configured host patterns.
- `BILLING_REDIRECT_ALLOWLIST_REQUIRED`
  - When `true`, billing redirect requests are rejected unless `BILLING_ALLOWED_REDIRECT_HOSTS` is set.
  - Recommended `true` in production.
- `BILLING_REDIRECT_REQUIRE_HTTPS`
  - When `true`, redirect URLs must use `https`.
  - Recommended `true` in production.

Supported patterns:
- Exact host: `app.example.com`
- Wildcard subdomain suffix: `*.example.com`

Examples:
- `BILLING_ALLOWED_REDIRECT_HOSTS=app.example.com,billing.example.com`
- `BILLING_ALLOWED_REDIRECT_HOSTS=*.example.com,localhost`

Validation behavior:
- Disallowed hosts are rejected with HTTP `400` before Stripe session creation.
- Missing required allowlist config is rejected with HTTP `503`.
- Non-HTTPS redirect URLs are rejected with HTTP `400` when HTTPS enforcement is enabled.
- The URL hostname is used for matching (scheme/path/query are ignored for allowlist matching).

## Notes

- Stripe-backed subscription cancel/resume operations fail closed when Stripe cannot be reached or is unavailable, to avoid local/remote state drift.
- Non-active subscription statuses (for example `past_due` or `canceled`) fall back to free-tier limits during enforcement.
- Hosted Stripe webhook prove-out should target `POST /api/v1/billing/webhooks/stripe`; see `Docs/Operations/Hosted_Stripe_Test_Mode_Runbook.md`.
