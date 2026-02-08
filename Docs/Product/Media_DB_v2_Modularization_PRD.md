# PRD: Media_DB_v2 Final Modularization

- Title: Media_DB_v2 Modularization
- Owner: DB and Backend Team
- Status: Draft
- Target Version: v0.2.x
- Last Updated: 2026-02-08

## Summary

`Media_DB_v2.py` remains a monolithic core data module with mixed responsibilities. This PRD defines a compatibility-safe extraction into the existing `MediaDB/` package while preserving the public `MediaDatabase` API and legacy import paths.

## Current State (Repo Evidence)

- Monolith file: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py` (~15931 lines).
- Existing package target exists but is empty:
  - `tldw_Server_API/app/core/DB_Management/MediaDB/`
- Mixed concerns currently co-located:
  - connection/backend handling
  - schema initialization and migrations
  - FTS setup/update/search helpers
  - sync-log writes
  - media CRUD and keyword maintenance
  - claims/review/monitoring/analytics export
  - chunking templates and unvectorized chunk processing
  - standalone helper functions at file bottom

## Problem Statement

The current file size and concern density increase merge conflicts, reduce readability, and make isolated testing difficult. Internal cohesion is low and module ownership boundaries are unclear.

## Goals

- Keep `MediaDatabase` public behavior and import path stable.
- Split internals into coherent modules under `MediaDB/`.
- Preserve transactional behavior and backend abstraction semantics.
- Enable smaller, focused unit/integration tests per concern area.
- Allow staged extraction without a big-bang rewrite.

## Non-Goals

- No DB schema redesign.
- No behavior changes for callers.
- No migration away from existing backend abstraction in this project phase.
- No endpoint contract changes tied to this effort.

## Scope

### In Scope

- Internal extraction of code currently inside `Media_DB_v2.py` into `MediaDB/` modules.
- Compatibility facade in `Media_DB_v2.py` preserving:
  - class name (`MediaDatabase`)
  - function names
  - import compatibility for existing callers/tests

### Out of Scope

- New tables/features.
- Refactor of unrelated DB modules.

## Target Module Map

Create modules under `tldw_Server_API/app/core/DB_Management/MediaDB/`:

- `connection.py`
  - backend resolution
  - connection/cursor adapters
  - transaction context helpers
- `schema.py`
  - `_initialize_schema*`
  - schema version helpers
  - migration orchestration
- `fts.py`
  - `_ensure_*fts` helpers
  - `_update_fts_*` helpers
  - FTS rebuild/search support functions
- `sync_log.py`
  - `_log_sync_event`
  - sync log query/write helpers
- `media.py`
  - primary media CRUD and related metadata operations
- `keywords.py`
  - keyword CRUD + media-keyword linkage
- `document_versions.py`
  - document version creation, updates, rollback paths
- `claims.py`
  - claims CRUD, review queue, monitoring, clusters, exports
- `chunking.py`
  - chunking templates and unvectorized chunk operations
- `standalone.py`
  - standalone utility functions currently at bottom of `Media_DB_v2.py`

## Integration Pattern

Two compatible implementation options are allowed; start with the least risky:

1. Facade + Delegation (preferred first)
- Keep `MediaDatabase` in `Media_DB_v2.py`.
- Delegate method implementations to extracted module functions.

2. Mixin Composition (later optimization)
- Build `MediaDatabase` from mixins imported from `MediaDB/*`.
- Preserve method names and signatures.

## Compatibility Requirements

- Existing imports remain valid:
  - `from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase`
- Existing function signatures and return structures stay unchanged.
- Transactional side effects and sync-log behavior stay unchanged.
- No change to caller-facing exceptions unless they are existing bug fixes documented separately.

## Migration Plan

### Phase 1: Standalone and Pure Helper Extraction

- Move standalone bottom-of-file functions into `MediaDB/standalone.py`.
- Re-export wrappers from `Media_DB_v2.py`.

### Phase 2: Low-Risk Core Infrastructure Extraction

- Extract `connection.py`, `schema.py`, `sync_log.py`, `fts.py`.
- Keep method names and delegation wrappers in facade.

### Phase 3: Domain Slice Extraction

- Extract `keywords.py`, `document_versions.py`, `chunking.py`.
- Run targeted tests for these flows.

### Phase 4: Claims and Remaining CRUD

- Extract `claims.py` and remaining heavy domain methods.
- Keep compatibility wrappers until all tests stabilize.

### Phase 5: Facade Cleanup

- Minimize `Media_DB_v2.py` to imports, facade wiring, and compatibility re-exports.

## Testing Strategy

- Preserve and run existing DB tests for media, claims, chunking, and sync.
- Add module-focused tests per extracted area:
  - schema init/migration behavior
  - FTS update/search invariants
  - sync-log correctness
  - claims queue and monitoring flows
  - chunking template CRUD and chunk persistence behavior
- Add compatibility tests validating imports and selected method signatures from `Media_DB_v2.py`.

## Risks and Mitigations

- Risk: subtle transaction behavior drift.
  - Mitigation: extract with wrapper delegation and no SQL changes in early phases.
- Risk: circular imports across extracted modules.
  - Mitigation: strict layering and shared utility module for common primitives.
- Risk: widespread regressions due to very large surface area.
  - Mitigation: phase extraction by concern, with incremental merges and tests per phase.

## Success Metrics

- `Media_DB_v2.py` reduced to a thin compatibility facade.
- `MediaDB/` package contains cohesive modules with clear ownership boundaries.
- Existing behavior and tests remain stable.
- Change review size for DB updates is materially reduced.

## Acceptance Criteria

- All existing call sites continue to work without import changes.
- Extracted modules are in place and used by facade/delegation.
- No behavior regressions in DB integration tests.
- New module boundaries documented and maintainable.
