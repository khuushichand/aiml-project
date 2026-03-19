# tldw SaaS Readiness Review

**Date:** 2026-03-18
**Scope:** Hosted self-serve launch, single-user subscriptions first
**Out of Scope:** Teams-first workflows, B2B-first controls, non-core product modules

## Executive Verdict

- Overall readiness: `Not ready for self-serve SaaS launch today`
- Launch recommendation:
  - Do not open paid self-serve signup yet.
  - The backend billing and auth foundations are materially ahead of the customer-facing product surface.
  - The immediate path to launch is to productize the public WebUI into a hosted customer funnel rather than to redesign billing or internal admin from scratch.

### Top Blockers

- No real hosted `/signup` or `/register` route in the public frontend
- `/login` is still effectively a server/auth configuration workflow, not a polished customer login or onboarding surface
- `/profile` is placeholder-only, so account and subscription self-management are incomplete
- Public frontend test coverage is actively failing in multiple unrelated areas, indicating release instability
- Hosted SaaS still requires an opinionated multi-user production profile instead of the repo’s default single-user/local posture

## Assumptions

- `admin-ui` remains internal-only
- Customer-facing v1 is a narrow core offer
- Pricing starts with flat tiers plus overages or credits

## Rubric

### 1. Customer Product Surface

- Current state:
  - The public frontend exposes many product routes, but it does not yet present a coherent self-serve SaaS funnel.
  - There is no actual `/signup` or `/register` page in the Next.js route tree, even though marketing pages link users to `/signup`.
  - `/login` currently routes users into the generic tldw settings/auth configuration surface rather than a dedicated hosted-product login or onboarding experience.
  - `/profile` is still a placeholder page rather than a real account-management surface.
  - Several routes remain explicit placeholders (`/config`, parts of `/connectors`, `/profile`), which weakens confidence in a tightly-scoped paid offering unless those modules are hidden from launch.
- Evidence:
  - `apps/tldw-frontend/pages/login.tsx`
  - `apps/packages/ui/src/components/Option/Settings/tldw.tsx`
  - `apps/tldw-frontend/e2e/login.spec.ts`
  - `apps/tldw-frontend/pages/profile.tsx`
  - `apps/tldw-frontend/README.md`
  - `apps/FRONTEND_AUDIT.md`
  - `apps/tldw-frontend/pages/for/researchers.tsx`
  - `apps/tldw-frontend/pages/for/journalists.tsx`
- Verification:
  - Route inventory confirms there is no `pages/signup.tsx` or `pages/register.tsx`.
  - `apps/tldw-frontend/e2e/login.spec.ts` explicitly expects `/login` to redirect into `/settings/tldw`, confirming the current login UX is settings-driven.
  - `bun run test:run` surfaced active failures in unrelated public UI areas, including workspace chat, media review, flashcards, and image-event synchronization.
  - `bun run build` was still running at the time this section was written, so no successful production-build signal was available yet.
- Readiness color: `Red`
- Scorecard:
  - Exists: `Partial`
  - Works end-to-end: `No`
  - Safe for customer use: `No`
  - Supportable in production: `No`
  - Team-ready without major rewrite: `Partial`
- Blocker or caveat:
  - A self-serve SaaS launch cannot proceed without a real hosted signup, login, onboarding, account, and billing funnel.
  - The current frontend still behaves like a client for configuring and using a server deployment, not like a product a new customer can purchase and enter cold.
  - Even after adding a signup funnel, the failing frontend test suite suggests broader release hardening work is required.

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
  - The broader billing integration suite was still running and mostly skipping locally because the heavier Postgres-backed integration environment was not enforced in this session.
- Readiness color: `Yellow`
- Scorecard:
  - Exists: `Yes`
  - Works end-to-end: `Mostly`
  - Safe for customer use: `Partial`
  - Supportable in production: `Partial`
  - Team-ready without major rewrite: `Yes`
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
- Scorecard:
  - Exists: `Yes`
  - Works end-to-end: `Mostly`
  - Safe for customer use: `Partial`
  - Supportable in production: `Partial`
  - Team-ready without major rewrite: `Yes`
- Blocker or caveat:
  - The default repo posture is still `single_user` / `local-single-user`, which is the opposite of a hosted self-serve SaaS baseline.
  - Multi-user readiness therefore exists more as a supported operating mode than as the default launch profile.
  - Tenant and data isolation look intentional, but the deeper isolation evidence still needs a dedicated pass before this can move above yellow.

### 4. Operations And Internal Admin Readiness

- Current state:
  - `admin-ui` is explicitly positioned as an internal sysadmin and operations console, not a customer-facing portal, which matches the intended SaaS operating model.
  - It covers core support and control-plane domains: users, organizations, teams, roles, API keys, monitoring, incidents, plans, budgets, data ops, logs, BYOK, and provider management.
  - The admin auth model is materially safer than the public frontend model: credentials are exchanged through Next route handlers and attached server-side via same-origin proxy routes instead of being left in browser-accessible storage.
  - The admin UI ships with a concrete release gate and real-backend Playwright lane rather than only ad hoc local dev guidance.
- Evidence:
  - `admin-ui/README.md`
  - `admin-ui/Release_Checklist.md`
  - `admin-ui/package.json`
  - `admin-ui/lib/billing.ts`
- Verification:
  - `cd admin-ui && bun run build` completed successfully.
  - `cd admin-ui && bun run test` finished with `473/474` tests passing and one failing logout-route test.
  - The built route inventory shows broad internal operational coverage across users, orgs, plans, monitoring, incidents, data ops, and subscriptions.
- Readiness color: `Green`
- Scorecard:
  - Exists: `Yes`
  - Works end-to-end: `Mostly`
  - Safe for customer use: `Yes`
  - Supportable in production: `Yes`
  - Team-ready without major rewrite: `Yes`
- Blocker or caveat:
  - This is in much better shape than the customer-facing WebUI and is not the immediate blocker for self-serve launch.
  - The single failing logout-route test should still be cleaned up because auth/session correctness matters for an internal control plane.
  - Admin UI strength does not compensate for missing customer signup, onboarding, and account/billing UX.

### 5. Deployment, Compliance, And Supportability

- Current state:
  - The repo already contains a credible production deployment story for hosted operation: multi-user + Postgres profile docs, first-time production setup, and an explicit hardening checklist.
  - Production docs call out the real SaaS baseline clearly: `tldw_production=true`, PostgreSQL for multi-user production, reverse-proxy TLS, restricted CORS, WebSocket upgrade support, backups, log centralization, metrics, and rate limiting.
  - The docs also recommend serving the WebUI behind the same origin as the API where possible, which is the right simplification for early SaaS.
- Evidence:
  - `Docs/Published/Deployment/First_Time_Production_Setup.md`
  - `Docs/Getting_Started/Profile_Docker_Multi_User_Postgres.md`
  - `Docs/User_Guides/Server/Production_Hardening_Checklist.md`
  - `README.md`
- Verification:
  - Documentation review confirms production guidance exists for secrets, Postgres, TLS, CORS, backups, observability, non-root containers, and rate limiting.
  - The deployment docs are substantially more mature than a typical hobby-only README.
- Readiness color: `Yellow`
- Scorecard:
  - Exists: `Yes`
  - Works end-to-end: `Mostly`
  - Safe for customer use: `Partial`
  - Supportable in production: `Mostly`
  - Team-ready without major rewrite: `Yes`
- Blocker or caveat:
  - The repo is operationally capable of production deployment, but the default running posture is still optimized for local or self-hosted use rather than hosted SaaS.
  - The missing pieces are now less about raw deployability and more about creating one opinionated hosted operating profile, with explicit env defaults, runbooks, and go-live checks for the SaaS product.
  - Legal/commercial customer-readiness items such as customer support workflows, service policy, and billing-ops runbooks are still implied rather than packaged as a launch system.

## Immediate

- Build a real hosted customer funnel in `apps/tldw-frontend`: dedicated signup, login, onboarding, account, and billing entry surfaces.
- Replace the settings-driven `/login` flow with a customer-facing auth flow that assumes hosted SaaS, not self-host configuration.
- Add a real `/signup` route and connect it to `/api/v1/auth/register`, email verification, password reset, and post-signup first-run onboarding.
- Add a real account and subscription management surface instead of the current `/profile` placeholder.
- Wire the public frontend to hosted billing flows: plans, checkout, portal, invoices, quota state, warnings, and upgrade/overage messaging.
- Hide, remove, or hard-gate placeholder and non-core routes from the launch product so the first paid offer is narrow and coherent.
- Get the public frontend release gate back to green enough for launch, starting with the failing Vitest coverage already observed in workspace chat, media review, flashcards, and image-event sync.
- Define and document one hosted production profile for SaaS: `AUTH_MODE=multi_user`, Postgres, `tldw_production=true`, same-origin WebUI/API, restricted CORS, TLS, backups, monitoring, and billing enabled.

## Short-term

- Add customer-facing quota and overage UX that explains what happens near limits, at limits, and after overage grace is exhausted.
- Decide the exact overage product model: notify-only vs degraded vs hard-block by category, and whether extra credits or raised limits are sold automatically or support-assisted first.
- Tighten the public release gate to the small launch surface rather than the whole product, so non-core regressions do not constantly obscure launch readiness.
- Package SaaS ops runbooks around billing exceptions, refunds, account recovery, password resets, and customer support triage using `admin-ui`.
- Run the Postgres-backed billing/AuthNZ integration lanes in a production-like staging profile and treat them as a real pre-launch gate.

## Later

- Expand from single-user subscriptions to team plans with invite acceptance, seat management, shared billing, and org-level settings.
- Add cleaner customer self-service for invoices, cancellations, plan changes, usage history, and support contacts.
- Add B2B features such as SSO, enterprise org provisioning, stronger audit exports, and contractual/compliance packaging.
- Rationalize the broader product catalog so advanced modules can be sold intentionally rather than simply exposed because routes already exist.

## Manual At Launch

- Refunds and billing exceptions
- Fraud review and suspicious-account handling
- Enterprise or team provisioning outside the self-serve path
- Support-assisted plan changes or raised limits, if the automated overage purchase flow is not ready
- Selected data export or deletion requests handled through internal ops rather than a polished customer portal

## Must Automate Before Launch

- Signup and login for hosted multi-user customers
- Password reset and email verification
- Subscription checkout and billing portal access
- Entitlement and quota enforcement tied to the active subscription state
- Basic account and subscription visibility in the customer-facing product
- Production deployment hardening, backups, monitoring, and alerting for the hosted profile
