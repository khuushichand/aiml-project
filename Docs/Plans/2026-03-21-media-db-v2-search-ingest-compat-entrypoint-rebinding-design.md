# Media DB V2 Search And Ingest Compat Entrypoint Rebinding Design

## Summary

Rebind the two remaining pure compat entrypoints
`search_media_db(...)` and `add_media_with_keywords(...)` onto a package-owned
runtime helper so the canonical `MediaDatabase` no longer owns them through
legacy globals. Preserve the exact package seams they already use today:
`search_media_db(...)` must keep calling the package read API, and
`add_media_with_keywords(...)` must keep calling the repository layer.

## Scope

In scope:
- `search_media_db(...)`
- `add_media_with_keywords(...)`
- direct ownership and compat-shell delegation regressions
- focused helper-path tests for:
  - `search_media_db(...)` forwarding its full kwargs surface to the package
    API helper
  - `add_media_with_keywords(...)` forwarding its full kwargs surface to the
    repository helper
- reuse of broader caller-facing guards for search and media ingest

Out of scope:
- `search_by_safe_metadata(...)`
- `replace_data_table_contents(...)`
- `media_db/api.py`
- `media_db/runtime/validation.py`
- claims, email, bootstrap/schema, and broader read-query extraction work

## Why This Slice

This is the cleanest remaining low-risk count-reduction move because both
methods are already pure shims:
- [search_media_db(...)](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/Media_DB_v2.py#L9897)
  already delegates to
  [media_db.api.search_media(...)](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/media_db/api.py#L293)
- [add_media_with_keywords(...)](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/Media_DB_v2.py#L10507)
  already delegates to
  [MediaRepository.add_media_with_keywords(...)](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/media_db/repositories/media_repository.py#L48)

By contrast,
[search_by_safe_metadata(...)](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/Media_DB_v2.py#L10010)
still owns real SQL/query assembly, so bundling it here would turn a cheap
compat-shell tranche into a read-logic extraction.

## Existing Risks To Preserve

### 1. `search_media_db(...)` must keep the package API seam

The canonical method is not allowed to bypass
`media_db.api.search_media(...)` and call the repository directly. Existing
coverage in
[test_read_contract_sqlite.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/MediaDB2/test_read_contract_sqlite.py#L61)
already pins the exact delegated kwargs payload. This tranche must preserve
that shape.

### 2. `add_media_with_keywords(...)` must stay a repository-backed compat call

The method has a large kwargs surface and is used broadly across ingestion,
sync, services, claims, and RAG callers. The runtime helper must continue to
delegate through `MediaRepository.from_legacy_db(db).add_media_with_keywords(...)`
rather than trying to inline or reinterpret ingestion logic.

### 3. Lightweight read-like and writer-like callers stay untouched

This tranche must not widen into `media_db/api.py` or
`media_db/runtime/validation.py`. The package API currently accepts:
- read-like doubles exposing `search_media_db(...)`
- writer-like doubles exposing `add_media_with_keywords(...)`

Those contracts are already used by caller-facing tests and should remain
unchanged.

### 4. `add_media_with_keywords(...)` must preserve overwrite/sharing behavior

Existing regression coverage in
[test_media_db_v2_regressions.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py#L2346)
proves that overwrite updates preserve sharing state. This tranche must not
disturb that behavior while moving canonical ownership off legacy globals.

## Test Strategy

### Ownership / compat-shell regressions

Add direct regressions in
`tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py` for:
- canonical `search_media_db(...)` rebound off legacy globals
- canonical `add_media_with_keywords(...)` rebound off legacy globals
- legacy `Media_DB_v2.search_media_db(...)` delegating through a live
  `import_module(...)` reference
- legacy `Media_DB_v2.add_media_with_keywords(...)` delegating through a live
  `import_module(...)` reference

The `add_media_with_keywords(...)` delegation regression should derive expected
forwarded kwargs from the method signature rather than pinning only a partial
subset.

### Focused helper-path tests

Add a new helper test file for the runtime module covering:
- `run_search_media_db(...)` forwarding the full search kwargs set to
  `media_db.api.search_media(...)`
- `run_add_media_with_keywords(...)` forwarding the full kwargs set to
  `MediaRepository.from_legacy_db(db).add_media_with_keywords(...)`

### Broader caller-facing guards

Retain and reuse:
- [test_read_contract_sqlite.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/MediaDB2/test_read_contract_sqlite.py)
- [test_sync_server.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/MediaDB2/test_sync_server.py)
- [test_media_db_v2_regressions.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py)
- [test_connectors_worker.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Services/test_connectors_worker.py)
- [test_document_processing_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Services/test_document_processing_service.py)
- [test_outputs_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Services/test_outputs_service.py)

The three service tests are secondary caller-compat guards, not the primary
proof of canonical rebinding.

## Implementation Shape

Add one small package runtime module, likely:
- `tldw_Server_API/app/core/DB_Management/media_db/runtime/media_entrypoint_ops.py`

It should expose:
- `run_search_media_db(...)`
- `run_add_media_with_keywords(...)`

Behavior requirements:
- `run_search_media_db(...)` must call `media_db.api.search_media(...)`
- `run_add_media_with_keywords(...)` must call
  `MediaRepository.from_legacy_db(db).add_media_with_keywords(...)`

Then:
- rebind the canonical methods in `media_database_impl.py`
- convert the legacy methods in `Media_DB_v2.py` into live-module compat shells

Do not modify `media_db/api.py` or `media_db/runtime/validation.py` in this
slice.

## Success Criteria

- canonical ownership for `search_media_db(...)` moves off legacy globals
- canonical ownership for `add_media_with_keywords(...)` moves off legacy
  globals
- both legacy methods remain present as live-module compat shells
- focused helper-path tests pass
- broader caller-facing guards stay green
- normalized ownership count drops from `116` to `114`
