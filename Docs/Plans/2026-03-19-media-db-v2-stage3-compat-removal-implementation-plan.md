# Media DB V2 Stage 3 Compat Removal Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the legacy Media DB runtime entrypoint with a package-native canonical export, contract `DB_Manager` to a narrow deprecated media facade, and delete any `legacy_*` modules that become provably unused in the same tranche.

**Architecture:** Introduce a package-native canonical class location under `media_db`, point runtime loading and request-scoped session creation at that location, then migrate remaining production media imports away from `DB_Manager` and removable `legacy_*` helpers. Keep `Media_DB_v2.py` as a compatibility shell during the handoff, and only delete specific `legacy_*` modules when import scans and tests prove they are no longer used.

**Tech Stack:** Python 3.11, FastAPI, pytest, SQLite, PostgreSQL, Loguru

---

### Task 1: Introduce The Native Runtime Class Export And Loader Handoff

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/native_class.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/runtime/media_class.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/runtime/session.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py`

**Step 1: Write the failing tests**

Add source and loader assertions:

```python
def test_runtime_media_class_no_longer_uses_legacy_media_db_module_name() -> None:
    import inspect
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import media_class

    assert "LEGACY_MEDIA_DB_MODULE" not in inspect.getsource(media_class)


def test_load_media_database_cls_resolves_native_class_module():
    from tldw_Server_API.app.core.DB_Management.media_db.runtime.media_class import (
        load_media_database_cls,
    )

    cls = load_media_database_cls()
    assert cls.__module__.endswith("media_db.native_class")
```

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py -k 'legacy_media_db_module_name or native_class_module'`

Expected: FAIL because runtime loading still depends on `LEGACY_MEDIA_DB_MODULE`.

**Step 3: Write minimal implementation**

- Create `media_db/native_class.py` as the package-native canonical class export.
- Point `runtime/media_class.py` at the native class module instead of
  `legacy_identifiers.py`.
- Keep `runtime/session.py` behavior unchanged apart from loading the canonical
  class through the updated runtime path.
- Do not change behavior of the DB instance yet; this task is about the loader
  handoff only.

**Step 4: Run test to verify it passes**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py -k 'legacy_media_db_module_name or native_class_module or uses_factory_validator'`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/native_class.py \
        tldw_Server_API/app/core/DB_Management/media_db/runtime/media_class.py \
        tldw_Server_API/app/core/DB_Management/media_db/runtime/session.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
        tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py
git commit -m "refactor: switch media db runtime to native class export"
```

### Task 2: Reduce `Media_DB_v2.py` To A Compatibility Shell

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/native_class.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Step 1: Write the failing tests**

Add tests proving `Media_DB_v2.py` is a compat shell rather than the canonical
runtime path:

```python
def test_media_db_v2_imports_native_class_for_runtime_surface() -> None:
    import inspect
    from tldw_Server_API.app.core.DB_Management import Media_DB_v2

    source = inspect.getsource(Media_DB_v2)
    assert "media_db.native_class" in source


def test_native_class_matches_media_db_v2_export():
    from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase as legacy_cls
    from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase as native_cls

    assert legacy_cls is native_cls
```

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py -k 'native_class_for_runtime_surface or matches_media_db_v2_export'`

Expected: FAIL because `Media_DB_v2.py` still owns the canonical class path.

**Step 3: Write minimal implementation**

- Make `media_db/native_class.py` own the canonical `MediaDatabase` symbol.
- Update `Media_DB_v2.py` so the module re-exports the native class instead of
  acting as the only canonical runtime source.
- Preserve explicit compatibility imports and existing tests that still import
  `Media_DB_v2.MediaDatabase`.

**Step 4: Run test to verify it passes**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py -k 'native_class_for_runtime_surface or matches_media_db_v2_export'`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
        tldw_Server_API/app/core/DB_Management/media_db/native_class.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
        tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git commit -m "refactor: turn media db v2 into compat shell"
```

### Task 3: Migrate Remaining Production Media Imports Off `DB_Manager`

**Files:**
- Modify: `tldw_Server_API/app/core/Ingestion_Media_Processing/XML_Ingestion_Lib.py`
- Modify: `tldw_Server_API/app/core/Ingestion_Media_Processing/Books/Book_Processing_Lib.py`
- Modify: `tldw_Server_API/tests/Media_Ingestion_Modification/test_media_processing.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

**Step 1: Write the failing tests**

Add source guards for the remaining production media imports:

```python
def test_xml_ingestion_lib_no_longer_imports_add_media_with_keywords_from_db_manager() -> None:
    from pathlib import Path

    source = Path(
        "tldw_Server_API/app/core/Ingestion_Media_Processing/XML_Ingestion_Lib.py"
    ).read_text(encoding="utf-8")
    assert "DB_Manager import add_media_with_keywords" not in source


def test_book_processing_lib_no_longer_imports_add_media_with_keywords_from_db_manager() -> None:
    from pathlib import Path

    source = Path(
        "tldw_Server_API/app/core/Ingestion_Media_Processing/Books/Book_Processing_Lib.py"
    ).read_text(encoding="utf-8")
    assert "DB_Manager import add_media_with_keywords" not in source
```

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'no_longer_imports_add_media_with_keywords_from_db_manager'`

Expected: FAIL because those production imports still use `DB_Manager`.

**Step 3: Write minimal implementation**

- Replace direct `DB_Manager.add_media_with_keywords` imports in the listed
  production files with `media_db.api.get_media_repository(...)` or the closest
  package-native write path already present in Stage 1/2.
- Keep behavior unchanged; this task is import-surface reduction, not write-path
  redesign.
- Update or add behavior coverage only where the import move affects tests.

**Step 4: Run test to verify it passes**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/Media_Ingestion_Modification/test_media_processing.py -k 'db_manager or xml or book'`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Ingestion_Media_Processing/XML_Ingestion_Lib.py \
        tldw_Server_API/app/core/Ingestion_Media_Processing/Books/Book_Processing_Lib.py \
        tldw_Server_API/tests/Media_Ingestion_Modification/test_media_processing.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git commit -m "refactor: migrate production media imports off db manager"
```

### Task 4: Thin `DB_Manager` To An Explicit Deprecated Media Facade

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/DB_Manager.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

**Step 1: Write the failing tests**

Add source and behavior guards:

```python
def test_db_manager_media_surface_is_explicit_compat_only_in_source() -> None:
    import inspect
    from tldw_Server_API.app.core.DB_Management import DB_Manager

    source = inspect.getsource(DB_Manager)
    assert "DEPRECATED MEDIA COMPATIBILITY SURFACE" in source


def test_no_production_app_file_imports_media_details_from_db_manager() -> None:
    from pathlib import Path

    app_root = Path("tldw_Server_API/app")
    offenders = []
    for path in app_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "DB_Manager import get_full_media_details" in text or "DB_Manager import get_full_media_details_rich" in text:
            offenders.append(str(path))
    assert offenders == []
```

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'compat_only_in_source or no_production_app_file_imports_media_details_from_db_manager'`

Expected: FAIL because `DB_Manager.py` is not yet marked or tested as a narrow
compatibility surface.

**Step 3: Write minimal implementation**

- Add an explicit compatibility section in `DB_Manager.py` for retained media
  forwards.
- Keep only the media wrappers still intentionally supported by compatibility
  tests.
- Prefer package-native helpers under `media_db.api` where `DB_Manager.py` still
  needs to delegate.
- Do not remove non-media factories or backend/config helpers.

**Step 4: Run test to verify it passes**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'compat_only_in_source or no_production_app_file_imports_media_details_from_db_manager or create_media_database or validate_postgres_content_backend'`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/DB_Manager.py \
        tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git commit -m "refactor: narrow db manager media compat surface"
```

### Task 5: Delete Safe Legacy Modules And Lock The Boundary

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/app/core/DB_Management/DB_Manager.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Delete: `tldw_Server_API/app/core/DB_Management/media_db/legacy_media_details.py`
- Optional Modify/Delete: `tldw_Server_API/app/core/DB_Management/media_db/legacy_identifiers.py`
- Optional Modify: `tldw_Server_API/app/core/DB_Management/db_path_utils.py`

**Step 1: Write the failing tests**

Add deletion guards:

```python
def test_legacy_media_details_has_no_remaining_noncompat_imports() -> None:
    from pathlib import Path

    offenders = []
    for path in Path("tldw_Server_API").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "legacy_media_details" in text and "test_media_db_api_imports.py" not in str(path):
            offenders.append(str(path))
    assert offenders == []
```

If loader and path work are complete, add the analogous test for
`legacy_identifiers.py`.

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'legacy_media_details_has_no_remaining_noncompat_imports or legacy_identifiers'`

Expected: FAIL because compat shells still reference the legacy modules.

**Step 3: Write minimal implementation**

- Repoint `Media_DB_v2.py` and `DB_Manager.py` to the package-native details
  service/API so `legacy_media_details.py` becomes unused.
- Delete `legacy_media_details.py` once import scans are clean.
- Delete `legacy_identifiers.py` only if runtime loading and db-path constants no
  longer reference it.
- Tighten source-guard tests so new production imports cannot reintroduce the
  deleted modules.

**Step 4: Run test to verify it passes**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py -k 'legacy_media_details or legacy_identifiers or runtime or compat'`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
        tldw_Server_API/app/core/DB_Management/DB_Manager.py \
        tldw_Server_API/app/core/DB_Management/db_path_utils.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
        tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py \
        tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py
git rm -f tldw_Server_API/app/core/DB_Management/media_db/legacy_media_details.py
git commit -m "refactor: delete safe media db legacy compat modules"
```

### Task 6: Run Stage 3 Verification And Final Boundary Checks

**Files:**
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py`
- Test: `tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`
- Test: `tldw_Server_API/tests/Media_Ingestion_Modification/test_media_processing.py`

**Step 1: Run the focused Stage 3 suite**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py tldw_Server_API/tests/Media_Ingestion_Modification/test_media_processing.py`

Expected: PASS

**Step 2: Run Bandit on the touched Stage 3 scope**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/DB_Management/media_db tldw_Server_API/app/core/DB_Management/Media_DB_v2.py tldw_Server_API/app/core/DB_Management/DB_Manager.py -f json -o /tmp/bandit_media_db_stage3.json`

Expected: JSON report written with no new findings in touched production code.

**Step 3: Run diff hygiene**

Run:
`git diff --check`

Expected: no output

**Step 4: Commit any final verification-only updates if needed**

```bash
git add tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
        tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py \
        tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py \
        tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
        tldw_Server_API/tests/Media_Ingestion_Modification/test_media_processing.py
git commit -m "test: lock media db compat removal boundary"
```
