# Media DB V2 Email Graph Persistence Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the remaining email tenant-resolution and message-graph
persist helpers onto a package-owned runtime module so the canonical
`MediaDatabase` no longer owns them through legacy globals while preserving the
normalized email write contract.

**Architecture:** Add one runtime helper module for
`_resolve_email_tenant_id(...)` and `upsert_email_message_graph(...)`, rebind
the canonical methods in `media_database_impl.py`, and convert the legacy
`Media_DB_v2` methods into live-module compat shells. Keep the static email
normalization helpers and the broader email query/mutation/retention/backfill
surfaces deferred and instance-routed.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting canonical ownership moved off legacy
   globals for:
   - `_resolve_email_tenant_id(...)`
   - `upsert_email_message_graph(...)`
2. Add failing compat-shell delegation regressions proving the legacy
   `Media_DB_v2` methods delegate through a package helper module via a live
   `import_module(...)` reference.
3. Keep `_normalize_email_address(...)`, `_parse_email_internal_date(...)`,
   `_collect_email_labels(...)`, and the already-moved email runtime methods
   out of this regression surface.
4. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k '_resolve_email_tenant_id or upsert_email_message_graph'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_email_graph_persistence_ops.py`

**Steps:**
1. Add failing helper-path tests asserting `_resolve_email_tenant_id(...)`
   preserves precedence for:
   - explicit tenant id
   - effective org scope
   - user scope
   - client-id fallback
2. Add a failing helper-path test asserting
   `upsert_email_message_graph(...)` creates the normalized graph through the
   new helper path, including source row, message row, labels, participants,
   attachments, and SQLite `email_fts`.
3. Add a failing helper-path test asserting re-upsert by
   `source_message_id` refreshes child rows rather than duplicating them.
4. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_email_graph_persistence_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/email_graph_persistence_ops.py`

**Steps:**
1. Move `_resolve_email_tenant_id(...)` and `upsert_email_message_graph(...)`
   into the new runtime module.
2. Preserve current routing through these DB-instance seams:
   - `_normalize_email_address(...)`
   - `_parse_email_internal_date(...)`
   - `_collect_email_labels(...)`
   - `_fetchone_with_connection(...)`
   - `_fetchall_with_connection(...)`
   - `_execute_with_connection(...)`
   - `transaction()`
3. Preserve current tenant precedence, match strategy ordering, child-row
   replacement semantics, and SQLite `email_fts` refresh behavior.
4. Re-run the Task 2 helper slice.

Expected: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions from
   `email_graph_persistence_ops.py`.
2. Rebind the two canonical methods onto the package-owned helpers.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate each of the two legacy methods through `import_module(...)`.
2. Keep the legacy methods present as compat shells.
3. Leave `_normalize_email_address(...)`, `_parse_email_internal_date(...)`,
   `_collect_email_labels(...)`, and the already-moved email runtime methods
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
  tldw_Server_API/tests/DB_Management/test_media_db_email_graph_persistence_ops.py \
  tldw_Server_API/tests/DB_Management/test_email_native_stage1.py \
  tldw_Server_API/tests/DB_Management/test_media_db_email_message_mutation_ops.py \
  tldw_Server_API/tests/DB_Management/test_media_db_email_query_ops.py \
  tldw_Server_API/tests/DB_Management/test_media_db_email_retention_ops.py \
  -k '_resolve_email_tenant_id or upsert_email_message_graph or email_message_graph'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `90`

Result: Achieved. The focused regression slice passed, the helper-path file
passed, the broader email-native bundle passed, Bandit reported no issues on
touched production files, `git diff --check` was clean, and the normalized
ownership count dropped from `92` to `90`.
