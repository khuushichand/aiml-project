# SQLite Concurrency Tuning Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Standardize high-value SQLite concurrency settings by using `BEGIN IMMEDIATE` in shared write paths, enabling missing foreign-key enforcement, and defaulting Prompt Studio to WAL outside CI/tests.

**Architecture:** Keep the change set narrow and behavior-focused. Update the shared SQLite transaction helpers and Prompt Studio bootstrap code instead of scattering more retry logic across call sites. Add regression tests in the existing DB, AuthNZ, Scheduler, and Prompt Studio suites so the concurrency policy is explicit and stable.

**Tech Stack:** Python, `sqlite3`, `aiosqlite`, `pytest`, FastAPI backend helpers

---

## Stage 1: Plan And Test Targets
**Goal**: Document the implementation scope and identify existing test files to extend.
**Success Criteria**: Plan file exists with exact code and test targets.
**Tests**: None.
**Status**: Complete

## Stage 2: Red Tests
**Goal**: Add failing tests for the intended SQLite transaction and PRAGMA behavior.
**Success Criteria**: New or updated tests fail because current code still uses deferred transactions or non-WAL Prompt Studio defaults.
**Tests**:
- `python -m pytest tldw_Server_API/tests/DB_Management/test_database_backends.py -k sqlite -v`
- `python -m pytest tldw_Server_API/tests/prompt_studio/test_database.py -k wal -v`
- `python -m pytest tldw_Server_API/tests/AuthNZ -k sqlite_transaction -v`
**Status**: Complete

## Stage 3: Minimal Implementation
**Goal**: Update the targeted SQLite helpers and Prompt Studio initialization to satisfy the new tests.
**Success Criteria**: Shared SQLite write transactions use `BEGIN IMMEDIATE`, the scheduler enables `foreign_keys=ON`, and Prompt Studio defaults to WAL unless CI/test context says otherwise.
**Tests**:
- Re-run the Stage 2 tests after each change.
**Status**: Complete

## Stage 4: Verification And Cleanup
**Goal**: Verify the touched scope and close the loop on security and plan status.
**Success Criteria**: Targeted tests and Bandit pass for the modified files, and this plan reflects final status.
**Tests**:
- `python -m pytest tldw_Server_API/tests/DB_Management/test_database_backends.py tldw_Server_API/tests/prompt_studio/test_database.py tldw_Server_API/tests/AuthNZ/unit/test_sqlite_transaction_modes.py tldw_Server_API/tests/Scheduler/test_sqlite_backend.py -v`
- `python -m bandit -r tldw_Server_API/app/core/AuthNZ/database.py tldw_Server_API/app/core/DB_Management/backends/sqlite_backend.py tldw_Server_API/app/core/DB_Management/Media_DB_v2.py tldw_Server_API/app/core/Scheduler/backends/sqlite_backend.py tldw_Server_API/app/core/DB_Management/PromptStudioDatabase.py -f json -o /tmp/bandit_sqlite_concurrency.json`
**Status**: Complete

**Verification Notes**:
- Targeted pytest suite passed: `67 passed, 7 skipped`
- `bandit` reported only pre-existing low-severity `B311` findings in unrelated Prompt Studio randomization code paths; no findings were introduced in the SQLite concurrency changes

### Task 1: Add backend transaction-mode coverage

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_database_backends.py`
- Modify: `tldw_Server_API/app/core/DB_Management/backends/sqlite_backend.py`

**Step 1: Write the failing test**

Add a test that opens a SQLite backend transaction and asserts the connection enters write mode immediately, for example by checking `PRAGMA transaction_state` or by forcing a competing writer to honor the lock semantics.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/DB_Management/test_database_backends.py -k sqlite_backend_transaction -v`
Expected: FAIL because the backend currently starts transactions with `BEGIN`.

**Step 3: Write minimal implementation**

Change the backend transaction helper to issue `BEGIN IMMEDIATE` for outermost SQLite transactions.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/DB_Management/test_database_backends.py -k sqlite_backend_transaction -v`
Expected: PASS

### Task 2: Add AuthNZ SQLite transaction coverage

**Files:**
- Create: `tldw_Server_API/tests/AuthNZ/unit/test_sqlite_transaction_modes.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/database.py`

**Step 1: Write the failing test**

Add a focused async test that monkeypatches the SQLite connection used by `DatabasePool.transaction()` and asserts the first explicit transaction statement is `BEGIN IMMEDIATE`.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/AuthNZ/unit/test_sqlite_transaction_modes.py -v`
Expected: FAIL because the implementation currently executes `BEGIN`.

**Step 3: Write minimal implementation**

Update the SQLite branch of `DatabasePool.transaction()` to execute `BEGIN IMMEDIATE`.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/AuthNZ/unit/test_sqlite_transaction_modes.py -v`
Expected: PASS

### Task 3: Add scheduler PRAGMA coverage

**Files:**
- Create: `tldw_Server_API/tests/Scheduler/test_sqlite_backend.py`
- Modify: `tldw_Server_API/app/core/Scheduler/backends/sqlite_backend.py`

**Step 1: Write the failing test**

Add a test that connects the scheduler SQLite backend, then verifies each connection has `foreign_keys=ON` and WAL-related tuning applied.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/Scheduler/test_sqlite_backend.py -v`
Expected: FAIL because the scheduler currently omits `PRAGMA foreign_keys=ON`.

**Step 3: Write minimal implementation**

Apply `PRAGMA foreign_keys=ON` during scheduler connection initialization.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/Scheduler/test_sqlite_backend.py -v`
Expected: PASS

### Task 4: Add Prompt Studio WAL default coverage

**Files:**
- Modify: `tldw_Server_API/tests/prompt_studio/test_database.py`
- Modify: `tldw_Server_API/app/core/DB_Management/PromptStudioDatabase.py`

**Step 1: Write the failing test**

Add tests for two cases:
- default local/test path with no CI markers should use WAL
- CI or explicit test environment markers should keep DELETE unless `TLDW_PS_SQLITE_WAL` overrides it

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/prompt_studio/test_database.py -k wal_mode -v`
Expected: FAIL because Prompt Studio currently defaults to DELETE unless explicitly opted into WAL.

**Step 3: Write minimal implementation**

Change Prompt Studio bootstrap logic to default to WAL outside CI/tests, while preserving `TLDW_PS_SQLITE_WAL` as an explicit override.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/prompt_studio/test_database.py -k wal_mode -v`
Expected: PASS

### Task 5: Update Media DB transaction mode

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Test: `tldw_Server_API/tests/Media_Ingestion_Modification/`

**Step 1: Write the failing test**

Prefer extending an existing media DB transaction test if one exists; otherwise add a focused regression test around the transaction helper entering immediate mode for outermost SQLite writes.

**Step 2: Run test to verify it fails**

Run: `python -m pytest <targeted media test> -v`
Expected: FAIL because the helper currently executes `BEGIN`.

**Step 3: Write minimal implementation**

Change the outermost SQLite transaction start in `Media_DB_v2.transaction()` from `BEGIN` to `BEGIN IMMEDIATE`.

**Step 4: Run test to verify it passes**

Run: `python -m pytest <targeted media test> -v`
Expected: PASS
