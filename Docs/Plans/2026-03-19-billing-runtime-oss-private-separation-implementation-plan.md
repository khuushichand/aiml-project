# Billing Runtime OSS/Private Separation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove commercial billing and subscription runtime from the public repo while preserving a coherent self-host OSS core and a non-destructive migration path for existing installs.

**Architecture:** Execute the split in phases. First remove public commercial policy leaks and hosted-mode marketing. Then extract Stripe/payment-provider runtime and admin revenue operations. Finally retire public billing schema/code paths for fresh OSS installs without requiring destructive table drops on existing databases.

**Tech Stack:** Python, FastAPI, Pydantic, Next.js, pytest, Vitest, AuthNZ migrations, MkDocs, Bandit.

---

### Task 1: Remove Hosted Commercial Branching From The Public Frontend

**Files:**
- Modify: `apps/tldw-frontend/pages/for/researchers.tsx`
- Modify: `apps/tldw-frontend/pages/for/journalists.tsx`
- Modify: `apps/tldw-frontend/pages/for/osint.tsx`
- Modify: `apps/tldw-frontend/lib/deployment-mode.ts`
- Modify: `apps/tldw-frontend/lib/auth.ts`
- Modify: `apps/tldw-frontend/__tests__/auth.mode.test.ts`
- Modify: `apps/tldw-frontend/lib/__tests__/deployment-mode.test.ts`
- Modify: any directly affected frontend tests under `apps/tldw-frontend/__tests__/`

**Step 1: Write or update failing frontend tests**

Add or update tests so the public frontend no longer:

- advertises hosted trials or hosted commercial pricing on the public segment pages
- depends on `NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE=hosted` for public OSS marketing behavior
- encodes hosted JWT/auth semantics unless a neutral extension seam is intentionally kept

**Step 2: Run the targeted frontend tests to verify failure**

Run:

```bash
bun run test:run apps/tldw-frontend/__tests__/auth.mode.test.ts apps/tldw-frontend/lib/__tests__/deployment-mode.test.ts
```

Expected: at least one test fails before implementation.

**Step 3: Implement the minimal frontend cleanup**

Make the public frontend consistently self-host/open-source oriented:

- remove hosted-trial CTA branching from public marketing pages
- remove public paid-tier marketing from those pages
- reduce or neutralize `deployment-mode` usage in OSS
- keep only the smallest extension seam if required for private overlay compatibility

**Step 4: Re-run targeted frontend tests**

Run the same command as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/tldw-frontend/pages/for apps/tldw-frontend/lib apps/tldw-frontend/__tests__
git commit -m "refactor: remove hosted commercial branching from public frontend"
```

### Task 2: Remove Paid Plan Seeds And Fallback Pricing From OSS

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Modify: `tldw_Server_API/app/core/Billing/plan_limits.py`
- Modify: `tldw_Server_API/app/core/Billing/subscription_service.py`
- Modify: affected billing/auth tests under `tldw_Server_API/tests/Billing/` and `tldw_Server_API/tests/AuthNZ/`

**Step 1: Add failing tests for public policy leaks**

Add or update tests that assert fresh OSS defaults do not ship a public paid catalog with hardcoded commercial pricing or hosted subscription packaging.

Cover:

- migration seed behavior
- fallback `list_available_plans()` behavior
- default plan-limit naming if still present in OSS

**Step 2: Run the targeted tests to verify failure**

Run the smallest relevant pytest target(s), for example:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Billing -k "plan or subscription" -v
```

Expected: FAIL in the targeted cases before implementation.

**Step 3: Implement non-commercial OSS defaults**

Change OSS behavior so:

- fresh public migrations no longer seed a commercial paid catalog
- fallback pricing defaults disappear from `subscription_service.py`
- any remaining generic limit math is detached from commercial pricing/plan semantics

Do not add destructive migration behavior that drops old tables for existing installs.

**Step 4: Re-run targeted backend tests**

Run the same pytest target(s) as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/migrations.py tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py tldw_Server_API/app/core/Billing/plan_limits.py tldw_Server_API/app/core/Billing/subscription_service.py tldw_Server_API/tests/Billing tldw_Server_API/tests/AuthNZ
git commit -m "refactor: remove public paid plan defaults from oss"
```

### Task 3: Extract Stripe Payment Runtime From OSS

**Files:**
- Delete or move from public: `tldw_Server_API/app/api/v1/endpoints/billing_webhooks.py`
- Modify or delete: `tldw_Server_API/app/api/v1/endpoints/billing.py`
- Delete or move from public: `tldw_Server_API/app/core/Billing/stripe_client.py`
- Delete or move from public: `tldw_Server_API/app/services/stripe_metering_service.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/billing_schemas.py`
- Modify: route registration/import sites that include billing endpoints
- Delete or update Stripe-specific tests under `tldw_Server_API/tests/Billing/` and `tldw_Server_API/tests/test_stripe_metering.py`

**Step 1: Decide the OSS neutral surface**

Before editing code, decide and encode one outcome:

- either OSS keeps a neutral usage/limits endpoint outside `billing`, or
- OSS removes the public billing API entirely

Prefer the latter unless a concrete self-host use case is already implemented and worth preserving.

**Step 2: Write failing tests around the intended public surface**

Add or update tests to capture the desired OSS result:

- no Stripe webhook route
- no checkout/portal/customer-payment surface in public API
- if a neutral usage endpoint remains, it is not exposed under `billing`

**Step 3: Run targeted tests to verify failure**

Run targeted pytest modules for billing endpoints and package imports.

**Step 4: Implement the minimal extraction**

Remove Stripe runtime from OSS:

- delete Stripe-only routes and provider wrappers
- update imports/registrations
- retain only explicitly approved neutral quota/usage functionality

**Step 5: Re-run targeted tests**

Expected: PASS.

**Step 6: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints tldw_Server_API/app/core/Billing tldw_Server_API/app/services tldw_Server_API/app/api/v1/schemas tldw_Server_API/tests/Billing tldw_Server_API/tests/test_stripe_metering.py
git commit -m "refactor: remove stripe billing runtime from oss"
```

### Task 4: Extract Admin Revenue Operations From OSS

**Files:**
- Delete or move from public: `tldw_Server_API/app/api/v1/endpoints/admin/admin_billing.py`
- Modify: admin route registration/import sites
- Modify or delete: public admin billing services under `tldw_Server_API/app/services/`
- Delete or update: admin billing tests under `tldw_Server_API/tests/Admin/`

**Step 1: Add or update failing tests**

Assert that public OSS no longer exposes:

- billing overview / MRR-style reporting
- subscription overrides
- credit grants
- billing events listings

**Step 2: Run targeted admin tests to verify failure**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Admin -k billing -v
```

Expected: FAIL before implementation.

**Step 3: Remove admin revenue-ops as one unit**

Delete or extract the endpoint, its service logic, and directly related tests/imports together so the public repo does not retain partial commercial admin functionality.

**Step 4: Re-run targeted admin tests**

Expected: PASS or the obsolete test modules are removed cleanly.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/admin tldw_Server_API/app/services tldw_Server_API/tests/Admin
git commit -m "refactor: remove admin billing operations from oss"
```

### Task 5: Retire Public Billing Schema And Repo Usage

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Modify or delete: `tldw_Server_API/app/core/AuthNZ/repos/billing_repo.py`
- Modify: any remaining importers of `billing_repo`
- Modify or delete: billing-focused schemas/tests that still remain

**Step 1: Add failing tests for fresh OSS install expectations**

Add or update tests that reflect the new public baseline:

- fresh OSS setup does not require billing schema or billing repo paths
- no public module import path should fail because a removed billing table or Stripe concept is missing

**Step 2: Run the targeted tests to verify failure**

Run the narrowest relevant AuthNZ/billing import tests.

**Step 3: Implement non-destructive retirement**

Change OSS so:

- fresh public installs stop creating/depending on billing schema
- historical installs are not forced through destructive table drops
- any remaining generic quota helpers are relocated or renamed out of billing framing where practical

**Step 4: Re-run targeted tests**

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ tldw_Server_API/app/core/Billing tldw_Server_API/tests
git commit -m "refactor: retire public billing schema from oss"
```

### Task 6: Tighten OSS/Private Boundary Enforcement For Commercial Runtime

**Files:**
- Modify: `Helper_Scripts/docs/check_public_private_boundary.py`
- Modify: `tldw_Server_API/tests/test_public_private_boundary.py`
- Modify: docs or policy references only if needed

**Step 1: Extend denylist coverage**

Add enforcement for the newly extracted commercial runtime surface, including filenames/tokens such as:

- Stripe webhook/payment files
- admin billing runtime
- public hosted billing/account markers that should no longer appear in OSS surfaces

Keep the checker out of `Docs/Plans` and policy docs.

**Step 2: Add direct absence assertions**

Extend the boundary pytest file so the public repo explicitly forbids the extracted runtime files from reappearing.

**Step 3: Run checker and boundary pytest**

Run:

```bash
source .venv/bin/activate
python Helper_Scripts/docs/check_public_private_boundary.py
python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -v
```

Expected: PASS.

**Step 4: Commit**

```bash
git add Helper_Scripts/docs/check_public_private_boundary.py tldw_Server_API/tests/test_public_private_boundary.py
git commit -m "test: enforce billing runtime oss private boundary"
```

### Task 7: Final Public Verification

**Files:**
- Verify only

**Step 1: Run public verification**

Run:

```bash
source .venv/bin/activate
python Helper_Scripts/docs/check_public_private_boundary.py
python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -v
mkdocs build --strict -f Docs/mkdocs.yml
```

Expected:

- boundary checker PASS
- boundary pytest PASS
- strict MkDocs PASS

**Step 2: Run targeted backend/frontend verification for touched areas**

Run the exact pytest/Vitest commands used in the implementation tasks for the touched billing/frontend scopes.

Expected: PASS.

**Step 3: Run Bandit on touched Python scope**

Run:

```bash
source .venv/bin/activate
python -m bandit -r Helper_Scripts/docs/check_public_private_boundary.py tldw_Server_API/app/api/v1/endpoints tldw_Server_API/app/core/Billing tldw_Server_API/app/services tldw_Server_API/app/core/AuthNZ tldw_Server_API/tests -f json -o /tmp/bandit_billing_runtime_oss_private_split.json
```

Expected: no new findings in the touched scope.

**Step 4: Commit only if verification required touched-scope edits**

Otherwise do not create an extra commit.
