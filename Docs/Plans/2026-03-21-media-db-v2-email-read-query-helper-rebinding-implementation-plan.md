# Media DB V2 Email Read Query Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the email read/query layer onto a package-owned runtime module
so the canonical `MediaDatabase` no longer owns those methods through legacy
globals, while preserving endpoint-facing search and detail contracts.

**Architecture:** Add one runtime helper module for the email query layer,
rebind the canonical methods in `media_database_impl.py`, and convert the
legacy `Media_DB_v2` methods into live-module compat shells. Keep
tenant-resolution and backfill/retention logic legacy-owned, and keep the tiny
relative-window and SQLite-FTS literal helpers module-local instead of
expanding the class surface.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting canonical ownership moved off legacy
   globals for:
   - `_parse_email_operator_query(...)`
   - `_email_like_clause(...)`
   - `search_email_messages(...)`
   - `get_email_message_detail(...)`
2. Add failing compat-shell delegation regressions proving the legacy
   `Media_DB_v2` methods delegate through a package helper module via a live
   `import_module(...)` reference.
3. Keep `_resolve_email_tenant_id(...)`,
   `_parse_email_relative_window(...)`, and `_sqlite_fts_literal_term(...)`
   out of the regression surface for this tranche.
4. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'parse_email_operator_query or email_like_clause or search_email_messages or get_email_message_detail'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_email_query_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - parser rejects parentheses and keeps unknown `foo:bar` tokens as text
   - relative-window terms like `older_than:7d` and `newer_than:12h` parse via
     the module-local helper path
   - `_email_like_clause(...)` selects `ILIKE` on PostgreSQL and
     `LIKE ... COLLATE NOCASE` on SQLite
   - `search_email_messages(...)` preserves deleted/trash filtering and
     SQLite FTS-assisted text search
   - `get_email_message_detail(...)` preserves normalized graph shape and
     `include_deleted` behavior
2. Keep these tests narrow: prove query/helper behavior only, not the wider
   backfill or retention surface.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_email_query_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/email_query_ops.py`

**Steps:**
1. Move the four in-scope helper bodies into the new runtime module.
2. Keep `_parse_email_relative_window(...)` and `_sqlite_fts_literal_term(...)`
   as module-local helper functions inside the runtime module.
3. Preserve current metrics, deleted/trash filtering, SQLite FTS assist, and
   detail graph hydration behavior.
4. Keep `_resolve_email_tenant_id(...)` routed through the DB instance.
5. Re-run the Task 2 helper slice.

Expected: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions from `email_query_ops.py`.
2. Rebind the four canonical methods onto the package-owned helpers.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate each of the four legacy methods through `import_module(...)`.
2. Keep the legacy methods present as compat shells.
3. Leave `_resolve_email_tenant_id(...)`, backfill, and retention methods
   untouched.
4. Re-run the Task 1 regression slice.

Expected: PASS

### Task 6: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  tldw_Server_API/tests/DB_Management/test_media_db_email_query_ops.py \
  tldw_Server_API/tests/DB_Management/test_email_native_stage1.py \
  tldw_Server_API/tests/MediaIngestion_NEW/integration/test_email_search_endpoint.py \
  tldw_Server_API/tests/MediaIngestion_NEW/integration/test_media_search_request_model.py \
  -k 'parse_email_operator_query or email_like_clause or search_email_messages or get_email_message_detail or email_search'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `97`
