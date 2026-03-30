# Media DB V2 Stage 2 Read Contract And Parity Design

**Status:** Proposed and approved on 2026-03-18.

**Goal:** Extract the canonical Media DB read surface from `Media_DB_v2`, harden SQLite/Postgres parity for that surface, and migrate all current read callers onto the package-level contract without changing request DB dependency wiring.

## Why Stage 2 Exists

Stage 1 removed the remaining app-side direct `Media_DB_v2` import and moved the
runtime/default wiring behind the `media_db` seam. The next risk concentration is
not construction anymore; it is the read behavior still trapped in:

- `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- `tldw_Server_API/app/core/DB_Management/media_db/legacy_media_details.py`
- `tldw_Server_API/app/core/DB_Management/media_db/legacy_wrappers.py`
- endpoint-local SQL in `media/versions.py`

Those reads now back media endpoints, workers, MCP modules, RAG, embeddings,
chatbooks, slides/quizzes, and other non-endpoint services. Stage 2 makes the
package seam the real source of truth for reads and proves that source of truth
against both SQLite and Postgres.

## Review Corrections Incorporated

### 1. Do not replace request-scoped DB dependencies

`get_media_db_for_user` in
`tldw_Server_API/app/api/v1/API_Deps/DB_Deps.py`
must continue yielding a request-scoped `MediaDbSession`.

Stage 2 will not introduce a new read-only dependency object. Instead, the new
read contract will be implemented as package-level functions/services that take
the existing `MediaDbLike` / `MediaDbSession` handle.

### 2. Keep `Media_DB_v2` as a delegating compatibility shell

Stage 2 will not remove legacy read instance methods outright. The safe sequence
is:

1. extract canonical read implementation under `media_db`
2. delegate `Media_DB_v2` read methods to that implementation
3. migrate callers to the extracted contract

This avoids a branch where both implementation and callers are rewritten at the
same time.

### 3. Treat search parity as a first-class concern

`search_media_db` is not a thin query helper. It embeds backend-specific access
behavior:

- SQLite applies visibility filtering in the method itself
- Postgres relies on RLS and scope context

Stage 2 contract tests must cover scope-sensitive search behavior, not just
shape/pagination smoke tests.

### 4. Collapse version reads to one source of truth

Version listing is currently duplicated across:

- `media/versions.py`
- `media_db/legacy_wrappers.py`
- `media_db/legacy_media_details.py`
- `Media_DB_v2.get_all_document_versions`

Stage 2 will make `DocumentVersionsRepository` the single canonical version-read
surface for latest-version lookup and paged version listing.

### 5. Preserve low-churn test doubles

Many tests currently stub objects that expose methods like
`get_media_by_id(...)` and `search_media_db(...)`.

Stage 2 will provide a small read protocol/adapter boundary so tests can satisfy
the new caller contract with minimal rewrites rather than forcing a service
container rewrite across the suite.

## Scope

### In scope

- Extract package-level read contract functions/services for:
  - `get_media_by_id`
  - `get_media_by_uuid`
  - `search_media`
  - `get_document_version`
  - `list_document_versions`
  - `get_full_media_details`
  - `get_full_media_details_rich`
- Expand repository/service internals under `media_db` to own those behaviors.
- Delegate the corresponding `Media_DB_v2` read methods to the extracted
  contract.
- Migrate current read callers across endpoints, services, jobs, MCP modules,
  RAG, embeddings, and chatbooks to the package-level contract.
- Add backend-neutral contract tests that run on SQLite and Postgres.
- Harden Postgres runtime validation so schema/policy/bootstrap failures are
  surfaced deterministically for the extracted read surface.

### Out of scope

- Write/update/delete path extraction.
- Removing `DB_Manager` media compat wrappers.
- Replacing the legacy runtime class loader.
- Deleting `legacy_*` modules wholesale.
- Full compatibility-debt removal.

## Architecture

### A. Public read contract stays package-level and session-oriented

Stage 2 will expose a canonical read API under `media_db` as package-level
functions that accept a `MediaDbLike` handle. The contract remains session-based
because the rest of the app already depends on request-scoped DB handles and
scope context.

Candidate public surface:

- `get_media_by_id(db, media_id, include_deleted=False, include_trash=False)`
- `get_media_by_uuid(db, media_uuid, include_deleted=False, include_trash=False)`
- `search_media(db, ..., include_deleted=False, include_trash=False)`
- `get_document_version(db, media_id, version_number=None, include_content=True)`
- `list_document_versions(db, media_id, include_content=False, include_deleted=False, limit=None, offset=0)`
- `get_full_media_details(db, media_id, include_content=True)`
- `get_full_media_details_rich(db, media_id, include_content=True, include_versions=True, include_version_content=False)`

### B. Internal implementation splits by responsibility

The extracted implementation should be owned by narrow components:

- `repositories/media_lookup_repository.py`
  - ID/UUID lookup and shared row filtering semantics.
- `repositories/document_versions_repository.py`
  - latest-version fetch and paged version listing.
- `repositories/media_search_repository.py`
  - search query assembly, filtering, ordering, paging, and backend-specific
    visibility/RLS semantics.
- `services/media_details_service.py`
  - rich detail assembly that composes lookup, versions, keywords, and original
    file availability without endpoint-local SQL.

The public API stays small even if internal components grow.

### C. `Media_DB_v2` becomes a delegating read shim

The following methods should delegate to the extracted package implementation:

- `Media_DB_v2.get_media_by_id`
- `Media_DB_v2.get_media_by_uuid`
- `Media_DB_v2.search_media_db`
- `Media_DB_v2.get_all_document_versions`

If needed, `Media_DB_v2` can keep its legacy method names while calling the new
package functions/repositories internally. That preserves older callers and test
surfaces while moving the real implementation out of the monolith.

### D. Caller migration uses the new contract, not a new dependency shape

Callers keep receiving `db` from existing dependency injection or service setup.
Migration only changes how they perform reads:

- from `db.get_media_by_id(...)`
- to `media_db.api.get_media_by_id(db, ...)`

and similarly for search/details/version reads.

This keeps request scoping, backend selection, and cleanup behavior unchanged.

## Data And Behavior Guarantees

### Lookup semantics

- Preserve current `None` return for not-found records.
- Preserve `include_deleted` and `include_trash` filtering behavior.
- Preserve row shape expected by existing callers.

### Search semantics

- Preserve `(rows, total)` response contract.
- Preserve keyword include/exclude filters, media type filters, date filters,
  search field selection, sorting, paging, and media-ID filters.
- Preserve SQLite visibility filtering via scope context.
- Preserve Postgres behavior via RLS-backed queries under the same public
  contract.

### Version semantics

- One canonical implementation for latest version and paged version listing.
- Preserve metadata/content inclusion semantics expected by endpoints and
  workers.
- Remove endpoint-local `DocumentVersions` SQL where the repository can provide
  the same result.

### Rich details semantics

- Preserve current detail payload shape used by `media/item.py`.
- Keep keyword lookup and original-file availability best-effort where today’s
  behavior is already tolerant of partial failures.
- Centralize content metadata normalization and versions-list shaping in one
  place.

## Error Handling

- Continue returning `None` for not-found lookups where callers currently expect
  absence rather than exceptions.
- Preserve `InputError` and `DatabaseError` semantics for invalid arguments and
  backend/query failures.
- Normalize backend row/JSON/boolean differences inside repositories/services,
  not at call sites.
- Keep Postgres runtime/bootstrap/schema/policy errors in the runtime layer so
  they fail fast during setup/validation instead of surfacing as surprising read
  behavior.

## Testing Strategy

### Contract suites

Add a backend-neutral contract suite that exercises the extracted read contract
on both SQLite and Postgres for:

- lookup by ID
- lookup by UUID
- search with paging/filtering
- search with scope-sensitive visibility behavior
- latest version lookup
- paged version listing
- rich detail assembly

### Postgres-specific checks

Keep heavier Postgres-only tests separate for:

- RLS enforcement
- runtime validation failures
- schema/policy/bootstrap diagnostics

Those tests should complement the contract suite rather than duplicate it.

### Caller migration guards

Add narrow regression guards that verify key production callers no longer reach
read behavior through legacy instance methods when Stage 2 migration is done.

## Exit Criteria

- The extracted `media_db` read contract is the source of truth for lookup,
  search, version reads, and rich detail assembly.
- `Media_DB_v2` read methods delegate to the extracted contract.
- Current read callers use the package-level contract without changing request
  DB dependency wiring.
- SQLite and Postgres pass the same read-contract assertions for the Stage 2
  surface.
- Postgres runtime validation fails deterministically when schema or RLS policy
  requirements are missing.
