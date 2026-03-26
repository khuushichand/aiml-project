# Media DB V2 Class-Chain Severing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move the canonical `MediaDatabase` class definition out of `Media_DB_v2.py` and into `media_db` while preserving runtime loading, supported compat exports, legacy monkeypatch seams, and schema-version continuity.

**Architecture:** First inventory and lock down the supported `Media_DB_v2` compat surface with tests. Then extract the full effective class implementation into a native module, rewire package-native exports to it, and reduce `Media_DB_v2.py` to a compat shell that preserves the explicitly supported symbol and patch surface.

**Tech Stack:** Python 3.11, FastAPI, pytest, SQLite, PostgreSQL, Loguru

---

### Task 1: Inventory The Supported `Media_DB_v2` Compat Surface

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`
- Reference: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Step 1: Write the failing tests**

Add explicit shell-surface expectations for the symbols this tranche must keep:

```python
def test_media_db_v2_supported_compat_exports_remain_available() -> None:
    import importlib

    module = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.Media_DB_v2"
    )

    expected = [
        "MediaDatabase",
        "ConflictError",
        "DatabaseError",
        "InputError",
        "SchemaError",
        "get_document_version",
        "get_media_prompts",
        "get_latest_transcription",
        "get_media_transcripts",
        "create_automated_backup",
        "create_incremental_backup",
        "rotate_backups",
        "configure_sqlite_connection",
        "begin_immediate_if_needed",
    ]

    for name in expected:
        assert hasattr(module, name), name
```

Add an identity/ownership guard placeholder:

```python
def test_canonical_media_database_definition_no_longer_lives_in_media_db_v2() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db import media_database

    assert "Media_DB_v2" not in media_database.MediaDatabase.__module__
```

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py -k 'supported_compat_exports or canonical_media_database_definition'`

Expected: FAIL because the canonical class still reports the legacy module.

**Step 3: Write minimal implementation**

- Update test expectations until they reflect the real supported shell surface.
- Do not change production code in this task beyond what is needed to make the
  inventory explicit in tests.

**Step 4: Run test to verify it passes or fails only on the intended class-ownership assertion**

Run the same command.

Expected: compat export inventory is green; class-ownership assertion still
fails until extraction lands.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
        tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git commit -m "test: lock media db v2 compat shell surface"
```

### Task 2: Extract The Full Effective MediaDatabase Implementation

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Step 1: Write the failing tests**

Add identity and ownership assertions:

```python
def test_native_media_database_definition_module_is_package_native() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db import media_database

    assert media_database.MediaDatabase.__module__.endswith("media_database_impl")


def test_media_db_v2_media_database_matches_native_export() -> None:
    from tldw_Server_API.app.core.DB_Management import Media_DB_v2 as legacy_module
    from tldw_Server_API.app.core.DB_Management.media_db import media_database
    from tldw_Server_API.app.core.DB_Management.media_db import native_class

    assert legacy_module.MediaDatabase is media_database.MediaDatabase
    assert legacy_module.MediaDatabase is native_class.MediaDatabase
```

Add one regression proving a late-bound method still exists:

```python
def test_native_media_database_retains_late_bound_get_media_by_uuid() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db import media_database

    assert callable(getattr(media_database.MediaDatabase, "get_media_by_uuid", None))
```

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py -k 'definition_module_is_package_native or matches_native_export or late_bound_get_media_by_uuid'`

Expected: FAIL because the class still subclasses `_LegacyMediaDatabase`.

**Step 3: Write minimal implementation**

- Create `media_database_impl.py`.
- Move the full effective class surface there:
  - `_LegacyMediaDatabase` class body
  - `_CURRENT_SCHEMA_VERSION`
  - required post-definition method attachments and runtime patch helpers
- Export the canonical class from the new module as `MediaDatabase`.
- Keep imports stable; avoid opportunistic cleanup.

**Step 4: Run test to verify it passes**

Run the same command.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py \
        tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
        tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git commit -m "refactor: extract native media database implementation"
```

### Task 3: Rewire Native Export Modules To The Extracted Class

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/native_class.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py`

**Step 1: Write the failing tests**

Add direct export checks:

```python
def test_media_db_media_database_exports_impl_class() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db import media_database

    assert media_database.MediaDatabase.__module__.endswith("media_database_impl")


def test_media_db_native_class_exports_same_impl_class() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db import media_database
    from tldw_Server_API.app.core.DB_Management.media_db import native_class

    assert native_class.MediaDatabase is media_database.MediaDatabase
```

**Step 2: Run test to verify it fails if rewiring is incomplete**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py -k 'exports_impl_class or same_impl_class or load_media_database_cls'`

Expected: FAIL until both modules point at the extracted implementation.

**Step 3: Write minimal implementation**

- Change `media_db/media_database.py` to import/export `MediaDatabase` from
  `media_database_impl.py`.
- Change `media_db/native_class.py` to import/export from the same module.
- Do not change `runtime/media_class.py` if it already points at
  `native_class.py`; keep the loader path stable.

**Step 4: Run test to verify it passes**

Run the same command.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/media_database.py \
        tldw_Server_API/app/core/DB_Management/media_db/native_class.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
        tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py
git commit -m "refactor: point native media db exports at extracted class"
```

### Task 4: Reduce `Media_DB_v2.py` To An Explicit Compat Shell

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Modify: `tldw_Server_API/tests/Utils/test_api_v1_utils.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_prompts_sqlite.py`
- Modify: `tldw_Server_API/tests/MediaIngestion_NEW/integration/test_external_file_sync_integration.py`

**Step 1: Write the failing tests**

Add an explicit shell-source assertion:

```python
def test_media_db_v2_shell_reexports_supported_surface_from_native_or_helper_modules() -> None:
    import inspect
    from tldw_Server_API.app.core.DB_Management import Media_DB_v2

    source = inspect.getsource(Media_DB_v2)
    assert "media_database_impl" in source or "media_db.media_database" in source
```

Also add a focused import smoke test for representative compat consumers:

```python
def test_compat_importers_still_resolve_media_db_v2_surface() -> None:
    from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import (
        MediaDatabase,
        DatabaseError,
        get_media_prompts,
        get_document_version,
    )

    assert MediaDatabase is not None
    assert DatabaseError is not None
    assert callable(get_media_prompts)
    assert callable(get_document_version)
```

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/Utils/test_api_v1_utils.py tldw_Server_API/tests/DB_Management/test_media_prompts_sqlite.py tldw_Server_API/tests/MediaIngestion_NEW/integration/test_external_file_sync_integration.py -k 'shell_reexports_supported_surface or compat_importers_still_resolve'`

Expected: FAIL until the shell is explicit and stable.

**Step 3: Write minimal implementation**

- Reduce `Media_DB_v2.py` to an explicit shell that re-exports:
  - `MediaDatabase` from the native package path
  - supported error classes
  - supported helper functions still intentionally exposed
  - shell-level helper names that tests patch directly
- Avoid deleting supported imports in this task.

**Step 4: Run test to verify it passes**

Run the same command.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
        tldw_Server_API/tests/Utils/test_api_v1_utils.py \
        tldw_Server_API/tests/DB_Management/test_media_prompts_sqlite.py \
        tldw_Server_API/tests/MediaIngestion_NEW/integration/test_external_file_sync_integration.py
git commit -m "refactor: reduce media db v2 to explicit compat shell"
```

### Task 5: Preserve Legacy Monkeypatch Seams And Schema-Version Continuity

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py`

**Step 1: Write the failing tests**

Add regression guards for patch seams and schema version:

```python
def test_media_db_shell_patch_for_configure_sqlite_connection_still_affects_class(monkeypatch, tmp_path):
    from tldw_Server_API.app.core.DB_Management import Media_DB_v2
    from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase

    calls = []

    def fake_configure(connection, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(Media_DB_v2, "configure_sqlite_connection", fake_configure, raising=False)

    db = MediaDatabase(db_path=str(tmp_path / "media.db"), client_id="patch-test")
    conn = sqlite3.connect(tmp_path / "other.db")
    db._apply_sqlite_connection_pragmas(conn)
    assert calls


def test_runtime_factory_reads_schema_version_from_native_class() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db import native_class
    from tldw_Server_API.app.core.DB_Management.media_db.runtime.factory import (
        get_current_media_schema_version,
    )

    assert get_current_media_schema_version() == native_class.MediaDatabase._CURRENT_SCHEMA_VERSION
```

**Step 2: Run test to verify it fails if seams are broken**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py -k 'patch_for_configure_sqlite_connection or schema_version_from_native_class'`

Expected: FAIL if the extraction broke shell-level helper indirection.

**Step 3: Write minimal implementation**

- Ensure extracted methods continue to honor the shell-level helper names where
  compat tests patch them.
- Preserve `_CURRENT_SCHEMA_VERSION` on the canonical class.
- Keep the runtime factory behavior unchanged apart from reading the truly
  native class.

**Step 4: Run test to verify it passes**

Run the same command.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
        tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py \
        tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
        tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py
git commit -m "test: preserve media db v2 compat patch seams"
```

### Task 6: Run Focused Verification And Close The Tranche

**Files:**
- No new files; verification only

**Step 1: Run the focused runtime/import/regression bundle**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
  tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  tldw_Server_API/tests/Utils/test_api_v1_utils.py \
  tldw_Server_API/tests/DB_Management/test_media_prompts_sqlite.py \
  tldw_Server_API/tests/MediaIngestion_NEW/integration/test_external_file_sync_integration.py
```

Expected: PASS

**Step 2: Run Bandit on the touched production scope**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m bandit -r \
  tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
  tldw_Server_API/app/core/DB_Management/media_db/media_database.py \
  tldw_Server_API/app/core/DB_Management/media_db/native_class.py \
  tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py \
  tldw_Server_API/app/core/DB_Management/media_db/runtime/media_class.py \
  -f json -o /tmp/bandit_media_db_class_chain_severing.json
```

Expected: zero new production findings

**Step 3: Run diff hygiene checks**

Run:

```bash
git diff --check
git status --short --branch
```

Expected: no diff-check output; branch clean after final commit

**Step 4: Final commit if verification-only follow-ups were needed**

```bash
git add <any verification-related follow-up files>
git commit -m "test: close media db class-chain severing tranche"
```
