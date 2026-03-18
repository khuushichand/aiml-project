# PR 898 Open Review Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Clear the remaining non-architecture PR 898 review issues while keeping the branch narrowly scoped and deferring the DB-boundary redesign to PR 908.

**Architecture:** Apply targeted fixes directly on `feat/production-readiness-gaps` for the remaining correctness gaps, then fold in the low-risk review cleanup items the bots still have open. Close the three architecture comments by explicitly pointing them at PR 908 instead of duplicating that refactor on PR 898.

**Tech Stack:** Python 3.11, FastAPI, pytest, loguru, SQLite, PostgreSQL/asyncpg, stripe-python, Bandit

**Execution Status:** Complete on 2026-03-17.

**Implementation Notes:**
- Task 2 landed in the actual URL-download processing path instead of a dedicated endpoint/worker-only branch: `process_batch_media(...)` now threads `user_id` into audio/video processors, and quota enforcement runs immediately after URL downloads in `Audio_Files.py` and `Video_DL_Ingestion_Lib.py`.
- The regression coverage for Task 2 therefore lives in:
  - `tldw_Server_API/tests/MediaIngestion_NEW/unit/test_audio_files_preflight.py`
  - `tldw_Server_API/tests/MediaIngestion_NEW/unit/test_video_ingestion.py`
  - `tldw_Server_API/tests/MediaIngestion_NEW/unit/test_process_batch_media_precheck_regressions.py`
- Final verification used the expanded targeted suite plus Bandit on the touched backend files; both completed successfully.

---

### Task 1: Fix Consent, Storage Guard, And Main Router Review Items

**Files:**
- Modify: `tldw_Server_API/app/api/v1/API_Deps/storage_quota_guard.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/consent.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/consent_schemas.py`
- Modify: `tldw_Server_API/app/main.py`
- Test: `tldw_Server_API/tests/Billing/test_storage_quota_guard.py`
- Test: `tldw_Server_API/tests/AuthNZ/test_consent_endpoints.py`

**Step 1: Write the failing tests**

Add focused tests for:

- logging when `guard_storage_quota` falls back to `user_id = 0`
- consent-manager reuse/caching in `consent.py`
- datetime parsing/serialization in `ConsentRecordResponse`
- consent router inclusion respecting `_include_if_enabled(...)`

**Step 2: Run the focused tests to verify failure**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Billing/test_storage_quota_guard.py \
  tldw_Server_API/tests/AuthNZ/test_consent_endpoints.py -v
```

Expected: failures for the new coverage.

**Step 3: Write the minimal implementation**

Implement:

- debug logging around the `user_id = 0` fallback path
- `contextlib.suppress(_NONCRITICAL)` around the warning-header assignment
- cached/singleton `ConsentManager` construction
- `datetime | None` consent schema fields
- `_include_if_enabled("consent", ...)` plus lazy Loguru formatting for `_consent_min_err`

**Step 4: Run the focused tests again**

Run the same pytest command and confirm it passes.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/api/v1/API_Deps/storage_quota_guard.py \
  tldw_Server_API/app/api/v1/endpoints/consent.py \
  tldw_Server_API/app/api/v1/schemas/consent_schemas.py \
  tldw_Server_API/app/main.py \
  tldw_Server_API/tests/Billing/test_storage_quota_guard.py \
  tldw_Server_API/tests/AuthNZ/test_consent_endpoints.py
git commit -m "fix: close consent and quota review gaps"
```

### Task 2: Add Post-Staging Quota Enforcement For URL Ingest

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/ingest_jobs.py`
- Modify: `tldw_Server_API/app/services/media_ingest_jobs_worker.py`
- Test: `tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_endpoint.py`
- Test: `tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_worker.py`

**Step 1: Write the failing tests**

Add one regression test that proves URL-only ingest cannot bypass quota after staging/download. The test should exercise the path that creates or processes a URL ingest job and fail once the real staged size exceeds remaining quota.

**Step 2: Run the targeted ingest tests to verify failure**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_endpoint.py \
  tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_worker.py -v
```

Expected: the new quota-bypass regression test fails.

**Step 3: Write the minimal implementation**

Add a second quota enforcement after remote content has been staged/downloaded and the real byte size is known. Keep the existing request-time `guard_storage_quota` pre-check intact.

**Step 4: Run the targeted ingest tests again**

Run the same pytest command and confirm it passes.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/api/v1/endpoints/media/ingest_jobs.py \
  tldw_Server_API/app/services/media_ingest_jobs_worker.py \
  tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_endpoint.py \
  tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_worker.py
git commit -m "fix: enforce media ingest quota after staging"
```

### Task 3: Fix Remaining Jobs And Stripe Correctness Issues

**Files:**
- Modify: `tldw_Server_API/app/core/Jobs/manager.py`
- Modify: `tldw_Server_API/app/services/stripe_metering_service.py`
- Test: `tldw_Server_API/tests/Jobs/test_fair_share_integration.py`
- Test: `tldw_Server_API/tests/test_stripe_metering.py`

**Step 1: Write the failing tests**

Add focused tests for:

- non-numeric `owner_user_id` not crashing fair-share checks
- admission-control rejection raising `BadRequestError`
- PostgreSQL DATE parameters converted to `datetime.date`
- `_get_subscription_metered_item()` re-raising non-missing Stripe errors
- `is_enabled` reporting false when Stripe runtime is unavailable
- deterministic “yesterday” handling in the metering tests

**Step 2: Run the focused Jobs/Stripe tests to verify failure**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Jobs/test_fair_share_integration.py \
  tldw_Server_API/tests/test_stripe_metering.py -v
```

Expected: the new regression tests fail.

**Step 3: Write the minimal implementation**

Implement:

- use `owner_user_id` as a string in fair-share scheduling
- replace the admission-control `ValueError` with `BadRequestError`
- normalize bound date strings to `datetime.date` before PostgreSQL queries
- catch only the Stripe “resource missing” case in `_get_subscription_metered_item`
- include `STRIPE_AVAILABLE` in `is_enabled`
- freeze or monkeypatch time in the affected metering tests

**Step 4: Run the focused Jobs/Stripe tests again**

Run the same pytest command and confirm it passes.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/Jobs/manager.py \
  tldw_Server_API/app/services/stripe_metering_service.py \
  tldw_Server_API/tests/Jobs/test_fair_share_integration.py \
  tldw_Server_API/tests/test_stripe_metering.py
git commit -m "fix: close jobs and stripe correctness gaps"
```

### Task 4: Close The Remaining Test Hygiene And Review Nit Threads

**Files:**
- Modify: `tldw_Server_API/tests/AuthNZ/test_audit_chain_integration.py`
- Modify: `tldw_Server_API/tests/Billing/test_overage_enforcement_integration.py`
- Modify: `tldw_Server_API/tests/Billing/test_storage_quota_guard.py`
- Modify: `tldw_Server_API/tests/Jobs/test_fair_share_integration.py`
- Modify: `tldw_Server_API/tests/test_stripe_metering.py`

**Step 1: Write or update the tests first**

Add or adjust tests to cover:

- deterministic `soft_limit_percent` behavior in the notify-only overage tests
- any public-behavior assertions needed if the fair-share active-count tests are decoupled from private helpers

The style-only cleanups should be done in the same task:

- remove unused imports
- remove `@pytest.fixture()` parentheses
- add missing return annotations where warranted
- replace the list-building loop with a comprehension
- simplify `_fake_user`
- add the integration marker for `test_fair_share_integration.py`
- convert metering shared scaffolding into pytest fixtures if that remains low-risk after Task 3

**Step 2: Run the affected test modules**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/AuthNZ/test_audit_chain_integration.py \
  tldw_Server_API/tests/Billing/test_overage_enforcement_integration.py \
  tldw_Server_API/tests/Billing/test_storage_quota_guard.py \
  tldw_Server_API/tests/Jobs/test_fair_share_integration.py \
  tldw_Server_API/tests/test_stripe_metering.py -v
```

Expected: pass.

**Step 3: Commit**

```bash
git add \
  tldw_Server_API/tests/AuthNZ/test_audit_chain_integration.py \
  tldw_Server_API/tests/Billing/test_overage_enforcement_integration.py \
  tldw_Server_API/tests/Billing/test_storage_quota_guard.py \
  tldw_Server_API/tests/Jobs/test_fair_share_integration.py \
  tldw_Server_API/tests/test_stripe_metering.py
git commit -m "test: clear remaining pr898 review nits"
```

### Task 5: Verify, Push, And Update PR 898 Threads

**Files:**
- Review: touched source/test files from Tasks 1-4
- Modify: `Docs/Plans/2026-03-17-pr898-open-review-cleanup-design.md` only if implementation scope changes
- Modify: this plan only if execution deviates materially

**Step 1: Run the expanded regression suite**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/AuthNZ/test_consent_endpoints.py \
  tldw_Server_API/tests/AuthNZ/test_audit_chain_integration.py \
  tldw_Server_API/tests/Billing/test_overage_enforcement_integration.py \
  tldw_Server_API/tests/Billing/test_storage_quota_guard.py \
  tldw_Server_API/tests/Jobs/test_fair_share_integration.py \
  tldw_Server_API/tests/test_stripe_metering.py \
  tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_endpoint.py \
  tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_worker.py -v
```

Expected: all pass.

**Step 2: Run Bandit on touched backend files**

Run:

```bash
source .venv/bin/activate
python -m bandit -r \
  tldw_Server_API/app/api/v1/API_Deps/storage_quota_guard.py \
  tldw_Server_API/app/api/v1/endpoints/consent.py \
  tldw_Server_API/app/api/v1/endpoints/media/ingest_jobs.py \
  tldw_Server_API/app/api/v1/schemas/consent_schemas.py \
  tldw_Server_API/app/core/Jobs/manager.py \
  tldw_Server_API/app/main.py \
  tldw_Server_API/app/services/media_ingest_jobs_worker.py \
  tldw_Server_API/app/services/stripe_metering_service.py \
  -f json -o /tmp/bandit_pr898_open_review_cleanup.json
```

Expected: `0` new findings in touched code.

**Step 3: Push and update PR 898**

- Push `feat/production-readiness-gaps`.
- Reply on the substantive threads with the implemented fix details.
- Resolve the three architecture threads by pointing to PR 908.
- Resolve the remaining bot-review threads with the landed fixes.

**Step 4: Commit doc updates if needed**

```bash
git add Docs/Plans/2026-03-17-pr898-open-review-cleanup-design.md Docs/Plans/2026-03-17-pr898-open-review-cleanup.md
git commit -m "docs: finalize pr898 cleanup notes"
```

Plan complete and saved to `Docs/Plans/2026-03-17-pr898-open-review-cleanup.md`. Defaulting to the in-session implementation path from here.
