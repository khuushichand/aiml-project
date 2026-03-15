# Media DB v2 Refactor Design

Date: 2026-03-15
Status: Approved
Target: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

## Context

`Media_DB_v2.py` is a long-lived god file that currently mixes:

- backend and connection handling
- transaction state
- schema/bootstrap logic
- SQLite/Postgres divergence
- domain CRUD for unrelated areas
- composite read helpers
- ingestion-oriented utility functions

This shape makes the module hard to reason about, hard to test in isolation, and risky to change without regressions. The repository already has shared backend abstractions under `DB_Management/backends/`, content backend helpers, and DB factory/dependency modules, but `Media_DB_v2.py` still concentrates too much behavior in one place.

The goal of this refactor is not just to reduce file size. The goal is to replace the god-file structure with a stable package boundary that can support long-term maintenance while preserving both SQLite and Postgres behavior from day 1.

## Constraints

- SQLite and Postgres must both keep working during and after phase 1.
- Long-term stability and pragmatic maintainability are more important than a fast cosmetic split.
- Caller changes are allowed in the first refactor if they produce cleaner boundaries.
- The design must account for current dependency hotspots such as `DB_Manager.py` and `DB_Deps.py`, not treat them as fixed external consumers.

## Problems To Solve

### 1. Overloaded module responsibilities

The current module combines infrastructure, schema, domain logic, and composite queries in a single surface area.

### 2. Wrong caching boundary in request handling

`DB_Deps.py` caches `MediaDatabase` instances and then mutates request-specific scope fields on those cached objects. That creates a tenant-context leak risk under concurrent requests.

### 3. Legacy helper surface scattered through factories

`DB_Manager.py` re-exports a large slice of `Media_DB_v2.py`. If the monolith is split without fixing that boundary, the god-file problem just moves into a different file.

### 4. Backend parity risk

The current module hides a large amount of backend-specific branching. Extraction must not cause SQLite/Postgres behavior to drift.

### 5. Phase 1 scope creep

Trying to move every domain in one pass would turn the refactor into a rewrite. The first slice needs clear limits.

## Chosen Approach

Use a repository-package refactor with a thin composition root.

This is preferred over:

- a pure facade-first split, which preserves the god-object shape too long
- a domain-only file split, which reduces file size but not architecture risk

The steady-state outcome is a `media_db` package with explicit infrastructure, repository, and query boundaries. Compatibility shims may exist temporarily, but they are migration tools, not the target design.

## Target Package Shape

Create a new package under:

- `tldw_Server_API/app/core/DB_Management/media_db/`

Proposed structure:

- `media_db/api.py`
  - stable public entry points for callers
  - exports factories, key repository/query types, and a transitional facade only if still needed
- `media_db/errors.py`
  - `DatabaseError`, `SchemaError`, `InputError`, `ConflictError`
- `media_db/runtime/`
  - shared runtime contracts and execution primitives
  - backend/session lifecycle
  - query execution helpers
  - row adapters and cursor wrappers
- `media_db/schema/`
  - split by capability, not just backend
  - bootstrap orchestration
  - migrations
  - FTS setup
  - backend-specific installers for SQLite and Postgres
  - Postgres RLS/policy setup where required
- `media_db/repositories/`
  - table/domain-oriented operations
- `media_db/queries/`
  - composite read models and higher-level read assembly
- `media_db/facade.py`
  - optional short-lived `MediaDatabase` compatibility facade for migration only

## Runtime Design

The design must avoid sharing request-scoped mutable state on cached DB objects.

### Required boundary change

Do not cache mutable `MediaDatabase` instances per user if those instances also carry request-level scope or transactional state.

Instead:

- cache only stable infrastructure such as backend pools, config, and factory objects
- produce a fresh request-scoped `MediaDbSession` or `MediaDbHandle` per request
- carry org/team scope in that session/handle, not on a cached shared singleton

That session object should expose:

- backend type and capability access
- scoped query execution
- transaction entry points
- current org/team scope
- request-safe connection/context lifecycle

This design addresses the concurrency hazard in `DB_Deps.py` while remaining compatible with both SQLite file-backed use and shared Postgres backends.

## Repository Boundaries

Repositories should own domain-specific persistence behavior and nothing else.

Phase 1 repositories:

- `media_repository.py`
- `document_versions_repository.py`
- `chunks_repository.py`
- `keywords_repository.py`
- `media_files_repository.py`

Deferred from phase 1:

- claims
- outputs and audiobook persistence
- tts history
- other secondary domains currently embedded in the monolith

Reason for deferral:

- these areas materially increase scope
- claims in particular are large enough to destabilize the pilot
- phase 1 should establish the architecture on the most central and reusable core media domains first

## Query Layer

Do not use a generic `services/` junk drawer.

Instead, create a read-focused `queries/` layer for composite retrieval operations that combine repositories without owning backend details.

Phase 1 query modules:

- `media_details_query.py`
  - replacement for full-media detail helpers
- `transcripts_query.py`
  - transcript lookup and latest transcript retrieval
- `prompts_query.py`
  - prompt retrieval helpers
- `keywords_query.py`
  - batch keyword resolution where it spans repository calls or response shaping

These modules are responsible for assembling higher-level read results. They should not perform schema initialization or transaction orchestration outside the runtime contract.

## Schema Design

Do not replace one monolith with two new monoliths called `sqlite.py` and `postgres.py`.

Schema code should be split by capability first, with backend-specific implementations behind those capability boundaries.

Example shape:

- `schema/bootstrap.py`
  - orchestration and version checks
- `schema/migrations.py`
  - migration registry and execution sequencing
- `schema/features/core_media.py`
  - Media, document versions, chunks, keywords, files
- `schema/features/fts.py`
  - FTS structures and triggers or equivalent backend setup
- `schema/features/policies.py`
  - Postgres RLS and policy installation
- `schema/backends/sqlite.py`
  - SQLite-specific feature installers/helpers
- `schema/backends/postgres.py`
  - Postgres-specific feature installers/helpers

This keeps schema growth segmented by responsibility and reduces the chance that new capability code recreates backend-sized god files.

## Public API Strategy

`DB_Manager.py` must be part of the refactor surface.

### Why

Today it imports and re-exports many `Media_DB_v2.py` helpers directly. Leaving that intact would preserve legacy coupling and simply move the giant import graph elsewhere.

### Target state

- `media_db/api.py` becomes the media persistence public surface
- `DB_Manager.py` becomes factory-oriented and compatibility-oriented only
- direct helper re-exports from the monolith are gradually removed

Temporary compatibility is acceptable, but the intended API should be explicit and small.

## Data Flow

Target request flow:

1. API dependency or service obtains a request-scoped `MediaDbSession` from a factory.
2. Query modules and repositories receive that session.
3. Repositories execute persistence operations through runtime contracts only.
4. Query modules compose repository results into higher-level responses.
5. Schema/bootstrap is invoked through composition/setup paths, not hidden inside arbitrary repository methods.

Boundary rules:

- endpoints and workers do not call private backend helpers
- repositories do not mutate request scope
- repositories do not directly depend on each other’s private SQL internals
- query modules compose repositories but do not own backend branching
- backend-specific SQL stays inside repository/schema internals

## Async And Transaction Scope

Phase 1 should not invent a second async/transaction abstraction stack unless media-specific needs require it immediately.

Reason:

- the repo already has ChaCha-specific async and transaction helpers
- duplicating that pattern prematurely for media would increase fragmentation
- the first priority is establishing clean sync/runtime/repository/query boundaries

Phase 1 non-goal:

- no generalized cross-DB async wrapper unification

If a concrete migrated media caller needs async adaptation, use the smallest compatibility layer necessary and defer broader unification to a later follow-up.

## Migration Plan Shape

Refactor in narrow, verifiable slices.

### Stage 1. Infrastructure extraction

Move into `media_db`:

- errors
- row adapters / cursor wrappers
- runtime/session abstractions
- query preparation helpers that belong to media runtime composition

Also update the request dependency path so cached state lives at the factory/backend level, not the request-mutated database object level.

### Stage 2. Schema extraction

Extract schema/bootstrap capability modules for core media tables and ensure SQLite/Postgres parity tests pass before proceeding.

### Stage 3. Core repositories

Extract:

- media
- document versions
- chunks
- keywords
- media files

### Stage 4. Core queries

Replace bottom-of-file standalone helpers for:

- full media details
- transcripts
- prompts
- keyword read aggregation

### Stage 5. Caller migration

Migrate callers in this order:

1. `DB_Deps.py`
2. `DB_Manager.py`
3. core services and workers
4. API endpoints
5. remaining tests and internal modules

### Stage 6. Compatibility cleanup

Keep `Media_DB_v2.py` only as a transitional shim if needed. Remove it once imports are fully migrated.

Deferred stage:

- claims
- outputs
- TTS history
- remaining lower-priority domains embedded in the current monolith

## Testing Strategy

The refactor succeeds only if behavior remains stable while architecture improves.

Required test coverage:

- SQLite/Postgres parity tests for every extracted phase 1 repository and query module
- schema bootstrap tests for both backends
- request-scope concurrency tests proving org/team scope does not bleed across concurrent requests
- contract tests for the new `media_db/api.py` public surface
- regression coverage through existing endpoint and service tests

Recommended additions:

- focused tests around transaction boundaries for migrated multi-step operations
- migration tests proving a request-scoped handle can be safely created repeatedly against the same cached factory/backend

## Risks And Mitigations

### Risk: hidden cross-domain coupling in the monolith

Mitigation:

- extract by observed method clusters and caller graph
- keep phase 1 limited to core media domains

### Risk: backend drift during extraction

Mitigation:

- parity tests before advancing each slice
- keep backend branching centralized inside runtime, schema, and repository internals

### Risk: `DB_Manager.py` becomes the new god file

Mitigation:

- make `DB_Manager.py` an explicit refactor target
- move the media public API to `media_db/api.py`

### Risk: request-scope leakage under concurrency

Mitigation:

- cached factory/backend plus request-scoped session design
- explicit concurrency tests

### Risk: “temporary facade” becomes permanent

Mitigation:

- track shim imports as migration debt
- define the steady-state public API before the first caller migration

## Non-Goals

- rewriting claims persistence in phase 1
- unifying all DB modules in the repo under one generic abstraction in this pass
- redesigning endpoint response schemas
- creating a generic async wrapper framework for all DB modules during this pilot

## Success Criteria

Phase 1 is successful when:

- core media persistence is served by the new `media_db` package
- SQLite and Postgres both pass parity and regression tests for migrated slices
- request-scoped org/team state is no longer stored on cached mutable DB objects
- `DB_Manager.py` no longer acts as a bulk re-export layer for `Media_DB_v2.py`
- `Media_DB_v2.py` is either reduced to a thin compatibility shim or removed for migrated callers

