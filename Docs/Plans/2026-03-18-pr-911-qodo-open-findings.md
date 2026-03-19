# PR 911 Qodo Open Findings Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Address the still-open top-level Qodo findings on PR #911 that appear technically actionable on the current branch head.

**Architecture:** Keep this batch narrow. Fix the request/session lifecycle and runtime factory correctness issues first because they can affect real DB behavior, then remove the raw SQL from the claims rebuild startup loop by routing through existing Claims DB management seams, and finish with the low-risk FTS type-hint cleanup. All behavior changes must follow red-green verification with focused tests.

**Tech Stack:** Python 3.11, FastAPI, pytest, Bandit, SQLite/PostgreSQL DB abstraction layer

---

## Stage 1: Confirm the Four Live Findings
**Goal:** Verify each Qodo item against current code before implementation.
**Success Criteria:** Each item is classified as `fix`, `already fixed`, or `reject with rationale`.
**Tests:** None
**Status:** Complete

### Classification
- `media_db/schema/features/fts.py`: already fixed on current head; helper parameters are typed.
- `app/main.py` raw SQL in claims rebuild loop: already fixed on current head; startup loop routes through `list_claims_rebuild_media_ids(...)`.
- `media_db/runtime/factory.py` explicit backend ignored in SQLite mode: already fixed on current head and covered by runtime factory tests.
- `media_db/runtime/session.py` request-owned session teardown: worth hardening in code because generic request-owned sessions could leave their own backend pool alive after request teardown.

## Stage 2: Fix Runtime/Session Correctness
**Goal:** Address the two DB lifecycle/runtime bugs in `DB_Deps.py` and `media_db/runtime/factory.py`.
**Success Criteria:** Explicit backend injection works in non-Postgres mode, and request-scoped SQLite sessions do not leak request-owned resources.
**Tests:** Focused pytest for `test_media_db_runtime_factory.py`, `test_media_db_request_scope_isolation.py`, and any new regression tests needed.
**Status:** Complete

### Result
- Hardened `MediaDbSession.release_context_connection()` so request-owned sessions now tear down their owned backend pool after releasing context-bound state.
- Added a direct regression proving repeated SQLite request sessions for the same user reuse one shared backend through `DB_Deps`.
- Confirmed the explicit-backend runtime factory issue was already fixed and remains covered by tests.

## Stage 3: Remove Raw SQL from Claims Rebuild Startup
**Goal:** Move the `main.py` claims rebuild media-selection logic behind an existing DB management helper instead of inline SQL in orchestration code.
**Success Criteria:** Startup loop no longer builds raw SQL strings directly; behavior is covered by focused tests.
**Tests:** Focused pytest for `test_main_claims_rebuild_startup.py` and any new claims rebuild helper regressions.
**Status:** Complete

### Result
- Verified this was already complete on the current branch head before this batch.
- `main.py` already uses `list_claims_rebuild_media_ids(...)`; no new code change was needed.

## Stage 4: Close Low-Risk Remaining Finding and Verify
**Goal:** Apply the FTS helper type-hint cleanup, run focused verification, and update PR disposition docs/comments.
**Success Criteria:** FTS helper signatures are typed, touched tests pass, Bandit is clean, and the PR note accurately reflects what remains visible vs actionable.
**Tests:** Focused pytest for touched DB schema/import surfaces; Bandit on touched production scope.
**Status:** Complete

### Verification
- `25 passed, 13 deselected` across the focused DB/session/runtime/startup slice
- Bandit on `media_db/runtime/session.py`: `0` findings
