# Media DB V2 Post-Stage-3 Native Class Handoff Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the canonical `MediaDatabase` definition package-native, remove production reliance on `legacy_identifiers.py`, and then migrate the remaining direct `Media_DB_v2` test imports in bounded domain slices.

**Architecture:** Keep `Media_DB_v2.py` as a compatibility module, but stop using it as part of the canonical class-definition chain. Introduce one package-native implementation module under `media_db`, make `native_class.py` a thin export of that module, and reduce legacy naming constants to compatibility-only status. After that, migrate test callers away from `Media_DB_v2` cluster by cluster instead of with one large churn-heavy sweep.

**Tech Stack:** Python 3.11, FastAPI, pytest, SQLite, PostgreSQL, Loguru

---

### Task 1: Extract The Canonical MediaDatabase Class Into A Package-Native Module

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/media_database.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/native_class.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py`

**Step 1: Write the failing tests**

Add source and identity guards:

```python
def test_native_class_no_longer_imports_media_db_v2_in_source() -> None:
    import inspect
    from tldw_Server_API.app.core.DB_Management.media_db import native_class

    source = inspect.getsource(native_class)
    assert "Media_DB_v2" not in source


def test_media_db_v2_reexports_package_native_media_database() -> None:
    from tldw_Server_API.app.core.DB_Management import Media_DB_v2
    from tldw_Server_API.app.core.DB_Management.media_db import media_database

    assert Media_DB_v2.MediaDatabase is media_database.MediaDatabase
```

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py -k 'native_class_no_longer_imports_media_db_v2_in_source or reexports_package_native_media_database'`

Expected: FAIL because `native_class.py` still subclasses through `Media_DB_v2`.

**Step 3: Write minimal implementation**

- Create `media_db/media_database.py` and move the canonical class definition there by importing `_LegacyMediaDatabase` from `Media_DB_v2.py` as a temporary transitional base.
- Change `native_class.py` to re-export `MediaDatabase` from `media_db.media_database`.
- Update `Media_DB_v2.py` to re-export the package-native class at the end of the module rather than owning the canonical symbol.
- Preserve function exports and compatibility imports from `Media_DB_v2.py`.

**Step 4: Run test to verify it passes**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py -k 'native_class_no_longer_imports_media_db_v2_in_source or reexports_package_native_media_database or resolves_native_class_module'`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/media_database.py \
        tldw_Server_API/app/core/DB_Management/media_db/native_class.py \
        tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
        tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
        tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py
git commit -m "refactor: extract native media database class module"
```

### Task 2: Remove Production Dependence On legacy_identifiers.py

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/constants.py`
- Modify: `tldw_Server_API/app/core/DB_Management/db_path_utils.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/legacy_identifiers.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

**Step 1: Write the failing tests**

Add source guards:

```python
def test_db_path_utils_no_longer_imports_legacy_identifiers_in_source() -> None:
    from pathlib import Path

    source = Path(
        "tldw_Server_API/app/core/DB_Management/db_path_utils.py"
    ).read_text(encoding="utf-8")
    assert "legacy_identifiers" not in source


def test_media_db_constants_export_canonical_filename() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.constants import MEDIA_DB_FILENAME

    assert MEDIA_DB_FILENAME == "Media_DB_v2.db"
```

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'db_path_utils_no_longer_imports_legacy_identifiers_in_source or constants_export_canonical_filename'`

Expected: FAIL because `db_path_utils.py` still imports `legacy_identifiers.py`.

**Step 3: Write minimal implementation**

- Add `media_db/constants.py` with the canonical filename/basename constants needed by active production code.
- Point `db_path_utils.py` at the new constants module.
- Leave `legacy_identifiers.py` in place as a compatibility module that re-exports those values for tests or compatibility-only imports.

**Step 4: Run test to verify it passes**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'db_path_utils_no_longer_imports_legacy_identifiers_in_source or constants_export_canonical_filename or legacy_identifiers_owns_media_db_v2_reference'`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/constants.py \
        tldw_Server_API/app/core/DB_Management/db_path_utils.py \
        tldw_Server_API/app/core/DB_Management/media_db/legacy_identifiers.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git commit -m "refactor: isolate media db constants from legacy identifiers"
```

### Task 3: Migrate The Remaining Direct Media_DB_v2 Test Imports By Domain

**Files:**
- Modify by slice: `tldw_Server_API/tests/Claims/**/*.py`
- Modify by slice: `tldw_Server_API/tests/RAG/**/*.py`
- Modify by slice: `tldw_Server_API/tests/RAG_NEW/**/*.py`
- Modify by slice: `tldw_Server_API/tests/TTS_NEW/**/*.py`
- Modify by slice: `tldw_Server_API/tests/DataTables/**/*.py`
- Modify by slice: `tldw_Server_API/tests/ChromaDB/**/*.py`
- Modify by slice: `tldw_Server_API/tests/MediaDB2/**/*.py`
- Modify: `tldw_Server_API/tests/test_utils.py`
- Modify: `tldw_Server_API/tests/conftest.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

**Step 1: Write the failing tests**

Add boundary scans per slice instead of repo-wide all at once:

```python
@pytest.mark.parametrize(
    "relative_root",
    [
        "tldw_Server_API/tests/Claims",
        "tldw_Server_API/tests/RAG",
        "tldw_Server_API/tests/RAG_NEW",
    ],
)
def test_domain_test_slice_no_longer_imports_media_db_v2(relative_root: str) -> None:
    from pathlib import Path

    offenders = []
    for path in Path(relative_root).rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase" in text:
            offenders.append(str(path))
    assert offenders == []
```

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'domain_test_slice_no_longer_imports_media_db_v2'`

Expected: FAIL because many domain suites still import `Media_DB_v2.MediaDatabase`.

**Step 3: Write minimal implementation**

- Migrate one domain cluster at a time to `media_db.native_class.MediaDatabase` or seam-backed helpers from `tests/conftest.py`.
- Keep compatibility-only tests in `tests/DB_Management/` allowed to import `Media_DB_v2`.
- Prefer shared helper/factory migration over per-test custom rewrites.

**Step 4: Run test to verify it passes for each migrated slice**

Run per slice, for example:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Claims tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'Claims or domain_test_slice_no_longer_imports_media_db_v2'`

Expected: PASS for the migrated slice before moving to the next one.

**Step 5: Commit per domain slice**

```bash
git add tldw_Server_API/tests/Claims \
        tldw_Server_API/tests/test_utils.py \
        tldw_Server_API/tests/conftest.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git commit -m "test: migrate claims media db imports off compat shell"
```

Repeat for `RAG`, `RAG_NEW`, `TTS_NEW`, `DataTables`, `ChromaDB`, and `MediaDB2`.

### Task 4: Run Post-Tranche Verification

**Files:**
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py`
- Test: migrated domain test slices
- Test: targeted compatibility tests in `tldw_Server_API/tests/DB_Management/`

**Step 1: Run focused verification**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py`

Expected: PASS

**Step 2: Run domain verification after each migrated cluster**

Run the affected test directories directly, not the whole suite, after each cluster commit.

**Step 3: Run Bandit on touched production paths**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/DB_Management/media_db tldw_Server_API/app/core/DB_Management/Media_DB_v2.py tldw_Server_API/app/core/DB_Management/db_path_utils.py -f json -o /tmp/bandit_media_db_post_stage3.json`

Expected: no new findings in touched production code.

**Step 4: Run diff hygiene**

Run:
`git diff --check`

Expected: no output
