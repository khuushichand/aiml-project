# Hosted Staging And Stripe Readiness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Stand up a repeatable hosted staging profile for `tldw_server` and prove the first paid-launch path with Stripe test mode, hosted smoke coverage, and operator-facing release gates.

**Architecture:** Build on the hosted SaaS launch contract that now exists in the repo instead of inventing a second deployment path. First, make the hosted validator and env template staging-friendly. Second, publish a canonical hosted staging stack and preflight script that can validate env, health, routes, and billing-plan reachability. Third, add a real staging smoke lane for the hosted customer surface plus docs for Stripe test mode, backup/restore, and monitoring.

**Tech Stack:** FastAPI, Next.js pages router, Bun, Playwright, pytest, Docker Compose, Caddy or reverse proxy, PostgreSQL, Stripe test mode, Markdown runbooks.

---

### Task 1: Add A Canonical Hosted Staging Env Template

**Files:**
- Create: `tldw_Server_API/Config_Files/.env.hosted-staging.example`
- Modify: `Helper_Scripts/validate_hosted_saas_profile.py`
- Modify: `tldw_Server_API/tests/AuthNZ/unit/test_validate_hosted_saas_profile.py`

**Step 1: Write the failing validator tests for env-file input**

Add coverage for:

```python
def test_validator_cli_can_read_env_file(tmp_path):
    env_file = tmp_path / ".env.hosted"
    env_file.write_text(
        "\n".join(
            [
                "AUTH_MODE=multi_user",
                "DATABASE_URL=postgresql://user:pass@db:5432/tldw",
                "tldw_production=true",
                "PUBLIC_WEB_BASE_URL=https://app.example.com",
                "BILLING_REDIRECT_ALLOWLIST_REQUIRED=true",
                "BILLING_REDIRECT_REQUIRE_HTTPS=true",
                "BILLING_ALLOWED_REDIRECT_HOSTS=app.example.com",
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(["validate_hosted_saas_profile.py", "--env-file", str(env_file)])
    assert exit_code == 0
```

Also add a negative case for a missing env file path.

**Step 2: Run the tests and confirm they fail**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/AuthNZ/unit/test_validate_hosted_saas_profile.py -v
```

Expected: FAIL because the CLI does not yet support `--env-file`.

**Step 3: Implement file-input support in the validator**

Add:

- `--env-file <path>` support in `Helper_Scripts/validate_hosted_saas_profile.py`
- a tiny `.env` parser that reads `KEY=value` pairs, ignores blank lines and `#` comments, and overlays them onto a provided env mapping
- clear non-zero exit when the env file is missing or unreadable

Keep the existing direct env validation behavior unchanged when `--env-file` is omitted.

**Step 4: Add the example hosted staging env file**

Create `tldw_Server_API/Config_Files/.env.hosted-staging.example` with:

- hosted profile requirements from `Docs/Published/Deployment/Hosted_SaaS_Profile.md`
- placeholders for:
  - `PUBLIC_WEB_BASE_URL`
  - `DATABASE_URL`
  - `JWT_SECRET_KEY`
  - `STRIPE_API_KEY`
  - `STRIPE_WEBHOOK_SECRET`
  - SMTP/email settings
  - `ALLOWED_ORIGINS`
  - `BILLING_ENABLED`
  - `BILLING_ALLOWED_REDIRECT_HOSTS`

Keep all secrets as obvious placeholders, not working defaults.

**Step 5: Re-run the validator tests**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/AuthNZ/unit/test_validate_hosted_saas_profile.py -v
python Helper_Scripts/validate_hosted_saas_profile.py --env-file tldw_Server_API/Config_Files/.env.hosted-staging.example
```

Expected:

- pytest PASS
- validator should fail on placeholder secrets if you choose to encode placeholders as invalid, or pass if the example is explicitly documented as shape-only; be consistent and document the expected behavior in the file header

**Step 6: Commit**

```bash
git add tldw_Server_API/Config_Files/.env.hosted-staging.example Helper_Scripts/validate_hosted_saas_profile.py tldw_Server_API/tests/AuthNZ/unit/test_validate_hosted_saas_profile.py
git commit -m "feat: add hosted staging env template"
```

### Task 2: Publish A Canonical Hosted Staging Stack

**Files:**
- Create: `Dockerfiles/docker-compose.hosted-saas-staging.yml`
- Create: `Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.compose`
- Create: `Docs/Published/Deployment/Hosted_Staging_Runbook.md`
- Modify: `Docs/Published/Deployment/Hosted_SaaS_Profile.md`
- Modify: `Docs/Published/Deployment/First_Time_Production_Setup.md`
- Test: `tldw_Server_API/tests/test_hosted_staging_compose.py`

**Step 1: Write the failing compose contract test**

Create a small test that parses the compose YAML and asserts it includes the expected services and env wiring:

```python
def test_hosted_staging_compose_declares_app_webui_proxy_and_postgres():
    data = yaml.safe_load(Path("Dockerfiles/docker-compose.hosted-saas-staging.yml").read_text())
    services = data["services"]
    assert "app" in services
    assert "webui" in services
    assert "caddy" in services
    assert "postgres" in services
```

Also assert:

- `webui` uses `NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE=hosted`
- `app` exposes hosted billing/env vars
- `caddy` mounts the hosted Caddyfile sample

**Step 2: Run the failing test**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_hosted_staging_compose.py -v
```

Expected: FAIL because the compose file does not exist yet.

**Step 3: Create the hosted staging compose overlay**

Build `Dockerfiles/docker-compose.hosted-saas-staging.yml` on top of the existing stack conventions:

- `postgres` from `docker-compose.postgres.yml`
- `webui` from `docker-compose.webui.yml`
- reverse proxy from `docker-compose.proxy.yml`

The hosted staging overlay should:

- set `NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE=hosted` for the web bundle
- route public traffic through a same-origin reverse proxy
- expose `app`, `webui`, `postgres`, and `caddy`
- leave secrets in `.env.hosted-staging.example`, not in the compose file

**Step 4: Add the hosted Caddy sample and runbook**

Create:

- `Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.compose`
- `Docs/Published/Deployment/Hosted_Staging_Runbook.md`

The runbook should document:

- how to copy and fill `.env.hosted-staging.example`
- how to launch the stack
- how to run the hosted validator against the env file
- how to confirm same-origin routing, login/signup pages, and `/api/v1/billing/plans`

Also update the hosted profile and first-time production setup docs to point at the runbook.

**Step 5: Re-run the tests and config render**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_hosted_staging_compose.py -v
docker compose --env-file tldw_Server_API/Config_Files/.env.hosted-staging.example -f Dockerfiles/docker-compose.yml -f Dockerfiles/docker-compose.hosted-saas-staging.yml config >/tmp/hosted-staging-compose.rendered.yml
```

Expected:

- pytest PASS
- compose config render PASS

**Step 6: Commit**

```bash
git add Dockerfiles/docker-compose.hosted-saas-staging.yml Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.compose Docs/Published/Deployment/Hosted_Staging_Runbook.md Docs/Published/Deployment/Hosted_SaaS_Profile.md Docs/Published/Deployment/First_Time_Production_Setup.md tldw_Server_API/tests/test_hosted_staging_compose.py
git commit -m "feat: add hosted staging stack runbook"
```

### Task 3: Add A Hosted Staging Preflight Runner

**Files:**
- Create: `Helper_Scripts/Deployment/hosted_staging_preflight.py`
- Create: `tldw_Server_API/tests/test_hosted_staging_preflight.py`
- Modify: `Docs/Published/Deployment/Hosted_Staging_Runbook.md`

**Step 1: Write the failing preflight tests**

Add tests for:

```python
def test_preflight_fails_when_billing_plans_endpoint_is_unreachable():
    ...

def test_preflight_passes_when_health_routes_and_public_pages_are_reachable():
    ...
```

Test the script as a pure Python module with mocked HTTP responses. Do not require a live server for unit tests.

**Step 2: Run the failing tests**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_hosted_staging_preflight.py -v
```

Expected: FAIL because the preflight script does not exist yet.

**Step 3: Implement the hosted staging preflight**

The script should support:

- `--env-file`
- `--base-url`
- `--api-base-url` (optional override)
- `--strict`

Checks should include:

- run `validate_hosted_profile()` against the env file or current env
- HTTP `GET` to:
  - `/health`
  - `/ready`
  - `/login`
  - `/signup`
  - `/api/v1/billing/plans`
- assert `/login` and `/signup` do not render the self-host placeholder copy
- assert billing plans return `200`

Return non-zero when any required check fails.

**Step 4: Update the staging runbook**

Document:

```bash
source .venv/bin/activate
python Helper_Scripts/Deployment/hosted_staging_preflight.py \
  --env-file tldw_Server_API/Config_Files/.env.hosted-staging.example \
  --base-url https://staging.example.com
```

**Step 5: Re-run the tests**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_hosted_staging_preflight.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add Helper_Scripts/Deployment/hosted_staging_preflight.py tldw_Server_API/tests/test_hosted_staging_preflight.py Docs/Published/Deployment/Hosted_Staging_Runbook.md
git commit -m "feat: add hosted staging preflight"
```

### Task 4: Add A Real Hosted Staging Smoke Lane

**Files:**
- Create: `apps/tldw-frontend/e2e/hosted/staging-smoke.spec.ts`
- Modify: `apps/tldw-frontend/package.json`
- Modify: `Docs/Published/Deployment/Hosted_Staging_Runbook.md`

**Step 1: Write the failing staging smoke spec**

Create a Playwright spec that assumes a real hosted staging environment and does not mock the app surface. Use env vars for optional credentials:

- `TLDW_STAGING_BASE_URL`
- `TLDW_STAGING_USER_EMAIL`
- `TLDW_STAGING_USER_PASSWORD`

At minimum:

- `/login` loads with hosted copy
- `/signup` loads with hosted copy
- `/api/v1/billing/plans` is reachable through the public app flow

If credentials are provided, extend the smoke to:

- sign in
- visit `/account`
- visit `/billing`

Skip the authenticated portion cleanly when creds are absent.

**Step 2: Run the spec and confirm the current command is missing**

Run:

```bash
cd apps/tldw-frontend
bun run e2e:hosted:staging
```

Expected: FAIL because the script does not exist yet.

**Step 3: Add the staging smoke script**

Add to `apps/tldw-frontend/package.json`:

```json
"e2e:hosted:staging": "TLDW_WEB_AUTOSTART=false NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE=hosted TLDW_WEB_URL=$TLDW_STAGING_BASE_URL playwright test e2e/hosted/staging-smoke.spec.ts --reporter=line"
```

If shell portability becomes a problem, wrap it in a small Node script instead of relying on inline env assignment.

**Step 4: Re-run the smoke lane**

Run:

```bash
cd apps/tldw-frontend
TLDW_STAGING_BASE_URL=https://staging.example.com bun run e2e:hosted:staging
```

Expected: PASS against staging once the stack is deployed.

**Step 5: Commit**

```bash
git add apps/tldw-frontend/e2e/hosted/staging-smoke.spec.ts apps/tldw-frontend/package.json Docs/Published/Deployment/Hosted_Staging_Runbook.md
git commit -m "feat: add hosted staging smoke lane"
```

### Task 5: Publish Stripe Test Mode And Ops Runbooks

**Files:**
- Create: `Docs/Operations/Hosted_Stripe_Test_Mode_Runbook.md`
- Create: `Docs/Operations/Hosted_Staging_Operations_Runbook.md`
- Modify: `Docs/Published/Deployment/Hosted_SaaS_Profile.md`
- Modify: `tldw_Server_API/app/core/Billing/README.md`

**Step 1: Document the Stripe test-mode prove-out flow**

The Stripe runbook should cover:

- required env vars:
  - `BILLING_ENABLED`
  - `STRIPE_API_KEY`
  - `STRIPE_WEBHOOK_SECRET`
  - `BILLING_ALLOWED_REDIRECT_HOSTS`
  - `BILLING_REDIRECT_ALLOWLIST_REQUIRED`
  - `BILLING_REDIRECT_REQUIRE_HTTPS`
- how to configure Stripe test products/prices
- how to run `stripe listen` or equivalent webhook forwarding for staging
- how to prove:
  - checkout session creation
  - redirect success/cancel
  - portal creation
  - webhook delivery
  - subscription state mutation
  - invoice visibility on `/billing`

**Step 2: Document the hosted operations runbook**

The ops runbook should cover:

- backup using:
  - `Helper_Scripts/backup_all.sh`
  - `Helper_Scripts/restore_all.sh`
  - `Helper_Scripts/pg_backup_restore.py`
- a required restore drill before launch
- metrics and alerting references:
  - `Docs/Deployment/Monitoring/README.md`
  - `Docs/Deployment/Monitoring/Alerts/README.md`
  - `Docs/Deployment/Monitoring/Metrics_Cheatsheet.md`
- minimum support/incident checklist for first paid customers

**Step 3: Update the hosted profile and billing README**

Add links from:

- `Docs/Published/Deployment/Hosted_SaaS_Profile.md`
- `tldw_Server_API/app/core/Billing/README.md`

to the new Stripe and ops runbooks.

**Step 4: Verify link and docs integrity**

Run:

```bash
python Helper_Scripts/check_site_anchors.py Docs/site
```

If the docs site is not rebuilt in this task, run the project’s existing docs link or path hygiene checks that apply to touched docs instead.

**Step 5: Commit**

```bash
git add Docs/Operations/Hosted_Stripe_Test_Mode_Runbook.md Docs/Operations/Hosted_Staging_Operations_Runbook.md Docs/Published/Deployment/Hosted_SaaS_Profile.md tldw_Server_API/app/core/Billing/README.md
git commit -m "docs: add hosted staging and stripe runbooks"
```

### Task 6: Final Verification And Launch Checklist

**Files:**
- Modify: `Docs/Published/Deployment/Hosted_Staging_Runbook.md`
- Modify: `Docs/Published/Deployment/Hosted_SaaS_Profile.md`

**Step 1: Run backend verification**

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/AuthNZ/unit/test_validate_hosted_saas_profile.py \
  tldw_Server_API/tests/test_hosted_staging_compose.py \
  tldw_Server_API/tests/test_hosted_staging_preflight.py \
  tldw_Server_API/tests/Billing/test_billing_webhooks_endpoint.py \
  tldw_Server_API/tests/Billing/test_subscription_webhook_updates.py -v
```

Expected: PASS

**Step 2: Run hosted frontend verification**

```bash
cd apps/tldw-frontend
bun run test:run \
  __tests__/pages/login.hosted.test.tsx \
  __tests__/pages/signup.hosted.test.tsx \
  __tests__/pages/account-page.test.tsx \
  __tests__/pages/billing-page.test.tsx \
  __tests__/landing-hub.hosted.test.tsx \
  __tests__/app/app-layout.hosted-navigation.test.tsx
bun run build
```

Expected: PASS

**Step 3: Run staging release gates**

```bash
source .venv/bin/activate
python Helper_Scripts/Deployment/hosted_staging_preflight.py \
  --env-file tldw_Server_API/Config_Files/.env.hosted-staging.example \
  --base-url https://staging.example.com

cd apps/tldw-frontend
TLDW_STAGING_BASE_URL=https://staging.example.com bun run e2e:hosted:staging
```

Expected: PASS against a real staging deployment.

**Step 4: Run Bandit on the touched scope**

```bash
source .venv/bin/activate
python -m bandit -r \
  Helper_Scripts/validate_hosted_saas_profile.py \
  Helper_Scripts/Deployment/hosted_staging_preflight.py \
  tldw_Server_API/app/core/Billing \
  -f json -o /tmp/bandit_hosted_staging_and_stripe.json
```

Expected: no new findings in touched code

**Step 5: Commit**

```bash
git add Docs/Published/Deployment/Hosted_Staging_Runbook.md Docs/Published/Deployment/Hosted_SaaS_Profile.md
git commit -m "chore: add hosted staging and stripe launch gates"
```

