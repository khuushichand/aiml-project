# Media DB V2 Mixed Caller Facade Migration Design

**Status:** Proposed, reviewed, and approved on 2026-03-20.

**Goal:** Reduce the next layer of non-compat production Media DB helper imports by moving a mixed cluster of read callers, lazy-import callers, and one write-adjacent caller onto `media_db.api`, while preserving lazy import behavior, module-local patchpoints, and existing update semantics.

## Why This Tranche Exists

The previous bundled read-helper migration removed direct compat-helper imports
from:

- `app/api/v1/endpoints/media/navigation.py`
- `app/services/quiz_source_resolver.py`
- `app/core/Data_Tables/jobs_worker.py`
- `app/core/MCP_unified/modules/implementations/media_module.py`

That left a smaller but still meaningful set of non-compat production callers:

- `app/api/v1/endpoints/slides.py`
- `app/core/Chatbooks/chatbook_service.py`
- `app/core/Embeddings/services/jobs_worker.py`
- `app/api/v1/endpoints/items.py`
- `app/api/v1/endpoints/outputs_templates.py`
- `app/api/v1/endpoints/media_embeddings.py`
- `app/core/Ingestion_Media_Processing/Media_Update_lib.py`

These callers are still pointed at extracted `legacy_*` modules for one of four
reasons:

1. direct module-scope read helper imports
2. lazy imports inside functions
3. optional-import blocks for stripped deployments
4. local alias names in write-adjacent code

This tranche should remove those direct compat imports without changing import
timing, patch seams, or runtime class ownership.

## Review Corrections Incorporated

### 1. Add exactly one new facade first

`chatbook_service.py` cannot migrate cleanly until `media_db.api` exports
`get_media_prompts(db, media_id)`. That is the only missing package-native
facade needed for this slice. The tranche should add and test that helper
before touching any production caller.

### 2. Lazy imports must remain lazy

These files currently import compat helpers inside functions:

- `app/core/Embeddings/services/jobs_worker.py`
- `app/api/v1/endpoints/items.py`
- `app/api/v1/endpoints/outputs_templates.py`
- `app/api/v1/endpoints/media_embeddings.py`

The tranche must keep those imports inside the same lazy call sites and only
change the import source from `legacy_*` to `media_db.api`. Promoting them to
module scope would change import-time behavior and widen the risk surface.

### 3. `Media_Update_lib.py` should keep local alias names

`Media_Update_lib.py` uses `_check_media_exists` and `_get_document_version`
aliases and has dedicated binding and regression coverage. The safe migration is
to keep those alias names and only change their source to `media_db.api`.

### 4. Existing compat-binding tests should stay authoritative

This tranche does not need new test architecture. It should extend the existing
binding and source-guard tests:

- `tests/DB_Management/test_media_db_api_imports.py`
- `tests/DB_Management/test_media_db_legacy_reads_imports.py`
- `tests/DB_Management/test_media_db_legacy_document_version_imports.py`
- `tests/DB_Management/test_media_db_legacy_content_query_imports.py`
- `tests/DB_Management/test_media_db_media_update_imports.py`

The behavior checks should remain focused and caller-specific.

## Scope

### In scope

- Add `media_db.api.get_media_prompts(db, media_id)` as a thin delegate.
- Migrate direct module-scope caller imports in:
  - `app/api/v1/endpoints/slides.py`
  - `app/core/Chatbooks/chatbook_service.py`
- Migrate lazy-import caller sites, preserving their laziness, in:
  - `app/core/Embeddings/services/jobs_worker.py`
  - `app/api/v1/endpoints/items.py`
  - `app/api/v1/endpoints/outputs_templates.py`
  - `app/api/v1/endpoints/media_embeddings.py`
- Migrate `app/core/Ingestion_Media_Processing/Media_Update_lib.py` by keeping
  `_check_media_exists` / `_get_document_version` and rebinding them to
  `media_db.api`.
- Add tranche-scoped source guards and update compat-binding assertions.

### Out of scope

- `app/api/v1/endpoints/media/__init__.py`
- `app/core/DB_Management/DB_Manager.py`
- `app/core/DB_Management/Media_DB_v2.py`
- runtime/class-chain changes
- repository rewrites or behavior redesign in chatbooks/slides/media update
- deletion of any `legacy_*` module

## Architecture

### A. `media_db.api` remains the only caller-facing package seam

This tranche should continue the established pattern:

- keep extracted helper implementations in place
- expose package-native facades in `media_db.api`
- migrate callers to import from that package seam

That preserves behavior while reducing production dependence on compat modules.

### B. Use the lightest migration shape per caller

There are three caller shapes in this tranche:

1. module-scope imports
2. lazy imports inside functions
3. local aliases

Each file should keep its current shape and only change the helper source:

- `slides.py` and `chatbook_service.py`: module-scope or optional-block imports
- `items.py`, `outputs_templates.py`, `media_embeddings.py`, embeddings
  `jobs_worker.py`: lazy imports stay lazy
- `Media_Update_lib.py`: `_check_media_exists` and `_get_document_version`
  remain local aliases

### C. The new `get_media_prompts` facade should stay thin

`get_media_prompts` should behave like the existing transcript and keyword
facades: thin delegation only, no new pagination/filter parameters, and no new
repository abstraction in this tranche.

## Migration Order

### 1. Add `get_media_prompts` to `media_db.api`

Start with the only missing facade and its direct API tests.

### 2. Migrate direct read callers

Move:

- `slides.py`
- `chatbook_service.py`

These are the clearest direct read-helper consumers once the prompt facade
exists.

### 3. Migrate lazy-import fallback callers

Move:

- embeddings `jobs_worker.py`
- `items.py`
- `outputs_templates.py`
- `media_embeddings.py`

These callers mainly use fallback document-version and keyword helpers. The
important thing is to keep their imports lazy.

### 4. Migrate the write-adjacent alias caller

Move `Media_Update_lib.py` last in this tranche. It is still a small change, but
it touches update behavior and should remain isolated from the broader read
caller migration.

### 5. Tighten guards and compat-binding tests

Update source guards and binding assertions so this cluster becomes part of the
enforced boundary.

## Testing Strategy

### Boundary tests

Extend `tests/DB_Management/test_media_db_api_imports.py` so it fails when the
selected callers still import:

- `media_db.legacy_reads`
- `media_db.legacy_wrappers`
- `media_db.legacy_content_queries`
- `media_db.legacy_state`

only for the exact tranche paths.

### Compat-binding tests

Update:

- `tests/DB_Management/test_media_db_legacy_reads_imports.py`
- `tests/DB_Management/test_media_db_legacy_document_version_imports.py`
- `tests/DB_Management/test_media_db_legacy_content_query_imports.py`
- `tests/DB_Management/test_media_db_media_update_imports.py`

so the selected callers now assert bindings to `media_db.api`.

### Behavior tests

Reuse focused tests for:

- slides transcript-source paths
- chatbook media export/import paths that use prompts/transcripts
- embeddings worker fallback content loading
- items/output template metadata/tag enrichment
- media embeddings document-version fallback
- `Media_Update_lib.py` regression coverage in
  `test_media_db_v2_regressions.py`

## Success Criteria

- `media_db.api` exports `get_media_prompts`
- `slides.py`, `chatbook_service.py`, embeddings `jobs_worker.py`, `items.py`,
  `outputs_templates.py`, `media_embeddings.py`, and `Media_Update_lib.py` no
  longer import compat helpers directly
- lazy-import callers remain lazy
- `Media_Update_lib.py` keeps `_check_media_exists` /
  `_get_document_version` aliases
- compat-binding and source-guard tests pass for the tranche
- focused behavior tests still pass without caller-behavior rewrites
