# Media DB V2 Helper-Cluster Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind selected `MediaDatabase` method clusters away from `Media_DB_v2` globals so the legacy module stops acting as the runtime dependency host for those slices while preserving shell compatibility.

**Architecture:** Extract helper clusters into package-native modules, then rebind the affected canonical `MediaDatabase` methods so they resolve package-native globals instead of `Media_DB_v2`. Preserve shell patchpoints by routing compatibility-sensitive calls through explicit shell-visible wrappers rather than breaking the existing monkeypatch contract.

**Tech Stack:** Python 3.11, pytest, sqlite3, FastAPI, Loguru

---

### Task 1: Add Ownership Counting And Method-Level Rebinding Tests

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py`

**Step 1: Write the failing test**

Add method-ownership tests for the first planned slices:

```python
def test_canonical_media_database_bootstrap_method_no_longer_uses_legacy_globals() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.media_database_impl import MediaDatabase

    assert MediaDatabase._apply_sqlite_connection_pragmas.__globals__["__name__"] != (
        "tldw_Server_API.app.core.DB_Management.Media_DB_v2"
    )


def test_canonical_media_database_backup_method_no_longer_uses_legacy_globals() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.media_database_impl import MediaDatabase

    assert MediaDatabase.backup_database.__globals__["__name__"] != (
        "tldw_Server_API.app.core.DB_Management.Media_DB_v2"
    )
```

Add a helper-count regression guard:

```python
def test_canonical_media_database_legacy_global_method_count_drops_for_completed_slices() -> None:
    import inspect
    from tldw_Server_API.app.core.DB_Management.media_db.media_database_impl import MediaDatabase

    count = sum(
        1
        for value in MediaDatabase.__dict__.values()
        if inspect.isfunction(value)
        and value.__globals__.get("__name__")
        == "tldw_Server_API.app.core.DB_Management.Media_DB_v2"
    )

    assert count < 278
```

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py -k 'bootstrap_method_no_longer_uses_legacy_globals or backup_method_no_longer_uses_legacy_globals or legacy_global_method_count_drops'`

Expected: FAIL because bootstrap and backup methods still resolve `Media_DB_v2`
globals and the count has not materially dropped.

**Step 3: Write minimal implementation**

- Update tests only in this task.
- Do not change production code yet.

**Step 4: Run test to verify it still fails for the intended reasons**

Run the same command.

Expected: FAIL only on the new ownership/count assertions.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
        tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git commit -m "test: add media db helper rebinding ownership guards"
```

### Task 2: Rebind SQLite Bootstrap Ownership While Preserving Shell Patchpoints

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/sqlite_bootstrap.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

**Step 1: Write the failing test**

Add an ownership check plus patch-seam continuity assertion:

```python
def test_sqlite_bootstrap_native_wrapper_still_honors_media_db_v2_patchpoints(monkeypatch) -> None:
    from tldw_Server_API.app.core.DB_Management import Media_DB_v2 as media_db_v2_module
    from tldw_Server_API.app.core.DB_Management.media_db.media_database_impl import MediaDatabase

    calls = []

    def fake_configure(conn, **kwargs):
        calls.append(("configure", kwargs))

    monkeypatch.setattr(media_db_v2_module, "configure_sqlite_connection", fake_configure, raising=False)

    db = MediaDatabase(db_path=":memory:", client_id="bootstrap-native")
    try:
        db._apply_sqlite_connection_pragmas(db._persistent_conn)
    finally:
        if db._persistent_conn is not None:
            db._persistent_conn.close()

    assert calls
```

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py -k 'bootstrap_native_wrapper_still_honors_media_db_v2_patchpoints'`

Expected: FAIL until bootstrap ownership is rebound through a native wrapper.

**Step 3: Write minimal implementation**

- Create `runtime/sqlite_bootstrap.py` with package-native wrapper functions that
  call shell-exported patchpoints from `Media_DB_v2`.
- Rebind `_apply_sqlite_connection_pragmas` and the SQLite branch of
  `transaction()` in `media_database_impl.py` to those wrappers.
- Keep `Media_DB_v2.configure_sqlite_connection` and
  `Media_DB_v2.begin_immediate_if_needed` as supported shell symbols.

**Step 4: Run test to verify it passes**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'bootstrap_native_wrapper_still_honors_media_db_v2_patchpoints or bootstrap_method_no_longer_uses_legacy_globals'`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/runtime/sqlite_bootstrap.py \
        tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py \
        tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
        tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git commit -m "refactor: rebind media db sqlite bootstrap helpers"
```

### Task 3: Rebind Backup Method Ownership

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/backup_ops.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

**Step 1: Write the failing test**

Add:

```python
def test_native_media_database_backup_method_uses_native_globals() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.media_database_impl import MediaDatabase

    assert MediaDatabase.backup_database.__globals__["__name__"].endswith("backup_ops")
```

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py -k 'backup_method_uses_native_globals or media_db_backup_helpers_create_and_rotate'`

Expected: FAIL on ownership before the rebind.

**Step 3: Write minimal implementation**

- Create `runtime/backup_ops.py` with the backup instance-method logic.
- Rebind `backup_database` and `_backup_non_sqlite_database` in
  `media_database_impl.py`.
- Keep shell-level backup exports in `Media_DB_v2.py`.

**Step 4: Run test to verify it passes**

Run the same command.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/runtime/backup_ops.py \
        tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py \
        tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
        tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git commit -m "refactor: rebind media db backup methods"
```

### Task 4: Rebind Chunk Tranche A Ownership

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/chunk_ops.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

**Step 1: Write the failing test**

Add:

```python
def test_native_media_database_chunk_methods_use_native_globals() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.media_database_impl import MediaDatabase

    names = [
        "add_media_chunks_in_batches",
        "batch_insert_chunks",
        "process_chunks",
    ]

    for name in names:
        assert MediaDatabase.__dict__[name].__globals__["__name__"].endswith("chunk_ops")
```

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py -k 'chunk_methods_use_native_globals or batch_insert_chunks_generates_unique_ids_across_calls'`

Expected: FAIL on ownership before rebinding.

**Step 3: Write minimal implementation**

- Create `runtime/chunk_ops.py`.
- Move only tranche-A methods:
  `add_media_chunks_in_batches`, `batch_insert_chunks`, `process_chunks`.
- Rebind those methods in `media_database_impl.py`.

**Step 4: Run test to verify it passes**

Run the same command.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/runtime/chunk_ops.py \
        tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py \
        tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
        tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git commit -m "refactor: rebind media db chunk batch methods"
```

### Task 5: Rebind Chunk Tranche B Ownership

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/runtime/chunk_ops.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

**Step 1: Write the failing test**

Add ownership assertions for:

```python
def test_native_media_database_unvectorized_and_chunk_template_methods_use_native_globals() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.media_database_impl import MediaDatabase

    names = [
        "clear_unvectorized_chunks",
        "process_unvectorized_chunks",
        "create_chunking_template",
        "get_chunking_template",
        "update_chunking_template",
        "delete_chunking_template",
    ]

    for name in names:
        assert MediaDatabase.__dict__[name].__globals__["__name__"].endswith("chunk_ops")
```

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'unvectorized_and_chunk_template_methods_use_native_globals'`

Expected: FAIL until those methods are rebound.

**Step 3: Write minimal implementation**

- Extend `chunk_ops.py` to own tranche-B methods.
- Rebind those methods in `media_database_impl.py`.

**Step 4: Run test to verify it passes**

Run the same command.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/runtime/chunk_ops.py \
        tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py \
        tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git commit -m "refactor: rebind media db chunk maintenance helpers"
```

### Task 6: Recount Ownership, Verify, And Close The Tranche

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py`
- Modify: `Docs/Plans/2026-03-19-media-db-v2-helper-cluster-rebinding-design.md` (only if design notes need factual updates)

**Step 1: Write the failing test**

Tighten the count guard to the actual reduced count once the tranche is in place:

```python
def test_canonical_media_database_legacy_global_method_count_drops_for_completed_slices() -> None:
    ...
    assert count < 278
```

If the actual count is much lower, update the threshold to the precise post-tranche
budget once measured.

**Step 2: Run focused verification**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py tldw_Server_API/tests/Utils/test_api_v1_utils.py tldw_Server_API/tests/DB_Management/test_media_prompts_sqlite.py`

Expected: PASS

**Step 3: Run Bandit**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/DB_Management/Media_DB_v2.py tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py tldw_Server_API/app/core/DB_Management/media_db/runtime/sqlite_bootstrap.py tldw_Server_API/app/core/DB_Management/media_db/runtime/backup_ops.py tldw_Server_API/app/core/DB_Management/media_db/runtime/chunk_ops.py -f json -o /tmp/bandit_media_db_helper_cluster_rebinding.json`

Expected: `results 0`

**Step 4: Run diff hygiene checks**

Run:
`git diff --check && git status --short --branch`

Expected: clean diff formatting; no unexpected files.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
        tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py
git commit -m "test: verify media db helper rebinding tranche"
```
