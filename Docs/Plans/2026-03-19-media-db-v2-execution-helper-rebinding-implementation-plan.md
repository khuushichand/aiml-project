# Media DB V2 Execution Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the Media DB execution-helper surface to a package-native runtime module while preserving SQLite cleanup seams, sync-trigger passthrough, Postgres helper behavior, and the current public error contract.

**Architecture:** Add a `media_db.runtime.execution_ops` module and rebind `_execute_with_connection`, `_executemany_with_connection`, `_fetchone_with_connection`, `_fetchall_with_connection`, `execute_query`, and `execute_many` onto the canonical `MediaDatabase` class. Keep statement-prep and parameter-normalization helpers legacy-owned for now and preserve the existing `Media_DB_v2.sqlite3.connect` patch seam so current cleanup regressions remain valid.

**Tech Stack:** Python 3.11, pytest, SQLite, PostgreSQL, Loguru

---

### Task 1: Add Ownership Regressions For The Execution Helper Methods

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Step 1: Write the failing test**

Add a parametrized ownership regression for:

- `_execute_with_connection`
- `_executemany_with_connection`
- `_fetchone_with_connection`
- `_fetchall_with_connection`
- `execute_query`
- `execute_many`

Follow the same structural pattern as the recent connection-lifecycle test:

```python
method = getattr(MediaDatabase, method_name, None)
assert callable(method)
assert method.__globals__["__name__"] == (
    "tldw_Server_API.app.core.DB_Management.media_db.runtime.execution_ops"
)
```

**Step 2: Run test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'execution_helper_methods_rebind'
```

Expected: FAIL because the six methods still resolve through `Media_DB_v2`.

**Step 3: Write minimal implementation**

Only add the regression test. Do not change production code yet.

**Step 4: Run test to verify it fails for the intended reason**

Run the same command again.

Expected: FAIL only on the selected ownership assertions.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git commit -m "test: add media db execution helper ownership regressions"
```

### Task 2: Add Focused Behavior Regressions For Execution Branches

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py`

**Step 1: Write the failing tests**

Add only the smallest missing focused regressions for:

1. sync-trigger passthrough in `execute_query()`:

```python
with pytest.raises(sqlite3.IntegrityError):
    db.execute_query("SELECT 1")
```

where the patched cursor raises `sqlite3.IntegrityError("sync error: ...")`.

2. empty batch no-op:

```python
assert db.execute_many("INSERT ...", []) is None
```

3. non-list validation:

```python
with pytest.raises(TypeError, match="params_list must be a list"):
    db.execute_many("INSERT ...", ("not", "a", "list"))
```

Preserve the existing cleanup tests that patch
`Media_DB_v2.sqlite3.connect`.

**Step 2: Run test to verify current behavior**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py
```

Expected: PASS if the new regressions match current behavior, or FAIL only if a
test assumption is wrong and needs tightening.

**Step 3: Adjust tests if needed, but do not change production code**

If a new regression is wrong, correct the test to match the current public
behavior before proceeding.

**Step 4: Run test to verify it passes**

Run the same command again.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py
git commit -m "test: lock media db execution helper behavior"
```

### Task 3: Add The Runtime Execution Module

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/execution_ops.py`

**Step 1: Write the failing test**

Use the ownership regression from Task 1 as the failing test. No additional red
test is required here.

**Step 2: Run test to verify it fails**

Run the Task 1 ownership command again.

Expected: FAIL because the methods are still legacy-owned.

**Step 3: Write minimal implementation**

Create `execution_ops.py` and implement:

- `_execute_with_connection`
- `_executemany_with_connection`
- `_fetchone_with_connection`
- `_fetchall_with_connection`
- `execute_query`
- `execute_many`

Hard requirements:

- keep calls through:
  - `self._prepare_backend_statement`
  - `self._prepare_backend_many_statement`
  - `self.get_connection`
  - `self._apply_sqlite_connection_pragmas`
- preserve SQLite ephemeral cleanup via `close_sqlite_ephemeral`
- preserve `BackendCursorAdapter` / `QueryResult`
- preserve `BackendDatabaseError -> DatabaseError` translation
- preserve sync-trigger `IntegrityError` passthrough in `execute_query`
- preserve `execute_many([]) -> None`

Preserve the cleanup test seam:

- do not directly depend on a locally imported `sqlite3.connect` in a way that
  bypasses the current `Media_DB_v2.sqlite3.connect` patchpoint

**Step 4: Run ownership test to verify it still fails until rebind**

Run the Task 1 command again.

Expected: FAIL because the canonical class is not rebound yet.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/runtime/execution_ops.py
git commit -m "feat: add media db execution runtime module"
```

### Task 4: Rebind The Canonical Class To The Runtime Execution Module

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Step 1: Write the failing test**

Reuse the ownership regression from Task 1.

**Step 2: Run test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'execution_helper_methods_rebind'
```

Expected: FAIL because the class is not rebound yet.

**Step 3: Write minimal implementation**

In `media_database_impl.py`:

- import the six runtime execution functions
- assign them onto `MediaDatabase`

Do not rebind:

- `_prepare_backend_statement`
- `_prepare_backend_many_statement`
- `_normalise_params`
- `_append_case_insensitive_like`
- `_keyword_order_expression`

**Step 4: Run test to verify it passes**

Run the Task 2 command again.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py
git commit -m "refactor: rebind media db execution helpers"
```

### Task 5: Verify Cleanup And Postgres Helper Behavior

**Files:**
- Modify only if verification reveals a defect

**Step 1: Run cleanup regressions**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py
```

Expected: PASS

**Step 2: Run targeted Postgres-support helper regressions**

Run a focused subset that exercises:

- `_execute_with_connection`
- `_executemany_with_connection`
- `_fetchone_with_connection`
- `_fetchall_with_connection`
- helper-driven `execute_many` behavior

Use the relevant cases from:

`tldw_Server_API/tests/DB_Management/test_media_postgres_support.py`

Expected: PASS

**Step 3: Fix only execution-slice defects if needed**

Do not widen into prep-helper ownership, constructor behavior, or unrelated
query helpers.

**Step 4: Re-run the same targeted commands**

Expected: PASS

**Step 5: Commit**

```bash
git add <touched files>
git commit -m "test: verify media db execution helper tranche"
```

### Task 6: Run Full Tranche Verification And Recount Ownership

**Files:**
- Modify only if verification reveals a defect

**Step 1: Run the broader DB-management bundle**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_support.py
```

Expected: PASS

**Step 2: Run Bandit on touched production files**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m bandit -r \
  tldw_Server_API/app/core/DB_Management/media_db/runtime/execution_ops.py \
  tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py \
  -f json -o /tmp/bandit_media_db_execution_ops.json
```

Expected: `0` new findings in touched production files.

**Step 3: Recount normalized legacy ownership**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python Helper_Scripts/checks/media_db_runtime_ownership_count.py
```

Expected: the count drops by `6` from the pre-tranche baseline.

**Step 4: Run diff hygiene**

Run:

```bash
git diff --check
```

Expected: clean

**Step 5: Commit final fixups if needed**

```bash
git add <touched files>
git commit -m "test: close out media db execution helper tranche"
```
