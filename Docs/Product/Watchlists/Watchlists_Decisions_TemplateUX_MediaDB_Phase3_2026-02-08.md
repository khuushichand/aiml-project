# Watchlists Decisions: Template UX, Media DB Export Semantics, Phase 3 Scope

Updated: 2026-02-08
Status: Accepted decisions for planning and backlog shaping

## Decision 1: Richer Template UX (Accepted)

### Decision
Ship a two-lane template UX:
- Guided lane: preset-first flow for common digest types (briefing/newsletter/MECE) with safe field toggles.
- Advanced lane: direct Jinja template editing with version history and rollback.

### Why
- Backend primitives are already present: file-backed templates, versioning, and per-job defaults.
  - `tldw_Server_API/app/core/Watchlists/template_store.py:325`
  - `tldw_Server_API/app/core/Watchlists/template_store.py:506`
  - `tldw_Server_API/app/api/v1/endpoints/watchlists.py:3742`
- Job defaults already persist template + delivery settings.
  - `tldw_Server_API/tests/Watchlists/test_job_output_prefs_roundtrip.py:32`

### Scope Outcome
- Keep Jinja2 as the single template language.
- Do not introduce a second template DSL.
- Implement UX in phases:
  - Phase A: preset selector + per-job default binding (`default_name`, `default_version`, format/retention/delivery).
  - Phase B: advanced editor polish (variable helper panel, diff/restore flow, lint/preview affordances).

## Decision 2: Media DB Aggregation-Export Clarification (Accepted)

### Decision
Treat "Media DB aggregation export" as fulfilled by current output artifact ingestion:
- Create output from run items with `POST /api/v1/watchlists/outputs`.
- Set `ingest_to_media_db=true` to persist a single artifact in Media DB with run/item linkage metadata.

### Why
- Behavior is implemented and tested:
  - Output ingest hook: `tldw_Server_API/app/api/v1/endpoints/watchlists.py:3405`
  - Media DB ingest implementation: `tldw_Server_API/app/services/outputs_service.py:371`
  - Integration test coverage: `tldw_Server_API/tests/Watchlists/test_watchlists_api.py:564`
- API docs already expose this path:
  - `Docs/API-related/Watchlists_API.md` ("Create a report from a run" with `ingest_to_media_db`).

### Scope Outcome
- No new dedicated "aggregation export" endpoint is required for v0.2.x.
- Terminology should use "Media DB artifact ingest" to avoid confusion with CSV tallies aggregation.
- Optional future enhancement: one-click "export latest run to Media DB artifact" UI action using the same existing endpoint.

## Decision 3: Phase 3 Scope (Accepted)

### Decision
Phase 3 is narrowed to platform work only:
- Forum productionization (graduate from feature-flagged/basic behavior).
- Multi-tenant watchlist sharing model (ownership, RBAC, safe cross-user access).
- Optional Postgres backend parity/hardening for Watchlists + Collections alignment.

### Why
- Forum support exists but is still feature-flagged and not productionized:
  - `tldw_Server_API/app/api/v1/endpoints/watchlists.py:783`
  - `tldw_Server_API/tests/Watchlists/test_watchlists_api.py:259`
- Postgres has baseline round-trip tests but parity/hardening is not complete:
  - `tldw_Server_API/tests/Watchlists/test_watchlists_postgres_integration.py:29`
- WS live logs are already implemented and should not remain a Phase 3 item:
  - `tldw_Server_API/app/api/v1/endpoints/watchlists.py:2703`

### Scope Outcome
- Remove WS live logs from Phase 3 backlog.
- Treat baseline TTS generation as shipped; keep only quality/polish items as separate backlog, not Phase 3 gate.
- Define Phase 3 exit criteria per stream:
  - Forums: production-ready selectors/pagination/backoff and docs.
  - Multi-tenant: explicit sharing boundaries + tests for tenant isolation.
  - Postgres: schema/API parity tests passing for key watchlists flows.

## Execution Update (2026-02-08)

- Template UX
  - Phase A job defaults UX extended with guided presets, template default format, and retention defaults.
  - Phase B editor follow-ups shipped: template version load/restore, quick-insert snippet helpers, and loaded-version drift indicator.

- Phase 3
  - Forums: default forum probe breadth is now configurable (`WATCHLIST_FORUM_DEFAULT_TOP_N`, fallback 20) and surfaced in `/watchlists/settings`.
  - Sharing model: cross-user watchlists access now has explicit mode control via `WATCHLIST_SHARING_MODE`:
    - `admin_cross_user` (default)
    - `private_only`
    - `admin_same_org` (admin cross-user only when actor/target share an org membership)
  - Postgres parity: added additional round-trip coverage for `output_prefs_json`, `job_filters_json`, and seen-state dedupe tables.
