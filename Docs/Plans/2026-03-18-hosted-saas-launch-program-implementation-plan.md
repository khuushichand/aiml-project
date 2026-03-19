# Hosted SaaS Launch Program Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert the current self-host biased `tldw_server` + `apps/tldw-frontend` stack into a cloud-managed hosted SaaS launch surface for self-serve single-user subscriptions, with magic-link auth, dedicated account and billing areas, and a narrow core product.

**Architecture:** Implement the launch in three ordered phases. First, add hosted-mode runtime primitives and the backend public URL contract. Second, reuse the `admin-ui` same-origin proxy and httpOnly-cookie pattern to give the hosted frontend a real SaaS auth boundary instead of browser-stored bearer tokens. Third, build the hosted customer funnel, account/billing surfaces, hosted marketing, and release gates on top of that boundary.

**Tech Stack:** Next.js pages router, FastAPI, Bun, Vitest, Playwright, pytest, Pydantic settings, Stripe billing endpoints, cloud-managed Postgres, SMTP or hosted email provider, Markdown docs.

---

### Task 1: Add Hosted Runtime Primitives And Route Policy

**Files:**
- Create: `apps/tldw-frontend/lib/deployment-mode.ts`
- Create: `apps/tldw-frontend/lib/hosted-route-allowlist.ts`
- Test: `apps/tldw-frontend/lib/__tests__/deployment-mode.test.ts`
- Test: `apps/tldw-frontend/__tests__/navigation/hosted-route-allowlist.test.ts`

**Step 1: Write the failing runtime-mode tests**

```ts
import { describe, expect, it } from "vitest"

import {
  getDeploymentMode,
  isHostedSaaSMode
} from "@/lib/deployment-mode"

describe("deployment mode", () => {
  it("defaults to self_host when no hosted env is present", () => {
    expect(getDeploymentMode()).toBe("self_host")
    expect(isHostedSaaSMode()).toBe(false)
  })

  it("returns hosted for NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE=hosted", () => {
    process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = "hosted"
    expect(getDeploymentMode()).toBe("hosted")
    expect(isHostedSaaSMode()).toBe(true)
  })
})
```

**Step 2: Write the failing hosted-route policy tests**

```ts
import { describe, expect, it } from "vitest"

import {
  getHostedAllowedRoutes,
  isHostedAllowedRoute
} from "@/lib/hosted-route-allowlist"

describe("hosted route allowlist", () => {
  it("allows signup, login, account, billing, and core product routes", () => {
    const routes = getHostedAllowedRoutes()
    expect(routes).toContain("/signup")
    expect(routes).toContain("/login")
    expect(routes).toContain("/account")
    expect(routes).toContain("/billing")
    expect(isHostedAllowedRoute("/chat")).toBe(true)
  })

  it("blocks operator and placeholder routes", () => {
    expect(isHostedAllowedRoute("/admin/server")).toBe(false)
    expect(isHostedAllowedRoute("/settings/tldw")).toBe(false)
    expect(isHostedAllowedRoute("/config")).toBe(false)
  })
})
```

**Step 3: Run the new tests and confirm they fail**

Run: `cd apps/tldw-frontend && bun run test:run lib/__tests__/deployment-mode.test.ts __tests__/navigation/hosted-route-allowlist.test.ts`

Expected: FAIL because the runtime helpers and allowlist module do not exist yet.

**Step 4: Implement the minimal runtime helpers**

```ts
export type DeploymentMode = "self_host" | "hosted"

export const getDeploymentMode = (): DeploymentMode => {
  const raw = String(process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE || "").trim().toLowerCase()
  return raw === "hosted" ? "hosted" : "self_host"
}

export const isHostedSaaSMode = (): boolean => getDeploymentMode() === "hosted"
```

```ts
const HOSTED_ALLOWED_ROUTES = new Set([
  "/",
  "/signup",
  "/login",
  "/auth/verify-email",
  "/auth/reset-password",
  "/auth/magic-link",
  "/account",
  "/billing",
  "/billing/success",
  "/billing/cancel",
  "/chat",
  "/media",
  "/knowledge",
  "/collections"
])
```

**Step 5: Re-run the tests**

Run: `cd apps/tldw-frontend && bun run test:run lib/__tests__/deployment-mode.test.ts __tests__/navigation/hosted-route-allowlist.test.ts`

Expected: PASS

**Step 6: Commit**

```bash
git add apps/tldw-frontend/lib/deployment-mode.ts apps/tldw-frontend/lib/hosted-route-allowlist.ts apps/tldw-frontend/lib/__tests__/deployment-mode.test.ts apps/tldw-frontend/__tests__/navigation/hosted-route-allowlist.test.ts
git commit -m "feat: add hosted runtime mode primitives"
```

### Task 2: Add The Hosted Public URL Contract To AuthNZ

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/settings.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/email_service.py`
- Modify: `Docs/Operations/Env_Vars.md`
- Test: `tldw_Server_API/tests/AuthNZ/unit/test_email_service.py`
- Create: `tldw_Server_API/tests/AuthNZ/unit/test_email_service_public_urls.py`

**Step 1: Write the failing public-URL tests**

```python
from tldw_Server_API.app.core.AuthNZ.email_service import EmailService


def test_magic_link_uses_public_web_base_url(monkeypatch):
    monkeypatch.setenv("PUBLIC_WEB_BASE_URL", "https://app.example.com")
    monkeypatch.setenv("PUBLIC_MAGIC_LINK_PATH", "/auth/magic-link")
    service = EmailService()
    link = service._build_magic_link_for_test("token-123")
    assert link == "https://app.example.com/auth/magic-link?token=token-123"
```

```python
def test_reset_and_verify_urls_fall_back_to_backend_base_url(monkeypatch):
    monkeypatch.delenv("PUBLIC_WEB_BASE_URL", raising=False)
    monkeypatch.setenv("BASE_URL", "https://api.example.com")
    service = EmailService()
    assert service._build_reset_link_for_test("r1").startswith("https://api.example.com/")
    assert service._build_verify_link_for_test("v1").startswith("https://api.example.com/")
```

**Step 2: Run the failing backend tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ/unit/test_email_service.py tldw_Server_API/tests/AuthNZ/unit/test_email_service_public_urls.py -v`

Expected: FAIL because the new env vars and link builders do not exist.

**Step 3: Add the hosted public URL settings**

Add settings fields for:

```python
PUBLIC_WEB_BASE_URL: Optional[str]
PUBLIC_PASSWORD_RESET_PATH: str = "/auth/reset-password"
PUBLIC_EMAIL_VERIFICATION_PATH: str = "/auth/verify-email"
PUBLIC_MAGIC_LINK_PATH: str = "/auth/magic-link"
```

Use them in `EmailService` so hosted emails prefer `PUBLIC_WEB_BASE_URL` and hosted callback paths, while keeping `BASE_URL` behavior as the fallback.

**Step 4: Update the env var docs**

Document:

- `PUBLIC_WEB_BASE_URL`
- `PUBLIC_PASSWORD_RESET_PATH`
- `PUBLIC_EMAIL_VERIFICATION_PATH`
- `PUBLIC_MAGIC_LINK_PATH`

Clarify that hosted SaaS should point these to the public web app, not the backend origin.

**Step 5: Re-run the backend tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ/unit/test_email_service.py tldw_Server_API/tests/AuthNZ/unit/test_email_service_public_urls.py -v`

Expected: PASS

**Step 6: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/settings.py tldw_Server_API/app/core/AuthNZ/email_service.py Docs/Operations/Env_Vars.md tldw_Server_API/tests/AuthNZ/unit/test_email_service_public_urls.py
git commit -m "feat: add hosted public auth url contract"
```

### Task 3: Reuse The Admin UI Proxy Pattern For Hosted Auth

**Files:**
- Reference: `admin-ui/lib/server-auth.ts`
- Reference: `admin-ui/app/api/auth/login/route.ts`
- Reference: `admin-ui/app/api/proxy/[...path]/route.ts`
- Create: `apps/tldw-frontend/lib/server-auth.ts`
- Create: `apps/tldw-frontend/pages/api/auth/login.ts`
- Create: `apps/tldw-frontend/pages/api/auth/logout.ts`
- Create: `apps/tldw-frontend/pages/api/auth/session.ts`
- Create: `apps/tldw-frontend/pages/api/auth/register.ts`
- Create: `apps/tldw-frontend/pages/api/auth/forgot-password.ts`
- Create: `apps/tldw-frontend/pages/api/auth/reset-password.ts`
- Create: `apps/tldw-frontend/pages/api/auth/verify-email.ts`
- Create: `apps/tldw-frontend/pages/api/auth/magic-link/request.ts`
- Create: `apps/tldw-frontend/pages/api/auth/magic-link/verify.ts`
- Create: `apps/tldw-frontend/pages/api/proxy/[...path].ts`
- Test: `apps/tldw-frontend/lib/__tests__/server-auth.test.ts`
- Create: `apps/tldw-frontend/__tests__/pages/api/hosted-auth-routes.test.ts`
- Create: `apps/tldw-frontend/__tests__/pages/api/proxy-route.test.ts`

**Step 1: Write the failing cookie/session tests**

```ts
import { describe, expect, it } from "vitest"

import {
  buildHostedSessionCookies,
  clearHostedSessionCookies
} from "@/lib/server-auth"

describe("hosted server auth", () => {
  it("sets httpOnly access and refresh cookies", () => {
    const cookies = buildHostedSessionCookies({
      accessToken: "access-1",
      refreshToken: "refresh-1"
    })
    expect(cookies.access.httpOnly).toBe(true)
    expect(cookies.refresh.httpOnly).toBe(true)
  })

  it("clears hosted session cookies on logout", () => {
    const cookies = clearHostedSessionCookies()
    expect(cookies.access.maxAge).toBe(0)
    expect(cookies.refresh.maxAge).toBe(0)
  })
})
```

**Step 2: Write the failing proxy-route tests**

```ts
it("forwards requests through the same-origin proxy without browser bearer headers", async () => {
  const response = await handler(makeProxyRequest("/api/proxy/users/me"))
  expect(fetch).toHaveBeenCalled()
  expect(extractForwardedAuthorizationHeader()).toMatch(/^Bearer /)
})
```

**Step 3: Run the failing frontend tests**

Run: `cd apps/tldw-frontend && bun run test:run lib/__tests__/server-auth.test.ts __tests__/pages/api/hosted-auth-routes.test.ts __tests__/pages/api/proxy-route.test.ts`

Expected: FAIL because the hosted server-auth helpers and API route handlers do not exist.

**Step 4: Implement the hosted auth boundary**

Implement:

- cookie helpers in `apps/tldw-frontend/lib/server-auth.ts`
- API route handlers that call the backend auth endpoints, set or clear httpOnly cookies, and never expose bearer tokens to browser JS
- a generic `/api/proxy/[...path].ts` route that forwards requests to the backend with server-managed auth headers, following the `admin-ui` pattern

Keep the hosted cookie names and same-origin behavior separate from self-host extension flows.

**Step 5: Re-run the tests**

Run: `cd apps/tldw-frontend && bun run test:run lib/__tests__/server-auth.test.ts __tests__/pages/api/hosted-auth-routes.test.ts __tests__/pages/api/proxy-route.test.ts`

Expected: PASS

**Step 6: Commit**

```bash
git add apps/tldw-frontend/lib/server-auth.ts apps/tldw-frontend/pages/api/auth apps/tldw-frontend/pages/api/proxy/[...path].ts apps/tldw-frontend/lib/__tests__/server-auth.test.ts apps/tldw-frontend/__tests__/pages/api/hosted-auth-routes.test.ts apps/tldw-frontend/__tests__/pages/api/proxy-route.test.ts
git commit -m "feat: add hosted auth proxy boundary"
```

### Task 4: Switch Hosted Requests To Proxy Mode And Remove Browser Org Bootstrap

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/request-core.ts`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Modify: `apps/packages/ui/src/services/tldw/TldwAuth.ts`
- Create: `apps/packages/ui/src/services/tldw/__tests__/request-core.hosted.test.ts`
- Create: `apps/packages/ui/src/services/tldw/__tests__/TldwAuth.hosted-mode.test.ts`
- Modify: `apps/tldw-frontend/__tests__/auth.mode.test.ts`

**Step 1: Write the failing hosted request-core tests**

```ts
it("uses /api/proxy paths in hosted mode and omits browser Authorization headers", async () => {
  process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = "hosted"
  await requestJson({ path: "/api/v1/users/me/profile", method: "GET" })
  expect(fetch).toHaveBeenCalledWith(
    "/api/proxy/users/me/profile",
    expect.objectContaining({ headers: expect.any(Headers) })
  )
  expect(lastHeaders.get("Authorization")).toBeNull()
})
```

```ts
it("does not create a personal org from the browser in hosted mode", async () => {
  process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = "hosted"
  await tldwAuth.login({ username: "user", password: "pass" })
  expect(fetch).not.toHaveBeenCalledWith(
    expect.stringContaining("/api/v1/orgs"),
    expect.objectContaining({ method: "POST" })
  )
})
```

**Step 2: Run the failing tests**

Run: `cd apps/tldw-frontend && bun run test:run ../packages/ui/src/services/tldw/__tests__/request-core.hosted.test.ts ../packages/ui/src/services/tldw/__tests__/TldwAuth.hosted-mode.test.ts __tests__/auth.mode.test.ts`

Expected: FAIL because hosted mode still relies on `tldwConfig` bearer tokens and `TldwAuth.ensureOrgId()` still performs client-side org creation.

**Step 3: Implement hosted-mode request behavior**

Implement the hosted branch so that:

- requests go through `/api/proxy/...`
- browser JS does not set bearer tokens
- hosted login and refresh do not persist `accessToken` or `refreshToken` into `tldwConfig`
- hosted post-login flow resolves the existing personal org via `GET /api/v1/orgs` or `GET /api/v1/users/me/profile` only
- hosted mode never issues `POST /api/v1/orgs` from the browser

Keep self-host and extension flows unchanged.

**Step 4: Re-run the tests**

Run: `cd apps/tldw-frontend && bun run test:run ../packages/ui/src/services/tldw/__tests__/request-core.hosted.test.ts ../packages/ui/src/services/tldw/__tests__/TldwAuth.hosted-mode.test.ts __tests__/auth.mode.test.ts`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/request-core.ts apps/packages/ui/src/services/tldw/TldwApiClient.ts apps/packages/ui/src/services/tldw/TldwAuth.ts apps/packages/ui/src/services/tldw/__tests__/request-core.hosted.test.ts apps/packages/ui/src/services/tldw/__tests__/TldwAuth.hosted-mode.test.ts apps/tldw-frontend/__tests__/auth.mode.test.ts
git commit -m "feat: route hosted web requests through proxy auth"
```

### Task 5: Build Hosted Signup, Login, And Auth Callback Pages

**Files:**
- Create: `apps/tldw-frontend/components/hosted/auth/AuthShell.tsx`
- Create: `apps/tldw-frontend/components/hosted/auth/LoginForm.tsx`
- Create: `apps/tldw-frontend/components/hosted/auth/SignupForm.tsx`
- Create: `apps/tldw-frontend/components/hosted/auth/VerifyEmailView.tsx`
- Create: `apps/tldw-frontend/components/hosted/auth/ResetPasswordView.tsx`
- Create: `apps/tldw-frontend/components/hosted/auth/MagicLinkView.tsx`
- Modify: `apps/tldw-frontend/pages/login.tsx`
- Create: `apps/tldw-frontend/pages/signup.tsx`
- Create: `apps/tldw-frontend/pages/auth/verify-email.tsx`
- Create: `apps/tldw-frontend/pages/auth/reset-password.tsx`
- Create: `apps/tldw-frontend/pages/auth/magic-link.tsx`
- Create: `apps/tldw-frontend/__tests__/pages/login.hosted.test.tsx`
- Create: `apps/tldw-frontend/__tests__/pages/signup.hosted.test.tsx`
- Create: `apps/tldw-frontend/__tests__/pages/auth-callbacks.test.tsx`

**Step 1: Write the failing page tests**

```tsx
it("renders hosted login instead of server settings in hosted mode", async () => {
  process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = "hosted"
  render(<LoginPage />)
  expect(screen.getByRole("heading", { name: /sign in/i })).toBeInTheDocument()
  expect(screen.queryByText(/server url/i)).toBeNull()
})
```

```tsx
it("submits magic-link requests through the hosted auth endpoint", async () => {
  render(<LoginPage />)
  await user.type(screen.getByLabelText(/email/i), "user@example.com")
  await user.click(screen.getByRole("button", { name: /email me a sign-in link/i }))
  expect(fetch).toHaveBeenCalledWith("/api/auth/magic-link/request", expect.anything())
})
```

**Step 2: Run the failing page tests**

Run: `cd apps/tldw-frontend && bun run test:run __tests__/pages/login.hosted.test.tsx __tests__/pages/signup.hosted.test.tsx __tests__/pages/auth-callbacks.test.tsx`

Expected: FAIL because the hosted auth pages and components do not exist.

**Step 3: Build the hosted auth pages**

Implement:

- a shared hosted auth shell
- password login and magic-link request in `/login`
- email/password registration in `/signup`
- callback pages that call the hosted API routes and then redirect into onboarding, account, or the core app

Retain the current `TldwSettings` login page only for self-host mode.

**Step 4: Re-run the tests**

Run: `cd apps/tldw-frontend && bun run test:run __tests__/pages/login.hosted.test.tsx __tests__/pages/signup.hosted.test.tsx __tests__/pages/auth-callbacks.test.tsx`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/tldw-frontend/components/hosted/auth apps/tldw-frontend/pages/login.tsx apps/tldw-frontend/pages/signup.tsx apps/tldw-frontend/pages/auth apps/tldw-frontend/__tests__/pages/login.hosted.test.tsx apps/tldw-frontend/__tests__/pages/signup.hosted.test.tsx apps/tldw-frontend/__tests__/pages/auth-callbacks.test.tsx
git commit -m "feat: add hosted auth pages"
```

### Task 6: Build Dedicated Account And Billing Areas

**Files:**
- Create: `apps/tldw-frontend/lib/api/account.ts`
- Create: `apps/tldw-frontend/lib/api/billing.ts`
- Create: `apps/tldw-frontend/components/hosted/account/AccountOverview.tsx`
- Create: `apps/tldw-frontend/components/hosted/billing/BillingOverview.tsx`
- Create: `apps/tldw-frontend/components/hosted/billing/PlanSelector.tsx`
- Create: `apps/tldw-frontend/pages/account/index.tsx`
- Create: `apps/tldw-frontend/pages/billing/index.tsx`
- Create: `apps/tldw-frontend/pages/billing/success.tsx`
- Create: `apps/tldw-frontend/pages/billing/cancel.tsx`
- Create: `apps/tldw-frontend/__tests__/pages/account-page.test.tsx`
- Create: `apps/tldw-frontend/__tests__/pages/billing-page.test.tsx`

**Step 1: Write the failing account and billing tests**

```tsx
it("loads the authenticated user profile into the account page", async () => {
  render(<AccountPage />)
  expect(await screen.findByText(/email/i)).toBeInTheDocument()
  expect(fetch).toHaveBeenCalledWith("/api/proxy/users/me/profile", expect.anything())
})
```

```tsx
it("loads subscription, usage, and invoice data into the billing page", async () => {
  render(<BillingPage />)
  expect(await screen.findByText(/current plan/i)).toBeInTheDocument()
  expect(fetch).toHaveBeenCalledWith("/api/proxy/billing/subscription", expect.anything())
  expect(fetch).toHaveBeenCalledWith("/api/proxy/billing/usage", expect.anything())
})
```

**Step 2: Run the failing tests**

Run: `cd apps/tldw-frontend && bun run test:run __tests__/pages/account-page.test.tsx __tests__/pages/billing-page.test.tsx`

Expected: FAIL because the account and billing pages do not exist yet.

**Step 3: Implement the dedicated customer areas**

Use existing backend endpoints through the hosted proxy:

- `/api/v1/users/me/profile`
- `/api/v1/billing/subscription`
- `/api/v1/billing/usage`
- `/api/v1/billing/invoices`
- `/api/v1/billing/checkout`
- `/api/v1/billing/portal`

Show:

- identity and profile basics
- verification and security state
- current plan
- quota and usage
- invoices
- checkout and portal entry points

**Step 4: Re-run the tests**

Run: `cd apps/tldw-frontend && bun run test:run __tests__/pages/account-page.test.tsx __tests__/pages/billing-page.test.tsx`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/tldw-frontend/lib/api/account.ts apps/tldw-frontend/lib/api/billing.ts apps/tldw-frontend/components/hosted/account apps/tldw-frontend/components/hosted/billing apps/tldw-frontend/pages/account/index.tsx apps/tldw-frontend/pages/billing apps/tldw-frontend/__tests__/pages/account-page.test.tsx apps/tldw-frontend/__tests__/pages/billing-page.test.tsx
git commit -m "feat: add hosted account and billing areas"
```

### Task 7: Replace Self-Host Onboarding And Gate Hosted Navigation

**Files:**
- Modify: `apps/packages/ui/src/routes/option-index.tsx`
- Modify: `apps/tldw-frontend/pages/_app.tsx`
- Modify: `apps/packages/ui/src/routes/route-registry.tsx`
- Modify: `apps/packages/ui/src/components/Layouts/Header.tsx`
- Modify: `apps/packages/ui/src/components/Layouts/header-shortcut-items.ts`
- Modify: `apps/tldw-frontend/pages/for/journalists.tsx`
- Modify: `apps/tldw-frontend/pages/for/researchers.tsx`
- Modify: `apps/tldw-frontend/pages/for/osint.tsx`
- Create: `apps/tldw-frontend/__tests__/landing-hub.hosted.test.tsx`
- Create: `apps/tldw-frontend/__tests__/app/app-layout.hosted-navigation.test.tsx`
- Modify: `apps/tldw-frontend/__tests__/header-runs-gating.test.tsx`
- Modify: `apps/tldw-frontend/__tests__/e2e/smoke-allowlist.test.ts`

**Step 1: Write the failing hosted-navigation tests**

```tsx
it("shows hosted landing content instead of the self-host onboarding wizard in hosted mode", async () => {
  process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = "hosted"
  render(<OptionIndex />)
  expect(screen.queryByText(/welcome.*connect your server/i)).toBeNull()
  expect(screen.getByRole("link", { name: /start trial/i })).toBeInTheDocument()
})
```

```tsx
it("hides admin and server-operator navigation in hosted mode", async () => {
  process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = "hosted"
  render(<App Component={DummyPage} pageProps={{}} />)
  expect(screen.queryByText(/server/i)).toBeNull()
  expect(screen.queryByText(/admin/i)).toBeNull()
})
```

**Step 2: Run the failing tests**

Run: `cd apps/tldw-frontend && bun run test:run __tests__/landing-hub.hosted.test.tsx __tests__/app/app-layout.hosted-navigation.test.tsx __tests__/header-runs-gating.test.tsx __tests__/e2e/smoke-allowlist.test.ts`

Expected: FAIL because the landing page and route registry still assume self-hosted onboarding and server/operator navigation.

**Step 3: Implement hosted landing and navigation gating**

In hosted mode:

- replace the self-host onboarding wizard on `/` with hosted landing or dashboard entry
- hide server setup, `/settings/tldw`, admin pages, and placeholders from the main nav
- keep only the hosted allowlist visible
- rewrite segment-page CTAs and messaging so they distinguish hosted and self-host options honestly

Leave self-host behavior unchanged when hosted mode is off.

**Step 4: Re-run the tests**

Run: `cd apps/tldw-frontend && bun run test:run __tests__/landing-hub.hosted.test.tsx __tests__/app/app-layout.hosted-navigation.test.tsx __tests__/header-runs-gating.test.tsx __tests__/e2e/smoke-allowlist.test.ts`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/option-index.tsx apps/tldw-frontend/pages/_app.tsx apps/packages/ui/src/routes/route-registry.tsx apps/packages/ui/src/components/Layouts/Header.tsx apps/packages/ui/src/components/Layouts/header-shortcut-items.ts apps/tldw-frontend/pages/for/journalists.tsx apps/tldw-frontend/pages/for/researchers.tsx apps/tldw-frontend/pages/for/osint.tsx apps/tldw-frontend/__tests__/landing-hub.hosted.test.tsx apps/tldw-frontend/__tests__/app/app-layout.hosted-navigation.test.tsx apps/tldw-frontend/__tests__/header-runs-gating.test.tsx apps/tldw-frontend/__tests__/e2e/smoke-allowlist.test.ts
git commit -m "feat: gate hosted navigation and landing flows"
```

### Task 8: Publish The Hosted Profile, Add A Validator, And Lock The Release Gate

**Files:**
- Create: `Docs/Published/Deployment/Hosted_SaaS_Profile.md`
- Modify: `Docs/Published/Deployment/First_Time_Production_Setup.md`
- Modify: `Docs/User_Guides/Server/Production_Hardening_Checklist.md`
- Modify: `Docs/Operations/Env_Vars.md`
- Create: `Helper_Scripts/validate_hosted_saas_profile.py`
- Create: `tldw_Server_API/tests/AuthNZ/unit/test_validate_hosted_saas_profile.py`
- Create: `apps/tldw-frontend/e2e/hosted/launch-funnel.spec.ts`
- Create: `apps/tldw-frontend/e2e/hosted/account-billing.spec.ts`
- Modify: `apps/tldw-frontend/package.json`
- Modify: `apps/tldw-frontend/e2e/login.spec.ts`

**Step 1: Write the failing hosted-profile validator tests**

```python
from Helper_Scripts.validate_hosted_saas_profile import validate_hosted_profile


def test_validator_rejects_missing_public_web_base_url():
    result = validate_hosted_profile(
        {
            "AUTH_MODE": "multi_user",
            "DATABASE_URL": "postgresql://user:pass@db/tldw",
            "tldw_production": "true",
        }
    )
    assert result.ok is False
    assert "PUBLIC_WEB_BASE_URL" in result.errors
```

**Step 2: Write the failing hosted E2E specs**

Create Playwright specs that assert:

- signup page loads
- magic-link request flow returns success messaging
- password login lands in the hosted app
- account page loads profile data
- billing page loads plan and usage state

**Step 3: Run the failing tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ/unit/test_validate_hosted_saas_profile.py -v`

Expected: FAIL because the validator does not exist.

Run: `cd apps/tldw-frontend && bun run test:run __tests__/pages/login.hosted.test.tsx __tests__/pages/signup.hosted.test.tsx __tests__/pages/account-page.test.tsx __tests__/pages/billing-page.test.tsx`

Expected: PASS if Tasks 5-7 are complete.

Run: `cd apps/tldw-frontend && bun run build`

Expected: PASS

**Step 4: Implement the validator and hosted release scripts**

Add:

- a validator that checks the required hosted env contract
- deployment docs that describe the cloud-managed profile plainly
- package scripts such as `e2e:hosted`
- updated login E2E to reflect hosted login semantics rather than `/settings/tldw`

**Step 5: Run final verification**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ/unit/test_validate_hosted_saas_profile.py tldw_Server_API/tests/AuthNZ/unit/test_email_service_public_urls.py -v`

Expected: PASS

Run: `cd apps/tldw-frontend && bun run test:run __tests__/pages/login.hosted.test.tsx __tests__/pages/signup.hosted.test.tsx __tests__/pages/account-page.test.tsx __tests__/pages/billing-page.test.tsx __tests__/landing-hub.hosted.test.tsx __tests__/app/app-layout.hosted-navigation.test.tsx`

Expected: PASS

Run: `cd apps/tldw-frontend && bun run build`

Expected: PASS

Run: `cd apps/tldw-frontend && bunx playwright test e2e/hosted/launch-funnel.spec.ts e2e/hosted/account-billing.spec.ts --reporter=line`

Expected: PASS

Run: `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/AuthNZ tldw_Server_API/app/api/v1/endpoints/auth.py Helper_Scripts/validate_hosted_saas_profile.py -f json -o /tmp/bandit_hosted_saas_launch.json`

Expected: `0` new findings in touched scope

**Step 6: Commit**

```bash
git add Docs/Published/Deployment/Hosted_SaaS_Profile.md Docs/Published/Deployment/First_Time_Production_Setup.md Docs/User_Guides/Server/Production_Hardening_Checklist.md Docs/Operations/Env_Vars.md Helper_Scripts/validate_hosted_saas_profile.py tldw_Server_API/tests/AuthNZ/unit/test_validate_hosted_saas_profile.py apps/tldw-frontend/e2e/hosted apps/tldw-frontend/package.json apps/tldw-frontend/e2e/login.spec.ts
git commit -m "feat: add hosted saas launch release gate"
```
