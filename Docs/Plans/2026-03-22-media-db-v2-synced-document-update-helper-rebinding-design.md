# Media DB V2 Synced Document Update Helper Rebinding Design

## Summary

After the data-table content-replace tranche, the normalized legacy ownership
count is `19`. The cleanest remaining non-bootstrap singleton is
`apply_synced_document_content_update(...)`.

This method is a real coordinator, but its boundary is still narrow enough for
an isolated ownership-reduction slice. It updates the active `Media` row,
creates a new `DocumentVersion`, logs the media sync event, refreshes media
FTS, then runs best-effort highlight/vector invalidation after commit. The
existing file-sync and ingestion caller surface is already strong enough to
support a focused rebinding tranche.

## Current Method Shape

`apply_synced_document_content_update(...)` currently owns:

- required-content validation
- active-media lookup and conflict detection
- content-hash calculation and media-row update
- `create_document_version(...)` coordination
- sync-payload enrichment with created document-version metadata
- `_log_sync_event(...)` and `_update_fts_media(...)` calls inside the main
  transaction
- post-commit best-effort highlight staleness notification
- post-commit intra-document vector invalidation
- wrapped exception behavior for input/conflict/database/unexpected failures

## Why This Slice Is Safe

The coordinator is active but bounded:

- it has a small public signature
- its transactional seams are already package-owned
  (`create_document_version(...)`, `_log_sync_event(...)`, `_update_fts_media(...)`)
- it already has real caller-facing coverage in sync and ingestion paths

That makes it a safer next move than the broader remaining surfaces:

- `rollback_to_version(...)`
- `search_by_safe_metadata(...)`
- bootstrap / postgres initialization coordinators
- `initialize_db(...)`

## Risks To Pin

### 1. Transaction ordering must stay intact

The method currently:

1. loads the current media row
2. updates `Media`
3. creates a new `DocumentVersion`
4. enriches the sync payload with created document-version identifiers
5. logs the media sync event
6. refreshes media FTS

That order matters. The helper tests need to pin the internal call sequence so
we do not accidentally move FTS or sync logging ahead of version creation.

### 2. Conflict and not-found behavior must not drift

The method currently raises:

- `InputError("Content is required for synced document updates.")`
- `InputError(f"Media {media_id} not found or deleted.")`
- `ConflictError("Media", media_id)` when the optimistic update rowcount is `0`

Those are important public semantics for sync callers and should be covered
directly.

### 3. Post-commit hooks must remain best-effort

The method intentionally treats highlight re-anchoring and intra-document vector
invalidation as noncritical:

- the main transaction has already committed
- failures in those hooks only log at debug level
- the main result still returns success

That behavior is easy to break if the helper collapses those hooks into the
transaction path or starts re-raising hook failures.

### 4. The collections integration must move off legacy globals

The legacy body currently depends on `_CollectionsDB` loaded from
`Media_DB_v2.py`. Rebinding must move that optional integration onto the
package-owned runtime layer, ideally through the existing runtime loader in
`media_db/runtime/collections.py`, so canonical ownership actually leaves the
legacy module.

## Recommended Tranche

Move only:

- `apply_synced_document_content_update(...)`

Defer:

- `rollback_to_version(...)`
- `search_by_safe_metadata(...)`
- `initialize_db(...)`
- `_initialize_schema*` / postgres bootstrap coordinators

## Design

Add one package-owned runtime module:

- `tldw_Server_API/app/core/DB_Management/media_db/runtime/synced_document_update_ops.py`

It should expose:

- `apply_synced_document_content_update(...)`

Implementation notes:

- use `MEDIA_NONCRITICAL_EXCEPTIONS` from
  `media_db/runtime/noncritical.py`
- use `load_collections_database_cls()` from
  `media_db/runtime/collections.py`
- keep post-commit hooks outside the main transaction
- preserve the current exception envelope and return payload

Then:

- rebind canonical `MediaDatabase.apply_synced_document_content_update` in
  [media_database_impl.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py)
- convert the legacy method in
  [Media_DB_v2.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
  into a live-module compat shell

## Test Strategy

### Direct regressions

Add ownership/delegation regressions in
[test_media_db_v2_regressions.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py)
for:

- canonical `MediaDatabase.apply_synced_document_content_update(...)` no longer
  using legacy globals
- legacy `Media_DB_v2.apply_synced_document_content_update(...)` delegating
  through `synced_document_update_ops.py`

### Focused helper coverage

Add:

- `tldw_Server_API/tests/DB_Management/test_media_db_synced_document_update_ops.py`

Pin:

- canonical helper rebinding
- missing-content rejection
- not-found rejection
- optimistic conflict rejection
- successful transactional ordering and return payload
- best-effort collection/vector hook behavior after commit

### Broader caller-facing guards

Reuse existing caller coverage:

- [test_sync_coordinator.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/External_Sources/test_sync_coordinator.py)
- [test_media_sink.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Ingestion_Sources/test_media_sink.py)
- [test_connectors_worker_file_sync.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/External_Sources/test_connectors_worker_file_sync.py)

## Success Criteria

- canonical ownership for `apply_synced_document_content_update(...)` moves off
  legacy globals
- legacy method remains a live-module compat shell
- helper-path tests pass for validation, transaction ordering, and noncritical
  hook suppression
- caller-facing sync/ingestion guards stay green
- normalized ownership count drops `19 -> 18`
