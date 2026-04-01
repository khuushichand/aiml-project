# Quiz And Media Worker Follow-Up Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the remaining quiz-generator and media-ingest worker test failures uncovered during the broader verification sweep.

**Architecture:** Keep the changes surgical. Restore the missing `workspace_id` handoff in the quiz generator test-mode path, and align the media ingest worker’s embedding completion path with the existing reprocess endpoint by importing the same ready-state helpers explicitly.

**Tech Stack:** Python, pytest, asyncio, FastAPI service helpers

---

### Task 1: Fix Quiz Generator Test-Mode Persistence Contract

**Files:**
- Modify: `tldw_Server_API/app/services/quiz_generator.py`
- Test: `tldw_Server_API/tests/Quizzes/test_quiz_generator_test_mode.py`

- [x] **Step 1: Re-run the failing quiz-generator test**

Run:
```bash
source .venv/bin/activate && python -m pytest -q \
  tldw_Server_API/tests/Quizzes/test_quiz_generator_test_mode.py::test_generate_quiz_from_sources_returns_deterministic_payload_in_test_mode -q
```

Expected: `TypeError` showing `_persist_generated_quiz()` is missing keyword-only argument `workspace_id`.

- [x] **Step 2: Restore the missing `workspace_id` keyword in the test-mode branch**

Update `generate_quiz_from_sources()` so the `is_test_mode()` branch passes both:
- `workspace_id=workspace_id`
- `workspace_tag=workspace_tag`

to `_persist_generated_quiz(...)`, matching the non-test-mode branch.

- [x] **Step 3: Verify the quiz-generator tests pass**

Run:
```bash
source .venv/bin/activate && python -m pytest -q \
  tldw_Server_API/tests/Quizzes/test_quiz_generator_test_mode.py -q
```


### Task 2: Fix Media Ingest Worker Embedding Completion Contract

**Files:**
- Modify: `tldw_Server_API/app/services/media_ingest_jobs_worker.py`
- Test: `tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_worker.py`

- [x] **Step 1: Re-run the failing media-ingest worker tests**

Run:
```bash
source .venv/bin/activate && python -m pytest -q \
  tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_worker.py::test_media_ingest_schedule_embeddings_marks_media_processed \
  tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_worker.py::test_media_ingest_schedule_embeddings_marks_error_on_failure \
  tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_worker.py::test_media_ingest_schedule_embeddings_retries_conflict_without_marking_error -q
```

Expected: `AttributeError` because `media_ingest_jobs_worker` does not expose `mark_media_as_processed`.

- [x] **Step 2: Import the same ready-state helpers used by the reprocess endpoint**

Update `media_ingest_jobs_worker.py` to import:
- `ConflictError` from `tldw_Server_API.app.core.DB_Management.media_db.errors`
- `mark_media_as_processed` from `tldw_Server_API.app.core.DB_Management.DB_Manager`

Do not refactor the retry flow; just make the intended public symbols available and functional.

- [x] **Step 3: Verify the worker tests pass**

Run:
```bash
source .venv/bin/activate && python -m pytest -q \
  tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_worker.py -q
```


### Task 3: Final Verification And Security Check

**Files:**
- Modify: `Docs/superpowers/plans/2026-03-29-quiz-media-worker-followup-fixes.md`

- [x] **Step 1: Run the exact previously failing follow-up tests**

Run:
```bash
source .venv/bin/activate && python -m pytest -q \
  tldw_Server_API/tests/Quizzes/test_quiz_generator_test_mode.py \
  tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_worker.py -q
```

- [x] **Step 2: Run Bandit on touched implementation files**

Run:
```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/services/quiz_generator.py \
  tldw_Server_API/app/services/media_ingest_jobs_worker.py \
  -f json -o /tmp/bandit_quiz_media_worker_followup.json
```

- [x] **Step 3: Record the verification outcome**

Update this file with:
- the tests that passed
- any environment-limited skips
- whether Bandit reported only pre-existing findings or anything new

## Status Notes

- Reproduced the two failures first:
  - `test_generate_quiz_from_sources_returns_deterministic_payload_in_test_mode`
  - `test_media_ingest_schedule_embeddings_marks_media_processed`

- Production fixes applied:
  - `tldw_Server_API/app/services/quiz_generator.py`
    - test-mode branch now passes `workspace_id=workspace_id` into `_persist_generated_quiz(...)`
  - `tldw_Server_API/app/services/media_ingest_jobs_worker.py`
    - imports `mark_media_as_processed` from `DB_Manager`
    - imports `ConflictError` from `media_db.errors`

- Verification passed:
  - `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Quizzes/test_quiz_generator_test_mode.py tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_worker.py -q`
  - Result: `9 passed`

- Security validation:
  - `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/services/quiz_generator.py tldw_Server_API/app/services/media_ingest_jobs_worker.py -f json -o /tmp/bandit_quiz_media_worker_followup.json`
  - Result: clean exit, `0` findings
