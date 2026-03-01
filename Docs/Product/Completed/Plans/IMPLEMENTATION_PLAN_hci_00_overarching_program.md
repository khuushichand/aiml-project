# Implementation Plan: Admin UI HCI Review - Overarching Program Oversight

## Scope

Provide one control plan to oversee implementation sequencing, quality gates, and release readiness for the Admin UI HCI/Design Expert Review remediation across 10 sub-plans covering 82 findings.

### Source Report
- `IMPLEMENTATION_PLAN_admin_ui_hci_findings_2026-02-17.md` (82 findings: 13 Critical, 48 Important, 21 Nice-to-Have)

### In-Scope Plan Sequence

| # | Plan File | Findings | Stages | Phase |
|---|-----------|----------|--------|-------|
| 01 | `IMPLEMENTATION_PLAN_hci_01_dashboard_overview.md` | 1.1-1.10 (10) | 4 | B |
| 02 | `IMPLEMENTATION_PLAN_hci_02_identity_access_management.md` | 2.1-2.11 (11) | 4 | C |
| 03 | `IMPLEMENTATION_PLAN_hci_03_api_key_secret_management.md` | 3.1-3.6 (6) | 3 | B |
| 04 | `IMPLEMENTATION_PLAN_hci_04_ai_model_governance.md` | 4.1-4.7 (7) | 4 | B |
| 05 | `IMPLEMENTATION_PLAN_hci_05_operational_monitoring.md` | 5.1-5.10 (10) | 4 | D |
| 06 | `IMPLEMENTATION_PLAN_hci_06_governance_compliance.md` | 6.1-6.9 (9) | 4 | D |
| 07 | `IMPLEMENTATION_PLAN_hci_07_data_operations.md` | 7.1-7.5 (5) | 3 | E |
| 08 | `IMPLEMENTATION_PLAN_hci_08_cross_cutting_ux.md` | 8.1-8.10 (10) | 3 | A |
| 09 | `IMPLEMENTATION_PLAN_hci_09_information_architecture.md` | 9.1-9.9 (9) | 4 | D |
| 10 | `IMPLEMENTATION_PLAN_hci_10_accessibility.md` | 10.1-10.7 (7) | 3 | A |

All plans live under `Docs/Plans/`.

---

## Oversight Model

- **Phase-level control**: One active phase at a time. Plans within a phase may run in parallel where independent.
- **Entry gate**: Predecessor phase reaches all stage success criteria with test evidence captured.
- **Exit gate**: All plans in the phase have updated status, tests pass, and regressions are checked.
- **Cross-reference**: Plan 08 (8.1) and Plan 10 (10.1) both cover skip-to-main-content link. Plan 10 owns the implementation; Plan 08 references it.
- **Backend dependency tracking**: Plans that require new backend endpoints are flagged. If a backend endpoint is unavailable, the frontend work proceeds with mocked data and a TODO annotation.

---

## Phase A: Accessibility & UX Foundation

**Goal**: Fix foundational UX and accessibility issues that affect every page before making page-specific improvements.

**Plans in phase**:
1. Plan 10: `IMPLEMENTATION_PLAN_hci_10_accessibility.md` -- Stage 1 (skip link + form errors)
2. Plan 08: `IMPLEMENTATION_PLAN_hci_08_cross_cutting_ux.md` -- Stage 1 (skip link ref + sticky headers + button loading)

**Rationale**: These are the quickest wins with the broadest impact. Every subsequent phase benefits from sticky table headers, button loading states, and skip links being in place.

**Success Criteria**:
- Skip-to-main-content link renders on all pages and is keyboard-accessible.
- All `<TableHeader>` elements are sticky.
- `Button` component supports `loading` prop; at least 5 high-traffic mutation buttons converted.
- Form error announcements (`aria-invalid` + `aria-describedby`) present on user create, org create, and policy create forms.
- All tests from Plan 08 Stage 1 and Plan 10 Stage 1 pass.

**Quality Gate**:
- `cd admin-ui && bun run lint` -- ESLint passes for admin-ui.
- `cd admin-ui && bunx vitest run` -- full admin-ui test suite passes.
- `cd admin-ui && bun run build` -- production build succeeds.
- Manual keyboard-only walkthrough of dashboard, users, and monitoring pages.

**Status**: Complete

---

## Phase B: Operational Intelligence & Dashboard

**Goal**: Make the dashboard an actionable operations hub and add usage/cost visibility to provider and key management pages.

**Plans in phase**:
1. Plan 01: `IMPLEMENTATION_PLAN_hci_01_dashboard_overview.md` -- All stages (1-4)
2. Plan 03: `IMPLEMENTATION_PLAN_hci_03_api_key_secret_management.md` -- Stages 1-2
3. Plan 04: `IMPLEMENTATION_PLAN_hci_04_ai_model_governance.md` -- Stage 1

**Rationale**: The dashboard is the first thing admins see. Adding KPI cards, real health checks, and usage data to the dashboard + providers + keys pages addresses the top critical gap.

**Dependencies**:
- Phase A complete (button loading states needed for new dashboard refresh patterns).
- Backend: verify `/admin/stats` exposes latency percentiles, `/admin/llm-usage/summary` supports `group_by=provider`.

**Success Criteria**:
- Dashboard StatsGrid shows 6+ cards including latency, error rate, cost burn.
- System health grid uses real health endpoints for all monitored subsystems.
- Activity chart supports 24h/7d/30d time range selection.
- `/api-keys` page shows unified key list with usage metrics.
- `/providers` page shows per-provider usage/cost columns.
- All tests from Plans 01, 03 (Stages 1-2), and 04 (Stage 1) pass.

**Quality Gate**:
- `cd admin-ui && bun run lint` -- ESLint passes for admin-ui.
- `cd admin-ui && bunx vitest run` -- full admin-ui test suite passes.
- `cd admin-ui && bun run build` -- production build succeeds.
- Dashboard loads within 3s on simulated slow connection (no waterfall blocking).

**Status**: Complete

---

## Phase C: IAM Completeness

**Goal**: Close the critical CRUD gaps in identity and access management.

**Plans in phase**:
1. Plan 02: `IMPLEMENTATION_PLAN_hci_02_identity_access_management.md` -- All stages (1-4)
2. Plan 03: `IMPLEMENTATION_PLAN_hci_03_api_key_secret_management.md` -- Stage 3 (BYOK cost + bulk ops)

**Dependencies**:
- Phase B complete (unified key list from Plan 03 Stage 1 needed before Stage 3 bulk operations).
- Backend: verify `PUT/DELETE /admin/organizations/{id}`, `PUT/DELETE /admin/teams/{id}`, `POST /admin/users/{id}/reset-password` exist.

**Success Criteria**:
- Admin can reset user passwords, edit/delete orgs, edit/delete teams.
- Permission matrix is interactive (click-to-toggle).
- Role comparison view functional.
- User list supports MFA/status filters.
- Login history visible on user detail page.
- Bulk role assignment and bulk password reset operational.
- BYOK per-user cost attribution displayed.
- All tests from Plans 02 and 03 Stage 3 pass.

**Quality Gate**:
- `cd admin-ui && bun run lint` -- ESLint passes for admin-ui.
- `cd admin-ui && bunx vitest run` -- full admin-ui test suite passes.
- `cd admin-ui && bun run build` -- production build succeeds.
- Manual walkthrough: create org → add members → create team → assign roles → edit → delete.

**Status**: Complete

---

## Phase D: Governance, Monitoring & Information Architecture

**Goal**: Make governance, monitoring, and cost management fully functional and add missing information surfaces.

**Plans in phase**:
1. Plan 04: `IMPLEMENTATION_PLAN_hci_04_ai_model_governance.md` -- Stages 2-4 (simulation, deprecation, voice test)
2. Plan 05: `IMPLEMENTATION_PLAN_hci_05_operational_monitoring.md` -- All stages (1-4)
3. Plan 06: `IMPLEMENTATION_PLAN_hci_06_governance_compliance.md` -- All stages (1-4)
4. Plan 09: `IMPLEMENTATION_PLAN_hci_09_information_architecture.md` -- Stages 1-2 (config overview, dependency health)

**Dependencies**:
- Phase C complete.
- Backend: multiple new endpoints likely needed (budget editing, alert rules, policy simulation, etc.). Catalog and prioritize before starting.

**Parallelism**: Plans 04, 05, 06, and 09 are largely independent of each other. Within the phase, they can be worked on in parallel with shared quality gates.

**Success Criteria**:
- Budget page supports editing with alert threshold wiring.
- Resource Governor has policy simulation.
- Monitoring supports custom time ranges, configurable thresholds, and expanded subsystems.
- Security risk score shows factor breakdown with remediation links.
- Audit log supports saved searches.
- Cost forecasting and per-org attribution on usage page.
- System configuration overview page exists.
- External dependency health dashboard exists.
- All tests from Plans 04 (Stages 2-4), 05, 06, 09 (Stages 1-2) pass.

**Quality Gate**:
- `cd admin-ui && bun run lint` -- ESLint passes for admin-ui.
- `cd admin-ui && bunx vitest run` -- full admin-ui test suite passes.
- `cd admin-ui && bun run build` -- production build succeeds.
- Manual walkthrough of governance flow: set budget → trigger alert → view in monitoring → acknowledge → check audit trail.

**Status**: Complete (manual governance walkthrough pending)

---

## Phase E: Advanced Features & Polish

**Goal**: Complete remaining Nice-to-Have features, advanced monitoring, data operations, and remaining information architecture gaps.

**Plans in phase**:
1. Plan 07: `IMPLEMENTATION_PLAN_hci_07_data_operations.md` -- All stages (1-3)
2. Plan 08: `IMPLEMENTATION_PLAN_hci_08_cross_cutting_ux.md` -- Stages 2-3 (breadcrumbs, empty states, mobile hints)
3. Plan 09: `IMPLEMENTATION_PLAN_hci_09_information_architecture.md` -- Stages 3-4 (endpoint heatmap, storage, queue viz)
4. Plan 10: `IMPLEMENTATION_PLAN_hci_10_accessibility.md` -- Stages 2-3 (live regions, contrast audit, captions, focus mgmt)

**Dependencies**:
- Phase D complete.
- Backend: GDPR data subject endpoints, backup scheduling, retention preview, queue depth metrics.

**Success Criteria**:
- Backup scheduling and history operational.
- Retention policies have impact preview.
- GDPR data subject request flow functional.
- Breadcrumbs on all nested pages.
- Consistent empty states across all list pages.
- Page titles set per route.
- `aria-live` regions on dynamic content.
- Dark mode contrast audit completed with all fixes applied.
- Table captions on all data tables.
- Icon-only button audit complete.
- API endpoint usage heatmap, storage breakdown, and queue visualization functional.
- All tests from remaining plan stages pass.

**Quality Gate**:
- `cd admin-ui && bun run lint` -- ESLint passes for admin-ui.
- `cd admin-ui && bunx vitest run` -- full admin-ui test suite passes.
- `cd admin-ui && bun run build` -- production build succeeds.
- `cd admin-ui && bun run test:a11y` -- axe smoke checks + contrast/icon accessibility audits pass.
- Automated accessibility audit (axe-core) reports zero critical/serious violations.
- Manual screen reader walkthrough of 5 key pages (dashboard, users, monitoring, audit, data-ops).

**Status**: Complete (manual screen reader walkthrough pending)

---

## Ordered Implementation Tracker

| Order | Plan | Stage(s) | Phase | Dependencies | Status |
|-------|------|----------|-------|--------------|--------|
| 1 | Plan 10: Accessibility | Stage 1 | A | None | Complete |
| 2 | Plan 08: Cross-Cutting UX | Stage 1 | A | Plan 10 S1 (skip link) | Complete |
| 3 | Plan 01: Dashboard Overview | Stages 1-4 | B | Phase A | Complete |
| 4 | Plan 03: API Key Management | Stages 1-2 | B | Phase A | Complete |
| 5 | Plan 04: AI Model Governance | Stage 1 | B | Phase A | Complete |
| 6 | Plan 02: IAM | Stages 1-4 | C | Phase B | Complete |
| 7 | Plan 03: API Key Management | Stage 3 | C | Plan 03 S1-2 | Complete |
| 8 | Plan 04: AI Model Governance | Stages 2-4 | D | Phase C | Complete |
| 9 | Plan 05: Operational Monitoring | Stages 1-4 | D | Phase C | Complete |
| 10 | Plan 06: Governance & Compliance | Stages 1-4 | D | Phase C | Complete |
| 11 | Plan 09: Info Architecture | Stages 1-2 | D | Phase C | Complete |
| 12 | Plan 07: Data Operations | Stages 1-3 | E | Phase D | Complete |
| 13 | Plan 08: Cross-Cutting UX | Stages 2-3 | E | Phase D | Complete |
| 14 | Plan 09: Info Architecture | Stages 3-4 | E | Plan 09 S1-2 | Complete |
| 15 | Plan 10: Accessibility | Stages 2-3 | E | Plan 10 S1 | Complete |

---

## Backend Endpoint Dependency Catalog

Before each phase begins, verify these backend endpoints exist. If missing, file a backend task and proceed with mocked data on the frontend.

### Phase A -- No backend dependencies

### Phase B
| Endpoint | Plan | Status |
|----------|------|--------|
| `GET /admin/stats` (with latency percentiles) | Plan 01 | Implemented |
| `GET /admin/llm-usage/summary?group_by=provider` | Plan 04 | Implemented |
| `GET /admin/api-keys` (aggregate across users) | Plan 03 | Frontend fallback implemented (per-user aggregation via `/admin/users/{id}/api-keys`) |
| `GET /monitoring/metrics?start=&end=&granularity=` | Plan 01 | Frontend fallback implemented (endpoint unavailable) |

### Phase C
| Endpoint | Plan | Status |
|----------|------|--------|
| `POST /admin/users/{id}/reset-password` | Plan 02 | Implemented |
| `PUT /admin/organizations/{id}` | Plan 02 | Implemented (`PATCH /orgs/{id}`) |
| `DELETE /admin/organizations/{id}` | Plan 02 | Implemented |
| `PUT /admin/teams/{id}` | Plan 02 | Implemented (`PATCH /orgs/{orgId}/teams/{id}`) |
| `DELETE /admin/teams/{id}` | Plan 02 | Implemented |
| `GET /admin/users/{id}/organizations` | Plan 02 | Implemented via `/admin/users/{id}/org-memberships` |
| `GET /admin/users/{id}/teams` | Plan 02 | Implemented via `/admin/users/{id}/team-memberships` |

### Phase D
| Endpoint | Plan | Status |
|----------|------|--------|
| `PUT /admin/budgets/{org_id}` | Plan 06 | Implemented |
| `POST /resource-governor/policy/simulate` | Plan 04 | Implemented |
| `POST /monitoring/alert-rules` | Plan 05 | Frontend fallback implemented (local alert-rule persistence) |
| `GET /health/tts`, `/health/stt`, `/health/embeddings` | Plan 05 | Frontend fallback implemented; endpoint checks used when available |
| `GET /admin/rate-limit-events` | Plan 04/09 | Implemented |

### Phase E
| Endpoint | Plan | Status |
|----------|------|--------|
| `POST /admin/backups/schedule` | Plan 07 | Frontend fallback implemented (local schedule persistence) |
| `POST /admin/retention-policies/{key}/preview` | Plan 07 | Implemented |
| `POST /admin/data-subject-requests` | Plan 07 | Implemented |
| `GET /admin/storage/breakdown` | Plan 09 | Frontend fallback implemented (`/admin/users` + `/metrics/text`) |
| `GET /admin/invitations` | Plan 09 | Frontend fallback implemented (`/orgs/{org_id}/invites` aggregation) |

---

## Finding Coverage Matrix

### By Severity
| Severity | Total | Phase A | Phase B | Phase C | Phase D | Phase E |
|----------|-------|---------|---------|---------|---------|---------|
| Critical | 13 | 1 (10.1) | 5 (1.1-1.3, 4.1, 5.1) | 3 (2.1-2.3) | 4 (6.1-6.2, 9.1-9.2) | 0 |
| Important | 48 | 3 (8.2-8.3, 10.2) | 8 | 10 | 22 | 5 |
| Nice-to-Have | 21 | 0 | 2 | 4 | 5 | 10 |
| **Total** | **82** | **4** | **15** | **17** | **31** | **15** |

### By Type
| Type | Total | Phase A | Phase B | Phase C | Phase D | Phase E |
|------|-------|---------|---------|---------|---------|---------|
| Missing Functionality | 38 | 0 | 5 | 10 | 17 | 6 |
| Information Gap | 25 | 0 | 8 | 3 | 9 | 5 |
| UX/Usability Issue | 14 | 2 | 2 | 3 | 3 | 4 |
| Accessibility Concern | 5 | 2 | 0 | 1 | 2 | 0 |

---

## Program Risks and Controls

| Risk | Impact | Control |
|------|--------|---------|
| Backend endpoints missing for frontend features | Blocks full functionality | Catalog endpoints per phase; mock missing endpoints; file backend tasks early |
| Regression from broad shared component changes (Phase A) | Breaks existing pages | Full admin-ui test suite + build gate after every shared component change |
| Phase D scope creep (31 findings, 4 parallel plans) | Delays completion | Enforce strict phase boundaries; defer Nice-to-Have items to Phase E if behind |
| Accessibility fixes conflict with existing styles | Visual regressions | Snapshot tests for any CSS variable changes; paired visual review |
| Cross-reference confusion (skip link in Plans 08 + 10) | Duplicate work | Plan 10 owns implementation; Plan 08 references. Documented in both plans |
| Stale plan status | Coordination failures | Status updated in plan file immediately upon stage completion; overarching tracker updated at phase gates |

---

## Progress Log

*(Updated at each phase gate)*

**2026-02-17**: Program initialized. 10 sub-plans created covering 82 findings across 5 phases. All plans at "Not Started" status. Backend dependency catalog compiled. Phase A ready to begin (no backend dependencies).

**2026-02-17**: Phase A kickoff started. Implemented shared UI foundations in `admin-ui`: skip-to-main-content link in `ResponsiveLayout`, sticky `TableHeader`, `Button` loading state API, initial conversion of high-traffic mutation buttons, and first pass of form error announcement semantics (`aria-invalid`, `aria-describedby`, `role="alert"`). Unit test coverage added for new shared behaviors.

**2026-02-17**: Phase B started. Plan 01 Stage 1 completed: dashboard `StatsGrid` now includes operational KPI cards (latency p95, error rate, daily LLM cost, jobs/queue), resilient `N/A` fallbacks, trend indicators, and supporting tests/snapshots.

**2026-02-17**: Plan 01 Stage 2 completed: dashboard system health now uses live health endpoints (`/health`, `/llm/health`, `/rag/health`) plus subsystem checks for TTS/STT/embeddings/cache, with last-checked timestamps and severity-based alerts breakdown (critical/warning/info). Added unit/component tests for health normalization, endpoint-failure rendering, and mixed-severity alert styling.

**2026-02-17**: Plan 01 Stage 3 completed: dashboard activity now supports range selector (`24h`, `7d`, `30d`) with range-specific fetch granularity, and Recent Activity now renders 10 entries with severity icon, resource badge, username fallback, and expandable details. Added tests for range selector interactions, granularity transforms, and expanded activity details. HCI plan quality-gate command strings were also normalized to Bun-based variants.

**2026-02-17**: Plan 01 Stage 4 completed: dashboard now surfaces queue summary as active/queued/failed from `/jobs/stats`, uptime percentage and last-incident timestamp from `/admin/incidents`, and RAG cache hit rate in System Health using `/rag/health` with `/metrics/text` fallback parsing. Added tests for queue summary rendering, uptime calculation from incident windows, and Prometheus cache hit-rate parsing.

**2026-02-17**: Plan 03 Stage 1 completed: `/api-keys` now renders a unified cross-user key inventory via client-side aggregation (`/admin/users` paged + `/admin/users/{id}/api-keys?include_revoked=true`) with required columns (Key ID, Owner, Created, Last Used, Status, Request Count 24h, Error Rate 24h), plus filters (owner, status, created-before), prefix/owner search, and row links to per-user key management pages. Added unit tests for mixed-status table rendering, filter/search combinations, and metric-unavailable fallback behavior.

**2026-02-17**: Plan 03 Stage 2 completed: `/api-keys` now includes key hygiene indicators (age badges with <90/90-180/>180 thresholds, expiration countdown badges for <30/<7 day windows, and inactive >30d warning badges), plus page-level summary cards for keys needing rotation, expiring soon, inactive keys, and a computed hygiene score. Added unit tests for threshold calculations, expiry countdown formatting, and hygiene summary scoring.

**2026-02-17**: Plan 03 Stage 3 completed: `/api-keys` now supports bulk key rotation from unified selection (row/select-all checkboxes, confirmation dialog, batch rotate calls, loading state + success/failure toasts), and `/byok` now includes a per-user BYOK usage section (user/provider/key hint + requests/tokens/cost) by correlating user BYOK key inventory with recent LLM usage logs. Removed dead validation-sweep button in favor of explicit backend dependency messaging. Added page tests for BYOK usage rendering and bulk rotation confirmation flow; full Bun quality gates pass.

**2026-02-17**: Plan 02 Stage 1 completed: added admin password reset (`POST /admin/users/{id}/reset-password`) with force-password-change metadata updates, surfaced reset controls on user detail (including one-time temporary password display), and added org/team edit-delete CRUD flows with confirmation dialogs and member-count acknowledgement on list/detail pages. Added tests for password reset action, org edit/delete validation/confirmation, and team edit/delete flows. Verified quality gates with `bun run lint`, `bunx vitest run`, and `bun run build` in `admin-ui`.

**2026-02-17**: Plan 02 Stage 2 completed: `/roles/matrix` now supports interactive permission toggles with staged multi-edit changes, unsaved-cell highlighting, and batch save/discard controls; new `/roles/compare` page provides 2-3 role side-by-side permission diffs with green/red highlighting for asymmetric grants; and role detail quick actions now include a "Compare with..." entry point. Added matrix toggle/batch-save tests, role comparison diff-calculation unit tests, and snapshot coverage for the comparison table highlighting.

**2026-02-17**: Plan 02 Stage 3 completed: `/users` now supports combined filters for Active/Inactive status, MFA enabled/disabled, and verification state with AND logic alongside search; bulk actions expanded to include role assignment, password resets, and MFA requirement toggles with standardized per-action loading states on the shared `Button` API; and `/users/{id}` now includes a Login History table (last 20 `action=login` audit events with timestamp, IP, user agent, and success/failure badges). Added/updated tests for filter API parameter construction, filter+search integration behavior, bulk role/password/MFA actions, and login history rendering.

**2026-02-17**: Remaining overarching phase quality-gate command blocks were normalized to Bun command forms by adding `bun run lint` alongside existing `bunx vitest run` and `bun run build` commands for each phase gate.

**2026-02-17**: Plan 02 Stage 4 completed: team detail now supports inline team-member role updates (`member`/`lead`/`admin`) with save controls; user detail quick actions now provide working organization and team membership dialogs (including org context for team memberships) via scoped admin endpoints; and effective permissions now render explicit source badges (`Role: <name>`, `Direct override`, `Inherited`). Added backend support for `PATCH /admin/teams/{team_id}/members/{user_id}` and `GET /admin/users/{user_id}/team-memberships`, plus unit tests for team-role updates, membership list rendering, and permission-source annotation. Re-verified admin-ui quality gates with `bun run lint`, `bunx vitest run`, and `bun run build`.

**2026-02-17**: Plan 04 Stage 1 completed: `/providers` now includes 7-day provider usage columns (requests, total tokens, cost, error rate) sourced from `/admin/llm-usage/summary?group_by=provider`, plus expandable per-model breakdown rows (requests, input/output/total tokens, cost, avg latency, error rate) sourced from `/admin/llm-usage` and aggregated client-side. Added provider deep links to `/usage?group_by=provider&provider=<name>` and updated `/usage` to honor this filter in the LLM summary view. Added tests for provider-row expansion, compact number/cost formatting, and summary-endpoint fallback (`—`). Re-ran `bun run lint`, `bunx vitest run`, and `bun run build` in `admin-ui`.

**2026-02-17**: Plan 04 Stage 2 completed: `/resource-governor` now includes policy simulation (backend attempt with client-estimate fallback) showing “Would affect X users / Y requests in last 24h,” a new Policy Resolution tool (user ID + resource type) with evaluation-chain explanation and winner selection by highest priority, and an Affected Users count column per policy row. Scope context is derived from paged admin users, org memberships, and last-24h LLM usage. Added Stage 2 tests for simulation display, resolution chain rendering, and affected-user counts; re-ran `bun run lint`, `bunx vitest run`, and `bun run build` in `admin-ui`.

**2026-02-17**: Plan 04 Stage 3 completed: `/providers` now flags deprecated models with orange "Deprecated" badges backed by a client-side deprecated-model configuration and click-through migration guidance that includes last-7-day request usage for the deprecated model family; `/resource-governor` now includes a "Rate Limit Events" section showing user/role actor, policy, rejection count, and last rejection timestamp, sourced from `/admin/rate-limit-events` when available with `/metrics/text` parsing fallback. Added tests for deprecated badge/dialog behavior, rate limit events table rendering, and a snapshot test for deprecated model configuration. Re-ran `bun run lint`, `bunx vitest run`, and `bun run build` in `admin-ui`. Verified remaining HCI quality-gate command strings are Bun-based.

**2026-02-17**: Plan 04 Stage 4 completed: `/voice-commands/[id]` now includes a client-side "Test Command" panel that evaluates sample text against trigger phrases with fuzzy matching confidence and best-phrase reporting; `/providers` now shows 7-day per-provider token sparklines sourced from `/admin/llm-usage/summary?group_by=provider&group_by=day`. Backend summary support was extended to accept up to two `group_by` values plus optional `provider` filter with new `group_value_secondary` response field. Added unit tests for voice-command matching logic, provider trend aggregation/sparkline rendering, and backend endpoint coverage for multi-group summary queries. Re-ran `bunx vitest run` (targeted), `bun run lint`, `bun run build` in `admin-ui`, and `python -m pytest tldw_Server_API/tests/Admin/test_llm_usage_endpoints.py -q`.

**2026-02-17**: Plan 05 Stage 1 completed: `/monitoring` now includes time-range controls (`1h`, `6h`, `24h`, `7d`, `30d`, `Custom`) with custom start/end date-time inputs and validation (`start < end`), expanded chart series (CPU, memory, disk usage, throughput, active connections, queue depth), per-series legend toggles, and dual y-axes for percent vs count metrics. The UI now attempts `/monitoring/metrics?start=&end=&granularity=` for range-aware history and falls back to synthesized history from existing health/metrics endpoints when unavailable. Added tests for range parameter construction, custom-range validation, series-toggle behavior, and multi-axis rendering; re-ran `bun run lint`, `bunx vitest run`, and `bun run build` in `admin-ui`.

**2026-02-17**: Plan 05 Stage 2 completed: `/monitoring` now includes a new Alert Rules section with threshold rule creation (metric, operator, threshold, duration, severity) and local persistence fallback while `/monitoring/alert-rules` is unavailable. Alerts management now supports assignment via user dropdown, snooze actions with `15m`/`1h`/`4h`/`24h` options, critical escalation, snoozed-alert filtering via "Show snoozed (N)", and an alert history timeline including resolved/dismissed state changes. Added tests for alert-rule validation, snooze countdown formatting, assignment dropdown behavior, and history timeline rendering; re-ran `bun run lint`, `bunx vitest run`, and `bun run build` in `admin-ui`.

**2026-02-17**: Plan 05 Stage 3 completed: `/monitoring` System Status now covers 9 subsystems (API, Database, LLM, RAG, TTS, STT, Embeddings, Cache, Queue) with status badges, last-checked timestamps, and response-time display. Health evaluation now prefers timed subsystem endpoint checks and falls back to parsed `/metrics/text` snapshots when endpoints are unavailable. `/incidents` now supports assignment via admin user selector and resolved-incident post-mortem fields (root cause, impact, action items checklist) with local workflow persistence and timeline-event writes. Added tests for monitoring fallback/status rendering and incident assignment/post-mortem workflows; re-ran `bun run lint`, `bunx vitest run`, and `bun run build` in `admin-ui`.

**2026-02-17**: Plan 05 Stage 4 completed: `/logs` now supports regex-mode search with explicit valid/invalid pattern messaging, clickable request-ID correlation filtering, and row-level "View correlated logs" actions for cross-service request tracing. `/jobs` now includes a dependency panel that renders parent/child relationships detected in the current result set plus a "Related Jobs" section in the job detail modal (parent/child links with unresolved reference badges when related records are out of scope). Added page tests for regex validation, request-id filter actions, dependency-row rendering, and job-detail related-jobs behavior; re-ran `bun run lint`, `bunx vitest run`, and `bun run build` in `admin-ui`.

**2026-02-17**: Plan 06 Stage 1 completed: `/budgets` is now editable with per-org edit actions, cap validation, per-metric threshold and enforcement controls, and hard-enforcement confirmation before save. Added notification-channel wiring status from monitoring notification settings and removed read-only messaging. Added `PUT /api/v1/admin/budgets/{org_id}` backend endpoint support (self-update payload conversion into existing upsert flow), updated client call path with `PUT` primary + `POST` fallback, and expanded budget page tests for edit/validation/confirmation flows. Re-verified `admin-ui` quality gates with `bun run lint`, `bunx vitest run`, and `bun run build`; backend integration coverage was added but is skipped in this local run when PostgreSQL fixture provisioning is unavailable.

**2026-02-17**: Plan 06 Stage 2 completed: `/security` now includes a weighted risk-factor breakdown (users without MFA, API keys >180 days, failed logins, suspicious activity) with explicit per-factor contribution math and remediation links; `/audit` now includes saved-search CRUD (localStorage v1), clickable saved-search pills, and per-search “alert on pattern” toggles that poll for new matches and raise in-app notifications with monitoring notification-test fallback. Added page tests for risk-breakdown rendering/remediation links and audit saved-search CRUD/alert behavior. Re-verified `admin-ui` quality gates with `bun run lint`, `bunx vitest run`, and `bun run build`.

**2026-02-17**: Plan 06 Stage 3 completed: `/usage` now includes a forecast card with 7/30/90-day spend projections based on linear regression over daily LLM cost history, confidence bands (low/expected/high), trend diagnostics (monthly run-rate, slope/day, R²), and monthly budget exceed-date warnings when projections cross configured caps. Added organization as a usable grouping dimension in the LLM summary selector (implemented via user-summary aggregation), plus a dedicated per-organization attribution table (org name, requests, total tokens, cost, % of total) with links to organization detail pages. Added new unit tests for forecast math (`admin-ui/lib/usage-forecast.test.ts`) and page-level tests for forecast/per-org rendering (`admin-ui/app/usage/__tests__/page.test.tsx`). Re-verified `admin-ui` quality gates with `bun run lint`, `bunx vitest run`, and `bun run build`.

**2026-02-17**: Plan 06 Stage 4 completed: `/flags` now supports rollout percentage (`0-100`), targeted user-ID lists, and optional variant values in the create/update form; flag rows now render rollout progress bars and variant/target summaries; and history now includes before/after change diffs for scope, targeting, rollout, variant, and enabled state. `/audit` now includes a compliance report generator with report type + date-range controls and downloadable formatted HTML output containing period, total events, events by category, user activity summary, and anomaly highlights. Added/updated tests for rollout input/progress, target-list validation, compliance report trigger/download, and change-diff rendering. Re-verified `admin-ui` quality gates with `bun run lint`, `bunx vitest run`, and `bun run build`. Remaining HCI quality-gate command blocks were re-checked and remain Bun-based.

**2026-02-17**: Plan 09 Stage 1 completed: `/config` was refactored from editable setup controls into a read-only system configuration overview with six sections (Authentication, Storage, Features, Providers, Services, Server) sourced from `/health`, `/admin/stats`, `/admin/feature-flags`, and `/llm/providers`, including management deep links and resilient missing-data fallbacks. Added new config-page unit coverage for full-data and unavailable-data states plus a navigation grouping assertion for `/config` under Advanced. Re-verified `admin-ui` quality gates with `bun run lint`, `bunx vitest run`, and `bun run build`.

**2026-02-17**: Plan 09 Stage 2 completed: added a dedicated `/dependencies` dashboard that lists configured LLM providers with load-time reachability checks, last-checked timestamps, response times, 24-hour error-rate summaries, per-provider "Test" actions using the existing `/admin/llm/providers/test` flow, and red-row highlighting for unreachable providers with "time since last successful response" display. Added a 7-day availability sparkline column gated by Prometheus metrics presence, wired the page into Operations navigation, and added unit tests for grid rendering, connectivity test updates, and unreachable highlighting. Re-verified `admin-ui` quality gates with `bun run lint`, `bunx vitest run`, and `bun run build`.

**2026-02-18**: Plan 09 Stage 3 completed: `/usage` now includes an `Endpoints` tab with sortable/filterable per-endpoint HTTP metrics (endpoint, method, requests, avg latency, error rate, p95) parsed from `/metrics/text`; a storage breakdown section with top-10 per-user storage consumers plus media-type upload-volume bars; and a rate-limit monitoring table with 24h/7d rejection counts, last rejection timestamp, source badge, and top-throttled highlighting. Added parser utilities/tests in `admin-ui/lib/usage-insights.ts`, expanded rate-limit normalization to include 7-day counts, and added page-level tests for endpoint sorting/filtering plus storage and rate-limit rendering. Re-verified `admin-ui` quality gates with `bun run lint`, `bunx vitest run`, and `bun run build`.

**2026-02-18**: Plan 09 Stage 4 completed: `/users` now includes an Invitations section with mixed-status rows (sent/accepted/expired), invitation funnel KPIs (total sent, accepted, conversion rate), and cross-org invite aggregation fallback via `/orgs/{org_id}/invites`; `/jobs` now includes a 24-hour queue-depth chart plus throughput KPIs (completed jobs/hour, average processing time); and `/monitoring` notifications now include a delivery dashboard (total sent, delivery rate, failure rate, channel split for email/slack/webhook/discord) with failed-notification error details and retry actions. Added unit coverage for invitation rendering/funnel, queue depth chart/throughput surfaces, and notification delivery+retry behavior. Re-verified `admin-ui` quality gates with `bun run lint`, `bunx vitest run`, and `bun run build`. Re-audited HCI plan quality-gate command blocks; all remain Bun-based.

**2026-02-18**: Plan 07 Stage 1-2 completed: `data-ops` backups now include a Schedule tab with local schedule CRUD (create/edit/pause/resume/delete), status icons, failed-backup error surfacing, and a filterable Backup History table (last 20 with status/dataset/duration). Retention policies now require impact preview before save, render explicit estimated deletion counts, and gate save behind an explicit “I understand” checkbox. Encryption key rotation now uses a 3-step wizard (confirm, progress with batch status, completion summary), persists running/completed state across refresh via local storage, and records rotation history (timestamp, records affected, initiated by). Added targeted component tests in `admin-ui/components/data-ops/BackupsSection.test.tsx`, `admin-ui/components/data-ops/RetentionPoliciesSection.test.tsx`, and `admin-ui/components/data-ops/MaintenanceSection.test.tsx`; re-ran targeted data-ops Vitest suite with all tests passing.

**2026-02-18**: Plan 07 Stage 3 completed: `data-ops` now includes a Data Subject Requests section with request-type form controls (export/erasure/access), erasure category preview + selection + irreversible-action confirmation, access-summary rendering, export archive generation, and request-log tracking (requested time, type, requester, status, completion time) persisted locally when backend endpoints are unavailable. `BackupsSection` now includes a storage-trending visualization for the last 10 backups per dataset and per-dataset monthly growth-rate text. Added Stage 3 tests in `admin-ui/components/data-ops/DataSubjectRequestsSection.test.tsx` and expanded `admin-ui/components/data-ops/BackupsSection.test.tsx` for growth-rate assertions. Re-ran targeted data-ops Vitest suite (`BackupsSection`, `RetentionPoliciesSection`, `MaintenanceSection`, `DataSubjectRequestsSection`) with all tests passing.

**2026-02-18**: Plan 08 Stage 2-3 completed: added route-aware breadcrumbs and route-title generation (`buildBreadcrumbs`, `getPageTitleForPath`) with a new `Breadcrumbs` component rendered automatically from `ResponsiveLayout` on nested/detail routes; `ResponsiveLayout` now sets `document.title` as `{Page Name} | Admin Dashboard`. Standardized list empty-state UX across target pages (`users`, `organizations`, `teams`, `api-keys`, `jobs`, `incidents`, `logs`, `voice-commands`) using the shared `EmptyState` component with contextual copy and primary CTAs. Added mobile table overflow hints by enhancing `Table` with dynamic left/right scroll shadows. Added keyboard-shortcut discoverability with persistent sidebar hint text and a once-per-user dismissible shortcuts tip banner (`Tip: Use keyboard shortcuts for faster navigation. Press Shift+? for help.`). Confirm-dialog usage remains provider-based; standalone `ConfirmDialog` is now explicitly deprecated in code comments. Re-verified targeted quality with `bunx vitest run` across navigation, breadcrumbs, responsive layout, table, confirm-dialog, and impacted page test suites (12 files, 40 tests, all passing).

**2026-02-18**: Plan 10 Stages 2-3 completed: added/verified live-region announcements on dashboard stats, monitoring alert counts, monitoring system-status grid, and jobs queue stats; added dark-mode contrast regression checks (`admin-ui/app/__tests__/dark-mode-contrast.test.ts`) and updated dark `--border`/`--input` tokens in `admin-ui/app/globals.css` to satisfy 3:1 UI contrast. Completed Stage 3 by enhancing `Table` to support explicit captions and auto-generate descriptive sr-only captions (header summary + row count) for uncaptioned tables, implementing route-change focus handoff to `#main-content`, and adding an icon-only button audit gate (`admin-ui/app/__tests__/icon-button-audit.test.ts`) plus targeted `aria-label` fixes on team member action buttons. Re-verified with `bun run lint`, targeted `bunx vitest run` suites (41 tests), and `bun run build` in `admin-ui`. Re-audited HCI plan quality-gate command blocks; no non-Bun frontend gate commands remain.

**2026-02-18**: Accessibility quality-gate automation expanded with an axe-core smoke harness and explicit execution script: added `admin-ui/test-utils/axe.ts`, dashboard/users/monitoring/audit/data-ops axe smoke coverage (`dashboard.a11y`, users/monitoring/audit page tests, and `data-ops` a11y test), and `bun run test:a11y` in `admin-ui/package.json`. The harness exposed and closed two critical issues (unlabeled dashboard registration toggles, unlabeled users saved-view select). Overarching dependency catalog statuses were reconciled from stale `TBD` markers to implemented/fallback states. Phase D and E statuses are now marked complete with explicit notes that manual walkthrough validations remain as release-signoff tasks.

**2026-02-18**: Plan 10 Stages 2-3 moved forward: added container-level live region announcements for dashboard stats, monitoring alert counts, monitoring system-health grid, and jobs queue stats; added assertive health announcements when degraded statuses are present; and added automated dark-mode contrast regression checks with token snapshot coverage (`admin-ui/app/__tests__/dark-mode-contrast.test.ts`). Updated dark-mode `--border`/`--input` tokens in `admin-ui/app/globals.css` to satisfy 3:1 UI contrast and documented results in `Docs/Product/Completed/Plans/IMPLEMENTATION_PLAN_hci_10_accessibility.md`. Started Stage 3 by adding `Table` caption API support, captioning key jobs tables, implementing route-change focus handoff to `<main>`, and adding an icon-only button audit gate (`admin-ui/app/__tests__/icon-button-audit.test.ts`) with checklist documentation in `Docs/Product/Completed/Plans/IMPLEMENTATION_PLAN_hci_10_accessibility.md`. Re-verified with `bun run lint`, targeted `bunx vitest run` suites (40 tests), and `bun run build` in `admin-ui`.
