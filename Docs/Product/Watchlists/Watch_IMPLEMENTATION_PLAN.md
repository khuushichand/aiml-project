# Watchlists v1 - Implementation Plan (Bridge PRD)

This plan tracks the remaining work to wrap Watchlists v1 per the Bridge PRD. Each stage lists goals, success criteria, and concrete test points. Update Status as work progresses.

## Current Status (snapshot)
- Core endpoints and WebUI implemented (filters CRUD, include-only gating, OPML import/export with group filter, preview, global runs, CSV exports).
- Tests added for CSV exports, OPML large/tag cases, global runs pagination/isolation, preview, YouTube normalization edges, and rate-limit headers (strict mode).
- Docs updated (API: runs/tallies/OPML examples/gating table; Product PRD; Ops runbook). 410 shim for legacy Subscriptions is live.

## Remaining To-Do (v1 sign-off)
- No additional v1 sign-off blockers tracked in this plan.
- Ongoing work remains under Stage 5 (scale/reliability).

## Stage 1: QA, Deprecations, and Docs Finalization
**Goal**: Ship Phase B wrap-up with hardened inputs, finalized docs, and visible metrics.

**Success Criteria**
- API docs include `GET /api/v1/watchlists/runs`, `include_tallies` for Run Detail, and OPML export `group` filter.
- Deprecation path finalized: all `/api/v1/subscriptions/*` return 410 with Link header and docs + release notes updated.
- YouTube normalization hardened (channel/user/playlist forms accepted and canonicalized to feeds; unsupported `@handle` and `/c/...` forms return 400; normalization headers logged in diagnostics).
- Admin Runs view shows per-run counters and supports CSV/JSON export.

**Tests**
- OPML export filtering: group, group+tag, type interactions.
  - tldw_Server_API/tests/Watchlists/test_opml_export_group.py
- YouTube normalization: create/update/bulk non-canonical inputs → normalized URL + headers.
  - tldw_Server_API/tests/Watchlists/test_youtube_normalization_more.py
- Run Detail tallies toggle returns `filter_tallies` when `include_tallies=true` and totals always present.
  - tldw_Server_API/tests/Watchlists/test_run_detail_filters_totals.py
- Optional: rate-limit headers present under non-test mode for OPML import and filters endpoints.
  - tldw_Server_API/tests/Watchlists/test_rate_limit_headers_optional.py

**Status**: Completed

---

## Stage 2: Migration Tooling (Subscriptions → Watchlists)
**Goal**: Provide an easy migration path from legacy Subscriptions to Watchlists.

**Success Criteria**
- CLI/import helper exports legacy Subscriptions as OPML + JSON filters and creates mapped Watchlists sources/jobs with filters.
- Dry-run mode prints planned changes without writing.
- Playbook doc (mapping table and fallbacks) linked from README/Docs.

**Tests**
- Unit: mapping from legacy fields → `{source, job, filters}` payloads (edge cases, unknown fields).
  - Helper_Scripts/tests/test_subscriptions_mapping.py
- Integration: sample legacy export → import → verify created sources/jobs/filters; dry-run yields no DB writes.
  - tldw_Server_API/tests/Watchlists/test_migration_import_cli.py

**Status**: Not Required (Subscriptions never shipped to prod; use OPML import)

---

## Stage 3: v1 UX Enhancements
**Goal**: Improve usability with preview/dry-run, richer filter editing, and stronger runs browsing.

**Success Criteria**
- Preview/dry-run endpoint (no ingestion) returns candidate items with matched filter metadata.
  - `POST /api/v1/watchlists/jobs/{id}/preview?limit=…` (or equivalent) returns items + reason (filter id/type/action).
- Filters editor supports reorder, enable/disable, presets, and advanced JSON textarea.
- Runs UI: global runs search/pagination, per-job pagination, tallies toggle, download log, link to items scoped by run.

**Tests**
- API: preview returns candidates and `matched_filter` indications; respects include-only gating.
  - tldw_Server_API/tests/Watchlists/test_preview_endpoint.py
- UI (lightweight): validate presence of editor controls and basic input constraints (IDs numeric, non-negative).
  - apps/tldw-frontend/tests/watchlists_ui_smoke.test.ts

**Status**: Completed

---

## Stage 4: Output & Delivery Expansions
**Goal**: Polish template authoring and wire delivery channels (email, Chatbook), with optional audio briefs.

**Success Criteria**
- Templates: CRUD with name/description/version; selectable per job; version history retained.
- Delivery: email and Chatbook paths configurable per job (subject/body, conversation target), with success/failure surfaced in run outputs.
- Optional: audio brief via TTS for small result sets.

**Tests**
- Unit: template rendering with variables and version selection.
  - tldw_Server_API/tests/Watchlists/test_templates_rendering.py
- Integration: email + Chatbook delivery using mocks; run artifacts record delivery status and IDs.
  - tldw_Server_API/tests/Watchlists/test_delivery_integrations.py
- Optional: TTS brief generated and attached when item count below threshold.
  - tldw_Server_API/tests/Watchlists/test_tts_brief_optional.py

**Status**: Completed (template version history + version-aware rendering landed; regenerate supports template version selection; delivery status is surfaced in outputs UI; job-level default email subject controls are wired in the Jobs form; optional small-run TTS brief auto-generation and delivery-default subject behavior are covered by integration tests)

---

## Stage 5: Scale & Reliability
**Goal**: Improve scheduling controls, dedup/seen visibility, and performance at higher scale.

**Success Criteria**
- Scheduler UX: concurrency, per-host delay, backoff controls; show next/last run per job.
- Dedup/seen: expose counts and reset tools per source; admin tooling to inspect/clear.
- Performance: validated on large filter sets, many sources, and long OPML imports; document limits and recommended settings.

**Tests**
- Scheduling: concurrency/backoff honored; next/last timestamps updated correctly.
  - tldw_Server_API/tests/Watchlists/test_scheduler_controls.py
- Dedup/seen: counts accurate; reset clears state safely; no duplicate ingestion after reset.
  - tldw_Server_API/tests/Watchlists/test_dedup_seen_tools.py
- Performance (sanity): marked `perf` scenarios for large inputs complete within budget.
  - tldw_Server_API/tests/Watchlists/test_perf_scenarios.py
- Rate-limit headers deterministic under non-test mode with configured backend.
  - tldw_Server_API/tests/Watchlists/test_rate_limit_headers_strict.py

**Status**: Complete (dedup/seen inspect-reset API + DB support shipped; scheduler controls and broader scale validation tests added; operational limits boundary tests + admin UI surfacing for dedup/seen completed; verification rerun on 2026-02-08: Stage-5 backend slice `40 passed`, SourceSeenDrawer UI tests `14 passed`; AuthNZ usage aggregation sqlite-corruption logging hardened with one-time warning + skip behavior and dedicated tests)

Stage 5 scale target matrix is tracked in:
- `Docs/Product/Completed/Watchlists_Subscriptions_Migration_Runbook.md` (all 5 stages complete)

---

## Notes
- Include-only gating: default can be set per-org (and via env); tests should cover both job-flag and org-default paths.
- Keep tests deterministic; mock external services (feeds, email, Chatbook, TTS). Mark performance tests with `@pytest.mark.perf`.
- Update Docs/API-related/Watchlists_API.md and Docs/Published/RELEASE_NOTES.md alongside code changes.

### Operational Limits (enforced via Pydantic Query constraints)

| Endpoint | Parameter | Max | Rejection |
|---|---|---|---|
| `/sources`, `/jobs`, `/runs`, `/tags`, `/groups` | `size` | 200 | 422 |
| `/jobs/{id}/preview` | `limit` | 200 | 422 |
| `/jobs/{id}/preview` | `per_source` | 100 | 422 |
| `/runs/export.csv` | `size` | 1000 | 422 |
| `/runs/export.csv` (aggregate tallies) | `scope` | must be `global` | 400 |
| `/sources/{id}/seen` (target_user_id) | auth | admin required | 403 |

Checklist (quick)
- [x] CSV export tests (global/by-job + tallies; headers/rows)
- [x] OPML export tests (multi-group OR + tag AND; large set; tag case-insensitivity)
- [x] Global runs API tests (q search, pagination boundaries, user isolation)
- [x] Docs polish (gating table, OPML examples, regex flags note, Admin Items/CSV)
- [x] Preview endpoint tests (RSS + site; include-only on/off)
- [x] Rate-limit headers strict test (non-test mode via monkeypatch)
- [x] Verify Runs role gating against real user object (or disable via env)
- [x] Optional: CSV include_tallies aggregation mode (API + UI)
- [x] Stage 5: scheduler controls focused tests (`test_scheduler_controls.py`)
- [x] Stage 5: dedup/seen inspect-reset tools + tests (`test_dedup_seen_tools.py`)
- [x] Stage 5: performance sanity test scaffold (`test_perf_scenarios.py`)
- [x] Stage 5: high-cardinality source/job performance coverage (`test_perf_scenarios.py`)
- [x] Stage 5: runs/export/details API load validation (`test_watchlists_scale_load_api.py`)
- [x] Stage 5: operational limits boundary tests (`test_operational_limits.py`)
- [x] Stage 5: admin UI dedup/seen drawer (`SourceSeenDrawer.tsx` + component tests)
- [x] Stage 5: AuthNZ usage aggregation sqlite-corruption warning hardening + tests (`test_authnz_usage_repo_corruption_sqlite.py`)
- [x] Stage 5: strict rate-limit header tests made rerun-safe via isolated temp DB base path (`test_rate_limit_headers_strict.py`)
