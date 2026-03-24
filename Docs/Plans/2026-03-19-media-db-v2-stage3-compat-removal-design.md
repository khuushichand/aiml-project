# Media DB V2 Stage 3 Compat Removal Design

**Status:** Proposed and approved on 2026-03-19.

**Goal:** Replace the remaining legacy Media DB compatibility path with a package-native runtime entrypoint, shrink `DB_Manager` to a narrow deprecated facade for media operations, and delete any `legacy_*` modules that become provably unused in the same tranche.

## Why Stage 3 Exists

Stage 1 moved app callers and test setup toward the `media_db` seam. Stage 2
made that seam the canonical source of truth for reads and hardened
SQLite/Postgres parity for the extracted read contract.

The remaining compatibility debt is now concentrated in three places:

- `tldw_Server_API/app/core/DB_Management/media_db/runtime/media_class.py`
- `tldw_Server_API/app/core/DB_Management/DB_Manager.py`
- `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

and in the legacy helper modules still imported by those boundaries.

At this point, `Media_DB_v2.py` is no longer the desired implementation surface,
but the runtime still resolves the canonical class through
`LEGACY_MEDIA_DB_MODULE`, and `DB_Manager.py` still exposes a broad media
wrapper surface. Stage 3 is the handoff from “incremental extraction” to “real
compatibility reduction.”

## Review Corrections Incorporated

### 1. Do not promise direct `Media_DB_v2.py` removal first

The runtime currently loads the Media DB class through
`media_db/runtime/media_class.py`, which still imports
`LEGACY_MEDIA_DB_MODULE` from `legacy_identifiers.py`.

That makes a direct `Media_DB_v2.py` deletion unsafe. Stage 3 must first
introduce a package-native canonical class location, then flip the runtime
loader to that native location, and only then reduce `Media_DB_v2.py` to a
deprecated shell or remove it.

### 2. `DB_Manager` has to be narrowed, not wholesale removed

`DB_Manager.py` still owns non-media responsibilities such as backend/config
helpers and factories for workflows, chat workflows, prompt studio, and
evaluations. Stage 3 will only contract the media surface.

The media-specific wrappers that remain relevant are:

- `add_media_with_keywords`
- `get_full_media_details`
- `get_full_media_details_rich`
- `get_all_document_versions`
- related convenience forwarding around media DB instances

Those should move to `media_db.api` or native package modules for production
callers, while `DB_Manager.py` remains a thin deprecated forwarder for any
explicit compatibility coverage that still needs it.

### 3. Legacy deletion must be selective, not rhetorical

A fresh source scan shows that not every `legacy_*` file is ready to disappear.

Still-active production imports exist for:

- `legacy_reads.py`
- `legacy_wrappers.py`
- `legacy_content_queries.py`
- `legacy_maintenance.py`
- `legacy_transcripts.py`
- `legacy_state.py`

So Stage 3 deletion has to be rule-based:

1. move or replace production imports
2. prove no non-compat imports remain
3. delete only the now-unused module

The first realistic deletion candidate is `legacy_media_details.py`, because its
behavior has already been absorbed by `media_details_service.py` and it is now
only retained through compatibility shells and import-guard tests.

### 4. Keep compatibility coverage centralized

Stage 3 should not scatter deprecation behavior across the app. The desired end
state is:

- production app code imports package-native Media DB APIs
- explicit compat tests cover deprecated `DB_Manager` and `Media_DB_v2` shells
- source guards fail if new production code reintroduces those shells

## Scope

### In scope

- Introduce a package-native canonical `MediaDatabase` export path under
  `media_db`.
- Switch runtime loading and session construction to that package-native export.
- Reduce `Media_DB_v2.py` to a deprecated compatibility shell over the native
  package implementation.
- Migrate remaining production callers that still use `DB_Manager` media
  wrappers.
- Add source-boundary tests that fail on new production media imports from
  `DB_Manager` and on new runtime references back to `LEGACY_MEDIA_DB_MODULE`.
- Delete any `legacy_*` module that becomes provably unused during the tranche.

### Out of scope

- Full removal of every `legacy_*` module regardless of current imports.
- Extraction of all remaining write/update/delete/media-maintenance logic out of
  `Media_DB_v2.py`.
- Removal of non-media factories and shared backend/config helpers from
  `DB_Manager.py`.
- A broad rewrite of ingestion, transcript, or prompt helper APIs unrelated to
  the active compatibility boundary.

## Architecture

### A. Introduce a package-native canonical class location

Stage 3 should create a package-native canonical class export that the runtime
can treat as authoritative.

The safest first step is not a full class rewrite. Instead:

1. add a native export module under `media_db`
2. point `runtime/media_class.py` at that native module
3. keep `Media_DB_v2.py` as a compatibility import target that re-exports the
   same class during the tranche

This decouples runtime construction from the legacy module name before any
larger shell cleanup.

### B. Contract `DB_Manager` to an explicit deprecated media facade

`DB_Manager.py` should stop being the default home for media operations.

Production callers that still use:

- `DB_Manager.add_media_with_keywords`
- `DB_Manager.get_all_document_versions`
- `DB_Manager.get_full_media_details`
- `DB_Manager.get_full_media_details_rich`

should migrate to package-native APIs, repositories, or services directly.

After that migration:

- `DB_Manager.py` keeps thin forwards only where compatibility is intentionally
  supported
- new source-boundary tests fail if production code imports media operations
  from `DB_Manager.py`

### C. Delete legacy modules only behind source and import guards

Deletion is allowed only when all three are true:

1. production app code no longer imports the module
2. non-compat tests no longer import the module
3. retained compat behavior is covered elsewhere

Applied to the current tree:

- `legacy_media_details.py` is the most likely early deletion candidate
- `legacy_identifiers.py` should be deleted only after the runtime loader is no
  longer tied to it and `db_path_utils.py` has a non-legacy constant source
- `legacy_wrappers.py`, `legacy_reads.py`, and related modules should only be
  deleted if their remaining write/read helpers are fully replaced or split

### D. Keep `Media_DB_v2.py` as the last shell to collapse

`Media_DB_v2.py` should become progressively smaller during Stage 3, but it
should be one of the last compatibility surfaces removed.

That shell still provides value while:

- old imports exist in tests
- compatibility behavior is being proven
- the runtime handoff is fresh

The target is for `Media_DB_v2.py` to stop being an implementation owner and
become either:

- a minimal deprecated re-export shell, or
- removable entirely if supported imports are gone

## Expected Migration Shape

### 1. Loader handoff

- add native canonical class export
- flip runtime loader to native path
- add tests proving runtime no longer depends on `LEGACY_MEDIA_DB_MODULE`

### 2. `DB_Manager` media contraction

- migrate the remaining production media imports from `DB_Manager.py`
- keep only narrow deprecated forwards for compatibility coverage
- add source tests preventing new production reintroduction

### 3. Safe `legacy_*` deletions in the same tranche

- delete `legacy_media_details.py` if `Media_DB_v2.py`, `DB_Manager.py`, and
  tests no longer need it
- delete `legacy_identifiers.py` only after runtime/db-path references are
  redirected
- do not delete broader legacy modules until import scans prove they are empty
  of real consumers

### 4. Final compat shell reduction

- reduce `Media_DB_v2.py` to the smallest supported shell
- keep explicit compat tests if the shell remains
- otherwise remove it only when imports and tests prove the path is no longer
  needed

## Testing Strategy

### Boundary tests

Add source/boundary tests for:

- runtime no longer referencing `LEGACY_MEDIA_DB_MODULE`
- production app code not importing media operations from `DB_Manager.py`
- deleted `legacy_*` modules having zero remaining non-compat imports

### Behavior tests

Retain or add focused behavior coverage for:

- runtime factory/session loading through the new native class path
- `Media_DB_v2.py` compatibility import behavior
- `DB_Manager.py` deprecated media forwards that remain intentionally supported

### Deletion guards

Before deleting a `legacy_*` file, add or update a source-scan test that proves:

- production app imports are gone
- non-compat test imports are gone
- the replacement package path is covered

## Exit Criteria

- Runtime class loading no longer depends on `LEGACY_MEDIA_DB_MODULE`.
- Production app code does not import media operations from `DB_Manager.py`.
- `DB_Manager.py` is reduced to an explicit deprecated media facade rather than
  an implementation switchboard.
- Any deleted `legacy_*` module is removed behind source and test proof, not by
  assumption.
- `Media_DB_v2.py` is no longer the active implementation surface for runtime
  construction or package-native media behavior.
