# Privilege Maps PRD

## Overview
- **Objective**: Deliver privilege-aware maps (API + WebUI) so admins, managers, and end users can see-in real time-what capabilities they actually have without combing through configs or triggering authorization errors.
- **Primary outcomes**: Cut "permission denied" support tickets by 50% within 30 days of launch; ensure 75% of new users view their map during week one; provide compliance-ready exports and snapshots with 90-day retention.
- **Version scope**: Initial release covering admin, organization, team, and self-service views exposed through FastAPI endpoints and surfaced in the WebUI.

## Current Status
- Privilege Metadata Catalog loader/validator (`tldw_Server_API/app/core/AuthNZ/privilege_catalog.py`) is wired into startup (`PrivilegeMapsStartup.initialize`) so missing metadata fails fast unless explicitly disabled for tests.
- Route introspection registry (`tldw_Server_API/app/core/PrivilegeMaps/introspection.py`) now captures normalized path, method, dependency, rate-limit, and catalog identifiers, with CI snapshot tooling refreshed for drift detection.
- Aggregation engine (`tldw_Server_API/app/core/PrivilegeMaps/service.py`) combines catalog + introspection + AuthNZ role data, exposes cache hooks, and feeds the privilege endpoints and snapshot store.
- Regression coverage added in `tldw_Server_API/tests/Privileges/test_privilege_introspection.py`, `test_privilege_service_sqlite.py`, `test_privilege_endpoints.py`, and `test_privilege_snapshot_retention.py`; all suites pass on the latest run, validating the new backend flow.
- Distributed cache now persists summaries to Redis (or the in-memory fallback), tracks cache generations per process, and emits pub/sub invalidations so multi-worker deployments stay coherent (`tldw_Server_API/app/core/PrivilegeMaps/cache.py`).
- Snapshot export endpoints (`/export.json` + `/export.csv`) and streaming serializers landed alongside store helpers and tests (`test_privilege_endpoints.py::test_export_snapshot_json` / `test_export_snapshot_csv`).
- WebUI privileges hub lives at `tldw-frontend/pages/privileges.tsx`, delivering virtualized tables, drill-downs, export buttons, and in-line “request access” CTAs powered by `components/ui/VirtualizedTable.tsx`.

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
- Maintain a deterministic serialized registry of scope→route mappings; publish diffs in CI so catalog drift is surfaced immediately.

### API Endpoints
- `GET /api/v1/privileges/self`
- `GET /api/v1/privileges/users/{user_id}`
- `GET /api/v1/privileges/teams/{team_id}`
- `GET /api/v1/privileges/org`
- `GET /api/v1/privileges/snapshots`
- `GET /api/v1/privileges/snapshots/{snapshot_id}`
- `POST /api/v1/privileges/snapshots`
- `GET /api/v1/privileges/snapshots/{snapshot_id}/export.{csv|json}`

### Summary & Detail Contracts
- Summary endpoints support `group_by` (org: `role|team|resource`; team: `member|resource`), optional `since`, `include_trends`; responses include `trends` arrays when requested. Each trend object contains `{ "key": "<bucket identifier>", "window": { "start": "<ISO8601>", "end": "<ISO8601>" }, "delta_users": <int>, "delta_endpoints": <int>, "delta_scopes": <int> }`. If `since` is omitted, `window.start` defaults to 30 days prior to `generated_at`.
- Detail endpoints enforce pagination (`page`, `page_size <= 500`), reject >50k row pulls, and expose per-user scope status (`allowed|blocked` with `blocked_reason`). Supported filters: `resource`, `role` (org/team detail), `view=summary|detail`, and enforce `429` when clients skip pagination.
- Detail endpoints also accept `dependency` to filter by dependency id (including derived rate-limit entries such as `ratelimit.media.ingest`), enabling operators to audit specific enforcement hooks.
- Detail item schema (applies to user/team/org detail and snapshot detail):
  ```json
  {
    "user_id": "user-123",
    "user_name": "Jane Doe",
    "role": "analyst",
    "endpoint": "/api/v1/media/process",
    "method": "POST",
    "dependencies": [
      {"id": "auth.APIKeyAuth", "type": "dependency", "module": "app.api.v1.API_Deps.auth_deps"},
      {"id": "ratelimit.standard", "type": "rate_limit", "module": "app.core.RateLimiting.Rate_Limit"}
    ],
    "source_module": "app.api.v1.endpoints.media",
    "privilege_scope_id": "media.ingest",
    "feature_flag_id": null,
    "rate_limit_class": "standard",
    "sensitivity_tier": "high",
    "ownership_predicates": ["same_org"],
    "status": "allowed",
    "blocked_reason": null
  }
  ```
  - Dependencies array preserves call order (outermost to innermost) and records normalized identifiers for decorators/partials. Unknown callables fall back to `"id": "custom.<import_path>"`.
- Self map mirrors detail schema without identity fields (`user_id`, `user_name`) and adds `recommended_actions` entries; backend maps `blocked_reason` values to actions (e.g., `feature_flag_disabled` → “Request org upgrade”, `missing_scope` → “Request scope assignment”), UI surfaces actions sorted by severity (feature-flag issues first, then scope gaps), and release notes document any new mappings so clients stay in sync.
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
- Snapshot detail endpoint accepts `page`/`page_size` query params, returns summary + paginated matrix (`detail.page`, `detail.page_size`, `detail.total_items`, `detail.items[]`) and includes `etag` for cache validation; `detail.filters` echoes applied filters. `404` when missing, `410` when downsampled. Bulk exports use separate streaming endpoints (`GET /api/v1/privileges/snapshots/{id}/export.{csv|json}`) with server-side chunking and max payload size of 25 MB per response.

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
- Extend FastAPI router introspection to harvest route metadata. Normalization rules:
  - Resolve dependency callables to import path + attribute name; wrap partial/lambda by referencing their original factory with suffix (e.g., `privacy.guard#partial`).
  - Capture custom decorators by registering shim IDs via catalog (e.g., `decorator.require_org_role`).
  - Export introspection results as deterministic JSON; CI compares the file to catalog entries + OpenAPI spec to ensure coverage.
- Maintain `tldw_Server_API/Config_Files/privilege_catalog.yaml` as the source of truth; load & validate on startup, fail CI on missing entries.
- Privilege evaluator resolves effective scopes/flags using AuthNZ DB roles, permissions, team memberships, feature flag tables.
- Aggregation layer precomputes summary buckets; detail results built on demand with pagination. Detail generator enriches rows with dependency list, rate-limit class, and source module from introspection registry.
- Snapshot store built on AuthNZ DB (`privilege_snapshots` table) with nightly retention job and metrics emission.
- Provide auto-linking to API docs and internal guides using catalog metadata.
- Cache design:
  - Keys follow `privmap:{view}:{hash(filters)}` format where `view ∈ {self,user,team,org,summary,detail}`; `hash` derived from sorted query params and user/team IDs.
  - Default TTL 15 minutes (configurable via `PRIVILEGE_CACHE_TTL_SECONDS`), refreshed on cache hits („sliding“ TTL optional).
  - Invalidation triggered by role assignment changes, catalog version bumps, deployment events. Multi-instance deployments broadcast invalidations via Redis pub/sub channel `privmap:invalidate`.
  - Trend computation windows default to 30 days but accept `window_days` override (1-90); trends stored alongside cache entry metadata so recomputation is deterministic.

## Implementation Phases
1. **Discovery & Design (1 week)** - *Status: complete*
   - Audit metadata coverage, finalize API schemas, align caching strategy.
2. **Backend Foundations (2 weeks)** - *Status: complete* (catalog loader, introspection registry, aggregation engine, retention job, refreshed tests)
3. **WebUI Integration (2 weeks)** - *Status: complete* (admin/org/team/self views, export flows, onboarding copy)
   - Build admin/org/team/self components, export flows, onboarding copy.
4. **Pilot & Rollout (1 week)** - *Status: queued*
   - Enable internally, gather feedback, tune metrics, publish documentation.

### Upcoming Deliverables
- Surface trend deltas + cache hit telemetry in metrics dashboards and surface summary badges in the WebUI when Prometheus wiring is ready.
- Validate virtualization + export flows against 10k×1k synthetic datasets; capture render/export timings for documentation.
- Prepare pilot playbook: enable feature flags, capture metrics baselines, draft admin onboarding comms.
- Refresh API + frontend docs with Redis cache knobs, export endpoints, and support troubleshooting guidance.
- QA & Performance checkpoints:
  - End of M2: regression tests ensure introspection + aggregation produce matching outputs for sample routes (diff snapshot stored in CI artifacts).
  - End of M3: load test cache layer with 10k users/1k routes; verify cache hit rate ≥80% and invalidation propagation latency <5s.
  - End of M4: retention job soak test in staging (simulate 12 months of snapshots) with success criteria for cleanup duration (<10 min) and no data loss within policy window.
  - M5: WebUI accessibility review (WCAG AA) and UX sign-off; export endpoints validated against rate limits and large dataset streaming.

## Testing Strategy
- Unit tests for catalog loader, evaluator edge cases, snapshot store DDL & retention logic **(status: passing; see `pytest -k privilege` run on latest commit)**.
- Integration tests for all endpoints (summary/detail/self/snapshot create/list/detail/export) covering filters, pagination, auth guards, and error cases. Include distributed cache invalidation scenario (two app instances) and trend window variations.
- Automated CI guard compares the serialized route registry against a checked-in snapshot (`Helper_Scripts/update_privilege_registry_snapshot.py` regenerates the fixture when intentional changes occur).
- Performance tests with synthetic datasets (10k users, 1k endpoints) to verify pagination guardrails.
- Negative tests ensuring unauthorized access and invalid scope inputs raise appropriate errors.
- UI automated tests cover admin/org/team/self pages, export downloads, and “request access” CTA flows; browser-based smoke suite runs nightly.
- Post-backend integration target: end-to-end test harness seeded with synthetic AuthNZ + catalog data to validate cache invalidation behaviour and trend delta accuracy across two app instances.
- New regression coverage: `test_privilege_cache.py` validates Redis generation sync; `test_privilege_endpoints.py::test_export_snapshot_json` / `test_export_snapshot_csv` lock export responses.

## Risks & Mitigations
- **Incomplete metadata**: Add CI validation; backfill missing route annotations.
- **Performance under load**: Cache results, paginate, precompute aggregates; load-test against 10k×1k dataset before rollout.
- **Security leaks**: Reuse proven dependency guards; add regression tests for hidden routes.
- **Stale data**: Invalidate caches on role/config change; expose manual refresh controls; clearly display timestamps; use Redis pub/sub to broadcast invalidations across workers.
- **Snapshot storage growth**: Retention job instrumentation with alerts (`privilege_snapshots_table_bytes` threshold); configurable env vars documented; periodic review of downsampling logic.
- **Worker failures**: Background queue integrates exponential backoff (max 5 retries) and emits alerts via existing monitoring (PagerDuty + Prometheus alert rules).

## Rollout & Communication
- Release notes targeted at admins; in-app toast linking to documentation.
- Admin onboarding guide and quickstart videos for team leads and end users.
- Document retention policy + metrics knobs in security/compliance handbooks.


# Privilege Maps v1 PRD

## Overview
- **Objective**: Deliver privilege-aware API maps that show users and managers exactly which endpoints and capabilities are available under their current permissions.
- **Primary outcome**: Reduce guesswork around access, accelerate onboarding, and give admins a proactive way to validate privilege configurations.
- **Version scope**: First release that covers admin, organization, team, and individual map views exposed via API and surfaced in the WebUI.

## Background & Problem Statement
- The platform supports multiple auth modes and nuanced endpoint-level guards, but there is no consolidated view of what any given user can access.
- Administrators must audit configuration files or run trial requests to confirm permissions, while users discover access gaps only by encountering authorization errors.
- Support and compliance teams lack a fast way to prove which data surfaces are available to a user or role at a given time.

## Goals
- Provide a dynamic privilege map per user that reflects their active auth mode, roles, scopes, and feature flags.
- Offer management views (admin, org-wide, team-level) that make it easy to audit who can invoke which APIs and when changes were last refreshed.
- Enable individual users to self-service an up-to-date capability list to guide workflow discovery.
- Expose maps through both backend APIs and the WebUI, with export options for audit/compliance snapshots.

## Non-Goals
- Making changes to the underlying authorization model (e.g., introducing new roles or scopes).
- Implementing granular rate-limit visualizations or historical analytics beyond last-fetch timestamps.
- Providing third-party IAM synchronization in v1.

## Personas & Use Cases
- **Platform Administrator**: Needs a complete, filterable view of all users, roles, and their accessible endpoints for audits and troubleshooting.
- **Org Manager/Owner**: Requires an organization-wide map to ensure policy compliance and verify that sensitive endpoints are limited to intended users.
- **Team Lead**: Must see a constrained map for their team(s) to confirm the right people have the right tools, and to identify gaps before project kickoffs.
- **Individual Contributor**: Wants a personal map to understand available APIs, feature toggles, and recommended next steps without trial-and-error.
- **Support/Success Engineer**: Needs to quickly inspect a user’s map when diagnosing “permission denied” tickets or preparing onboarding.

## Functional Requirements
### Shared Capabilities
- Generate privilege maps by inspecting registered FastAPI routes, their dependencies (auth, RBAC, feature flags), HTTP methods, and descriptive metadata.
- Capture the source of each constraint (e.g., `APIKeyAuth`, `JWTScopes`, `TeamMembership`) and expose it alongside endpoint details.
- Back each dependency and scope with a formal Privilege Metadata Catalog that enumerates scopes, feature flags, sensitivity tiers, and ownership predicates so generated maps cannot drift from the authoritative definitions.
- Provide filters for resource type (media, chat, rag, audio, etc.), HTTP method, sensitivity tier, rate-limit class, and feature flag status.
- Limit v1 maps to coarse-grained API and capability surfaces; per-resource (e.g., single media item) visibility remains out of scope so we avoid duplicating dynamic business logic while still reflecting cross-org/team guardrails.
- Include timestamps for last refresh and highlight when cache is invalidated due to config or role updates.

### Admin View
- Default to aggregated counts (users and endpoints grouped by role, team, and resource) with server-side drill-down that reveals paginated user x endpoint detail when requested, alongside multi-select filters for user(s), roles, teams, resources, and sensitivity tiers.
- Offer CSV/JSON export for audits and optional diff view comparing two users or snapshots.
- Surface alerts for stale or conflicting configurations (e.g., endpoint registered but missing dependency, user assigned deprecated role).

### Organization-Wide Map
- Aggregate all users within an organization, grouped by role or team, with counts of accessible endpoints per category.
- Restrict access to org owners and higher; provide drill-down from summary to user-level detail.
- Support scheduled snapshot generation for compliance audits (configurable cadence).

### Team Map
- Allow team leads and above to view the privilege map limited to their team(s).
- Enable quick comparisons between members to identify missing permissions before project work begins.
- Provide action recommendations (e.g., “User lacks `media.ingest` scope required for DS Pipeline”).

### Individual Map
- Expose a personal capability list, including endpoint descriptions, required headers, example calls, and links to documentation.
- Indicate which features are currently gated (e.g., “Requires Org upgrade” or “Contact Admin for access”).
- Include an API endpoint (`GET /api/v1/privileges/self`) so CLIs/scripts can tailor UI based on real-time capabilities.

### API & Integration
- Introduce REST endpoints:
  - `GET /api/v1/privileges/self`
  - `GET /api/v1/privileges/users/{user_id}`
  - `GET /api/v1/privileges/teams/{team_id}`
  - `GET /api/v1/privileges/org`
  - `GET /api/v1/privileges/snapshots`
  - `GET /api/v1/privileges/snapshots/{snapshot_id}`
  - `POST /api/v1/privileges/snapshots` (admin only)
- Provide WebUI components under Admin > Privileges, Team Dashboard, and User Profile sections.
- List and aggregation endpoints return pagination metadata and support filters (e.g., date range, generated_by, org_id, team_id, sensitivity tier) so compliance tooling can retrieve relevant snapshots without guessing identifiers.
- Ensure responses include `etag` or version to support client-side caching.
- `GET /api/v1/privileges/self` returns the same schema as `GET /api/v1/privileges/users/{user_id}` but is automatically scoped to the caller, omits `user_id` in each item (implicit `self`), and adds `recommended_actions` describing next steps (e.g., “Request org upgrade for TTS access”).

### Aggregation & Drill-Down API Contract (Draft)
- **Summary Endpoints** (`GET /api/v1/privileges/org`, `GET /api/v1/privileges/teams/{team_id}`):
  - Query params:
    - `group_by`:
      - `GET /api/v1/privileges/org` supports `role`, `team`, or `resource` (default `role`).
      - `GET /api/v1/privileges/teams/{team_id}` supports `member` or `resource` (default `member`); setting `team` is invalid because the request is already scoped to a single team.
    - `include_trends` (bool, default `false`): when `true`, the response adds a `trends` array describing deltas over the requested window.
    - `since` (ISO timestamp, optional): bounds the aggregation window; defaults to previous 30 days when omitted.
  - Response:
    ```json
    {
      "catalog_version": "1.0.0",
      "generated_at": "2025-01-15T10:12:03Z",
      "group_by": "role",
      "buckets": [
        {"key": "admin", "users": 12, "endpoints": 145, "scopes": 83},
        {"key": "analyst", "users": 48, "endpoints": 97, "scopes": 52}
      ],
      "trends": [
        {"key": "admin", "window": {"start": "2024-12-16T00:00:00Z", "end": "2025-01-15T10:12:03Z"}, "delta_users": 2, "delta_endpoints": 5, "delta_scopes": 3}
      ],
      "metadata": {
        "org_id": "acme",
        "filters": {"include_trends": true, "since": null}
      }
    }
    ```
- **Drill-Down Endpoint** (`GET /api/v1/privileges/users/{user_id}` with `view=detail` or `GET /api/v1/privileges/org` with `view=detail`):
  - Query params: `view` (`summary` default, `detail` for matrix rows), `page` (int, default `1`), `page_size` (int, default `100`, max `500`), `resource` (optional filter), `role` (optional filter).
  - Response:
    ```json
    {
      "catalog_version": "1.0.0",
      "generated_at": "2025-01-15T10:12:03Z",
      "page": 1,
      "page_size": 100,
      "total_items": 2350,
      "items": [
        {
          "user_id": "user-123",
          "user_name": "Jane Doe",
          "role": "analyst",
          "endpoint": "/api/v1/media/process",
          "method": "POST",
          "privilege_scope_id": "media.ingest",
          "feature_flag_id": null,
          "rate_limit_class": "standard",
          "sensitivity_tier": "high",
          "ownership_predicates": ["same_org"],
          "dependencies": [
            {"id": "auth.APIKeyAuth", "type": "dependency", "module": "app.api.v1.API_Deps.auth_deps"},
            {"id": "ratelimit.standard", "type": "rate_limit", "module": "app.core.RateLimiting.Rate_Limit"}
          ],
          "source_module": "app.api.v1.endpoints.media",
          "status": "allowed",
          "blocked_reason": null
        }
      ]
    }
    ```
- **Performance Guardrails**: Clients must paginate detail requests; the service enforces `page_size <= 500` and returns `429` if callers request total result sets beyond 50k rows without pagination. Aggregation requests remain cached and should respond <300 ms.
- **Self Map Endpoint** (`GET /api/v1/privileges/self`):
  - Response mirrors the detail payload but omits `user_id` in each item and adds `recommended_actions`.
    ```json
    {
      "catalog_version": "1.0.0",
      "generated_at": "2025-01-15T10:12:03Z",
      "items": [
        {
          "role": "analyst",
          "endpoint": "/api/v1/media/process",
          "method": "POST",
          "privilege_scope_id": "media.ingest",
          "feature_flag_id": null,
          "rate_limit_class": "standard",
          "sensitivity_tier": "high",
          "ownership_predicates": ["same_org"],
          "dependencies": [
            {"id": "auth.APIKeyAuth", "type": "dependency", "module": "app.api.v1.API_Deps.auth_deps"},
            {"id": "ratelimit.standard", "type": "rate_limit", "module": "app.core.RateLimiting.Rate_Limit"}
          ],
          "source_module": "app.api.v1.endpoints.media",
          "status": "allowed",
          "blocked_reason": null
        }
      ],
      "recommended_actions": [
        {"privilege_scope_id": "audio.tts", "action": "Request org upgrade", "reason": "Feature flag disabled"}
      ]
    }
    ```
- **Trend Semantics**: When `include_trends=true`, responses add the `trends` array where each entry corresponds to a `buckets[].key` and reports deltas (`delta_users`, `delta_endpoints`, `delta_scopes`) over the window defined by `window.start`/`window.end`. If `since` is provided, the window begins at that timestamp; otherwise it spans 30 days prior to `generated_at`.

### Snapshot Listing Filters & Examples
- **Endpoint**: `GET /api/v1/privileges/snapshots`
- **Query Parameters**:
  - `page` (int, default `1`)
  - `page_size` (int, default `50`, max `200`)
  - `date_from` / `date_to` (ISO timestamps) to bound snapshot creation time.
  - `generated_by` (user id or service account id).
  - `org_id` / `team_id` (optional scoping; mutually exclusive).
  - `catalog_version` (optional exact match).
  - `scope` (optional `privilege_scope_id` to return only snapshots containing that scope).
  - `include_counts` (bool, default `false`) to add aggregate counts per scope/resource in the listing response.
- **Response Shape**:
  ```json
  {
    "page": 1,
    "page_size": 50,
    "total_items": 187,
    "items": [
      {
        "snapshot_id": "snap-2025-01-15-001",
        "generated_at": "2025-01-15T10:00:00Z",
        "generated_by": "user-42",
        "org_id": "acme",
        "team_id": null,
        "catalog_version": "1.0.0",
        "summary": {
          "users": 120,
          "scopes": 86,
          "sensitivity_breakdown": {"high": 24, "restricted": 6}
        }
      }
    ],
    "filters": {
      "date_from": "2025-01-01T00:00:00Z",
      "date_to": "2025-01-16T00:00:00Z",
      "org_id": "acme",
      "include_counts": true
    }
  }
  ```
- **Usage Example**:
  ```
  GET /api/v1/privileges/snapshots?org_id=acme&date_from=2025-01-01T00:00:00Z&include_counts=true&page=1&page_size=25
  ```
- **Notes**: When both `date_from` and `date_to` are absent, defaults to last 30 days. If `scope` is provided, `include_counts` is forced true so responses include awareness of the matching scope presence.

### Snapshot Creation Endpoint
- **Endpoint**: `POST /api/v1/privileges/snapshots` (admin only)
- **Request Body**:
  ```json
  {
    "target_scope": "org",       // enum: org, team, user
    "org_id": "acme",            // required when target_scope=org or team
    "team_id": "research",       // required when target_scope=team
    "user_ids": ["user-123"],    // optional when target_scope=user (defaults to requester)
    "catalog_version": "1.0.0",  // optional override; defaults to active catalog
    "notes": "Quarterly audit run",
    "async": true                // optional bool; when true returns 202 and processes in background
  }
  ```
- **Response**:
  - `202 Accepted` when `async=true`, returning job metadata:
    ```json
    {
      "request_id": "snap-job-001",
      "status": "queued",
      "estimated_ready_at": "2025-01-15T10:20:00Z"
    }
    ```
  - `201 Created` when synchronous (default). Response echoes the snapshot record:
    ```json
    {
      "snapshot_id": "snap-2025-01-15-001",
      "generated_at": "2025-01-15T10:12:03Z",
      "generated_by": "admin-7",
      "target_scope": "org",
      "org_id": "acme",
      "team_id": null,
      "catalog_version": "1.0.0",
      "summary": {
        "users": 120,
        "scopes": 86,
        "sensitivity_breakdown": {"high": 24, "restricted": 6}
      }
    }
    ```
- **Behaviour Notes**: Snapshot jobs reuse the privilege evaluator, store raw detail matrices, and emit the retention metrics described below. Invalid combinations (e.g., `target_scope="team"` without `team_id`) return `422`.

### Snapshot Detail Endpoint
- **Endpoint**: `GET /api/v1/privileges/snapshots/{snapshot_id}`
- **Response**:
  ```json
  {
    "snapshot_id": "snap-2025-01-15-001",
    "catalog_version": "1.0.0",
    "generated_at": "2025-01-15T10:12:03Z",
    "generated_by": "admin-7",
    "target_scope": "org",
    "org_id": "acme",
    "team_id": null,
    "summary": {
      "users": 120,
      "scopes": 86,
      "endpoints": 145,
      "sensitivity_breakdown": {"high": 24, "restricted": 6}
    },
    "detail": {
      "page": 1,
      "page_size": 500,
      "total_items": 2350,
      "filters": {
        "page": 1,
        "page_size": 500
      },
      "items": [
        {
          "user_id": "user-123",
          "user_name": "Jane Doe",
          "role": "analyst",
          "endpoint": "/api/v1/media/process",
          "method": "POST",
          "privilege_scope_id": "media.ingest",
          "feature_flag_id": null,
          "rate_limit_class": "standard",
          "sensitivity_tier": "high",
          "ownership_predicates": ["same_org"],
          "dependencies": [
            {"id": "auth.APIKeyAuth", "type": "dependency", "module": "app.api.v1.API_Deps.auth_deps"},
            {"id": "ratelimit.standard", "type": "rate_limit", "module": "app.core.RateLimiting.Rate_Limit"}
          ],
          "source_module": "app.api.v1.endpoints.media",
          "status": "allowed",
          "blocked_reason": null
        }
      ]
    },
    "etag": "W/\"snap-2025-01-15-001-v1\""
  }
  ```
- **Pagination**: `detail.page` and `detail.page_size` respond to `page`/`page_size` query params; defaults match the drill-down endpoint.
- **Error Handling**: Returns `404` if the snapshot is purged by retention policy, and `410` when the snapshot metadata exists but the underlying matrix was downsampled (detail replaced by weekly summary).

## Non-Functional Requirements
- **Security**: Respect existing RBAC-users can only request maps they have rights to see; avoid leaking hidden endpoints.
- **Performance**: Initial map generation should complete within 2 seconds for <500 endpoints; cached responses should return <300 ms; admin drill-down views must rely on server-side pagination/virtualized tables so clients never render full 10k x 1k matrices.
- **Scalability**: Support up to 10k users and 1k endpoints per instance with incremental caching, precomputed aggregates, and paginated detail queries that cap payload sizes.
- **Reliability**: Cache invalidation tied to role/config updates; provide background job to refresh stale entries.
- **Auditability**: Maintain optional snapshot store with immutable records and metadata (generated by, scope, timestamp). Nightly retention task keeps full-fidelity snapshots for 90 days, downsamples to one per ISO week (per org/team) up to 12 months, then purges everything older; retention is configurable via `PRIVILEGE_SNAPSHOT_RETENTION_DAYS` and `PRIVILEGE_SNAPSHOT_WEEKLY_RETENTION_DAYS`.

## UX & Content Guidelines
- Admin dashboard: matrix/table view with column pinning, quick filters, and severity badges.
- Org and team dashboards: summary cards with drill-down tables and sparklines showing counts by category.
- Individual view: friendly card list grouped by capability category with quick-copy for example curl commands.
- Provide inline explanations for auth dependency names (hover tooltips) and call-to-action buttons for requesting access.

## Instrumentation & Metrics
- Track usage: total map fetches by persona, cache hit rate, export frequency.
- Monitor success metrics:
  - 50% reduction in “permission denied” support tickets within 30 days of launch.
  - 75% of new users view their map during first week.
  - <5% of admin map fetches result in manual escalation due to missing data.
- Log map generation duration and cache invalidation events for performance tuning.
- Emit privilege snapshot storage gauges: `privilege_snapshots_table_rows` (all backends) and `privilege_snapshots_table_bytes` (Postgres) so operators can alert before retention thresholds are exceeded.

## Technical Approach
- **Route Introspection Service**: Extend existing FastAPI router introspection to gather route, method, dependency stack, and metadata tags.
- **Privilege Metadata Catalog**: Maintain a source-of-truth registry (YAML or module constants) that enumerates scopes, feature flags, sensitivity tiers, rate-limit classes, and dependency aliases, and require routes/dependencies to declare identifiers that resolve back to this catalog.
- **Privilege Evaluator**: For a given user context, resolve effective scopes/roles, evaluate dependencies, and determine accessibility.
- **Aggregation & Drill-Down**: Precompute org/team/user capability counts for high-level dashboards, then service paginated detail requests on-demand to avoid materializing full user x endpoint matrices.
- **Caching Layer**: Store per-user and per-aggregate maps in Redis or in-memory cache with TTL and invalidation hooks (role updates, config changes, deployment).
- **Snapshot Store**: Persist optional snapshots and metadata in existing SQLite/PostgreSQL auth DB.
- **Retention & Downsampling**: AuthNZ scheduler runs a nightly job that enforces the 90-day full snapshot window, collapses older data to weekly representatives up to 12 months, and purges legacy records. Job emits metrics and honors the retention env vars documented above.
- **Access Control**: Guard new endpoints using existing dependency injection patterns (`AdminRequired`, `OrgManagerRequired`, `TeamLeadRequired`, `CurrentUser`).
- **Documentation Integration**: Auto-link endpoints to OpenAPI docs and internal guides using shared metadata.

## Metadata Model & Validation
- Require each FastAPI route and dependency to supply catalog-backed identifiers: `privilege_scope_id`, `feature_flag_id` (optional), `sensitivity_tier`, and `rate_limit_class`.
- Extend dependency annotations to describe ownership predicates (e.g., `same_team`, `same_org`), allowing the evaluator to reflect coarse-grained dynamic checks without exposing individual resource memberships.
- Validate metadata during CI by failing builds when routes reference unknown catalog entries or omit required fields.
- Persist catalog definitions alongside versioning info so maps and snapshots can reference the exact privilege schema used at generation time.

### Privilege Metadata Catalog Schema (Draft)
- **Storage**: `tldw_Server_API/Config_Files/privilege_catalog.yaml` (source-controlled, loaded into `PrivilegeMetadataCatalog` helper on startup). Generated artifacts cached to `Databases/privilege_catalog_cache.db` to support quick lookups.
- **Owners**: AuthNZ Platform team (primary), with change reviews from Security and API Platform leads.
- **Top-Level Fields**:
  - `version`: Semantic version for the catalog (e.g., `1.0.0`) referenced in map responses and snapshots.
  - `updated_at`: ISO timestamp of last catalog publish.
  - `scopes`: Array of scope definitions:
    - `id` (string, required): Canonical identifier (`media.ingest`, `chat.admin`).
    - `description` (string, required): Human-readable purpose.
    - `resource_tags` (array[str], optional): Links to capability categories (media, chat, rag, audio).
    - `sensitivity_tier` (enum: `low`, `moderate`, `high`, `restricted`, required).
    - `rate_limit_class` (enum, required): Must match limiter configuration (`standard`, `elevated`, `admin`, etc.).
    - `default_roles` (array[str], optional): Roles granted this scope by default.
    - `feature_flag_id` (string, optional): Reference to associated feature flag entry.
    - `ownership_predicates` (array[str], optional): Coarse-grained predicates (`same_org`, `same_team`, `self_only`) used to describe dynamic checks.
    - `doc_url` (string, optional): Link to internal/external documentation.
  - `feature_flags`: Array of flag definitions with `id`, `description`, `default_state`, `allowed_roles`, `expires_at` (optional).
  - `rate_limit_classes`: Definitions that map class names to policy metadata (`requests_per_min`, `burst`, `notes`).
  - `ownership_predicates`: Registry describing each predicate name, evaluation helper, and notes on visibility.
- **Change Management**: Updates require PR with catalog diff, automated schema validation, and notification in release notes. Snapshots include `catalog_version` so downstream systems can reconcile scope meanings over time.

## Testing & QA Considerations
- Add unit tests for the catalog loader to cover the happy path, missing references, duplicate identifiers, and malformed enum values.
- Integration tests for `GET /api/v1/privileges/snapshots` must assert pagination metadata (`page`, `page_size`, `total_items`) and verify that `catalog_version` is echoed in every response payload.
- Snapshot list tests should exercise filter permutations: date ranges, `generated_by`, mutually exclusive `org_id` vs. `team_id`, `scope`, and forced `include_counts`.
- API contract tests for summary vs. detail views should validate enforced `page_size` caps and `429` behaviour when clients attempt unbounded retrieval.

## Phased Implementation Plan
1. **Discovery & Design (1 week)**: Confirm dependency metadata completeness, finalize API response schema, validate caching approach.
2. **Backend Foundations (2 weeks)**: Build introspection service, privilege evaluator, caching hooks, and new API endpoints with tests.
3. **WebUI Integration (2 weeks)**: Implement admin, org, team, and individual views; add export flows; run usability testing.
4. **Pilot & Rollout (1 week)**: Enable for internal admins, collect feedback, polish metrics dashboards, and launch publicly.

## Dependencies
- Accurate metadata on all FastAPI routes (tags, descriptions, dependency annotations).
- Privilege Metadata Catalog defined and versioned so scopes, feature flags, sensitivity tiers, and rate-limit classes are discoverable.
- Existing auth and RBAC services providing user-role-scope resolution.
- WebUI component library support for tables, filters, and export modals.
- Cache infrastructure (Redis or equivalent) in target deployment environments.
- AuthNZ scheduler running in production environments so nightly retention/metric tasks execute; operators can tune windows with `PRIVILEGE_SNAPSHOT_RETENTION_DAYS` / `PRIVILEGE_SNAPSHOT_WEEKLY_RETENTION_DAYS`.

## Risks & Mitigations
- **Incomplete metadata**: Some routes may lack descriptions or tags. Mitigation: add validation step during CI and backfill missing metadata.
- **Performance load**: Large orgs could stress introspection. Mitigation: cache results, paginate admin views, and precompute in background.
- **Security leaks**: Misconfigured access control could expose hidden routes. Mitigation: reuse proven dependency guards and add automated tests for negative cases.
- **Stale data**: Users might view outdated maps. Mitigation: invalidation on config/role change, manual refresh action, and clear timestamp display.

## Rollout & Communication
- Announce to admins and team leads via release notes and in-app toast with link to documentation.
- Provide onboarding guide for managers with recommended workflows.
- Offer quick video or doc for end users on reading their personal map.

## Open Questions
- Do we need historical diffs beyond snapshots (e.g., timeline view)? If so, define retention and storage.
- Should map exports include actual sample requests or just endpoint metadata?
- How do we surface third-party provider limitations (e.g., vendor quota) within the map?
- Are there regulatory requirements that mandate a longer retention window or encrypted snapshot store beyond the default 12-month policy?
