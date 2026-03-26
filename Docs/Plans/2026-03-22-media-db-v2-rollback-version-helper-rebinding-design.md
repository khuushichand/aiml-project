# Media DB V2 Rollback Version Helper Rebinding Design

**Date:** 2026-03-22
**Status:** Proposed
**Target Area:** `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
**Target Ownership Count:** `1 -> 0`

## Objective

Move the final remaining legacy-owned canonical method off
`Media_DB_v2.py`:

- `rollback_to_version(...)`

This finishes the caller-first ownership reduction run for canonical
`MediaDatabase` methods by removing the last remaining method whose globals are
still owned by the legacy module.

## Why This Slice

After the bootstrap lifecycle tranche, the only legacy-owned canonical method
left is:

- `rollback_to_version(...)`

Unlike the previous helper slices, this is an active high-blast-radius mutation
coordinator. It is still called through:

- the media versions API endpoint
- `DB_Manager.rollback_to_version(...)`
- the document-version/rollback test surface in
  `test_media_processing.py`

That means this final cut must preserve behavior exactly. The right scope is
therefore the single method only, with no adjacent read/write refactors.

## Current State

`rollback_to_version(...)` currently owns a full rollback transaction:

1. validate `target_version_number`
2. read the current `Media` row
3. resolve the rollback target document version via `get_document_version(...)`
4. reject rollback to the current latest version number
5. create a new `DocumentVersion` that captures the rolled-back state
6. update the main `Media` row content/hash/version
7. emit the media sync-log update payload with rollback context
8. refresh media FTS
9. run best-effort post-transaction hooks:
   - stale highlight marking through collections DB
   - intra-doc vector invalidation
10. return the legacy dict contract

It also has mixed error behavior:

- invalid target number -> `ValueError`
- semantic failures like not found/latest/no content -> `{"error": ...}`
- DB conflicts/input errors -> re-raised
- raw SQLite errors -> wrapped to `DatabaseError`

## Proposed Design

Add one package-owned runtime module:

- `tldw_Server_API/app/core/DB_Management/media_db/runtime/document_version_rollback_ops.py`

It should own:

- `rollback_to_version(...)`

Then:

1. rebind canonical `MediaDatabase.rollback_to_version` in
   `media_db/media_database_impl.py`
2. convert the legacy method in `Media_DB_v2.py` into a live-module compat
   shell using `import_module(...)`

No changes should be made to:

- `app/api/v1/endpoints/media/versions.py`
- `app/core/DB_Management/DB_Manager.py`
- document-version repository helpers

## Invariants To Preserve

`rollback_to_version(...)` must preserve:

1. `ValueError` for non-positive or non-int version input
2. `{"error": ...}` returns for:
   - missing/deleted media
   - missing rollback target version
   - rollback target equal to latest version
   - target version with no content
3. creation of a *new* document version rather than mutating an old one
4. media update with:
   - rolled-back content
   - fresh content hash
   - incremented media sync version
   - `chunking_status='pending'`
   - `vector_processing=0`
5. media sync-log payload enrichment with:
   - `rolled_back_to_doc_ver_uuid`
   - `rolled_back_to_doc_ver_num`
6. media FTS refresh using the existing title and rolled-back content
7. best-effort post-transaction hooks:
   - collections stale-highlight marking
   - intra-doc vector invalidation
8. error taxonomy:
   - `InputError`, `ValueError`, `ConflictError`, `DatabaseError`, `TypeError`
     still re-raise
   - raw SQLite errors still wrap into `DatabaseError`
   - other noncritical exceptions still wrap into `DatabaseError`
9. success return contract:
   - `success`
   - `new_document_version_number`
   - `new_document_version_uuid`
   - `new_media_version`

## Test Strategy

### New focused tests

Add:

- `tldw_Server_API/tests/DB_Management/test_media_db_document_version_rollback_ops.py`

Pin:

1. canonical rebinding to the package runtime module
2. semantic error returns for:
   - missing rollback target
   - rollback to latest version
3. success payload and media sync payload enrichment
4. post-transaction hook failures remain warning-only/non-blocking

### Ownership/delegation regressions

Extend:

- `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

Pin:

1. canonical `rollback_to_version(...)` no longer resolves globals from
   `Media_DB_v2`
2. legacy compat shell delegates through the runtime helper module

### Broader guards

Reuse existing caller-facing coverage in:

- `tldw_Server_API/tests/Media_Ingestion_Modification/test_media_processing.py`
- `tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py`

## Risks

### Risk 1: Dict contract drift

The API endpoint inspects the returned dict for `"error"` and maps messages to
HTTP status codes. Accidentally switching to pure exceptions would be a real
breaking change.

Mitigation:

- focused helper tests for semantic error returns
- broader API-adjacent guards stay green through existing callers

### Risk 2: Post-rollback side-effect drift

The collections stale-highlight hook and intra-doc vector invalidation are
best-effort follow-up behavior, not transaction blockers.

Mitigation:

- focused helper test proving hook failures do not fail rollback

### Risk 3: Error taxonomy drift

The current method intentionally mixes returned errors and raised exceptions.
Changing that balance would ripple into wrappers and callers.

Mitigation:

- preserve the exact try/except boundaries and add focused negative-path tests

## Success Criteria

1. Canonical ownership for `rollback_to_version(...)` moves into
   `runtime/document_version_rollback_ops.py`
2. The legacy method becomes a compat shell only
3. Focused helper tests and ownership regressions pass
4. Existing rollback callers remain green
5. Normalized ownership count drops from `1` to `0`
