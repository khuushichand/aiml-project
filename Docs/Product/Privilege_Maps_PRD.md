# Privilege Maps PRD

## Overview
- **Objective**: Deliver privilege-aware maps (API + WebUI) so admins, managers, and end users can see—in real time—what capabilities they actually have without combing through configs or triggering authorization errors.
- **Primary outcomes**: Cut "permission denied" support tickets by 50% within 30 days of launch; ensure 75% of new users view their map during week one; provide compliance-ready exports and snapshots with 90-day retention.
- **Version scope**: Initial release covering admin, organization, team, and self-service views exposed through FastAPI endpoints and surfaced in the WebUI.

## Background & Problem Statement
- Current RBAC modes (single-user API key, multi-user JWT, scopes, feature flags) lack a consolidated view for effective access.
- Admins audit configuration files or probe endpoints manually; end users learn capabilities by hitting authorization errors.
- Support/compliance cannot quickly generate evidence of exact privileges for audits or incident reviews.

## Goals
- Generate dynamic, per-user privilege maps reflecting roles, scopes, feature flags, and auth mode.
- Provide management dashboards (admin/org/team) alongside self-service views.
- Offer drill-down, exports, and snapshots to support compliance and troubleshooting workflows.
- Ensure maps are driven by the authoritative Privilege Metadata Catalog so they remain in sync with the permission model.

## Non-Goals
- Redesigning the underlying authorization model (roles/scopes).
- Resource-level access checks (e.g., specific media objects) in v1.
- Third-party IAM synchronization or historical analytics beyond snapshots.

## Personas & Use Cases
- **Platform Administrator**: Needs filterable org/team views, drill-downs, exports, and alerts about misconfigurations.
- **Org Owner/Manager**: Audits sensitive access and triggers compliance snapshots.
- **Team Lead**: Compares teammates' access and receives remediation guidance.
- **Individual Contributor**: Understands available APIs/features and next steps without trial-and-error.
- **Support/Success Engineer**: Diagnoses "permission denied" tickets quickly by inspecting real maps.
- **Compliance/Audit**: Generates snapshots with metadata and retention guarantees for evidence.

## Functional Requirements
### Shared Capabilities
- Inspect FastAPI routes, dependencies, scopes, and feature flags to generate privilege maps.
- Require catalog-backed metadata on routes/dependencies: `privilege_scope_id`, `feature_flag_id` (optional), `sensitivity_tier`, `rate_limit_class`, `ownership_predicates`.
- Cache results per user/org/team with invalidation on role/config changes and manual refresh support.
- Include `catalog_version`, `generated_at`, and cache metadata in all responses.

### API Endpoints
- `GET /api/v1/privileges/self`
- `GET /api/v1/privileges/users/{user_id}`
- `GET /api/v1/privileges/teams/{team_id}`
- `GET /api/v1/privileges/org`
- `GET /api/v1/privileges/snapshots`
- `GET /api/v1/privileges/snapshots/{snapshot_id}`
- `POST /api/v1/privileges/snapshots`

### Summary & Detail Contracts
- Summary endpoints support `group_by` (org: `role|team|resource`; team: `member|resource`), optional `since`, `include_trends`; responses include `trends` arrays when requested. Each trend object contains `{ "key": "<bucket identifier>", "window": { "start": "<ISO8601>", "end": "<ISO8601>" }, "delta_users": <int>, "delta_endpoints": <int>, "delta_scopes": <int> }`. If `since` is omitted, `window.start` defaults to 30 days prior to `generated_at`.
- Detail endpoints enforce pagination (`page`, `page_size <= 500`), reject >50k row pulls, and expose per-user scope status (`allowed|blocked` with `blocked_reason`). Supported filters: `resource`, `role` (org/team detail), `view=summary|detail`, and enforce `429` when clients skip pagination.
- Self map mirrors detail schema without `user_id` and adds `recommended_actions` entries; backend maps `blocked_reason` values to actions (e.g., `feature_flag_disabled` → “Request org upgrade”, `missing_scope` → “Request scope assignment”), UI surfaces actions sorted by severity (feature-flag issues first, then scope gaps), and release notes document any new mappings so clients stay in sync.
- Recommended action mapping table (initial):
  - `feature_flag_disabled` → action: “Request org upgrade”, reason: “Feature flag disabled”
  - `missing_scope` → action: “Request scope assignment”, reason: “Scope not assigned”
  - Additional reasons may be appended with backward-compatible defaults (UI should treat unknown reasons as informational badges).

### Snapshot Store & Retention
- DB-backed snapshots with metadata (`target_scope`, org/team IDs, `catalog_version`, summary counts, sensitivity breakdowns, scope IDs).
- Filters: pagination, date range, `generated_by`, `org_id` XOR `team_id`, `catalog_version`, `scope`, `include_counts`.
- Nightly cleanup job enforces retention: full-fidelity rows remain for `PRIVILEGE_SNAPSHOT_RETENTION_DAYS` (default 90), oldest snapshot per ISO week is kept up to `PRIVILEGE_SNAPSHOT_WEEKLY_RETENTION_DAYS` (default 365), then purged. When detail matrices are downsampled, the API returns `410 Gone`; once metadata is deleted the API returns `404`.
- `POST /privileges/snapshots` validates required identifiers (`org_id`, `team_id`, `user_ids`) based on `target_scope`. Supports synchronous 201 (returns snapshot record) or async 202 (queues job). Request body:
  ```json
  {
    "target_scope": "org|team|user",
    "org_id": "acme",          // required for org/team
    "team_id": "team-123",     // required for team
    "user_ids": ["user-7"],    // optional; defaults to requester when scope=user
    "catalog_version": "1.0.0",
    "notes": "Quarterly audit",
    "async": false
  }
  ```
  - `201 Created` response (`async=false`): snapshot record with summary counts, `target_scope`, `catalog_version`, and metadata.
  - `202 Accepted` response (`async=true`): `{"request_id": "...", "status": "queued", "estimated_ready_at": "<ISO8601>"}`; clients poll list endpoint for completion.
- Snapshot detail endpoint accepts `page`/`page_size` query params, returns summary + paginated matrix (`detail.page`, `detail.page_size`, `detail.total_items`, `detail.items[]`) and includes `etag` for cache validation; `404` when missing, `410` when downsampled.

### WebUI Requirements
- Admin dashboard: aggregated cards, filters, server-side virtualized tables, CSV/JSON export, diff comparisons, stale-config alerts.
- Org/team dashboards: summary cards with drill-down tables, quick filters, action recommendations.
- Self view: capability cards with descriptions, example curl commands, and call-to-action for requesting access.
- Tooltips describing dependencies and privilege catalog metadata.

## Non-Functional Requirements
- **Security**: Reuse existing RBAC dependencies; prevent leakage of hidden routes.
- **Performance**: Initial map generation <2s for <=500 endpoints; cached responses <300 ms.
- **Scalability**: Support 10k users & 1k endpoints; rely on caching, incremental summaries.
- **Reliability**: Automatic cache invalidation on role/config changes; scheduled refresh for stale entries.
- **Auditability**: Immutable snapshots with documented retention and metrics.
- **Instrumentation**: Track map fetches, cache hit rates, export frequency, generation latency, invalidations, snapshot table size (`rows`, `bytes`).

## Technical Approach
- Extend FastAPI router introspection to harvest route metadata.
- Maintain `tldw_Server_API/Config_Files/privilege_catalog.yaml` as the source of truth; load & validate on startup, fail CI on missing entries.
- Privilege evaluator resolves effective scopes/flags using AuthNZ DB roles, permissions, team memberships, feature flag tables.
- Aggregation layer precomputes summary buckets; detail results built on demand with pagination.
- Snapshot store built on AuthNZ DB (`privilege_snapshots` table) with nightly retention job and metrics emission.
- Provide auto-linking to API docs and internal guides using catalog metadata.

## Implementation Phases
1. **Discovery & Design (1 week)**
   - Audit metadata coverage, finalize API schemas, align caching strategy.
2. **Backend Foundations (2 weeks)**
   - Introspection, evaluator, catalog loader, privilege endpoints, snapshot store, retention job, unit/integration tests.
3. **WebUI Integration (2 weeks)**
   - Build admin/org/team/self components, export flows, onboarding copy.
4. **Pilot & Rollout (1 week)**
   - Enable internally, gather feedback, tune metrics, publish documentation.

## Testing Strategy
- Unit tests for catalog loader, evaluator edge cases, snapshot store DDL & retention logic.
- Integration tests for all endpoints (summary/detail/self/snapshot create/list/detail) covering filters, pagination, auth guards, and error cases.
- Performance tests with synthetic datasets (10k users, 1k endpoints) to verify pagination guardrails.
- Negative tests ensuring unauthorized access and invalid scope inputs raise appropriate errors.

## Risks & Mitigations
- **Incomplete metadata**: Add CI validation; backfill missing route annotations.
- **Performance under load**: Cache results, paginate, precompute aggregates.
- **Security leaks**: Reuse proven dependency guards; add regression tests for hidden routes.
- **Stale data**: Invalidate caches on role/config change; expose manual refresh controls; clearly display timestamps.

## Rollout & Communication
- Release notes targeted at admins; in-app toast linking to documentation.
- Admin onboarding guide and quickstart videos for team leads and end users.
- Document retention policy + metrics knobs in security/compliance handbooks.
