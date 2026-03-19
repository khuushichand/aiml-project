# Hosted SaaS Launch Program Design

**Date:** 2026-03-18
**Scope:** Full `Immediate` bucket from the SaaS readiness review
**Goal:** Define the shortest credible path from the current self-host biased stack to a cloud-managed hosted SaaS launch with self-serve single-user subscriptions, magic link support, and a narrow core product.

## Launch Target

- Hosted SaaS, not self-host-first packaging
- Single-user subscriptions first
- Teams later
- B2B later
- `admin-ui` remains internal-only
- Customer-facing v1 is a narrow core offer, not the full route catalog
- Pricing starts with flat tiers plus usage-based overage or add-on mechanics
- Hosted deployment uses cloud-managed infrastructure from day one

## Inputs

- [SaaS readiness review report](/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Plans/2026-03-18-saas-readiness-review-report.md)
- Existing billing, auth, and admin coverage already present in the repo
- Current public frontend in [`apps/tldw-frontend`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend)

## Design Review Corrections

The initial two-phase idea was directionally correct but too optimistic in a few places. These issues must be treated as first-class design constraints:

1. Hosted auth cannot inherit the current self-hosted browser-token model unchanged.
   - The public frontend currently persists `accessToken`, `refreshToken`, and `orgId` in client storage.
   - That is acceptable for extension or self-host flows, but it is the wrong default security boundary for a hosted SaaS web app.

2. Auth email flows do not yet target an explicit hosted frontend URL contract.
   - Password reset, email verification, and magic-link emails currently derive links from `BASE_URL` and backend-oriented paths.
   - Hosted SaaS needs canonical frontend callback routes and a stable way for backend email templates to point at them.

3. Personal account, org bootstrap, and billing scope are still ambiguous.
   - Billing is org-scoped.
   - The backend and frontend both contain best-effort org bootstrap behavior.
   - The hosted launch needs one deterministic rule: a new self-serve customer gets one personal org/workspace, and billing/account surfaces resolve against it consistently.

4. Hosted route hiding must be a platform/profile decision, not a late UX cleanup task.
   - The route registry and navigation currently expose many server-operator and non-core surfaces.
   - The hosted launch needs an allowlist, not ad hoc hiding.

5. Marketing and segment messaging currently conflict with the hosted product direction.
   - The public site strongly emphasizes self-hosting and “your data never leaves your infrastructure.”
   - Hosted SaaS messaging must be deliberate and not contradict the offering.

6. Cloud-managed launch should not quietly expand into a storage re-architecture project.
   - The current storage and quota model still relies heavily on filesystem-backed per-user data paths.
   - The first hosted profile should assume managed Postgres plus persistent volume-backed application storage unless a storage migration is explicitly added.

## Recommended Approach

Use a three-step launch program:

1. `Phase 1A: Hosted SaaS control plane contract`
   - Define the hosted auth boundary.
   - Define public callback URL contracts for email-based auth.
   - Define the personal-org invariant and hosted billing/account scope.
   - Define the hosted route allowlist.

2. `Phase 1B: Cloud-managed hosted operating profile`
   - Turn the contract into one canonical deployment profile.
   - Lock env vars, secrets, redirect allowlists, billing, staging checks, backup/restore, logs, metrics, and alerting.

3. `Phase 2: Customer funnel and launch-surface productization`
   - Build the customer-facing signup, login, onboarding, account, and billing experience on top of the hosted profile.
   - Rewrite hosted messaging and gate the public app to the narrow launch offer.

This sequencing deliberately makes the hosted product assumptions explicit before any funnel work is built on top of them.

## Phase 1A: Hosted SaaS Control Plane Contract

### Purpose

Freeze the behavioral rules that distinguish hosted SaaS from self-host or extension mode.

### Required decisions

#### 1. Hosted auth boundary

Pick one of these and treat it as a launch constraint:

- Recommended: same-origin BFF model with httpOnly cookies for the hosted web app
  - The browser does not persist bearer tokens directly.
  - Next routes or a thin frontend server layer proxy auth-sensitive requests.
  - The current client-storage token path remains available for extension and self-host surfaces.

- Not recommended for hosted v1: continue using browser-stored bearer tokens
  - Faster to wire
  - Creates a weaker security posture and likely rework later

Recommendation: use the BFF/httpOnly-cookie model for hosted SaaS.

#### 2. Public URL contract for auth emails

Define canonical public routes for:

- `/signup`
- `/login`
- `/auth/verify-email`
- `/auth/reset-password`
- `/auth/magic-link`
- `/billing/success`
- `/billing/cancel`
- `/billing`

The backend email service and billing redirect configuration must target these routes in hosted mode.

#### 3. Personal-org invariant

For self-serve single-user launch:

- each newly registered hosted customer receives one personal org/workspace
- that org is the default active org after signup, password login, or magic-link login
- billing, invoices, quotas, and account state resolve against that org unless the product later adds explicit multi-org switching
- the hosted frontend must not do best-effort org creation in the browser

#### 4. Hosted route allowlist

Define exactly which routes are visible in hosted mode:

- landing and segment pages that support the launch
- signup/login/auth callbacks
- onboarding
- core app routes only
- account area
- billing area

Everything else is either hidden, disabled, or excluded from hosted navigation until intentionally launched.

### Deliverables

- hosted auth architecture note
- hosted public URL contract
- hosted org and billing scope rules
- hosted route allowlist

## Phase 1B: Cloud-Managed Hosted Operating Profile

### Purpose

Turn the hosted contract into one deployment profile that can actually be staged and operated.

### Baseline assumptions

- `AUTH_MODE=multi_user`
- managed PostgreSQL
- managed email delivery for verification, password reset, and magic link
- same-origin frontend and API where possible
- restricted CORS
- managed TLS / reverse proxy
- centralized secret management
- billing enabled with staged Stripe setup and webhook validation
- persistent application storage backed by durable volumes unless a storage migration is explicitly added
- backups, restore test, logs, metrics, and alerting required before launch

### Deliverables

- canonical hosted env/config contract
- staging and production variable checklist
- auth email and billing redirect configuration guide
- backup/restore runbook
- logs/metrics/alerting baseline
- go-live checklist for hosted mode

## Phase 2: Customer Funnel And Launch-Surface Productization

### Purpose

Build a hosted product surface that a cold visitor can actually buy and enter.

### Scope

- dedicated `/signup` and `/login`
- password and magic-link entry points
- email verification and password reset completion screens
- first-run onboarding for the narrow core offer
- dedicated top-level customer account area
- dedicated top-level billing area
- plan, quota, invoice, checkout, portal, and overage messaging
- hosted navigation and route gating aligned with the allowlist
- rewrite marketing/segment messaging so hosted and self-host options are clearly distinguished

### Explicit non-goals

- team invites and seat management
- B2B SSO
- enterprise provisioning
- full route-catalog polish
- storage backend re-architecture unless separately approved

## Verification Strategy

### Phase 1A gates

- hosted auth boundary chosen and documented
- public auth/billing URL contract documented
- personal-org invariant documented and validated against backend behavior
- hosted route allowlist defined

### Phase 1B gates

- staging environment matches hosted env contract
- register, login, refresh, logout, password reset, email verification, and magic-link flows work in hosted multi-user mode
- billing checkout, portal, and webhook reconciliation pass in staging
- backup and restore are exercised
- logs, metrics, and alerting are live

### Phase 2 gates

- `apps/tldw-frontend` production build passes
- E2E coverage exists for the hosted customer funnel only
- account and billing surfaces are reachable and coherent
- non-core/operator-only routes are not exposed in hosted mode
- narrow core product smoke test passes after authentication

## Risks And Mitigations

### Risk: hosted funnel built on wrong auth model

- Mitigation: Phase 1A requires an explicit hosted auth boundary before frontend funnel implementation.

### Risk: billing/account UX breaks due to org ambiguity

- Mitigation: establish the personal-org invariant and remove hosted client-side org bootstrap behavior.

### Risk: hosted launch still looks like self-host product marketing

- Mitigation: treat positioning rewrite as required Phase 2 work, not optional polish.

### Risk: launch scope expands into full-platform cleanup

- Mitigation: use route allowlisting and narrow launch-surface tests instead of trying to perfect every existing route.

### Risk: “cloud-managed” expands into storage re-architecture

- Mitigation: keep hosted storage assumptions minimal for v1 unless a separate storage migration is approved.

## Final Recommendation

Proceed with the `platform-first` sequence, but split it into a contract-setting subphase and an operating-profile subphase before starting the customer funnel. That is the lowest-risk path to getting `tldw_server` and `apps/tldw-frontend` ready for a real hosted self-serve offer without rebuilding billing or admin from scratch.
