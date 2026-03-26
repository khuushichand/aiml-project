# Media DB V2 Bundled Read-Helper Migration Design

**Status:** Proposed, reviewed, and approved on 2026-03-19.

**Goal:** Reduce the remaining production compat surface for the current read-helper cluster by moving `navigation`, `quiz_source_resolver`, `data_tables.jobs_worker`, and `media_module` onto package-native `media_db.api` facades, while preserving existing monkeypatch seams and avoiding class-chain/runtime work.

## Why This Tranche Exists

The previous production compat-reduction tranche moved these user-facing media
endpoints onto `media_db.api`:

- `media/item.py`
- `media/listing.py`
- `media/versions.py`
- `media/document_insights.py`
- `media/document_references.py`

That removed a meaningful slice of direct `legacy_*` usage, but production code
still imports `legacy_reads`, `legacy_wrappers`, and one `legacy_maintenance`
path in a remaining cluster of callers:

- `app/api/v1/endpoints/media/navigation.py`
- `app/services/quiz_source_resolver.py`
- `app/core/Data_Tables/jobs_worker.py`
- `app/core/MCP_unified/modules/implementations/media_module.py`

Those modules are a natural next slice because they all depend on the same small
family of helper functions:

- `get_document_version`
- `get_latest_transcription`
- `get_media_transcripts`
- optionally `permanently_delete_item` in `media_module`

## Review Corrections Incorporated

### 1. Keep the new transcript facade narrow

`legacy_reads.get_media_transcripts()` currently supports only:

- `db_instance`
- `media_id`

The live callers only need that narrow shape. This tranche must not invent a
broader API with optional pagination or metadata flags that the current
implementation does not support. The package-native facade should be a direct,
thin delegate.

### 2. Preserve module-local helper patchpoints

Existing tests patch helper names directly on the caller modules, for example:

- `navigation_mod.get_document_version`
- `jobs_worker.get_document_version`
- `jobs_worker.get_latest_transcription`
- `resolver_mod.get_latest_transcription`
- `media_module_impl.get_document_version`
- `media_module_impl.get_latest_transcription`
- `media_module_impl.permanently_delete_item`

So the migration must continue to import helper symbols into each module’s local
namespace from `media_db.api`. It must **not** replace those call sites with
qualified lookups like `media_db_api.get_document_version(...)`, because that
would remove useful test seams and create unnecessary churn.

### 3. Keep `media/__init__.py` out of scope

`app/api/v1/endpoints/media/__init__.py` still intentionally re-exports
`get_document_version` from `legacy_wrappers`. That is package-level compat
surface, not part of this caller tranche. New boundary guards must exclude it.

### 4. Treat `media_module` delete wiring as a scoped add-on

`media_module.py` still imports `permanently_delete_item` from
`legacy_maintenance`. That import can move in this tranche because
`media_db.api` already exposes a delete facade, but only if the MCP delete-path
tests are included in verification. This must remain an explicit step, not an
incidental side effect of the read-helper migration.

### 5. Keep runtime/class-chain work out of scope

This tranche does not change:

- `MediaDatabase` class ownership
- runtime loader resolution
- `Media_DB_v2.py` compat shell behavior
- `DB_Manager.py` beyond already completed slices

It is strictly about reducing remaining production caller imports.

## Scope

### In scope

- Add a narrow package-native `get_media_transcripts(db, media_id)` facade to
  `media_db.api`
- Migrate these production callers to import helper symbols from `media_db.api`:
  - `app/api/v1/endpoints/media/navigation.py`
  - `app/services/quiz_source_resolver.py`
  - `app/core/Data_Tables/jobs_worker.py`
  - `app/core/MCP_unified/modules/implementations/media_module.py`
- Move `media_module.py` from `legacy_maintenance.permanently_delete_item` to
  `media_db.api.permanently_delete_item`
- Add tranche-scoped source guards
- Update existing compat-import tests to assert these modules now bind to
  `media_db.api`

### Out of scope

- `app/api/v1/endpoints/media/__init__.py`
- `chatbook_service` and other remaining `legacy_reads` users outside this slice
- broader read-contract redesign for `navigation`
- deletion of `legacy_reads.py`, `legacy_wrappers.py`, or `legacy_maintenance.py`
- class-chain severing and runtime loader changes

## Architecture

### A. `media_db.api` remains the only new package boundary

The safest path is the same pattern used in the prior tranche:

- keep extracted compat helper implementations in place
- expose one caller-facing package surface in `media_db.api`
- migrate production imports to that surface

This reduces caller debt without forcing implementation rewrites.

### B. The migration is import-level plus stale call-shape cleanup

The actual caller logic should stay intact. The expected production changes are:

- replace imports from `legacy_reads`, `legacy_wrappers`, and
  `legacy_maintenance` with imports from `media_db.api`
- fix stale `db_instance=` keyword usage where the new API uses positional `db`
- preserve current branching, error handling, and response formatting

### C. Tests should verify bindings as well as behavior

This cluster is unusually patch-heavy. The important test questions are:

1. do the selected modules still import compat helpers directly?
2. after reload, do their helper names bind to `media_db.api`?
3. do the existing behavior tests still pass without changing the caller logic?

That gives confidence the seam moved without widening behavior.

## Migration Order

### 1. Add the narrow transcript facade and its direct API tests

Start with `media_db.api.get_media_transcripts(db, media_id)` and confirm it
delegates to the existing extracted read helper.

### 2. Migrate the lowest-risk callers first

Move:

- `quiz_source_resolver.py`
- `core/Data_Tables/jobs_worker.py`

These are small helper consumers and validate the facade shape quickly.

### 3. Migrate `navigation.py`

`navigation.py` uses all three read helpers and contains a local DB protocol,
making it the riskiest read-only caller in the slice.

### 4. Migrate `media_module.py`

Move the read helpers first, then move `permanently_delete_item` in the same
task only because:

- the facade already exists
- the module already has delete-path coverage
- it removes the last compat helper import in that file

### 5. Tighten guards and compat-import tests

Update:

- source guards
- reload/binding assertions
- caller-focused behavior tests

## Testing Strategy

### Boundary tests

Extend `tests/DB_Management/test_media_db_api_imports.py` so it fails when the
selected modules still import:

- `media_db.legacy_reads`
- `media_db.legacy_wrappers`
- `media_db.legacy_maintenance` for `media_module.py`

### Compat-import tests

Update:

- `tests/DB_Management/test_media_db_legacy_reads_imports.py`
- `tests/DB_Management/test_media_db_legacy_document_version_imports.py`

so the selected modules now assert bindings to `media_db.api`.

### Behavior tests

Reuse existing focused tests for:

- navigation content and outline behavior
- quiz source resolution
- Data Tables text extraction
- MCP media retrieval and delete gating

## Success Criteria

- `navigation.py`, `quiz_source_resolver.py`, `jobs_worker.py`, and
  `media_module.py` no longer import `legacy_reads` or `legacy_wrappers`
- `media_module.py` no longer imports `legacy_maintenance`
- `media_db.api` exports `get_media_transcripts`
- selected module helper names bind to `media_db.api` after reload
- focused navigation, quiz, Data Tables, and MCP media tests pass
- no broader compat surfaces are pulled into this tranche
