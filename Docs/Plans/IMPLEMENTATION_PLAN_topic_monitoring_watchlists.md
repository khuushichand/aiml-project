# Implementation Plan: Topic Monitoring & Watchlists

PRD: `Docs/Product/Topic_Monitoring_Watchlists.md`

## Baseline vs Target
**Baseline**:
- Watchlists are file-backed (`monitoring_watchlists.json`) with in-memory compilation.
- Alerts are stored in SQLite via `TopicMonitoring_DB` with a minimal schema.
- Matching behavior is already close to ModerationService but lacks DB-backed watchlists, per-rule IDs, and streaming dedupe metadata.

**Target**:
- Watchlists and rules are persisted in DB; file import is seed-only with explicit reload flags.
- Alerts capture rule/source/chunk identifiers and dedupe metadata.
- Matching and chunking are explicitly aligned with ModerationService.
- Streaming dedupe is implemented with a sliding window and similarity hash (best-effort per process).

## Stage 1: Data Model + Persistence
**Goal**: Create durable storage for watchlists and alerts with reload semantics.
**Success Criteria**:
- DB tables for watchlists, rules, and alerts are defined and managed in `tldw_Server_API/app/core/DB_Management/TopicMonitoring_DB.py`.
- `topic_alerts` is extended with `rule_id`, `source_id`, `chunk_id`, and new indexes (user_id, watchlist_id, rule_id, source, created_at, is_read).
- Watchlist tables include `managed_by` and `rule_id` (rules) to support idempotent reload upserts and dedupe.
- Backward-compatible schema updates keep existing `monitoring_alerts.db` readable (new columns default to NULL).
- Startup seeding: `monitoring_watchlists.json` is imported on service startup with `managed_by=config` and idempotent upserts.
- Reload follows the same upsert rules and honors flags (`delete_missing`/`disable_missing`) when explicitly set.
- Idempotency: startup seeding uses watchlist natural keys `(name, scope_type, scope_id)` and rule `rule_id` (or a stable hash of rule fields) to avoid duplicate inserts across restarts.
**Tests**:
- Unit tests for repository CRUD, natural key matching, rule_id hashing, and reload flags.
- Migration tests for schema changes and indexes (SQLite; Postgres if the module is wired to it).
- Tests that file-based watchlists import without data loss and preserve `managed_by` semantics.
**Status**: Complete

## Stage 2: Core Monitoring Service
**Goal**: Implement rule parsing, safe regex compilation, matching, and alert creation.
**Success Criteria**:
- `TopicMonitoringService` uses DB-backed watchlists as the source of truth; the file path is used only for seed/import.
- Matching mirrors ModerationService (case-insensitive, chunked scans with overlap, safe regex checks, and identical max-scan settings).
- Rule compilation supports `/pattern/flags` with `i/m/s/x`, logs unknown flags, and skips dangerous regexes.
- Alert creation captures `rule_id`, `source_id`, `chunk_id`, `chunk_seq`, and dedupe metadata fields.
- Streaming dedupe uses a custom SimHash implementation with a per-stream, per-rule sliding window (TTL aligned to config); best-effort per process.
**Tests**:
- Unit tests for rule parsing, regex safety, match detection across chunk boundaries, and scan truncation flags.
- Unit tests for SimHash generation, dedupe thresholds, and sliding-window eviction.
- Property-based tests for regex safety heuristics and chunked scan boundaries.
**Status**: Complete

## Stage 3: API + Schemas
**Goal**: Expose admin endpoints to manage watchlists and alerts.
**Success Criteria**:
- Schemas in `tldw_Server_API/app/api/v1/schemas/monitoring_schemas.py` include `rule_id`, `managed_by`, `source_id`, `chunk_id`, and match PRD fields.
- Endpoints in `tldw_Server_API/app/api/v1/endpoints/monitoring.py` use DB-backed services and expose reload flags.
- Watchlist CRUD validates `scope_type=global` with null `scope_id` and enforces allowed severities.
- Alerts list supports filters (user_id, source, severity, category, scope, unread, since) with pagination defaults.
- Auth uses claim-first admin dependencies (roles/permissions) and mirrors existing rate-limit patterns.
**Tests**:
- Integration tests for watchlist CRUD, reload flags, and alert query filters.
- AuthZ tests ensuring non-admin access is denied and admin access is allowed.
- Schema validation tests for invalid scope/severity/pattern formats.
**Status**: Complete

## Stage 4: Integration + Notifications
**Goal**: Wire monitoring into chat, ingestion, notes, and RAG without blocking content.
**Success Criteria**:
- Hooks emit alerts for chat input/output (stream + non-stream), ingestion, notes, and RAG queries using background tasks.
- Streaming output emits per chunk with similarity-based dedupe and `source_id`/`chunk_seq` metadata.
- JSONL notification sink honors severity threshold and privacy constraints; alert snippets remain bounded.
- Metrics/logging capture counts for alerts created, deduped, and errors.
- Monitoring is opt-in: integration points short-circuit if monitoring is disabled or no watchlists are enabled.
- Docs update to reflect new APIs, config keys, and reload semantics.
**Tests**:
- Integration tests for each source type with alert creation.
- Streaming tests to validate per-chunk alerts and dedupe behavior.
- Notification tests for JSONL file output and severity filtering.
**Status**: Complete
