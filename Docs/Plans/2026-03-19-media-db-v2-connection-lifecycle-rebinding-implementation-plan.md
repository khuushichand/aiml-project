# Media DB V2 Connection Lifecycle Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the Media DB transaction-state and persistent-connection lifecycle methods to a package-native runtime module without changing constructor, query execution, or bootstrap behavior.

**Architecture:** Add a dedicated `media_db.runtime.connection_lifecycle` module and rebind only the connection-state methods on the canonical `MediaDatabase` class in `media_database_impl.py`. Keep `_resolve_backend`, query-execution helpers, statement-prep helpers, and bootstrap methods in legacy ownership for later slices so this tranche stays narrowly behavioral.

**Tech Stack:** Python 3.11, pytest, SQLite, PostgreSQL, Loguru, ContextVar

---

### Task 1: Add Ownership Regressions For The Connection Lifecycle Methods

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Step 1: Write the failing test**

Add a regression that asserts these canonical class methods still exist and
currently resolve through the legacy module before the implementation change:

- `_get_txn_conn`
- `_set_txn_conn`
- `_get_tx_depth`
- `_set_tx_depth`
- `_inc_tx_depth`
- `_dec_tx_depth`
- `_get_persistent_conn`
- `_set_persistent_conn`
- `get_connection`
- `close_connection`
- `release_context_connection`

Model it after the existing ownership tests that check
`MediaDatabase.__dict__[name].__globals__["__name__"]`.

Expected target after implementation:

```python
"tldw_Server_API.app.core.DB_Management.media_db.runtime.connection_lifecycle"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'connection_lifecycle_methods_rebind'
```

Expected: FAIL because the methods still resolve through `Media_DB_v2`.

**Step 3: Write minimal implementation**

Only add the new regression test. Do not change production code yet.

**Step 4: Run test to verify it fails for the intended reason**

Run the same command again.

Expected: FAIL only on the ownership assertions for the selected methods.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git commit -m "test: add media db connection lifecycle ownership regressions"
```

### Task 2: Add The Runtime Connection Lifecycle Module

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/connection_lifecycle.py`

**Step 1: Write the failing test**

Use the Task 1 ownership regression as the failing test. No extra test file is
needed for this step.

**Step 2: Run test to verify it fails**

Run the Task 1 command again.

Expected: FAIL because the runtime module does not exist and the class methods
are still legacy-owned.

**Step 3: Write minimal implementation**

Create `connection_lifecycle.py` with method-shaped functions:

```python
def _get_txn_conn(self):
    return self._txn_conn_var.get()


def _set_txn_conn(self, conn) -> None:
    self._txn_conn_var.set(conn)
```

Also implement:

- `_get_tx_depth`
- `_set_tx_depth`
- `_inc_tx_depth`
- `_dec_tx_depth`
- `_get_persistent_conn`
- `_set_persistent_conn`
- `get_connection`
- `close_connection`
- `release_context_connection`

Keep semantics identical to the current implementations in `Media_DB_v2.py`.

Hard requirements:

- `get_connection()` must still:
  - return transaction-local connection first
  - return SQLite memory persistent connection when present
  - use pool connections for regular SQLite
  - reuse a persistent PostgreSQL connection outside transactions
  - call `self.backend.apply_scope(conn)` under `suppress(_MEDIA_NONCRITICAL_EXCEPTIONS)`
- `close_connection()` and `release_context_connection()` must still return
  pooled Postgres connections and clear persistent state
- `release_context_connection()` must remain a no-op for SQLite

Do not import or change `_resolve_backend`, `_apply_sqlite_connection_pragmas`,
statement-prep helpers, or execution helpers in this module.

**Step 4: Run test to verify it still fails until rebound**

Run the Task 1 command again.

Expected: FAIL because the canonical class is not rebound yet.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/runtime/connection_lifecycle.py
git commit -m "feat: add media db connection lifecycle runtime module"
```

### Task 3: Rebind The Canonical Class To The New Runtime Module

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Step 1: Write the failing test**

Reuse the ownership regression from Task 1.

Also add a narrow class-surface presence assertion if needed:

```python
assert "_get_txn_conn" in MediaDatabase.__dict__
assert "release_context_connection" in MediaDatabase.__dict__
```

**Step 2: Run test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'connection_lifecycle_methods_rebind'
```

Expected: FAIL because the methods are still bound to `Media_DB_v2`.

**Step 3: Write minimal implementation**

In `media_database_impl.py`:

- import the tranche-A runtime functions from
  `media_db.runtime.connection_lifecycle`
- assign them onto `MediaDatabase`

Example:

```python
MediaDatabase._get_txn_conn = _get_txn_conn
MediaDatabase._set_txn_conn = _set_txn_conn
MediaDatabase.get_connection = get_connection
MediaDatabase.close_connection = close_connection
MediaDatabase.release_context_connection = release_context_connection
```

Do not touch `__init__`.
Do not rebind `_resolve_backend`.
Do not rebind `execute_query` or `execute_many`.

**Step 4: Run test to verify it passes**

Run the Task 2 command again.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py \
        tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git commit -m "refactor: rebind media db connection lifecycle helpers"
```

### Task 4: Verify Lifecycle Behavior Did Not Change

**Files:**
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Step 1: Write the failing test**

If existing tests do not already cover all three behaviors below, add only the
smallest missing regression:

- PostgreSQL `get_connection()` reuses persistent connection and reapplies scope
- `close_connection()` is a no-op while a transaction connection is active
- `release_context_connection()` remains Postgres-only and clears persistent
  connection state

Prefer extending existing regression files instead of creating a new test file.

**Step 2: Run test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'connection or persistent or release_context'
```

Expected: PASS if existing coverage is sufficient, or FAIL only on the new
targeted regression you added.

**Step 3: Write minimal implementation**

Only adjust the new runtime lifecycle module if a behavior mismatch appears.

Do not widen scope into `execute_query`, `_resolve_backend`, or bootstrap.

**Step 4: Run test to verify it passes**

Run the same command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py \
        tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
        tldw_Server_API/app/core/DB_Management/media_db/runtime/connection_lifecycle.py
git commit -m "test: lock media db connection lifecycle behavior"
```

### Task 5: Run Full Tranche Verification And Recount Ownership

**Files:**
- Modify only if verification reveals a defect

**Step 1: Run focused verification**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py
```

Expected: PASS

**Step 2: Run broader tranche verification**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py
```

Expected: PASS

**Step 3: Run Bandit on touched production files**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m bandit -r \
  tldw_Server_API/app/core/DB_Management/media_db/runtime/connection_lifecycle.py \
  tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py \
  -f json -o /tmp/bandit_media_db_connection_lifecycle.json
```

Expected: `0` new findings in touched production files.

**Step 4: Recount normalized legacy ownership**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python Helper_Scripts/checks/media_db_runtime_ownership_count.py
```

Expected: the count drops by `11` from the pre-tranche baseline because this
slice rebinds eleven methods.

**Step 5: Commit final fixups if needed**

```bash
git add <touched files>
git commit -m "test: close out media db connection lifecycle tranche"
```
