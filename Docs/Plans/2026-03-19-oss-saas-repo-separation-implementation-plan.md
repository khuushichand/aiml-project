# OSS And SaaS Repo Separation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Separate hosted SaaS documentation, deployment assets, billing/customer-surface code, and commercial operating material from the public `tldw_server` repo into a dedicated private repo without breaking the OSS docs site, build, or tests.

**Architecture:** Treat `tldw_server` as the OSS core and create a private overlay repo `tldw-hosted` that imports a pinned public revision. First harden the public boundary, then extract hosted docs and deployment assets, then move hosted customer-surface code, and finally verify that the public repo is coherent on its own.

**Tech Stack:** Git, MkDocs, shell scripts, pytest, FastAPI, Next.js, Docker Compose, Markdown documentation.

---

### Task 1: Add A Public/Private Boundary Policy And Inventory

**Status:** Complete

**Files:**
- Create: `Docs/Policies/OSS_Private_Boundary.md`
- Create: `Docs/Plans/2026-03-19-oss-saas-private-inventory.md`
- Test: `tldw_Server_API/tests/test_public_private_boundary.py`

**Step 1: Write the failing boundary-policy test**

Add a test that asserts the policy doc and inventory doc exist and contain the key boundary labels:

```python
def test_boundary_policy_and_inventory_exist():
    policy = Path("Docs/Policies/OSS_Private_Boundary.md").read_text(encoding="utf-8")
    inventory = Path("Docs/Plans/2026-03-19-oss-saas-private-inventory.md").read_text(encoding="utf-8")
    _require("Public" in policy, "expected public boundary rules")
    _require("Private" in policy, "expected private boundary rules")
    _require("Hosted_Production_Runbook.md" in inventory, "expected hosted inventory entry")
```

**Step 2: Run the test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -v
```

Expected: FAIL because the new policy and inventory docs do not exist yet.

**Step 3: Create the boundary policy**

Create `Docs/Policies/OSS_Private_Boundary.md` and document:

- the public-vs-private rule
- examples of public-safe and private-only materials
- a rule that hosted commercial docs do not belong in public `Docs/Published`
- a rule that public CI/tests/docs may not depend on private artifacts

**Step 4: Create the extraction inventory**

Create `Docs/Plans/2026-03-19-oss-saas-private-inventory.md` and list the first extraction set:

- hosted runbooks
- hosted env templates
- hosted compose overlays
- hosted Caddy samples
- hosted smoke/preflight tests
- hosted frontend account/billing/signup/login surfaces
- SaaS launch plans in `Docs/Plans`

**Step 5: Re-run the test**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add Docs/Policies/OSS_Private_Boundary.md Docs/Plans/2026-03-19-oss-saas-private-inventory.md tldw_Server_API/tests/test_public_private_boundary.py
git commit -m "docs: add oss and private boundary policy"
```

### Task 2: Stop Publishing Hosted SaaS Docs In The Public Site

**Status:** Complete

**Files:**
- Modify: `Docs/Code_Documentation/Docs_Site_Guide.md`
- Modify: `Docs/mkdocs.yml`
- Modify: `Helper_Scripts/refresh_docs_published.sh`
- Test: `tldw_Server_API/tests/test_public_private_boundary.py`

**Step 1: Write the failing docs-site boundary test**

Extend the test file with checks that public publishing docs do not name hosted SaaS runbooks as public artifacts:

```python
def test_public_docs_pipeline_does_not_name_hosted_saas_runbooks():
    guide = Path("Docs/Code_Documentation/Docs_Site_Guide.md").read_text(encoding="utf-8")
    _require("Hosted_Production_Runbook.md" not in guide, "public docs guide should not point at hosted runbooks")
```

Also assert:

- `Docs/mkdocs.yml` nav does not include hosted SaaS docs
- `Helper_Scripts/refresh_docs_published.sh` does not explicitly preserve hosted-only paths

**Step 2: Run the test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -v
```

Expected: FAIL because the current docs guidance still treats hosted runbooks as part of the published deployment surface.

**Step 3: Update the docs site guide**

Revise `Docs/Code_Documentation/Docs_Site_Guide.md` so it:

- describes the public docs site as self-host/developer focused
- explicitly excludes hosted/commercial docs from the published scope
- points contributors to the private repo for hosted-only documentation

**Step 4: Update MkDocs/nav wording if needed**

Edit `Docs/mkdocs.yml` only if any nav entries or deployment wording still imply hosted SaaS is part of the public docs contract.

**Step 5: Update the refresh script**

Adjust `Helper_Scripts/refresh_docs_published.sh` comments or copy rules so the script documents that hosted/commercial docs are excluded from the public published tree.

**Step 6: Re-run the test and verify the docs site still builds**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -v
mkdocs build --strict -f Docs/mkdocs.yml
```

Expected:

- pytest PASS
- MkDocs build PASS

**Step 7: Commit**

```bash
git add Docs/Code_Documentation/Docs_Site_Guide.md Docs/mkdocs.yml Helper_Scripts/refresh_docs_published.sh tldw_Server_API/tests/test_public_private_boundary.py
git commit -m "docs: exclude hosted saas material from public docs guidance"
```

### Task 3: Remove Hosted SaaS References From Public Docs And Public Tests

**Status:** Complete

**Files:**
- Modify: `Docs/Published/Deployment/First_Time_Production_Setup.md`
- Modify: `Docs/Published/Deployment/Hosted_SaaS_Profile.md`
- Modify: `Docs/Published/Deployment/Hosted_Staging_Runbook.md`
- Modify: `Docs/Published/Deployment/Hosted_Production_Runbook.md`
- Modify: `Docs/Operations/Hosted_Staging_Operations_Runbook.md`
- Modify: `Docs/Operations/Hosted_Stripe_Test_Mode_Runbook.md`
- Modify: `tldw_Server_API/tests/test_hosted_production_compose.py`
- Modify: `tldw_Server_API/tests/test_hosted_staging_compose.py`
- Test: `tldw_Server_API/tests/test_public_private_boundary.py`

**Step 1: Write the failing public-reference test**

Extend the boundary test file with a list of public docs that must no longer reference hosted SaaS pages once the extraction starts:

```python
def test_public_docs_do_not_link_to_private_hosted_runbooks():
    text = Path("Docs/Published/Deployment/First_Time_Production_Setup.md").read_text(encoding="utf-8")
    _require("Hosted_Production_Runbook.md" not in text, "public production setup should not link private hosted runbook")
```

Also cover any public tests that currently assert hosted/private files exist.

**Step 2: Run the tests to verify they fail**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -v
```

Expected: FAIL because the current public docs and tests still reference hosted SaaS files.

**Step 3: Replace or remove hosted references**

Edit the public docs so they:

- point to self-host deployment guides instead of hosted runbooks
- stop presenting hosted SaaS as canonical
- remove operational detail that belongs in the private repo

Edit public tests so they validate public-safe docs only, not hosted-private files.

**Step 4: Re-run the targeted tests**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_public_private_boundary.py tldw_Server_API/tests/test_hosted_production_compose.py tldw_Server_API/tests/test_hosted_staging_compose.py -v
```

Expected: PASS, or the hosted-specific tests are deleted/moved as part of extraction and replaced by public-safe coverage.

**Step 5: Commit**

```bash
git add Docs/Published/Deployment/First_Time_Production_Setup.md Docs/Published/Deployment/Hosted_SaaS_Profile.md Docs/Published/Deployment/Hosted_Staging_Runbook.md Docs/Published/Deployment/Hosted_Production_Runbook.md Docs/Operations/Hosted_Staging_Operations_Runbook.md Docs/Operations/Hosted_Stripe_Test_Mode_Runbook.md tldw_Server_API/tests/test_hosted_production_compose.py tldw_Server_API/tests/test_hosted_staging_compose.py tldw_Server_API/tests/test_public_private_boundary.py
git commit -m "docs: scrub hosted private references from public repo"
```

### Task 4: Bootstrap The Private Hosted Repo And Move Docs/Deployment Assets

**Status:** Complete

**Files:**
- Create: `../tldw-hosted/README.md`
- Create: `../tldw-hosted/docs/Hosted_SaaS_Profile.md`
- Create: `../tldw-hosted/docs/Hosted_Staging_Runbook.md`
- Create: `../tldw-hosted/docs/Hosted_Production_Runbook.md`
- Create: `../tldw-hosted/docs/Operations/Hosted_Staging_Operations_Runbook.md`
- Create: `../tldw-hosted/docs/Operations/Hosted_Stripe_Test_Mode_Runbook.md`
- Create: `../tldw-hosted/deploy/docker-compose.hosted-saas-staging.yml`
- Create: `../tldw-hosted/deploy/docker-compose.hosted-saas-prod.yml`
- Create: `../tldw-hosted/deploy/docker-compose.hosted-saas-prod.local-postgres.yml`
- Create: `../tldw-hosted/deploy/.env.hosted-staging.example`
- Create: `../tldw-hosted/deploy/.env.hosted-production.example`
- Create: `../tldw-hosted/deploy/Caddyfile.hosted-saas.prod.compose`

**Step 1: Create the private repo skeleton**

Create the sibling repo path `../tldw-hosted` with top-level folders:

- `docs/`
- `docs/Operations/`
- `deploy/`
- `tests/`

Add a `README.md` that explains:

- this repo layers hosted/commercial assets on top of `tldw_server`
- the pinned public repo revision lives under a dedicated vendor/upstream path
- hosted docs and deploy assets are intentionally private

**Step 2: Move hosted docs and deploy assets**

Copy the hosted docs and deploy/config files from the public repo into the new private repo structure and update internal paths so they no longer point into `Docs/Published`.

**Step 3: Run a private-repo smoke check**

Run:

```bash
test -f ../tldw-hosted/docs/Hosted_Production_Runbook.md
test -f ../tldw-hosted/deploy/docker-compose.hosted-saas-prod.yml
```

Expected: PASS.

**Step 4: Commit in the private repo**

Run:

```bash
git -C ../tldw-hosted add .
git -C ../tldw-hosted commit -m "feat: bootstrap private hosted repo"
```

Expected: PASS in the private repo.

### Task 5: Extract Hosted Customer-Surface Code To The Private Repo

**Status:** Complete

**Files:**
- Create: `../tldw-hosted/web/`
- Move or recreate: hosted-only files currently under `apps/tldw-frontend/pages/account`
- Move or recreate: hosted-only files currently under `apps/tldw-frontend/pages/billing`
- Move or recreate: hosted-only files currently under `apps/tldw-frontend/pages/auth`
- Move or recreate: hosted-only files currently under `apps/tldw-frontend/components/hosted`
- Move or recreate: hosted-only hosted-route/session/billing helpers under `apps/tldw-frontend/lib/`
- Test: `apps/tldw-frontend/__tests__/pages/`
- Test: `apps/tldw-frontend/e2e/hosted/`

**Step 1: Inventory hosted-only frontend files**

Use `rg` to list files in `apps/tldw-frontend` that are clearly hosted-only:

```bash
rg -n "hosted|billing|signup|verify-email|reset-password" apps/tldw-frontend
```

Record the extraction list in the private repo or the inventory doc.

**Step 2: Write a failing public-boundary test**

Add a test that asserts the public frontend does not import hosted-only customer-surface modules after extraction:

```python
def test_public_frontend_has_no_hosted_customer_surface_imports():
    text = Path("apps/tldw-frontend/pages/_app.tsx").read_text(encoding="utf-8")
    _require("@web/components/hosted" not in text, "public app shell should not depend on hosted private components")
```

**Step 3: Move or recreate the hosted customer surface in the private repo**

Relocate hosted account/billing/auth pages and their helpers into `../tldw-hosted/web/` or an equivalent private package.

In the public repo:

- remove hosted-only imports
- replace hosted-only pages with OSS-safe equivalents or remove them from routing
- keep only generic auth/account capabilities that self-host users need

**Step 4: Re-run the public frontend tests**

Run:

```bash
bun run test:run apps/tldw-frontend/__tests__/pages
```

Expected: PASS for the public-safe surface.

**Step 5: Commit in both repos**

Run:

```bash
git add apps/tldw-frontend
git commit -m "refactor: remove hosted customer surface from public frontend"
git -C ../tldw-hosted add web
git -C ../tldw-hosted commit -m "feat: add private hosted customer surface"
```

### Task 6: Add Boundary Enforcement And Verify Public Repo Independence

**Status:** Not Started

**Files:**
- Create: `Helper_Scripts/docs/check_public_private_boundary.py`
- Modify: `.github/workflows/mkdocs.yml`
- Modify: public docs/tests touched in earlier tasks
- Test: `tldw_Server_API/tests/test_public_private_boundary.py`

**Step 1: Write the failing boundary-enforcement test**

Add tests for a new helper script that scans public docs and known public code paths for forbidden hosted/private references:

```python
def test_boundary_checker_exists():
    text = Path("Helper_Scripts/docs/check_public_private_boundary.py").read_text(encoding="utf-8")
    _require("Hosted_Production_Runbook.md" in text, "expected hosted reference denylist")
```

**Step 2: Run the test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -v
```

Expected: FAIL because the checker does not exist yet.

**Step 3: Implement the checker**

Create `Helper_Scripts/docs/check_public_private_boundary.py` that:

- scans public docs/code paths
- fails if it finds banned hosted/private filenames or phrases
- prints clear remediation messages

**Step 4: Wire it into CI**

Add a workflow step in `.github/workflows/mkdocs.yml` before `mkdocs build`:

```bash
python Helper_Scripts/docs/check_public_private_boundary.py
```

**Step 5: Run the full public verification**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -v
python Helper_Scripts/docs/check_public_private_boundary.py
mkdocs build --strict -f Docs/mkdocs.yml
```

Expected:

- all tests PASS
- boundary checker PASS
- public docs build PASS

**Step 6: Run Bandit on the touched Python scope**

Run:

```bash
source .venv/bin/activate
python -m bandit -r Helper_Scripts/docs/check_public_private_boundary.py tldw_Server_API/tests/test_public_private_boundary.py -f json -o /tmp/bandit_oss_private_boundary.json
```

Expected: no new findings in the touched scope.

**Step 7: Commit**

```bash
git add Helper_Scripts/docs/check_public_private_boundary.py .github/workflows/mkdocs.yml tldw_Server_API/tests/test_public_private_boundary.py
git commit -m "test: enforce oss and private repo boundary"
```
