# Remove Public Hosted Assets Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the remaining hosted-only ops, deploy, config, helper, and test assets from the public repo and tighten boundary enforcement so they cannot reappear in OSS surfaces.

**Architecture:** Treat the private hosted repo as canonical for hosted operational and deployment material. Hard-delete hosted assets from the public tree, expand the boundary checker to cover deploy/config/helper/test paths, and extend boundary pytest with direct absence assertions for the extracted assets.

**Tech Stack:** Markdown, YAML, Python, pytest, MkDocs, shell verification commands.

---

### Task 1: Add Failing Absence Coverage For Hosted Ops And Assets

Status: Complete

**Files:**
- Modify: `tldw_Server_API/tests/test_public_private_boundary.py`

**Step 1: Add failing absence checks**

Extend `tldw_Server_API/tests/test_public_private_boundary.py` with direct absence assertions for:

- `Docs/Operations/Hosted_Staging_Operations_Runbook.md`
- `Docs/Operations/Hosted_Stripe_Test_Mode_Runbook.md`
- `Dockerfiles/docker-compose.hosted-saas-staging.yml`
- `Dockerfiles/docker-compose.hosted-saas-prod.yml`
- `Dockerfiles/docker-compose.hosted-saas-prod.local-postgres.yml`
- `tldw_Server_API/Config_Files/.env.hosted-staging.example`
- `tldw_Server_API/Config_Files/.env.hosted-production.example`
- `Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.compose`
- `Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.prod.compose`
- `Helper_Scripts/validate_hosted_saas_profile.py`
- `Helper_Scripts/Deployment/hosted_staging_preflight.py`
- `tldw_Server_API/tests/test_hosted_production_compose.py`
- `tldw_Server_API/tests/test_hosted_staging_compose.py`

**Step 2: Run the test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -v
```

Expected: FAIL because those hosted assets still exist in the public repo.

### Task 2: Delete Hosted Ops And Deploy Assets From Public

Status: Complete

**Files:**
- Delete: `Docs/Operations/Hosted_Staging_Operations_Runbook.md`
- Delete: `Docs/Operations/Hosted_Stripe_Test_Mode_Runbook.md`
- Delete: `Dockerfiles/docker-compose.hosted-saas-staging.yml`
- Delete: `Dockerfiles/docker-compose.hosted-saas-prod.yml`
- Delete: `Dockerfiles/docker-compose.hosted-saas-prod.local-postgres.yml`
- Delete: `tldw_Server_API/Config_Files/.env.hosted-staging.example`
- Delete: `tldw_Server_API/Config_Files/.env.hosted-production.example`
- Delete: `Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.compose`
- Delete: `Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.prod.compose`

**Step 1: Hard-delete the hosted ops and deploy/config assets**

Remove the files outright. Do not replace them with public stubs or redirect placeholders.

**Step 2: Re-run boundary pytest**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -v
```

Expected: still red or partially red until helper/test extraction and checker expansion land.

**Step 3: Commit the ops/deploy asset removal**

```bash
git add tldw_Server_API/tests/test_public_private_boundary.py Docs/Operations Dockerfiles tldw_Server_API/Config_Files Helper_Scripts/Samples/Caddy
git commit -m "docs: remove hosted ops and deploy assets from public repo"
```

### Task 3: Remove Hosted Helper Scripts And Hosted Compose Tests

Status: Complete

**Files:**
- Delete: `Helper_Scripts/validate_hosted_saas_profile.py`
- Delete: `Helper_Scripts/Deployment/hosted_staging_preflight.py`
- Delete: `tldw_Server_API/tests/test_hosted_production_compose.py`
- Delete: `tldw_Server_API/tests/test_hosted_staging_compose.py`
- Review/Delete if hosted-only: `tldw_Server_API/tests/AuthNZ/unit/test_validate_hosted_saas_profile.py`
- Review/Delete if hosted-only: `tldw_Server_API/tests/AuthNZ/unit/test_email_service_public_urls.py`

**Step 1: Remove hosted-only helper/runtime test files**

Delete the hosted helper scripts and hosted compose tests that no longer belong in OSS once the hosted deployment assets are gone.

If `test_email_service_public_urls.py` proves to be generic and not hosted-only, keep it. Otherwise extract it too.

**Step 2: Re-run boundary pytest**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -v
```

Expected: red only if checker enforcement still needs updating.

**Step 3: Commit helper/test extraction**

```bash
git add Helper_Scripts tldw_Server_API/tests
git commit -m "test: remove hosted helpers and compose tests from public repo"
```

### Task 4: Expand Boundary Enforcement To Public Asset Paths

Status: Complete

**Files:**
- Modify: `Helper_Scripts/docs/check_public_private_boundary.py`
- Modify: `tldw_Server_API/tests/test_public_private_boundary.py`

**Step 1: Expand checker scan targets**

Update `Helper_Scripts/docs/check_public_private_boundary.py` so it scans these public surfaces:

- `Docs/Published`
- `Docs/Operations`
- `Dockerfiles`
- `tldw_Server_API/Config_Files`
- `Helper_Scripts/Samples/Caddy`
- selected public helper/test paths where hosted assets previously lived

Keep it out of:

- `Docs/Plans`
- policy/governance docs

**Step 2: Keep denylist coverage for hosted filenames**

Retain or extend denylist entries for:

- hosted runbooks
- hosted compose files
- hosted env examples
- hosted Caddy samples
- hosted helper filenames if needed

**Step 3: Run checker and boundary pytest**

Run:

```bash
source .venv/bin/activate
python Helper_Scripts/docs/check_public_private_boundary.py
python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -v
```

Expected: PASS.

**Step 4: Commit enforcement tightening**

```bash
git add Helper_Scripts/docs/check_public_private_boundary.py tldw_Server_API/tests/test_public_private_boundary.py
git commit -m "test: expand public hosted asset boundary enforcement"
```

### Task 5: Final Public Verification

Status: Complete

**Files:**
- Verify only

**Step 1: Run full public verification**

Run:

```bash
source .venv/bin/activate
python Helper_Scripts/docs/check_public_private_boundary.py
python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -v
mkdocs build --strict -f Docs/mkdocs.yml
```

Expected:

- checker PASS
- boundary pytest PASS
- strict MkDocs PASS

**Step 2: Run Bandit on touched Python scope**

Run:

```bash
source .venv/bin/activate
python -m bandit -r Helper_Scripts/docs/check_public_private_boundary.py tldw_Server_API/tests/test_public_private_boundary.py -f json -o /tmp/bandit_remove_public_hosted_assets.json
```

Expected: no new findings in the touched Python scope.

**Step 3: Commit only if verification required additional touched-scope edits**

Otherwise do not create an extra commit.
