# Media DB V2 Stage 1 Caller-First Design

**Status:** Complete on `codex/media-db-v2-stage1-caller-first` as of 2026-03-18.

**Goal:** Reduce refactor risk by moving remaining app and non-compat test callers onto the `media_db` seam before backend parity work and compat removal.

**Why this stage exists**

The merged Phase 1 branch already has a usable seam:

- `tldw_Server_API/app/core/DB_Management/media_db/api.py`
- `tldw_Server_API/app/core/DB_Management/media_db/runtime/*`
- `tldw_Server_API/app/core/DB_Management/media_db/repositories/*`

App adoption is already far ahead of test adoption, so the lowest-risk next tranche is caller migration, not another internal rewrite.

The approved sequencing is:

1. Caller-first migration with minimal churn
2. Backend parity and PostgreSQL hardening
3. Full compatibility debt removal

## Review Findings Incorporated

### 1. Do not replace a legacy import with `Any`

`MediaDbLike` is currently defined as `Any` in
`tldw_Server_API/app/core/DB_Management/media_db/runtime/validation.py`.

That means replacing the last direct `MediaDatabase` import in
`tldw_Server_API/app/core/Sharing/shared_workspace_resolver.py`
with `MediaDbLike` would remove the runtime dependency but also erase the
type contract. Stage 1 must introduce a real protocol or a narrower typed
interface before migrating that import.

### 2. Avoid two sources of truth for runtime defaults

`tldw_Server_API/app/core/DB_Management/media_db/api.py` currently imports
runtime defaults from `DB_Manager` at call time.

Stage 1 must not copy that logic into a second module. Instead it should
extract a single runtime-defaults provider that both `media_db.api` and
`DB_Manager` consume.

### 3. Keep compatibility tests explicit

Not every direct `MediaDatabase` import should move in Stage 1.

There are existing compatibility-oriented tests that should remain explicit,
including:

- `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- `tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py`
- `tldw_Server_API/tests/MediaDB2/*`

Stage 1 should migrate only non-compat callers that use `MediaDatabase` as a
fixture or seed helper.

### 4. Stage 3 still needs a loader handoff

The runtime still resolves the canonical class through:

- `tldw_Server_API/app/core/DB_Management/media_db/runtime/media_class.py`
- `tldw_Server_API/app/core/DB_Management/media_db/legacy_identifiers.py`

That means full compat removal later requires an explicit loader handoff. Stage 1
should not try to delete or bypass that machinery yet.

## Stage 1 Scope

### In scope

- Extract one shared runtime-defaults helper for Media DB construction.
- Rewire `media_db.api` to use that helper instead of importing `DB_Manager`.
- Rewire `DB_Manager` to use that same helper rather than duplicating config.
- Add a real typed protocol for the subset of Media DB behavior app callers use.
- Migrate the last direct app import of `MediaDatabase` in
  `shared_workspace_resolver.py`.
- Add a shared test helper/fixture path for non-compat tests.
- Migrate a first controlled batch of non-compat tests to the seam.
- Add import-boundary regression tests so new direct imports do not creep back in.

### Out of scope

- Deleting `DB_Manager` Media DB wrappers.
- Deleting `legacy_*` modules.
- Replacing the runtime class loader in `runtime/media_class.py`.
- Full SQLite/Postgres contract parity work.
- Wide migration of all direct `MediaDatabase` tests in one pass.

## Design Decisions

### A. Runtime defaults become a shared dependency, not a `DB_Manager` side effect

Create a new runtime-defaults helper under
`tldw_Server_API/app/core/DB_Management/media_db/runtime/`
that resolves:

- default content config
- default Media DB path
- PostgreSQL content mode
- lazy backend loader

`media_db.api` should consume this helper directly.

`DB_Manager` should consume the same helper and remain the compatibility surface,
not the owner of runtime-default state.

### B. Add a real protocol before removing the last app import

Introduce a typed protocol in
`tldw_Server_API/app/core/DB_Management/media_db/runtime/validation.py`
for the subset of operations required by `shared_workspace_resolver.py`.

That allows `shared_workspace_resolver.py` to stop importing
`Media_DB_v2.MediaDatabase` while still documenting a meaningful contract.

### C. Split tests into three buckets

Stage 1 will treat direct `MediaDatabase` tests as three categories:

1. Compatibility tests: keep direct imports
2. Backend contract tests: keep direct imports for now
3. Feature/integration tests using DBs only as fixtures: migrate first

This preserves signal and avoids broad churn.

### D. Guard the boundary

Add targeted tests that assert:

- `media_db.api` no longer references `DB_Manager`
- `shared_workspace_resolver.py` no longer imports `Media_DB_v2`
- compatibility tests remain the intentional quarantine for legacy imports

## Expected Outcome

After Stage 1:

- app code no longer directly imports `Media_DB_v2.MediaDatabase`
- `media_db.api` no longer depends on `DB_Manager`
- test migrations start from shared helpers instead of ad hoc `MediaDatabase(...)`
- the repo has a clear seam boundary before parity work begins

## Implemented Outcome

Stage 1 landed with the intended seam changes and a narrower first migration
batch than originally sketched:

- added shared runtime defaults in
  `tldw_Server_API/app/core/DB_Management/media_db/runtime/defaults.py`
- rewired both `media_db.api` and `DB_Manager` to consume the shared runtime
  defaults provider
- replaced `MediaDbLike = Any` with a real protocol in
  `tldw_Server_API/app/core/DB_Management/media_db/runtime/validation.py`
- removed the last direct app import of `Media_DB_v2.MediaDatabase` from
  `tldw_Server_API/app/core/Sharing/shared_workspace_resolver.py`
- added seam-backed test helpers in `tldw_Server_API/tests/conftest.py`
  instead of creating a new helper module
- migrated the first non-compat callers in:
  - `tldw_Server_API/tests/Chat/test_fixtures.py`
  - `tldw_Server_API/tests/External_Sources/test_sync_coordinator.py`
  - `tldw_Server_API/tests/Media/test_media_reprocess_endpoint.py`
  - the `data_tables_app_factory` fixture in `tldw_Server_API/tests/conftest.py`
- added boundary guards asserting the app tree no longer references
  `Media_DB_v2` outside `legacy_identifiers.py`

Fresh verification for the implemented scope:

- `153 passed, 29 deselected` on the Stage 1 targeted pytest sweep
- Bandit reported no findings in touched production files; only expected
  low-severity findings remained in touched test files

## Exit Criteria

- `tldw_Server_API/app/` has zero direct imports of `Media_DB_v2.MediaDatabase`
- `media_db.api` constructs runtime config without importing `DB_Manager`
- non-compat tests have a shared seam-based DB helper
- compatibility tests remain explicit and green
- regression tests exist for the new boundary
