# Hosted Stripe Test Mode Runbook

Version: v0.1.0
Audience: operators proving the first hosted self-serve billing path in staging

This runbook covers the Stripe test-mode prove-out for the hosted SaaS launch profile. Use it only after the hosted staging stack is up, the public staging URL is reachable, and the hosted staging preflight passes.

## 1) Required env contract

These settings must be present in the hosted staging env file before checkout is enabled:

- `BILLING_ENABLED=true`
- `STRIPE_API_KEY=sk_test_...`
- `STRIPE_WEBHOOK_SECRET=whsec_...`
- `BILLING_ALLOWED_REDIRECT_HOSTS=<public-host>`
- `BILLING_REDIRECT_ALLOWLIST_REQUIRED=true`
- `BILLING_REDIRECT_REQUIRE_HTTPS=true`

Keep `PUBLIC_WEB_BASE_URL` aligned with the public staging app origin so checkout success, cancel, and billing-portal returns land on the same customer-facing host.

## 2) Confirm the public billing surface

Before involving Stripe, verify the staging app exposes the hosted billing routes:

```bash
curl -I https://staging.example.com/api/v1/billing/plans
```

The customer-facing `/billing` page should also load through the public app origin after sign-in.

## 3) Configure Stripe test products and prices

In the Stripe test dashboard:

1. create or confirm the test products and recurring prices for the launch plans
2. ensure the local plan catalog returned by `/api/v1/billing/plans` matches the plans you intend to sell
3. keep the launch offer narrow; do not expose plans that are not ready for customer checkout

This repo’s billing endpoints create checkout and portal sessions from the local plan catalog, so the staging prove-out should validate both the Stripe dashboard configuration and the server’s plan definitions together.

## 4) Forward Stripe webhooks to staging

The hosted Stripe webhook endpoint is:

```text
https://staging.example.com/api/v1/billing/webhooks/stripe
```

For Stripe CLI forwarding, run:

```bash
stripe listen \
  --forward-to https://staging.example.com/api/v1/billing/webhooks/stripe
```

Stripe CLI prints a signing secret for the forwarded session. Use that value for `STRIPE_WEBHOOK_SECRET` in staging while the forwarder is active.

## 5) Prove the core billing flows

Run these in order with a real staging account that owns its personal org:

1. `Checkout session creation`
   - Sign in to staging.
   - Visit `/billing`.
   - Choose a plan.
   - Confirm you are redirected into Stripe Checkout without redirect-host rejection errors.

2. `Redirect success and cancel`
   - Cancel once and confirm you return to the hosted app’s billing surface.
   - Complete checkout once and confirm success returns to the hosted app origin.

3. `Billing portal session`
   - Use the billing portal entrypoint from `/billing`.
   - Confirm the portal opens and the return link lands back on `/billing`.

4. `Webhook delivery and processing`
   - Confirm Stripe CLI or the Stripe dashboard shows delivery to `/api/v1/billing/webhooks/stripe`.
   - Confirm staging app logs show the webhook event accepted and processed.
   - Re-send one event from Stripe to confirm idempotent handling.

5. `Subscription state mutation`
   - After a successful checkout, confirm `/billing` reflects the active plan and current period.
   - Confirm `/api/v1/billing/subscription` returns the updated status for the signed-in org.

6. `Invoice visibility`
   - Confirm `/billing` shows the invoice history returned by `/api/v1/billing/invoices`.

7. `Cancel or downgrade`
   - Use the portal or the in-app flow to cancel or downgrade.
   - Confirm the new state is reflected on `/billing` and in the billing API.

## 6) Failure triage

- `Checkout or portal rejects redirects`
  - Re-check `BILLING_ALLOWED_REDIRECT_HOSTS`, `BILLING_REDIRECT_ALLOWLIST_REQUIRED`, and `BILLING_REDIRECT_REQUIRE_HTTPS`.

- `Webhook returns 400 invalid signature`
  - `STRIPE_WEBHOOK_SECRET` does not match the active Stripe CLI forwarder or dashboard endpoint secret.

- `Checkout or portal returns 502/503`
  - Re-check `BILLING_ENABLED`, `STRIPE_API_KEY`, and upstream Stripe reachability.

- `Subscription state is stale after a successful payment`
  - Confirm webhook delivery reached `/api/v1/billing/webhooks/stripe`.
  - Re-send the event from Stripe and inspect staging logs for processing failures.

## 7) Exit criteria

Do not call billing staging-ready until all of these are true:

- checkout succeeds in Stripe test mode
- cancel/success redirects return to the hosted app origin
- billing portal opens and returns cleanly
- Stripe webhooks are delivered and processed
- `/billing` reflects subscription and invoice state correctly

Related documents:

- `Docs/Operations/Hosted_Staging_Operations_Runbook.md`
- `tldw_Server_API/app/core/Billing/README.md`
- Private hosted deployment runbooks
