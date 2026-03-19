# tldw SaaS Readiness Review

**Date:** 2026-03-18
**Scope:** Hosted self-serve launch, single-user subscriptions first
**Out of Scope:** Teams-first workflows, B2B-first controls, non-core product modules

## Executive Verdict

- Overall readiness:
- Launch recommendation:

## Assumptions

- `admin-ui` remains internal-only
- Customer-facing v1 is a narrow core offer
- Pricing starts with flat tiers plus overages or credits

## Rubric

### 1. Customer Product Surface

### 2. Billing And Monetization

- Current state:
  - Backend billing is not a placeholder. The API exposes public plan listing plus authenticated org-scoped subscription, usage, checkout, billing portal, cancel, resume, and invoice flows.
  - Checkout and portal redirects are guarded by host allowlisting and optional HTTPS enforcement in the API layer.
  - Billing enforcement includes plan limits plus configurable overage behavior (`notify_only`, `degraded`, `hard_block`) with grace thresholds.
  - Trial support and Stripe price mapping exist in the subscription service layer.
- Evidence:
  - `tldw_Server_API/app/api/v1/endpoints/billing.py`
  - `tldw_Server_API/app/core/Billing/subscription_service.py`
  - `tldw_Server_API/app/core/Billing/enforcement.py`
  - `tldw_Server_API/tests/Billing/test_billing_usage_endpoint_unit.py`
  - `tldw_Server_API/tests/Billing/test_billing_webhooks_endpoint.py`
  - `tldw_Server_API/tests/Billing/test_billing_enforcement.py`
  - `tldw_Server_API/tests/Billing/test_overage_config.py`
  - `tldw_Server_API/tests/Billing/test_overage_enforcement_integration.py`
- Verification:
  - `python -m pytest tldw_Server_API/tests/Billing/test_billing_usage_endpoint_unit.py tldw_Server_API/tests/Billing/test_billing_webhooks_endpoint.py -v` passed `21/21`.
  - `python -m pytest tldw_Server_API/tests/Billing/test_billing_enforcement.py -v` passed `38/38`.
  - The broader integration billing lane is materially larger and was still running locally at the time this section was drafted.
- Readiness color: `Yellow`
- Blocker or caveat:
  - Billing primitives are present, but customer launch readiness still depends on deployment configuration and the customer-facing billing UX.
  - Billing is designed to fail closed when disabled or misconfigured, which is correct operationally but means launch readiness is configuration-sensitive rather than turnkey.
  - Overage policy exists, but the actual self-serve purchase UX for extra credits or raised limits is not yet verified in the public frontend.

### 3. Identity, Tenancy, And Data Isolation

- Current state:
  - The backend supports public registration, login, logout, refresh, session listing, password reset, email verification, magic-link auth, and MFA-aware login in multi-user deployments.
  - Self-registration is allowed outside the `local-single-user` profile and only requires a registration code when `REQUIRE_REGISTRATION_CODE` is enabled.
  - New users are auto-bootstrapped into a personal organization or workspace if they have no org membership.
  - Registration codes can optionally attach org or team scope for invite-driven expansion later.
- Evidence:
  - `tldw_Server_API/app/api/v1/endpoints/auth.py`
  - `tldw_Server_API/app/services/registration_service.py`
  - `tldw_Server_API/app/core/AuthNZ/settings.py`
- Verification:
  - Code inspection confirms `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, password reset, email verification, magic-link, and MFA paths.
  - Registration service logic confirms `ENABLE_REGISTRATION` and `REQUIRE_REGISTRATION_CODE` are the principal self-serve gating controls.
- Readiness color: `Yellow`
- Blocker or caveat:
  - The default repo posture is still `single_user` / `local-single-user`, which is the opposite of a hosted self-serve SaaS baseline.
  - Multi-user readiness therefore exists more as a supported operating mode than as the default launch profile.
  - Tenant and data isolation look intentional, but the deeper isolation evidence still needs a dedicated pass before this can move above yellow.

### 4. Operations And Internal Admin Readiness

### 5. Deployment, Compliance, And Supportability

## Immediate

## Short-term

## Later

## Manual At Launch

## Must Automate Before Launch
