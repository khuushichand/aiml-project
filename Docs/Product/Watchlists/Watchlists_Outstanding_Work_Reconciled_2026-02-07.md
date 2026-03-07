# Watchlists Outstanding Work (Reconciled)

Updated: 2026-02-07  
Scope audited:
- `Docs/Product/Watchlists/Watch_IMPLEMENTATION_PLAN.md`
- `Docs/Product/Watchlists/Watchlist_PRD.md`
- `Docs/Product/Watchlists/Watchlists_Filters.md`
- `Docs/Product/Watchlists/Watchlists_Remaining_Checklist.md`
- `Docs/Product/Watchlists/Watchlists_Subscriptions_Bridge_PRD.md`

## Claim Audit Summary

- `Watch_IMPLEMENTATION_PLAN.md`: mostly accurate on completion status, but one policy line is stale.
  - It says handles/vanity are accepted and canonicalized (`Docs/Product/Watchlists/Watch_IMPLEMENTATION_PLAN.md:20`).
  - Current code/tests reject those forms with `invalid_youtube_rss_url` (`tldw_Server_API/app/api/v1/endpoints/watchlists.py:767`, `tldw_Server_API/tests/Watchlists/test_youtube_normalization_more.py:333`).

- `Watchlist_PRD.md`: partially stale.
  - It lists preview and WS stream as "Not yet implemented" (`Docs/Product/Watchlists/Watchlist_PRD.md:191`), but both are implemented:
  - Preview endpoint exists (`tldw_Server_API/app/api/v1/endpoints/watchlists.py:1846`).
  - WS stream endpoint exists (`tldw_Server_API/app/api/v1/endpoints/watchlists.py:2703`).

- `Watchlists_Filters.md`: stale status and endpoint lifecycle text.
  - Status still "In Progress" (`Docs/Product/Watchlists/Watchlists_Filters.md:3`).
  - Endpoints marked "planned" (`Docs/Product/Watchlists/Watchlists_Filters.md:97`), but are implemented (`tldw_Server_API/app/api/v1/endpoints/watchlists.py:2299`, `tldw_Server_API/app/api/v1/endpoints/watchlists.py:2321`).

- `Watchlists_Remaining_Checklist.md`: several unchecked items are already delivered or superseded.
  - Unchecked items at `Docs/Product/Watchlists/Watchlists_Remaining_Checklist.md:6` to `Docs/Product/Watchlists/Watchlists_Remaining_Checklist.md:12`.
  - Evidence for completed items:
  - OPML multi-group OR + tag AND + unknown group tests: `tldw_Server_API/tests/Watchlists/test_opml_export_group_more.py:48`.
  - Admin org search edge tests: `tldw_Server_API/tests/Admin/test_admin_orgs_search_edge.py:1`.
  - Site include-only e2e: `tldw_Server_API/tests/Watchlists/test_site_include_only_gating.py:1`.
  - Strict rate-limit header tests: `tldw_Server_API/tests/Watchlists/test_rate_limit_headers_strict.py:1`.
  - Migration CLI item is explicitly superseded by "not required" guidance (`Docs/Operations/Watchlists_Migration_Notes.md:3`).

- `Watchlists_Subscriptions_Bridge_PRD.md`: generally consistent.
  - It correctly marks no blocking in-progress work (`Docs/Product/Watchlists/Watchlists_Subscriptions_Bridge_PRD.md:59`).
  - It leaves an optional resolver as remaining (`Docs/Product/Watchlists/Watchlists_Subscriptions_Bridge_PRD.md:62`), which is still not implemented (server rejects handle/vanity URLs: `tldw_Server_API/app/api/v1/endpoints/watchlists.py:770`).

## Outstanding Work To Do

## 1) Documentation Reconciliation (Immediate)

- [x] Align YouTube policy wording in `Watch_IMPLEMENTATION_PLAN.md` with current behavior (reject `@handle` and `/c/...` forms; canonicalize only supported URL types).
- [x] Update stale "Not yet implemented" section in `Watchlist_PRD.md` (preview endpoint and WS stream are implemented).
- [x] Update `Watchlists_Filters.md` status and endpoint section from "planned" to implemented.
- [x] Reconcile `Watchlists_Remaining_Checklist.md` with shipped coverage:
  - mark completed: OPML export edge tests, admin org edge tests, site include-only e2e, docs polish follow-ups, runs CSV/rich metrics polish, strict rate-limit tests.
  - mark migration CLI as "Not Required" (or move to explicitly deferred backlog).
- [x] Fix stale API doc path references to the current location (`Docs/API-related/Watchlists_API.md`).

## 2) Product/Engineering Backlog (Confirmed Open or Optional)

- [ ] Optional: implement server-side YouTube resolver for `@handle`/vanity URLs (currently out-of-scope for v1, still called out as a nice-to-have).
  - Source: `Docs/Product/Watchlists/Watchlists_Subscriptions_Bridge_PRD.md:62`.
- [x] Decision made: ship richer template UX as a two-lane model (guided presets + advanced Jinja editor), while reusing existing template/version APIs and per-job defaults.
  - Decision log: `Docs/Product/Watchlists/Watchlists_Decisions_TemplateUX_MediaDB_Phase3_2026-02-08.md`.
- [x] Clarification made: "Media DB aggregation export" is fulfilled by current output artifact ingest flow (`POST /watchlists/outputs` + `ingest_to_media_db=true`); no separate endpoint required for v0.2.x.
  - Decision log: `Docs/Product/Watchlists/Watchlists_Decisions_TemplateUX_MediaDB_Phase3_2026-02-08.md`.
- [x] Phase-3 scope decision made: focus on forum productionization, multi-tenant sharing, and optional Postgres parity/hardening; remove WS logs from Phase-3 backlog.
  - Decision log: `Docs/Product/Watchlists/Watchlists_Decisions_TemplateUX_MediaDB_Phase3_2026-02-08.md`.

Decision-derived implementation follow-ups (still open):
- [ ] Implement Template UX Phase A (preset selector + per-job defaults UX wiring).
- [ ] Implement Template UX Phase B polish (advanced editor helpers, preview/lint affordances, version diff/restore UX).
- [ ] Execute Phase-3 streams (forums productionization, sharing model, Postgres parity) with explicit acceptance criteria.

## 3) Explicitly Not Outstanding (Closed or Superseded)

- Subscriptions migration CLI is not required for production (subscriptions never shipped); migration path is OPML + job filters.
  - `Docs/Operations/Watchlists_Migration_Notes.md:3`
  - `Docs/Product/Watchlists/Watch_IMPLEMENTATION_PLAN.md:51`
- Stage 5 scale/reliability matrix is complete per its own plan document.
  - `Docs/Product/Completed/Watchlists_Subscriptions_Migration_Runbook.md:1`
