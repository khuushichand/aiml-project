# Targeted Test Failure Investigation Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the current targeted failure set by fixing reproducible regressions in auth override handling, ChaCha legacy migration robustness, and Media DB compatibility/test debt.

**Architecture:** Keep the changes narrow and contract-focused. Preserve the ongoing `media_db` extraction while restoring the compatibility surface the tests still exercise, harden migration logic against older schemas, and make test auth overrides synthesize the same admin principal semantics as real single-user mode when no explicit claims are provided.

**Tech Stack:** Python, FastAPI dependency injection, pytest, SQLite/PostgreSQL schema migration helpers, Bandit

---

### Task 1: Stabilize Investigation Scope

**Files:**
- Modify: `Docs/superpowers/plans/2026-03-29-targeted-test-failure-investigation-fixes.md`
- Test: `tldw_Server_API/tests/DB_Management/test_chacha_migration_v10.py`
- Test: `tldw_Server_API/tests/Discord/test_discord_oauth_lifecycle.py`
- Test: `tldw_Server_API/tests/Slack/test_slack_oauth_lifecycle.py`

- [x] **Step 1: Reproduce the focused failures**

Run:
```bash
source .venv/bin/activate && python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_chacha_migration_v10.py::test_sqlite_migration_v9_to_v10_backfills_and_indexes \
  tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py::test_active_tests_no_longer_import_media_db_v2 \
  tldw_Server_API/tests/Discord/test_discord_oauth_lifecycle.py::test_discord_oauth_callback_persists_installation_and_lists \
  tldw_Server_API/tests/Slack/test_slack_oauth_lifecycle.py::test_slack_oauth_callback_persists_installation_and_lists -q
```

Expected: failures matching the missing `decks` migration guard, stale `Media_DB_v2` references, and 401s on admin installation listing.

- [x] **Step 2: Record the root-cause groups in this plan**

Update this file’s progress notes after confirming the breakpoints.

### Task 2: Write Failing Regression Tests

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_chacha_migration_v10.py`
- Modify: `tldw_Server_API/tests/Discord/test_discord_oauth_lifecycle.py`
- Modify: `tldw_Server_API/tests/Slack/test_slack_oauth_lifecycle.py`
- Modify: `tldw_Server_API/tests/Quizzes/test_quiz_generator_test_mode.py`
- Modify: `tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_worker.py`
- Modify: `Docs/Published/Deployment/Long_Term_Admin_Guide.md`

- [x] **Step 1: Ensure the regression tests describe intended behavior**

Add or adjust tests so they clearly assert:
- legacy ChaCha SQLite schemas without `decks` still migrate successfully
- OAuth admin installation endpoints accept a simple `get_request_user` override in single-user test mode
- active tests/docs no longer reference `Media_DB_v2` directly

- [x] **Step 2: Run the focused tests and confirm they fail for the expected reasons**

Run:
```bash
source .venv/bin/activate && python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_chacha_migration_v10.py \
  tldw_Server_API/tests/Discord/test_discord_oauth_lifecycle.py \
  tldw_Server_API/tests/Slack/test_slack_oauth_lifecycle.py \
  tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
  tldw_Server_API/tests/Quizzes/test_quiz_generator_test_mode.py \
  tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_worker.py -q
```

Expected: red state tied to the implementation gaps, not broken test syntax.

### Task 3: Implement Minimal Fixes

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Modify: `tldw_Server_API/app/api/v1/API_Deps/auth_deps.py`
- Create or Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/tests/Quizzes/test_quiz_generator_test_mode.py`
- Modify: `tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_worker.py`
- Modify: `Docs/Published/Deployment/Long_Term_Admin_Guide.md`

- [x] **Step 1: Harden the ChaCha migration**

Update the flashcard scheduler schema helper so older schemas that predate `decks` do not fail during v36→v37 migration.

- [x] **Step 2: Restore the narrow legacy Media DB compatibility surface**

Provide an importable `Media_DB_v2` shim that keeps type/error imports working for callers and tests without reintroducing legacy helper re-exports the refactor intentionally removed.

- [x] **Step 3: Fix auth override handling for admin routes in tests**

Teach auth dependency resolution to synthesize a principal from `get_request_user` overrides, and in single-user mode only auto-fill admin claims when the override is otherwise claimless.

- [x] **Step 4: Remove stale direct references**

Update the remaining active tests and docs still importing or naming `Media_DB_v2`.

### Task 4: Verify and Secure

**Files:**
- Modify: `Docs/superpowers/plans/2026-03-29-targeted-test-failure-investigation-fixes.md`

- [x] **Step 1: Run targeted pytest verification**

Run:
```bash
source .venv/bin/activate && python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_chacha_migration_v10.py \
  tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
  tldw_Server_API/tests/DB_Management/test_media_db_legacy_maintenance_imports.py \
  tldw_Server_API/tests/DB_Management/test_media_db_legacy_reads_imports.py \
  tldw_Server_API/tests/DB_Management/test_media_db_legacy_transcript_imports.py \
  tldw_Server_API/tests/DB_Management/test_media_db_media_update_imports.py \
  tldw_Server_API/tests/DB_Management/test_media_db_repo_reference_guards.py \
  tldw_Server_API/tests/Discord/test_discord_oauth_lifecycle.py \
  tldw_Server_API/tests/Slack/test_slack_oauth_lifecycle.py \
  tldw_Server_API/tests/Quizzes/test_quiz_generator_test_mode.py \
  tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_worker.py -q
```

- [x] **Step 2: Run Bandit on touched implementation files**

Run:
```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/API_Deps/auth_deps.py \
  tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
  tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
  -f json -o /tmp/bandit_targeted_test_failures.json
```

- [x] **Step 3: Update plan status notes**

## Status Notes

- Original failure set verified green:
  - `test_chacha_migration_v10.py::test_sqlite_migration_v9_to_v10_backfills_and_indexes`
  - `test_media_db_api_imports.py::test_active_tests_no_longer_import_media_db_v2`
  - `test_media_db_legacy_maintenance_imports.py`
  - `test_media_db_legacy_reads_imports.py`
  - `test_media_db_legacy_transcript_imports.py`
  - `test_media_db_media_update_imports.py`
  - `test_media_db_repo_reference_guards.py` guard for `Docs/Published/Deployment/Long_Term_Admin_Guide.md`
  - `test_discord_oauth_lifecycle.py`
  - `test_slack_oauth_lifecycle.py`

- PostgreSQL migration verification is environment-limited here:
  - targeted `test_media_postgres_migrations.py` cases skipped locally rather than failing after the converter/setup changes

- Bandit report written to `/tmp/bandit_targeted_test_failures.json`
  - only existing `B608` findings were reported in untouched portions of `ChaChaNotes_DB.py` (lines `10552`, `10588`, `10692`)

- Broader sweep surfaced unrelated existing failures outside the original report:
  - `tldw_Server_API/tests/Quizzes/test_quiz_generator_test_mode.py`
  - `tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_worker.py`

Record what was verified, what remains unverified, and any environment-limited items such as PostgreSQL-specific migrations if the fixture is unavailable locally.
