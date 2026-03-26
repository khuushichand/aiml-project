# Media DB V2 Email Message Mutation Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the email message mutation helper layer onto a package-owned
runtime module so the canonical `MediaDatabase` no longer owns those methods
through legacy globals, while preserving worker-facing delta and delete-state
contracts.

**Architecture:** Add one runtime helper module for the email mutation layer,
rebind the canonical methods in `media_database_impl.py`, and convert the
legacy `Media_DB_v2` methods into live-module compat shells. Keep the email
read/query surface and tenant-resolution logic legacy-owned for this tranche,
and lock the mutation semantics first with focused helper tests plus
caller-facing worker/email-native guards.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting canonical ownership moved off legacy
   globals for:
   - `_normalize_email_label_values(...)`
   - `_resolve_email_message_row_for_source_message(...)`
   - `apply_email_label_delta(...)`
   - `reconcile_email_message_state(...)`
2. Add failing compat-shell delegation regressions proving the legacy
   `Media_DB_v2` methods delegate through a package helper module via a live
   `import_module(...)` reference.
3. Keep `search_email_messages(...)`, `get_email_message_detail(...)`, and
   `_resolve_email_tenant_id(...)` out of the regression surface for this
   tranche.
4. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'email_label_delta or email_message_state or normalize_email_label_values or resolve_email_message_row_for_source_message'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_email_message_mutation_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `_normalize_email_label_values(...)` dedupes case-insensitively and
     ignores empty values
   - `_resolve_email_message_row_for_source_message(...)` returns a row for an
     existing source/message mapping and `None` when absent
   - `apply_email_label_delta(...)` preserves empty-delta and contradictory
     delta behavior
   - `apply_email_label_delta(...)` updates labels, `label_text`, metadata
     labels, and SQLite FTS rows on success
   - `reconcile_email_message_state(...)` preserves no-state-change,
     source-not-found, delete, and already-deleted outcomes
2. Keep these tests narrow: prove mutation-helper behavior only, not the wider
   email read/query surface.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_email_message_mutation_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/email_message_mutation_ops.py`

**Steps:**
1. Move the four in-scope helper bodies into the new runtime module.
2. Preserve current return payloads, label-text updates, metadata updates, and
   SQLite FTS refresh behavior.
3. Keep `_resolve_email_tenant_id(...)`,
   `_resolve_email_sync_source_row_id(...)`, and `soft_delete_media(...)`
   routed through the DB instance.
4. Do not modify the email read/query methods in this task.
5. Re-run the Task 2 helper slice.

Expected: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions from
   `email_message_mutation_ops.py`.
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
3. Leave `search_email_messages(...)`, `get_email_message_detail(...)`, and
   `_resolve_email_tenant_id(...)` untouched.
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
  tldw_Server_API/tests/DB_Management/test_media_db_email_message_mutation_ops.py \
  tldw_Server_API/tests/DB_Management/test_email_native_stage1.py \
  tldw_Server_API/tests/External_Sources/test_policy_and_connectors.py \
  -k 'email_label_delta or email_message_state or normalize_email_label_values or resolve_email_message_row_for_source_message or connectors'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `101`

Note: `_normalize_email_label_values(...)` is rebound semantically, but the
ownership script counts only `inspect.isfunction(...)` entries on
`MediaDatabase.__dict__`, so the rebound `staticmethod` does not reduce the
normalized total.
