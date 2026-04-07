# Media DB V2 Compat-Breaking Delete Design

**Status:** Proposed and approved in-session on 2026-03-23.

**Goal:** Delete `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
entirely, migrate the remaining active tests and active code documentation off
the legacy module path, and make the package-native media DB surfaces the only
supported import boundary.

## Why This Tranche Exists

The removal-ready tranche finished the structural de-monolithing:

- the canonical `MediaDatabase` class is native-owned
- package-internal runtime imports of `Media_DB_v2` are gone
- `Media_DB_v2.py` is already only a 40-line compatibility shim

That still leaves one explicit compatibility promise in the repo: the module
file exists and active tests can still import or patch through it.

The user has now chosen the compat-breaking step. That changes the target from
"removal-ready" to "deleted."

## Current Ground Truth

There are no remaining production runtime dependencies on `Media_DB_v2.py`.
The live delete blockers are now limited to active tests and active code docs.

### Remaining active test blockers

The current tree still has active tests that reference the legacy Python module
path directly:

- `tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py`
- `tldw_Server_API/tests/Workflows/adapters/test_media_adapters.py`
- `tldw_Server_API/tests/RAG_NEW/unit/test_unified_pipeline_focused.py`
- `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

The first three are ordinary active tests that patch or guard the old path.
The last two are compatibility-boundary suites that were intentionally added to
protect the tiny shim. Those tests must now be rewritten to protect deletion
instead.

### Remaining active documentation blockers

Current code/developer docs still describe `Media_DB_v2.py` as a live module.
The active-doc scope for this tranche is:

- `Docs/Database_Migrations.md`
- `Docs/Code_Documentation/Database.md`
- `Docs/Code_Documentation/index.md`
- `Docs/Code_Documentation/Code_Map.md`
- `Docs/Code_Documentation/Email_Search_Architecture.md`
- `Docs/Code_Documentation/Pieces.md`
- `Docs/Code_Documentation/Claims_Extraction.md`
- `Docs/Code_Documentation/Ingestion_Media_Processing.md`
- `Docs/Code_Documentation/RAG-Developer-Guide.md`
- `Docs/Code_Documentation/Chunking_Templates_Developer_Guide.md`
- `Docs/Code_Documentation/Databases/Media_DB_v2.md`

These docs can keep `Media_DB_v2.db` filename references where they describe
SQLite file locations. What must go away is live guidance that points users to
the deleted Python module path.

### Explicitly out of scope

The following are not delete blockers for this tranche:

- historical plans under `Docs/Plans/`
- design and PRD history under `Docs/Design/` and `Docs/Product/`
- completed product artifacts under `Docs/Product/Completed/`
- SQLite database filename references such as `Media_DB_v2.db`

Those can remain as historical or storage-layout references without preserving
the Python import compatibility surface.

## Design Principles

### 1. Delete the module, not the runtime behavior

This tranche should remove the legacy import path, not reopen media DB logic.
No database behavior, schema behavior, or helper ownership should change.

### 2. Replace shim tests with deletion-boundary tests

The existing compatibility regression suite currently proves that the tiny shim
re-exports approved symbols. That is the wrong contract after the breaking
change. The new contract is:

- `Media_DB_v2.py` does not exist
- active tests no longer import or patch through it
- package-native exports still resolve and behave correctly

### 3. Keep doc cleanup targeted to active guidance

This is not a repo-wide prose rewrite. The doc work should update current code
documentation so it no longer teaches a deleted module path. Historical PRDs
and plans remain unchanged.

## Architecture

### A. Replace the legacy compat boundary tests

`test_media_db_api_imports.py` and `test_media_db_v2_regressions.py` currently
assume the file exists. They should be converted to a delete-boundary suite
that asserts:

- the file path is absent
- no active tests import or patch `Media_DB_v2`
- native exports still resolve through `media_db.native_class` and
  `media_db.media_database`

The filename `test_media_db_v2_regressions.py` may be retained or renamed; the
important change is that it must no longer import the deleted module.

### B. Migrate the remaining active monkeypatch sites

The three active test slices should move to package-native patch points:

- native `MediaDatabase` class path when the test is exercising a class method
- package-native runtime helper seam when that is what the subject module uses
- remove obsolete defensive patches if the subject already routes only through
  `managed_media_database(...)`

This work is mechanical but must use the actual import seam of the subject
module rather than a guessed replacement string.

### C. Update active code documentation to the native boundary

Current code docs should refer to:

- `tldw_Server_API.app.core.DB_Management.media_db.native_class.MediaDatabase`
- `tldw_Server_API.app.core.DB_Management.media_db.media_database`
- package-native schema/runtime helpers where relevant

The documentation file
`Docs/Code_Documentation/Databases/Media_DB_v2.md` may keep its path for now,
but its content should stop describing `Media_DB_v2.py` as the live library.

### D. Delete the file only after the red scans are green

Once the active tests and active docs are migrated, delete:

- `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

There should be no fallback shim in this tranche. This is the deliberate
breaking step.

## Success Criteria

This tranche is successful when:

- `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py` is deleted
- active test code no longer imports or patches `Media_DB_v2`
- active code documentation no longer points at `Media_DB_v2.py` as a live
  module
- package-native `MediaDatabase` exports remain stable
- the focused verification bundle is green

## Recommendation

Implement this as a short compat-breaking cleanup tranche with four stages:

1. rewrite the boundary tests for deletion
2. migrate the remaining active monkeypatch/import tests
3. migrate the active code docs
4. delete the file and run final verification

That keeps the change surgical while still making the old module path truly
unsupported.
