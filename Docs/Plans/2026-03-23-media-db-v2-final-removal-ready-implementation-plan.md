# Media DB V2 Final Removal-Ready Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the remaining structural dependence on `Media_DB_v2.py`, migrate
live code/tests/active docs to package-native media DB seams, and make the
legacy module deletable at the end of the tranche if the deletion gate passes.

**Architecture:** Replace the current class-clone assembly in
`media_database_impl.py` with a directly owned native class, eliminate
package-internal `Media_DB_v2` imports from `media_db/**`, then migrate the
remaining active tests/docs and compatibility wrappers to package-native
surfaces. Treat actual `Media_DB_v2.py` deletion as a final gated step rather
than a promise at the start.

**Tech Stack:** Python 3.11, pytest, FastAPI, SQLite, PostgreSQL, Loguru

---

### Task 1: Lock The Native-Class Boundary With Red Tests

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Step 1: Write the failing tests**

Add boundary guards that fail against the current clone-based class assembly:

```python
def test_media_database_impl_source_no_longer_imports_media_db_v2() -> None:
    from pathlib import Path

    source = Path(
        "tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py"
    ).read_text(encoding="utf-8")
    assert "Media_DB_v2 as _legacy_media_db" not in source


def test_media_database_impl_source_no_longer_clones_legacy_media_database() -> None:
    from pathlib import Path

    source = Path(
        "tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py"
    ).read_text(encoding="utf-8")
    assert "_clone_legacy_media_database" not in source


def test_runtime_media_database_cls_resolves_direct_native_owner() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime.media_class import (
        load_media_database_cls,
    )

    cls = load_media_database_cls()
    assert cls.__module__.endswith("media_database_impl")
```

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py -k 'media_database_impl_source_no_longer_imports_media_db_v2 or media_database_impl_source_no_longer_clones_legacy_media_database or resolves_direct_native_owner'`

Expected: FAIL because `media_database_impl.py` still imports and clones the
legacy class.

**Step 3: Write minimal implementation**

- Remove the `_legacy_media_db` import from
  `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`.
- Delete `_clone_legacy_media_database()`.
- Define `class MediaDatabase:` directly in
  `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`.
- Rebind the already-extracted methods and preserved class attributes onto that
  direct class.
- Keep `media_db/media_database.py` and `media_db/native_class.py` as thin
  re-exports.

**Step 4: Run test to verify it passes**

Run the same pytest command.

Expected: PASS

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor add \
  tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py \
  tldw_Server_API/app/core/DB_Management/media_db/media_database.py \
  tldw_Server_API/app/core/DB_Management/media_db/native_class.py \
  tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
  tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor commit -m "refactor: remove legacy media db class clone"
```

### Task 2: Eliminate Package-Internal Imports Of `Media_DB_v2`

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/runtime/chunk_fts_ops.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/runtime/sqlite_bootstrap.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/runtime/backup_ops.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/runtime/execution_ops.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/runtime/fts_ops.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/runtime/data_table_metadata_ops.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/postgres_visibility_owner.py`
- Modify any additional `media_db/**` file found by the red scan
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

**Step 1: Write the failing test**

Add a package-boundary scan:

```python
def test_media_db_package_has_no_internal_media_db_v2_imports() -> None:
    from pathlib import Path

    offenders = []
    root = Path("tldw_Server_API/app/core/DB_Management/media_db")
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "Media_DB_v2" in text:
            offenders.append(str(path))
    assert offenders == []
```

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'package_has_no_internal_media_db_v2_imports'`

Expected: FAIL with the currently importing files listed.

**Step 3: Write minimal implementation**

- Replace each package-internal `Media_DB_v2` import with a direct native helper,
  constant, or error-module import.
- If a shared legacy constant/helper is still needed, move it into a small
  package-native module under `media_db/` rather than keeping the monolith
  import.
- Keep the write scope bounded to `media_db/**`; do not start changing test or
  app caller imports in this task.

**Step 4: Run test to verify it passes**

Run the same pytest command.

Expected: PASS

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor add \
  tldw_Server_API/app/core/DB_Management/media_db \
  tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor commit -m "refactor: remove internal media db legacy imports"
```

### Task 3: Migrate Active Tests Off `Media_DB_v2`

**Files:**
- Modify by slice: `tldw_Server_API/tests/**/*.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Modify shared helpers if needed:
  - `tldw_Server_API/tests/conftest.py`
  - `tldw_Server_API/tests/test_utils.py`

**Step 1: Write the failing test**

Add an active-test boundary guard. Exclude compatibility-history tests only if
the deletion gate has not been reached yet.

```python
def test_active_tests_no_longer_import_media_db_v2() -> None:
    from pathlib import Path

    offenders = []
    root = Path("tldw_Server_API/tests")
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase" in text:
            offenders.append(str(path))
    assert offenders == []
```

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'active_tests_no_longer_import_media_db_v2'`

Expected: FAIL because many active tests still import the legacy path.

**Step 3: Write minimal implementation**

- Migrate tests to `tldw_Server_API.app.core.DB_Management.media_db.native_class`
  or `media_db.media_database`.
- Prefer shared fixture/helper updates over one-off local rewrites.
- Update regression tests that only existed to prove legacy compat shells if the
  tranche is now intentionally deleting that shell.
- Keep historical design docs untouched; only active tests change here.

**Step 4: Run test to verify it passes**

Run the same boundary test, then run each touched domain slice directly.

Example:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'Claims or active_tests_no_longer_import_media_db_v2'`

Expected: PASS for each touched slice.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor add \
  tldw_Server_API/tests \
  tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor commit -m "test: migrate active media db imports off legacy module"
```

**Execution Notes (2026-03-23)**

- Boundary guard passed after migration: active tests no longer import
  `Media_DB_v2`; remaining references are limited to the explicit compatibility
  regressions in `test_media_db_v2_regressions.py`.
- The touched `DB_Management` migration bundle passed as
  `187 passed, 9 skipped, 6 warnings` when run without
  `test_migration_cli_integration.py`; that file remains sandbox-blocked here by
  local PostgreSQL connection attempts to `127.0.0.1:5432`.
- `test_chat_integration.py` was validated with `--collect-only`; full execution
  is sandbox-limited in this environment because its mock OpenAI fixture binds a
  local `HTTPServer`, which raises `PermissionError: [Errno 1] Operation not permitted`.
- `test_add_media_endpoint.py` changed only its `MediaDatabase` import line.
  The isolated `video_upload` case still fails with HTTP `422`, and the file
  still defines `TEST_VIDEO_TRANSCRIPTION_MODEL = "small"`. The matching
  non-video parameter set verified as `8 passed, 28 deselected, 1 xpassed`,
  so the remaining failure is recorded as a pre-existing validation/config issue
  outside this import-migration tranche.

### Task 4: Migrate Active Documentation And `DB_Manager` Media Surface

**Files:**
- Modify active docs that still instruct direct `Media_DB_v2` imports, for example:
  - `Docs/Code_Documentation/Database-Backends.md`
  - `Docs/Code_Documentation/Databases/Media_DB_v2.md`
  - `Docs/Code_Documentation/RAG-Developer-Guide.md`
  - `Docs/Product/**/*.md`
- Modify: `tldw_Server_API/app/core/DB_Management/DB_Manager.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

**Step 1: Write the failing tests**

Add active-doc and compat-facade boundary guards:

```python
def test_active_docs_no_longer_instruct_media_db_v2_imports() -> None:
    from pathlib import Path

    doc_roots = [
        Path("Docs/Code_Documentation"),
        Path("Docs/Product"),
    ]
    offenders = []
    for root in doc_roots:
        if not root.exists():
            continue
        for path in root.rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            if "core.DB_Management.Media_DB_v2 import MediaDatabase" in text:
                offenders.append(str(path))
    assert offenders == []


def test_db_manager_source_no_longer_routes_media_surface_through_media_db_v2() -> None:
    from pathlib import Path

    source = Path(
        "tldw_Server_API/app/core/DB_Management/DB_Manager.py"
    ).read_text(encoding="utf-8")
    assert "Media_DB_v2" not in source
```

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py -k 'active_docs_no_longer_instruct_media_db_v2_imports or db_manager_source_no_longer_routes_media_surface_through_media_db_v2'`

Expected: FAIL

**Step 3: Write minimal implementation**

- Update active docs to point to package-native imports and media DB APIs.
- Narrow `DB_Manager` media forwards so any retained wrappers delegate to
  `media_db.api`, repositories, or package-native services rather than the
  legacy module.
- Keep non-media factories and backend/config helpers untouched.

**Step 4: Run test to verify it passes**

Run the same boundary tests, then the wrapper suite:

`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

Expected: PASS

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor add \
  Docs/Code_Documentation \
  Docs/Product \
  tldw_Server_API/app/core/DB_Management/DB_Manager.py \
  tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py \
  tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor commit -m "refactor: retire media db legacy compat references"
```

**Execution Notes (2026-03-23)**

- The doc boundary failed only on active import guidance in
  `Docs/Code_Documentation/RAG-Developer-Guide.md`, but the legacy-named
  `Docs/Code_Documentation/Databases/Media_DB_v2.md` still taught the old
  import path too, so both docs were updated in the same tranche.
- `Docs/Code_Documentation/Database-Backends.md` now points to the
  package-native entry point `media_db.native_class.MediaDatabase`.
- `DB_Manager.py` required no production change here. The source was already
  free of direct `Media_DB_v2` routing; this tranche only added a local wrapper
  guard in `test_db_manager_wrappers.py` alongside the broader import-boundary
  check in `test_media_db_api_imports.py`.

### Task 5: Delete `Media_DB_v2.py` If The Gate Passes, Else Replace It With A Tiny Shim

**Files:**
- Modify or Delete: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify if needed: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

**Step 1: Write the failing test**

Gate the final state explicitly:

```python
def test_legacy_media_db_module_is_deleted_or_tiny_shim() -> None:
    from pathlib import Path

    path = Path("tldw_Server_API/app/core/DB_Management/Media_DB_v2.py")
    if not path.exists():
        assert True
        return
    line_count = len(path.read_text(encoding="utf-8").splitlines())
    assert line_count <= 80
```

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'deleted_or_tiny_shim'`

Expected: FAIL because the module is currently large.

**Step 3: Write minimal implementation**

- If Tasks 1-4 leave zero active imports, delete
  `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`.
- If any justified compatibility edge remains, replace the file with a tiny
  explicit shim that re-exports the approved package-native symbols and nothing
  else.
- Update or remove old compat regressions accordingly.

**Step 4: Run test to verify it passes**

Run the same boundary test.

Expected: PASS

**Step 5: Commit**

If deleted:

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor rm \
  tldw_Server_API/app/core/DB_Management/Media_DB_v2.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor add \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor commit -m "refactor: delete legacy media db compat module"
```

If shimmed:

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor add \
  tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor commit -m "refactor: reduce media db compat module to tiny shim"
```

**Execution Notes (2026-03-23)**

- The deletion gate did not fully pass for this tranche because the explicitly
  retained compatibility surface still matters to the repo boundary tests:
  `MediaDatabase`, DB error types, document-version lookup, media prompt/
  transcript reads, backup helpers, and SQLite policy helpers. The module was
  therefore reduced to a tiny explicit shim instead of being deleted outright.
- `Media_DB_v2.py` now measures 40 lines and contains only package-native
  re-exports; the embedded `_LegacyMediaDatabase` runtime body is gone.
- The legacy backup compatibility layer in
  `media_db/legacy_backup.py` now owns `create_incremental_backup(...)` and
  `rotate_backups(...)` alongside `create_automated_backup(...)`, and it was
  hardened back to the original shared `MEDIA_NONCRITICAL_EXCEPTIONS` shield
  after code review surfaced a behavior regression.
- `test_media_db_v2_regressions.py` was rewritten from legacy-body delegation
  checks to a focused shim contract suite that verifies the approved compat
  exports, the tiny-source boundary, and the retained helper behavior.
- Focused boundary verification passed as `103 passed, 147 deselected`.
- The wider touched bundle passed as
  `285 passed, 1 deselected, 10 warnings` when excluding the unrelated
  pre-existing branch failure
  `test_media_db_api_imports.py::test_media_db_api_soft_delete_keyword_accepts_partial_legacy_like_db`.
- Bandit on the touched production files reported `0` findings, and
  `git diff --check` remained clean.

### Task 6: Run Final Removal-Ready Verification

**Files:**
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py`
- Test: `tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py`
- Test: touched active test slices
- Production paths touched in Tasks 1-5

**Step 1: Run the focused verification suite**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py`

Expected: PASS

**Step 2: Run touched domain suites**

Run the touched test directories from Tasks 3-5 directly.

Expected: PASS per touched slice.

**Step 3: Run Bandit on touched production paths**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/media_db /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/DB_Manager.py /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/Media_DB_v2.py -f json -o /tmp/bandit_media_db_final_removal_ready.json`

Expected: JSON report with no new findings in touched production code. If
`Media_DB_v2.py` was deleted, omit that path from the command.

**Step 4: Run diff hygiene**

Run:
`git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor diff --check`

Expected: no output

**Step 5: Commit any verification-only updates if needed**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor add \
  tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
  tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py \
  tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor commit -m "test: lock media db final removal boundary"
```

**Execution Notes (2026-03-23)**

- The final removal-ready verification bundle passed as
  `299 passed, 1 deselected, 10 warnings` across
  `test_media_db_api_imports.py`, `test_media_db_runtime_factory.py`,
  `test_db_manager_wrappers.py`, `test_media_db_v2_regressions.py`, and
  `test_db_backup_integrity.py`, with the single deselection preserving the
  pre-existing unrelated branch failure
  `test_media_db_api_soft_delete_keyword_accepts_partial_legacy_like_db`.
- The wider touched-slice verification from Tasks 3-5 remained green at close:
  `187 passed, 9 skipped, 6 warnings` for the active-test migration bundle,
  `285 passed, 1 deselected, 10 warnings` for the shim/backup boundary bundle,
  and the focused shim boundary run passed as `103 passed, 147 deselected`.
- Bandit on the touched production scope
  (`media_db/**`, `DB_Manager.py`, and the tiny `Media_DB_v2.py` shim)
  reported `0` findings and `0` errors.
- `git diff --check` and `git status --short` were clean before the final
  plan-note update; after this documentation-only note, the only remaining
  delta is this plan record itself.
