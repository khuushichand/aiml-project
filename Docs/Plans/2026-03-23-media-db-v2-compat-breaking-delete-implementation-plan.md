# Media DB V2 Compat-Breaking Delete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete `Media_DB_v2.py` entirely and migrate the remaining active
tests and active code documentation to package-native media DB seams.

**Architecture:** Replace the current tiny-shim contract with a hard deletion
contract. First rewrite the boundary tests so they expect the module to be
absent, then migrate the remaining live monkeypatch/import sites and current
code docs, and only then delete the file. Historical plans/PRDs and
`Media_DB_v2.db` filename references remain out of scope.

**Tech Stack:** Python 3.11, pytest, FastAPI, SQLite, PostgreSQL, Loguru

---

### Task 1: Rewrite The Boundary Suite For Hard Deletion

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

- [ ] **Step 1: Write the failing tests**

Add native-boundary checks and replace the tiny-shim contract with an explicit
delete-blocker inventory.

```python
def test_media_db_delete_blockers_match_known_inventory() -> None:
    expected = {
        "tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py",
        "tldw_Server_API/tests/Workflows/adapters/test_media_adapters.py",
        "tldw_Server_API/tests/RAG_NEW/unit/test_unified_pipeline_focused.py",
        "Docs/Database_Migrations.md",
        "Docs/Code_Documentation/Database.md",
        "Docs/Code_Documentation/index.md",
        "Docs/Code_Documentation/Code_Map.md",
        "Docs/Code_Documentation/Email_Search_Architecture.md",
        "Docs/Code_Documentation/Pieces.md",
        "Docs/Code_Documentation/Claims_Extraction.md",
        "Docs/Code_Documentation/Ingestion_Media_Processing.md",
        "Docs/Code_Documentation/RAG-Developer-Guide.md",
        "Docs/Code_Documentation/Chunking_Templates_Developer_Guide.md",
        "Docs/Code_Documentation/Databases/Media_DB_v2.md",
    }
    assert _media_db_delete_blockers() == expected


def test_media_db_delete_gate_not_yet_satisfied() -> None:
    legacy_module_path = (
        Path(__file__).resolve().parents[2]
        / "app/core/DB_Management/Media_DB_v2.py"
    )
    assert legacy_module_path.exists()
```

Replace the top-level imports in `test_media_db_v2_regressions.py` with native
imports only, then add a native-boundary regression such as:

```python
from tldw_Server_API.app.core.DB_Management.media_db import native_class
from tldw_Server_API.app.core.DB_Management.media_db import media_database


def test_native_media_database_exports_resolve_same_class() -> None:
    assert native_class.MediaDatabase is media_database.MediaDatabase
```

- [ ] **Step 2: Run test to verify it fails**

Run:

`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py -k 'delete_blockers_match_known_inventory or delete_gate_not_yet_satisfied or native_media_database_exports_resolve_same_class'`

Expected: FAIL because the current boundary suite still assumes the tiny shim
contract and does not expose the blocker inventory yet.

- [ ] **Step 3: Write minimal implementation**

- Remove the old tiny-shim assertions and legacy-module imports from
  `test_media_db_v2_regressions.py`.
- Convert that file into a native-boundary regression suite that does not
  import `Media_DB_v2`.
- Update `test_media_db_api_imports.py` so:
  - helper scans collect active test/doc blockers by module-path guidance only
  - the known blocker inventory is asserted explicitly
  - the file-existence check is still expected to be true until Task 4

- [ ] **Step 4: Run test to verify it passes**

Run the same pytest command.

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor add \
  tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor commit -m "test: replace media db shim boundary with delete gate"
```

### Task 2: Migrate Remaining Active Test Patch Sites

**Files:**
- Modify: `tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py`
- Modify: `tldw_Server_API/tests/Workflows/adapters/test_media_adapters.py`
- Modify: `tldw_Server_API/tests/RAG_NEW/unit/test_unified_pipeline_focused.py`
- Modify if needed: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

- [ ] **Step 1: Write the failing tests**

Use the blocker inventory from Task 1 as the red guard, then add or tighten
targeted assertions in each touched test if needed.

Examples:

```python
def test_tts_history_write_failure_uses_native_media_db_patch_point(...):
    ...


def test_workflow_ingest_does_not_construct_native_media_database_directly(...):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run:

`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Workflows/adapters/test_media_adapters.py /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/RAG_NEW/unit/test_unified_pipeline_focused.py /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'delete_blockers_match_known_inventory or workflow_ingest or history_write_failure or unified_rag_pipeline'`

Expected: FAIL because the blocker inventory still includes the three active
test files.

- [ ] **Step 3: Write minimal implementation**

- In `test_tts_endpoints.py`, move the patch target from
  `tldw_Server_API.app.core.DB_Management.Media_DB_v2.MediaDatabase.create_tts_history_entry`
  to the package-native class path that owns the method, using the same method
  object identity.
- In `test_media_adapters.py`, replace the direct legacy-class patch with the
  native class path or remove the patch entirely if the ingest module is already
  fully guarded through `managed_media_database(...)`.
- In `test_unified_pipeline_focused.py`, remove the obsolete legacy
  `MediaDatabase` patch if the test already patches `managed_media_database`;
  otherwise move it to the native class path.
- Update the blocker inventory in `test_media_db_api_imports.py` so the active
  test offender set shrinks to the remaining doc-only blockers.

- [ ] **Step 4: Run test to verify it passes**

Run:

`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Workflows/adapters/test_media_adapters.py /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/RAG_NEW/unit/test_unified_pipeline_focused.py /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'not soft_delete_keyword_accepts_partial_legacy_like_db and (delete_blockers_match_known_inventory or workflow_ingest or history_write_failure or unified_rag_pipeline)'`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor add \
  tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py \
  tldw_Server_API/tests/Workflows/adapters/test_media_adapters.py \
  tldw_Server_API/tests/RAG_NEW/unit/test_unified_pipeline_focused.py \
  tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor commit -m "test: migrate media db delete blockers to native seams"
```

### Task 3: Migrate Active Code Documentation Off The Deleted Module Path

**Files:**
- Modify: `Docs/Database_Migrations.md`
- Modify: `Docs/Code_Documentation/Database.md`
- Modify: `Docs/Code_Documentation/index.md`
- Modify: `Docs/Code_Documentation/Code_Map.md`
- Modify: `Docs/Code_Documentation/Email_Search_Architecture.md`
- Modify: `Docs/Code_Documentation/Pieces.md`
- Modify: `Docs/Code_Documentation/Claims_Extraction.md`
- Modify: `Docs/Code_Documentation/Ingestion_Media_Processing.md`
- Modify: `Docs/Code_Documentation/RAG-Developer-Guide.md`
- Modify: `Docs/Code_Documentation/Chunking_Templates_Developer_Guide.md`
- Modify: `Docs/Code_Documentation/Databases/Media_DB_v2.md`
- Modify if needed: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

- [ ] **Step 1: Write the failing test**

Narrow the active-doc boundary to deleted Python module guidance only and use
the blocker inventory from Task 1 as the red guard.

```python
def test_active_code_docs_no_longer_point_to_media_db_v2_module() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    doc_paths = [
        repo_root / "Docs/Database_Migrations.md",
        repo_root / "Docs/Code_Documentation/Database.md",
        repo_root / "Docs/Code_Documentation/index.md",
        repo_root / "Docs/Code_Documentation/Code_Map.md",
        repo_root / "Docs/Code_Documentation/Email_Search_Architecture.md",
        repo_root / "Docs/Code_Documentation/Pieces.md",
        repo_root / "Docs/Code_Documentation/Claims_Extraction.md",
        repo_root / "Docs/Code_Documentation/Ingestion_Media_Processing.md",
        repo_root / "Docs/Code_Documentation/RAG-Developer-Guide.md",
        repo_root / "Docs/Code_Documentation/Chunking_Templates_Developer_Guide.md",
        repo_root / "Docs/Code_Documentation/Databases/Media_DB_v2.md",
    ]
    offenders = []
    for path in doc_paths:
        text = path.read_text(encoding="utf-8")
        if "tldw_Server_API/app/core/DB_Management/Media_DB_v2.py" in text:
            offenders.append(str(path))
        if "from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import" in text:
            offenders.append(str(path))
    assert offenders == []
```

- [ ] **Step 2: Run test to verify it fails**

Run:

`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'active_code_docs_no_longer_point_to_media_db_v2_module or delete_blockers_match_known_inventory'`

Expected: FAIL because multiple active code docs still point at the deleted
module path.

- [ ] **Step 3: Write minimal implementation**

- Update each active code doc to reference package-native media DB seams.
- Keep `Media_DB_v2.db` filename references when they describe storage layout.
- In `Docs/Code_Documentation/Databases/Media_DB_v2.md`, keep the document path
  for now if desired, but rewrite the content so it documents `MediaDatabase`
  as a package-native library rather than `Media_DB_v2.py`.
- Update the blocker inventory in `test_media_db_api_imports.py` so only the
  still-existing `Media_DB_v2.py` file remains as a delete blocker.

- [ ] **Step 4: Run test to verify it passes**

Run:

`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'active_code_docs_no_longer_point_to_media_db_v2_module or delete_blockers_match_known_inventory'`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor add \
  Docs/Database_Migrations.md \
  Docs/Code_Documentation \
  tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor commit -m "docs: remove live media db module references"
```

### Task 4: Delete `Media_DB_v2.py` And Lock The Hard-Delete Gate

**Files:**
- Delete: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`
- Modify: `Docs/Plans/2026-03-23-media-db-v2-compat-breaking-delete-implementation-plan.md`

- [x] **Step 1: Delete the file**

Delete:

`/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

- [x] **Step 2: Run test to verify the hard-delete boundary passes**

As part of this step, update the blocker inventory to the empty set and flip the
file-presence assertion from "exists" to "is deleted."

Run:

`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py -k 'legacy_media_db_module_is_deleted or delete_blockers_match_known_inventory or active_code_docs_no_longer_point_to_media_db_v2_module or native_media_database_exports_resolve_same_class'`

Expected: PASS

- [x] **Step 3: Run the focused verification bundle**

Run:

`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Workflows/adapters/test_media_adapters.py /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/RAG_NEW/unit/test_unified_pipeline_focused.py -k 'not soft_delete_keyword_accepts_partial_legacy_like_db'`

Expected: PASS

- [x] **Step 4: Run Bandit and diff hygiene**

Run:

`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/media_db /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/DB_Manager.py -f json -o /tmp/bandit_media_db_hard_delete.json`

Then:

`git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor diff --check`

Expected: Bandit reports no new findings; `git diff --check` prints nothing.

- [ ] **Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor rm \
  tldw_Server_API/app/core/DB_Management/Media_DB_v2.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor add \
  tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py \
  tldw_Server_API/tests/Workflows/adapters/test_media_adapters.py \
  tldw_Server_API/tests/RAG_NEW/unit/test_unified_pipeline_focused.py \
  Docs/Database_Migrations.md \
  Docs/Code_Documentation \
  Docs/Plans/2026-03-23-media-db-v2-compat-breaking-delete-implementation-plan.md
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor commit -m "refactor: delete media db legacy compat module"
```
