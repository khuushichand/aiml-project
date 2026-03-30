# Media DB V2 Media Files Helper Rebinding Design

## Summary

Rebind the repository-backed MediaFiles CRUD wrapper cluster onto
package-owned runtime helpers so the canonical `MediaDatabase` no longer owns
`insert_media_file`, `get_media_file`, `get_media_files`,
`has_original_file`, `soft_delete_media_file`, or
`soft_delete_media_files_for_media` through legacy globals, while preserving
`Media_DB_v2` as a live-module compatibility shell.

## Scope

In scope:

- Add one package runtime helper module for:
  - `insert_media_file(...)`
  - `get_media_file(...)`
  - `get_media_files(...)`
  - `has_original_file(...)`
  - `soft_delete_media_file(...)`
  - `soft_delete_media_files_for_media(...)`
- Rebind canonical `MediaDatabase` methods for those six helpers
- Convert legacy `Media_DB_v2` methods into live-module compat shells
- Add direct ownership/delegation regressions
- Add focused helper-path tests asserting the new runtime helpers forward into
  `MediaFilesRepository.from_legacy_db(...)` with the expected arguments
- Reuse the existing MediaFiles behavior tests as the broader behavioral guard

Out of scope:

- Rebinding the VisualDocuments helper trio
- Changing `MediaFilesRepository` behavior or SQL
- Changing media-details service logic
- Rebinding `_get_db_version(...)`, schema/bootstrap helpers, or domain
  surfaces such as claims, email, or data tables

## Why This Slice

This is the highest-leverage low-risk cluster left near the remaining storage
helpers. The canonical methods are already thin repository delegates with
substantial existing test coverage, so moving them to package-owned runtime
helpers reduces legacy ownership without introducing a new behavior surface.

## Risks

Low. The main invariants are:

- canonical methods must stop resolving through `Media_DB_v2`
- legacy `Media_DB_v2` methods must remain present and delegate through a live
  module reference
- wrapper methods must preserve their current forwarding contract into
  `MediaFilesRepository.from_legacy_db(...)`
- existing MediaFiles CRUD, soft-delete, and sync-log behavior must remain
  unchanged

## Test Strategy

Add:

1. canonical ownership regressions for all six methods
2. legacy compat-shell delegation regressions for all six methods
3. focused helper-path tests in `test_media_files.py` for:
   - insert forwarding
   - get/list forwarding
   - `has_original_file(...)` forwarding
   - soft-delete forwarding
4. reuse existing broader guards in:
   - `tldw_Server_API/tests/MediaDB2/test_media_files.py`
   - `tldw_Server_API/tests/Media/test_document_outline.py`
   - `tldw_Server_API/tests/Media/test_media_navigation.py`

## Success Criteria

- canonical MediaFiles wrapper methods are package-owned
- legacy `Media_DB_v2` methods remain live-module compat shells
- focused helper-path tests pass
- existing MediaFiles behavior tests stay green
- normalized ownership count drops from `172` to `166`
