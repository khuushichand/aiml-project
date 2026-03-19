# Hosted SaaS Profile

Version: v0.1.0
Audience: operators preparing the first cloud-managed customer-facing deployment

Related documents
- Hosted staging runbook: `Docs/Published/Deployment/Hosted_Staging_Runbook.md`
- Hosted production runbook: `Docs/Published/Deployment/Hosted_Production_Runbook.md`
- Hosted Stripe test-mode runbook: `Docs/Operations/Hosted_Stripe_Test_Mode_Runbook.md`
- Hosted staging operations runbook: `Docs/Operations/Hosted_Staging_Operations_Runbook.md`

This profile defines the minimum deployment contract for the hosted SaaS launch surface. It is intentionally narrower than the general self-host guidance. The target is a same-origin hosted web app with server-managed auth sessions, public auth callback routes, org-scoped billing, and a narrow core product surface.

## 1) What this profile assumes

- Hosted SaaS, not self-host packaging.
- Single-user subscriptions first.
- `admin-ui` remains internal-only.
- Frontend and API are served behind the same public origin where possible.
- Auth sessions stay server-side through the hosted auth proxy boundary.
- AuthNZ runs in `multi_user` mode on PostgreSQL.
- Billing redirects are locked to the public app host.
- Application file storage remains durable volume-backed for v1 instead of forcing an immediate storage re-architecture.

## 2) Required env contract

These settings form the hosted release gate:

- `AUTH_MODE=multi_user`
- `DATABASE_URL=postgresql://...`
- `tldw_production=true`
- `PUBLIC_WEB_BASE_URL=https://app.example.com`
- `PUBLIC_PASSWORD_RESET_PATH=/auth/reset-password`
- `PUBLIC_EMAIL_VERIFICATION_PATH=/auth/verify-email`
- `PUBLIC_MAGIC_LINK_PATH=/auth/magic-link`
- `BILLING_REDIRECT_ALLOWLIST_REQUIRED=true`
- `BILLING_REDIRECT_REQUIRE_HTTPS=true`
- `BILLING_ALLOWED_REDIRECT_HOSTS=app.example.com`

Recommended supporting settings:

- `ALLOWED_ORIGINS=https://app.example.com`
- `CORS_ALLOW_CREDENTIALS=true` only when the deployed topology requires credentialed browser requests across origins
- managed SMTP or hosted email provider configured for verification, reset, and magic-link delivery
- Stripe secrets and webhook signing secret configured before checkout is enabled

## 3) Hosted topology

- Public entrypoint: `https://app.example.com`
- Next.js frontend and FastAPI API should sit behind the same reverse proxy or gateway where possible.
- Hosted auth routes live on the public frontend origin and keep bearer tokens out of browser storage.
- Internal admin tooling should stay on a separate origin or separate access path.

## 4) Storage and state

- AuthNZ and billing state should live in managed PostgreSQL.
- Per-user application data can remain on durable mounted storage for the first hosted launch.
- Backups must cover both PostgreSQL and the durable application storage path.
- Restore should be exercised before launch, not just documented.

## 5) Release-gate verification

For the canonical same-origin staging topology, start with `Docs/Published/Deployment/Hosted_Staging_Runbook.md` and use its compose overlay plus env-file validation flow.
For the first paid production cutover, use `Docs/Published/Deployment/Hosted_Production_Runbook.md` and the standalone hosted production compose files.

Run these checks before calling a hosted environment launch-ready:

```bash
source .venv/bin/activate
python Helper_Scripts/validate_hosted_saas_profile.py
python -m pytest tldw_Server_API/tests/AuthNZ/unit/test_validate_hosted_saas_profile.py tldw_Server_API/tests/AuthNZ/unit/test_email_service_public_urls.py -v
```

```bash
cd apps/tldw-frontend
bun run test:run __tests__/pages/login.hosted.test.tsx __tests__/pages/signup.hosted.test.tsx __tests__/pages/account-page.test.tsx __tests__/pages/billing-page.test.tsx __tests__/landing-hub.hosted.test.tsx __tests__/app/app-layout.hosted-navigation.test.tsx
bun run build
bun run e2e:hosted
```

## 6) What this profile does not promise yet

- team invites or seat management
- B2B or enterprise provisioning
- SSO
- a fully polished route catalog outside the hosted allowlist
- a new object-storage-first architecture

Use this profile as the canonical baseline for hosted staging and production. If a deployment needs to violate these assumptions, it is no longer the launch profile and should be treated as a separate design decision.
