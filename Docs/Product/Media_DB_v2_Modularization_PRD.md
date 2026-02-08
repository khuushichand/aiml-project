# PRD: Media_DB_v2 Final Modularization

- Title: Media_DB_v2 Modularization
- Owner: DB and Backend Team
- Status: Execution Ready
- Target Version: v0.2.x
- Last Updated: 2026-02-08

## Summary

`Media_DB_v2.py` is still a high-risk monolith. This PRD defines a staged modularization into `MediaDB/` while preserving the current public API surface (`MediaDatabase`, exceptions, and standalone helper exports) and all existing import paths.

## Repo Evidence (Current Baseline)

- Monolith:
  - `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py` is 15,931 lines.
- Target package currently empty:
  - `tldw_Server_API/app/core/DB_Management/MediaDB/`
- The module currently mixes:
  - backend/connection/query execution and adapters
  - schema bootstrapping and sqlite/postgres migrations
  - sync-log write logic
  - FTS maintenance and search
  - media CRUD, file metadata, keywords
  - claims (review, monitoring, cluster, analytics, notifications)
  - data tables
  - chunking templates and chunk helpers
  - document versions/rollback
  - many standalone module-level helpers
- Blast radius:
  - ~190 imports/usages across `tldw_Server_API/app` and `tldw_Server_API/tests`.

## Problem Statement

The module has low cohesion and very high change coupling. Small fixes in one area are difficult to review and test safely because unrelated concerns are in the same file. This creates frequent merge friction and increases regression risk.

## Goals

- Keep public behavior and import paths stable.
- Split internals into cohesive modules under `MediaDB/`.
- Preserve transaction and backend semantics (SQLite/PostgreSQL).
- Enable focused tests by concern area.
- Complete migration incrementally without a big-bang rewrite.

## Non-Goals

- No schema redesign.
- No endpoint contract changes.
- No backend abstraction rewrite.
- No feature additions bundled into this refactor.

## Scope

### In Scope

- Internal extraction from `Media_DB_v2.py` into `MediaDB/*`.
- Compatibility facade in `Media_DB_v2.py` preserving existing symbols and behaviors.

### Out of Scope

- Refactor of unrelated DB modules.
- Product behavior changes unrelated to modularization.

## Compatibility Contract (Must Preserve)

### Stable Import Path

- `from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import ...`

### Required Public Symbols

- Class and exceptions:
  - `MediaDatabase`
  - `DatabaseError`
  - `SchemaError`
  - `InputError`
  - `ConflictError`
- Common standalone helpers that external code/tests import:
  - `get_document_version`
  - `get_latest_transcription`
  - `upsert_transcript`
  - `fetch_keywords_for_media`
  - `fetch_keywords_for_media_batch`
  - other currently exported module-level helpers

### Behavioral Compatibility

- Existing method signatures and return payload structures unchanged.
- Sync-log semantics unchanged.
- Soft-delete/version bump semantics unchanged.
- Existing runtime compatibility patches remain effective (or are replaced by equivalent explicit definitions).

## Target Module Map

Create modules in `tldw_Server_API/app/core/DB_Management/MediaDB/`:

- `connection.py`
  - `_resolve_backend`
  - query preparation/execution wrappers
  - cursor adapters
  - transaction context helpers
- `schema.py`
  - `_initialize_schema*`
  - sqlite bootstrap path
  - postgres migration chain (`_postgres_migrate_to_v*`)
  - schema version helpers
- `fts.py`
  - `_ensure_fts_structures`
  - chunk FTS maintenance (`ensure_chunk_fts`, `maybe_rebuild_chunk_fts_if_empty`)
  - `_update_fts_media` / `_delete_fts_media`
  - `_update_fts_keyword` / `_delete_fts_keyword`
  - search helpers (`search_media_db`, `search_claims`)
- `sync_log.py`
  - `_log_sync_event`
  - sync log read/write helpers
- `media.py`
  - media CRUD/read/list operations
  - media files and visibility/share operations
- `keywords.py`
  - keyword CRUD and media-keyword linkage/update logic
- `document_versions.py`
  - `create_document_version`
  - version retrieval helpers
  - `rollback_to_version`
- `claims/` (subpackage)
  - `claims_core.py` (CRUD/search/review status basics)
  - `claims_review.py`
  - `claims_monitoring.py`
  - `claims_clusters.py`
  - `claims_notifications.py`
  - `claims_exports.py`
- `data_tables.py`
  - `create_data_table`, `get_data_table`, `list_data_tables`, `update_data_table`, counts/sources helpers
- `chunking.py`
  - chunk CRUD/batch helpers
  - chunking templates CRUD
- `standalone.py`
  - module-level helper functions currently at bottom of `Media_DB_v2.py`

## Architecture Pattern

### Phase-Preferred Pattern: Facade + Delegation

- Keep `MediaDatabase` defined in `Media_DB_v2.py`.
- Delegate method bodies to extracted functions/modules.
- Preserve module-level helper exports by re-exporting wrappers.

### Optional Later Pattern: Mixin Composition

- Move delegated groups to mixins after stabilization.
- Keep the same outward class API and import path.

## Migration Plan

### Phase 1: Standalone Helper Extraction (Lowest Risk)

- Move bottom-of-file standalone functions to `MediaDB/standalone.py`.
- Re-export wrappers in `Media_DB_v2.py`.

### Phase 2: Infrastructure Extraction

- Extract `connection.py`, `schema.py`, `sync_log.py`, `fts.py`.
- Preserve existing SQL and control flow; no behavior changes.

### Phase 3: Medium-Risk Domain Extraction

- Extract `keywords.py`, `document_versions.py`, `chunking.py`, `data_tables.py`.
- Keep same method signatures on `MediaDatabase`.

### Phase 4: Claims Subsystem Extraction

- Extract claims into `MediaDB/claims/*` modules.
- Move in slices (core -> review -> monitoring -> clustering -> notifications/exports).

### Phase 5: Media Core and Final Facade Slimming

- Move remaining media CRUD and related methods to `media.py`.
- Reduce `Media_DB_v2.py` to facade wiring + compatibility exports.

## Test and Verification Plan

### Core Regression Gates (Required)

- `tldw_Server_API/tests/MediaDB2/test_sqlite_db.py`
- `tldw_Server_API/tests/MediaDB2/test_media_db_postgres.py`
- `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`
- `tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py`
- `tldw_Server_API/tests/DB_Management/test_media_db_migration_missing_scripts_error.py`
- `tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py`

### Domain Regression Gates (Required)

- `tldw_Server_API/tests/DB_Management/test_claims_schema.py`
- `tldw_Server_API/tests/DB_Management/test_claims_fts_triggers.py`
- `tldw_Server_API/tests/DB_Management/test_data_tables_crud.py`
- `tldw_Server_API/tests/DB_Management/test_media_transcripts_upsert.py`
- `tldw_Server_API/tests/Chunking/test_chunking_templates.py`

### Compatibility Verification

- Import smoke tests for class/exceptions/standalone helpers from `Media_DB_v2`.
- Targeted checks for runtime monkeypatch points used by tests.
- No endpoint-level behavior regressions for routes that depend on `MediaDatabase`.

## Risks and Mitigations

- Risk: transaction and versioning drift.
  - Mitigation: facade delegation first, no SQL changes during early phases.
- Risk: import breakages due to very high fan-out.
  - Mitigation: preserve `Media_DB_v2` import path and symbol exports throughout.
- Risk: circular imports in claims/data-table extraction.
  - Mitigation: strict module layering and minimal shared utility modules.
- Risk: hidden behavior coupling in standalone helpers.
  - Mitigation: extract standalone helpers first and verify parity before moving core methods.

## Success Metrics

- `Media_DB_v2.py` reduced substantially and acts as a compatibility facade.
- `MediaDB/` contains cohesive modules with clear ownership.
- Required regression gates pass without endpoint contract changes.
- DB-related PRs become smaller and easier to review.

## Acceptance Criteria

- Existing imports from `Media_DB_v2` remain valid.
- `MediaDatabase` behavior/signatures are unchanged for callers.
- Extracted modules are wired and used via delegation/facade.
- Regression suites for MediaDB/claims/data-tables/chunking remain green.
