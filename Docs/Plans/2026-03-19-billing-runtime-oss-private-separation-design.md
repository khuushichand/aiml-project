# Billing Runtime OSS/Private Separation Design

## Goal

Remove commercial billing and subscription runtime from the public `tldw_server` repo while preserving a coherent OSS/self-host core. The private hosted repo becomes the sole home for payments, pricing, subscriptions, entitlements, credits, overages, admin revenue operations, and hosted commercial frontend behavior.

## Current Problem

The public repo still ships commercial runtime in multiple layers:

- Stripe-backed checkout, portal, invoice, cancel/resume, and webhook endpoints.
- Stripe client and metering synchronization services.
- Billing admin endpoints for subscription overrides, credits, and revenue operations.
- Seeded paid-plan catalog and fallback pricing defaults in the OSS schema and service layer.
- Public frontend pages that still branch on hosted mode and advertise hosted trials or paid packaging.

This means the current OSS/private split is incomplete. Docs and hosted deployment assets are already private, but the public runtime still contains the hosted business model.

## Boundary Decision

This phase uses a hard commercial extraction model.

### Keep Public

The OSS repo should keep only self-host useful primitives:

- users, organizations, memberships, ownership, and RBAC
- generic rate limiting and resource-governance controls
- generic storage usage tracking
- generic quota math that has no dependency on plans, pricing, subscriptions, credits, or payment providers

### Move Private

The private repo should own:

- checkout, portal, invoice, cancel/resume, and customer billing routes
- Stripe webhook ingestion and idempotency handling
- Stripe client and metering sync
- admin billing and revenue-ops endpoints/services
- plan catalogs, paid-plan defaults, prices, credits, overages, and commercial entitlement policy
- hosted/commercial frontend messaging and account/billing flows

## Key Refinement From Review

This should not be implemented as a destructive table-drop project for OSS users.

The public repo should stop creating and using billing schema going forward, but we do not need to force upgrades to drop historical billing tables from existing installs. Existing public installs can retain now-unused tables. The private repo will carry forward any hosted schema and migration continuity it needs.

## Recommended Extraction Shape

### Phase 1: Remove Commercial Policy Leaks From OSS

First, remove the easiest policy leaks:

- seeded paid-plan catalog in AuthNZ migrations
- fallback pricing and public plan defaults in billing services
- hosted-mode marketing and hosted-trial CTAs in public frontend pages

This step reduces public leakage immediately and simplifies later runtime extraction.

### Phase 2: Extract Payment-Provider Runtime

Remove from OSS:

- Stripe checkout and portal routes
- Stripe webhook route
- Stripe client wrapper
- Stripe metering reconciliation service
- Stripe-specific tests and schemas

If any neutral usage or limits status API is still desired for OSS, it should be explicitly renamed and relocated outside the `billing` namespace.

### Phase 3: Extract Admin Revenue Operations

Remove from OSS:

- admin billing overview, subscription management, credits, and billing events
- related services, schemas, and tests
- any admin UI/API assumptions tied to revenue operations

This extraction should happen as a unit so the public repo does not retain orphaned internal-commercial admin code.

### Phase 4: Retire Public Billing Data Model

Stop shipping public billing schema/code paths:

- `subscription_plans`
- `org_subscriptions`
- `stripe_webhook_events`
- payment history
- billing audit tables/logs if they are purely commercial

This means:

- fresh OSS installs no longer create or rely on these tables
- OSS docs/tests stop referring to them
- the private repo becomes the only maintained home for that schema

Historical OSS installs may still have those tables present; that is acceptable.

## Neutral Usage API Decision

One explicit decision is required during implementation:

- If OSS should keep a neutral usage or limits endpoint for self-host admins, preserve only that narrow surface and rename/rehome it outside `billing`.
- If OSS should not expose any such surface, remove the public billing API entirely.

The default recommendation is to preserve only generic quota/resource-governance primitives and remove the `billing` namespace entirely from OSS unless a concrete self-host use case demands a neutral replacement.

## Frontend Guidance

The public frontend should no longer market or branch around hosted SaaS.

That means:

- remove hosted trial CTAs and commercial pricing from public pages
- remove public hosted-mode copy from industry/segment landing pages
- keep the OSS web client self-host/open-source focused
- only retain a minimal extension seam if the private repo genuinely depends on it cleanly

The seam should be neutral. OSS pages should not advertise hosted pricing or customer funnel behavior.

## Backend Refactor Guidance

Do not split by directory name alone. Split by dependency graph.

Examples:

- `check_limit()`-style generic limit math can stay public if detached from plan and payment concepts.
- plan/pricing/subscription state should move private even if currently mixed into a shared module.
- Stripe IDs, invoices, credits, overages, or portal/checkout semantics are all private by definition.

Mixed modules should be decomposed before deletion where needed so OSS keeps only the generic portion.

## Success Criteria

After this separation:

- fresh OSS installs do not create or depend on commercial billing schema
- the public backend ships no payment-provider runtime
- the public repo ships no revenue-ops admin surface
- the public frontend does not market or branch on hosted commercial flows
- the private repo is the sole canonical location for commercial billing/subscription runtime

## Non-Goals

This phase does not attempt to:

- drop historical billing tables from existing public deployments
- redesign the private hosted billing model
- change unrelated quota/rate-limit/resource-governance behavior that remains useful in OSS

## Recommended Next Step

Execute the split as a phased extraction plan:

1. Remove commercial policy leaks from frontend and plan defaults.
2. Extract Stripe/payment-provider runtime.
3. Extract admin revenue ops.
4. Retire the public billing schema and tests without destructive upgrade behavior.
