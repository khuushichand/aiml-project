# Privilege Maps PRD

## Overview
- **Objective**: Deliver privilege-aware maps (API + WebUI) so admins, managers, and end users can see-in real time-what capabilities they actually have without combing through configs or triggering authorization errors.
- **Primary outcomes**: Cut "permission denied" support tickets by 50% within 30 days of launch; ensure 75% of new users view their map during week one; provide compliance-ready exports and snapshots with 90-day retention.
- **Version scope**: Initial release covering admin, organization, team, and self-service views exposed through FastAPI endpoints and surfaced in the WebUI.

## Current Status
- Privilege Metadata Catalog loader/validator (`tldw_Server_API/app/core/AuthNZ/privilege_catalog.py`) is wired into startup via `validate_privilege_metadata_on_startup()` in `tldw_Server_API/app/core/PrivilegeMaps/startup.py`, so missing metadata fails fast unless explicitly disabled via `PRIVILEGE_METADATA_VALIDATE_ON_STARTUP=0`.
- Route introspection registry (`tldw_Server_API/app/core/PrivilegeMaps/introspection.py`) now captures normalized path, method, dependency, rate-limit, and catalog identifiers, with CI snapshot tooling refreshed for drift detection.
- Aggregation engine (`tldw_Server_API/app/core/PrivilegeMaps/service.py`) combines catalog + introspection + AuthNZ role data, exposes cache hooks, and feeds the privilege endpoints and snapshot store.
- Regression coverage added in `tldw_Server_API/tests/Privileges/test_privilege_introspection.py`, `test_privilege_service_sqlite.py`, `test_privilege_endpoints.py`, and `test_privilege_snapshot_retention.py`; all suites pass on the latest run, validating the new backend flow.
- Distributed cache now persists summaries to Redis (or the in-memory fallback), tracks cache generations per process, and emits pub/sub invalidations so multi-worker deployments stay coherent (`tldw_Server_API/app/core/PrivilegeMaps/cache.py`).
- Snapshot export endpoints (`/export.json` + `/export.csv`) and streaming serializers landed alongside store helpers and tests (`test_privilege_endpoints.py::test_export_snapshot_json` / `test_export_snapshot_csv`).
- WebUI: **not started**. `apps/tldw-frontend/pages/privileges.tsx` is a placeholder redirect to `/settings`. Admin dashboard, drill-down tables, export flows, and "request access" CTAs are not yet implemented.
- Access control: Currently admin-only (`admin`, `owner`, `platform_admin`). Team lead and org manager tiers described in this PRD are **not yet implemented** (tracked for v1.1).

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
- Granular rate-limit visualizations beyond the `rate_limit_class` field in detail items.

## Personas & Use Cases
- **Platform Administrator**: Needs a complete, filterable view of all users, roles, and their accessible endpoints for audits and troubleshooting. Uses drill-downs, exports, and alerts about misconfigurations.
- **Org Owner/Manager**: Requires an organization-wide map to ensure policy compliance and verify that sensitive endpoints are limited to intended users. Triggers compliance snapshots.
- **Team Lead**: Must see a constrained map for their team(s) to confirm the right people have the right tools. Compares teammates' access and receives remediation guidance.
- **Individual Contributor**: Wants a personal map to understand available APIs, feature toggles, and recommended next steps without trial-and-error.
- **Support/Success Engineer**: Needs to quickly inspect a user's map when diagnosing "permission denied" tickets or preparing onboarding.
- **Compliance/Audit**: Generates snapshots with metadata and retention guarantees for evidence.

## Functional Requirements

### Shared Capabilities
- Inspect FastAPI routes, dependencies, scopes, and feature flags to generate privilege maps.
- Require catalog-backed metadata on routes/dependencies: `privilege_scope_id`, `feature_flag_id` (optional), `sensitivity_tier`, `rate_limit_class`, `ownership_predicates`.
- Cache results per user/org/team with invalidation on role/config changes and manual refresh support.
- Include `catalog_version`, `generated_at`, and cache metadata in all responses.
- Maintain a deterministic serialized registry of scope-to-route mappings; publish diffs in CI so catalog drift is surfaced immediately.
- Limit v1 maps to coarse-grained API and capability surfaces; per-resource (e.g., single media item) visibility remains out of scope.
- Include timestamps for last refresh and highlight when cache is invalidated due to config or role updates.

### API Endpoints
- `GET /api/v1/privileges/self`
- `GET /api/v1/privileges/users/{user_id}`
- `GET /api/v1/privileges/teams/{team_id}`
- `GET /api/v1/privileges/org`
- `GET /api/v1/privileges/snapshots`
- `GET /api/v1/privileges/snapshots/{snapshot_id}`
- `POST /api/v1/privileges/snapshots`
- `GET /api/v1/privileges/snapshots/{snapshot_id}/export.{csv|json}`

### Admin View
- Default to aggregated counts (users and endpoints grouped by role, team, and resource) with server-side drill-down that reveals paginated user x endpoint detail when requested, alongside multi-select filters for user(s), roles, teams, resources, and sensitivity tiers.
- Offer CSV/JSON export for audits and optional diff view comparing two users or snapshots.
- Surface alerts for stale or conflicting configurations (e.g., endpoint registered but missing dependency, user assigned deprecated role).

### Organization-Wide Map
- Aggregate all users within an organization, grouped by role or team, with counts of accessible endpoints per category.
- Accept optional `org_id` query parameter for multi-tenant scoping; when omitted, returns all users visible to the caller.
- Restrict access to org owners and higher; provide drill-down from summary to user-level detail.
- Support scheduled snapshot generation for compliance audits (configurable cadence) -- *deferred to v1.1*.

### Team Map
- Allow team leads and above to view the privilege map limited to their team(s).
- Enable quick comparisons between members to identify missing permissions before project work begins.
- Provide action recommendations (e.g., "User lacks `media.ingest` scope required for DS Pipeline").

### Individual Map (Self)
- Expose a personal capability list, including endpoint descriptions, required headers, example calls, and links to documentation.
- Indicate which features are currently gated (e.g., "Requires Org upgrade" or "Contact Admin for access").
- Include an API endpoint (`GET /api/v1/privileges/self`) so CLIs/scripts can tailor UI based on real-time capabilities.

### Summary & Detail Contracts
- Summary endpoints support `group_by` (org: `role|team|resource`; team: `member|resource`), optional `since`, `include_trends`; responses include `trends` arrays when requested. Each trend object contains `{ "key": "<bucket identifier>", "window": { "start": "<ISO8601>", "end": "<ISO8601>" }, "delta_users": <int>, "delta_endpoints": <int>, "delta_scopes": <int> }`. If `since` is omitted, `window.start` defaults to 30 days prior to `generated_at`.
- Detail endpoints enforce pagination (`page`, `page_size <= 500`), reject >50k row pulls with `429`, and expose per-user scope status (`allowed|blocked` with `blocked_reason`). Supported filters: `resource`, `role` (org/team detail), `view=summary|detail`.
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
- Self map mirrors detail schema without identity fields (`user_id`, `user_name`) and adds `recommended_actions` entries; backend maps `blocked_reason` values to actions:
  - `feature_flag_disabled` -> action: "Request org upgrade", reason: "Feature flag disabled"
  - `missing_scope` -> action: "Request scope assignment", reason: "Scope not assigned"
  - Additional reasons may be appended with backward-compatible defaults (UI should treat unknown reasons as informational badges).

### Aggregation & Drill-Down API Contract
- **Summary Endpoints** (`GET /api/v1/privileges/org`, `GET /api/v1/privileges/teams/{team_id}`):
  - Query params:
    - `group_by`: org supports `role`, `team`, or `resource` (default `role`); team supports `member` or `resource` (default `member`).
    - `include_trends` (bool, default `false`): when `true`, the response adds a `trends` array.
    - `since` (ISO timestamp, optional): bounds the aggregation window; defaults to previous 30 days.
    - `org_id` (optional, org endpoint only): filter to a specific organization in multi-tenant deployments.
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
- **Trend Semantics**: When `include_trends=true`, responses add the `trends` array where each entry corresponds to a `buckets[].key` and reports deltas over the window. If `since` is provided, the window begins at that timestamp; otherwise it spans 30 days prior to `generated_at`.

### Snapshot Store & Retention
- DB-backed snapshots with metadata (`target_scope`, org/team IDs, `catalog_version`, summary counts, sensitivity breakdowns, scope IDs).
- Filters: pagination, date range, `generated_by`, `org_id` XOR `team_id`, `catalog_version`, `scope`, `include_counts`.
- Nightly cleanup job enforces retention: full-fidelity rows remain for `PRIVILEGE_SNAPSHOT_RETENTION_DAYS` (default 90), oldest snapshot per ISO week is kept up to `PRIVILEGE_SNAPSHOT_WEEKLY_RETENTION_DAYS` (default 365), then purged. When detail matrices are downsampled, the API returns `410 Gone`; once metadata is deleted the API returns `404`.
- `POST /privileges/snapshots` validates required identifiers (`org_id`, `team_id`, `user_ids`) based on `target_scope`. Supports synchronous 201 (returns snapshot record) or async 202 (queues job). Request body:
  ```json
  {
    "target_scope": "org|team|user",
    "org_id": "acme",
    "team_id": "team-123",
    "user_ids": ["user-7"],
    "catalog_version": "1.0.0",
    "notes": "Quarterly audit",
    "async": false
  }
  ```
  - `201 Created` response (`async=false`): snapshot record with summary counts, `target_scope`, `catalog_version`, and metadata.
  - `202 Accepted` response (`async=true`): `{"request_id": "...", "status": "queued", "estimated_ready_at": "<ISO8601>"}`; clients poll list endpoint for completion.

### Snapshot Detail Endpoint
- **Endpoint**: `GET /api/v1/privileges/snapshots/{snapshot_id}`
- Accepts `page`/`page_size` query params, returns summary + paginated matrix (`detail.page`, `detail.page_size`, `detail.total_items`, `detail.items[]`) and includes `etag` for cache validation.
- Returns `404` when snapshot metadata is purged, `410 Gone` when the snapshot exists but its detail matrix has been downsampled.
- Response:
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
      "items": [...]
    },
    "etag": "W/\"snap-2025-01-15-001-v1\""
  }
  ```
- Bulk exports use separate streaming endpoints (`GET /api/v1/privileges/snapshots/{id}/export.{csv|json}`) with server-side chunking.

### Snapshot Listing
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
- When both `date_from` and `date_to` are absent, defaults to last 30 days. If `scope` is provided, `include_counts` is forced true.

### WebUI Requirements
- **Status: not started** -- all items below are acceptance criteria for the WebUI phase.
- Admin dashboard: aggregated cards, filters, server-side virtualized tables, CSV/JSON export, diff comparisons, stale-config alerts.
- Org/team dashboards: summary cards with drill-down tables, quick filters, action recommendations, sparklines showing counts by category.
- Self view: friendly card list grouped by capability category with quick-copy for example curl commands and call-to-action for requesting access.
- Tooltips describing dependencies and privilege catalog metadata.
- Column pinning, severity badges, hover tooltips for auth dependency names.

## Non-Functional Requirements
- **Security**: Reuse existing RBAC dependencies; prevent leakage of hidden routes. Users can only request maps they have rights to see.
- **Performance**: Initial map generation <2s for <=500 endpoints; cached responses <300 ms. Admin drill-down views rely on server-side pagination so clients never render full 10k x 1k matrices.
- **Scalability**: Support 10k users & 1k endpoints; rely on caching, incremental summaries, paginated detail queries capping payload sizes.
- **Reliability**: Automatic cache invalidation on role/config changes; scheduled refresh for stale entries.
- **Auditability**: Immutable snapshots with documented retention and metrics. Nightly retention task keeps full-fidelity snapshots for 90 days, downsamples to one per ISO week up to 12 months, then purges.
- **Instrumentation**: Track map fetches, cache hit rates, export frequency, generation latency, invalidations, snapshot table size (`rows`, `bytes`). Emit `privilege_snapshots_table_rows` (all backends) and `privilege_snapshots_table_bytes` (Postgres) gauges.

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
  - Keys follow `privmap:{view}:{hash(filters)}` format where `view` is one of `self`, `user`, `team`, `org`, `summary`, `detail`; `hash` derived from sorted query params and user/team IDs.
  - Default TTL 15 minutes (configurable via `PRIVILEGE_MAP_CACHE_TTL_SECONDS`), refreshed on cache hits (sliding TTL optional).
  - Invalidation triggered by role assignment changes, catalog version bumps, deployment events. Multi-instance deployments broadcast invalidations via Redis pub/sub channel `privmap:invalidate`.
  - Trend computation windows default to 30 days but accept `window_days` override (1-90); trends stored alongside cache entry metadata so recomputation is deterministic.
- Access control: Guard new endpoints using existing dependency injection patterns (`AdminRequired`, `OrgManagerRequired`, `TeamLeadRequired`, `CurrentUser`). Note: currently only admin-level guards are implemented; tiered access is tracked for v1.1.
- Retention & downsampling: AuthNZ scheduler runs a nightly job enforcing the 90-day full snapshot window, collapses older data to weekly representatives up to 12 months, and purges legacy records. Downsampled snapshots are marked in the database and return `410 Gone` via the detail endpoint.

### Privilege Metadata Catalog Schema
- **Storage**: `tldw_Server_API/Config_Files/privilege_catalog.yaml` (source-controlled, loaded into `PrivilegeCatalog` helper on startup).
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
    - `ownership_predicates` (array[str], optional): Coarse-grained predicates (`same_org`, `same_team`, `self_only`).
    - `doc_url` (string, optional): Link to internal/external documentation.
  - `feature_flags`: Array of flag definitions with `id`, `description`, `default_state`, `allowed_roles`, `expires_at` (optional).
  - `rate_limit_classes`: Definitions that map class names to policy metadata (`requests_per_min`, `burst`, `notes`).
  - `ownership_predicates`: Registry describing each predicate name, evaluation helper, and notes on visibility.
- **Change Management**: Updates require PR with catalog diff, automated schema validation, and notification in release notes. Snapshots include `catalog_version` so downstream systems can reconcile scope meanings over time.

### Example Privilege Scope Entries

The Privilege Metadata Catalog includes entries for all first-class permission scopes, such as:

- `media.create`, `media.read`, `media.update`, `media.delete` -- core media ingestion and management.
- `evals.read`, `evals.manage` -- evaluations CRUD and run management.
- `workflows.admin` -- workflows scheduler administration.
- `flashcards.admin` -- flashcards import abuse-cap overrides (TSV/JSON import endpoints that accept higher `max_lines` / `max_items` / `max_field_length` settings for bulk operations).
- `embeddings.admin` -- embeddings v5 admin and maintenance utilities (DLQ tools, stage controls, job-skip registry, ledger inspection, re-embed scheduling, and orchestrator diagnostics).

Each scope entry records sensitivity tier, owning module, and default role bindings so the generated maps can surface flashcards admins alongside other domain-specific administrators.

## Error Code Reference

| Endpoint | Code | Condition |
|---|---|---|
| All privilege endpoints | `400` | Invalid query parameters or filter values |
| All privilege endpoints | `403` | Insufficient role to access the requested view |
| `GET /privileges/org` (detail), `GET /privileges/users/{user_id}`, `GET /privileges/teams/{team_id}` (detail) | `429` | Pagination offset exceeds 50k row limit |
| `GET /privileges/snapshots/{snapshot_id}` | `404` | Snapshot metadata purged by retention policy |
| `GET /privileges/snapshots/{snapshot_id}` | `410` | Snapshot exists but detail matrix downsampled to weekly summary |
| `POST /privileges/snapshots` | `201` | Synchronous snapshot created successfully |
| `POST /privileges/snapshots` | `202` | Async snapshot job queued |
| `POST /privileges/snapshots` | `422` | Invalid scope/ID combination (e.g., `target_scope=team` without `team_id`) |
| `GET /privileges/snapshots/{snapshot_id}/export.{csv,json}` | `404` | Snapshot not found |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PRIVILEGE_MAP_CACHE_TTL_SECONDS` | `900` | TTL for cached privilege map summaries (seconds). Minimum enforced: 10s. |
| `PRIVILEGE_METADATA_VALIDATE_ON_STARTUP` | `1` | Set to `0` to skip catalog validation on startup (useful for tests). |
| `PRIVILEGE_SNAPSHOT_RETENTION_DAYS` | `90` | Full-fidelity snapshot retention window. |
| `PRIVILEGE_SNAPSHOT_WEEKLY_RETENTION_DAYS` | `365` | Weekly-downsampled snapshot retention window. |

## Implementation Phases
1. **Discovery & Design (1 week)** -- *Status: complete*
   - Audit metadata coverage, finalize API schemas, align caching strategy.
2. **Backend Foundations (2 weeks)** -- *Status: complete*
   - Catalog loader, introspection registry, aggregation engine, retention job, refreshed tests.
3. **WebUI Integration (2 weeks)** -- *Status: not started*
   - Build admin/org/team/self components, export flows, onboarding copy.
   - Acceptance criteria:
     - Admin dashboard with virtualized tables, filters, CSV/JSON export buttons.
     - Org/team drill-down views with summary cards and sparklines.
     - Self view with capability cards, example curl commands, and "request access" CTAs.
     - Accessibility review (WCAG AA).
4. **Pilot & Rollout (1 week)** -- *Status: queued* (blocked on phase 3)
   - Enable internally, gather feedback, tune metrics, publish documentation.

### Upcoming Deliverables
- Surface trend deltas + cache hit telemetry in metrics dashboards and surface summary badges in the WebUI when Prometheus wiring is ready.
- Validate virtualization + export flows against 10k x 1k synthetic datasets; capture render/export timings for documentation.
- Prepare pilot playbook: enable feature flags, capture metrics baselines, draft admin onboarding comms.
- Refresh API + frontend docs with Redis cache knobs, export endpoints, and support troubleshooting guidance.
- Implement tiered access control (`OrgManagerRequired`, `TeamLeadRequired` dependencies) for v1.1.

### QA & Performance Checkpoints
- End of M2: regression tests ensure introspection + aggregation produce matching outputs for sample routes (diff snapshot stored in CI artifacts).
- End of M3: load test cache layer with 10k users/1k routes; verify cache hit rate >=80% and invalidation propagation latency <5s.
- End of M4: retention job soak test in staging (simulate 12 months of snapshots) with success criteria for cleanup duration (<10 min) and no data loss within policy window.
- M5: WebUI accessibility review (WCAG AA) and UX sign-off; export endpoints validated against rate limits and large dataset streaming.

## Testing Strategy
- Unit tests for catalog loader, evaluator edge cases, snapshot store DDL & retention logic **(status: passing)**.
- Integration tests for all endpoints (summary/detail/self/snapshot create/list/detail/export) covering filters, pagination, auth guards, and error cases. Include distributed cache invalidation scenario (two app instances) and trend window variations.
- Automated CI guard compares the serialized route registry against a checked-in snapshot (`Helper_Scripts/update_privilege_registry_snapshot.py` regenerates the fixture when intentional changes occur).
- Performance tests with synthetic datasets (10k users, 1k endpoints) to verify pagination guardrails.
- Negative tests ensuring unauthorized access and invalid scope inputs raise appropriate errors.
- API contract tests for summary vs. detail views should validate enforced `page_size` caps and `429` behavior when clients attempt unbounded retrieval.
- Post-backend integration target: end-to-end test harness seeded with synthetic AuthNZ + catalog data to validate cache invalidation behavior and trend delta accuracy across two app instances.
- Regression coverage: `test_privilege_cache.py` validates Redis generation sync; `test_privilege_endpoints.py::test_export_snapshot_json` / `test_export_snapshot_csv` lock export responses.
- UI automated tests (when WebUI is implemented): cover admin/org/team/self pages, export downloads, and "request access" CTA flows; browser-based smoke suite runs nightly.

## Risks & Mitigations
- **Incomplete metadata**: Add CI validation; backfill missing route annotations.
- **Performance under load**: Cache results, paginate, precompute aggregates; load-test against 10k x 1k dataset before rollout.
- **Security leaks**: Reuse proven dependency guards; add regression tests for hidden routes.
- **Stale data**: Invalidate caches on role/config change; expose manual refresh controls; clearly display timestamps; use Redis pub/sub to broadcast invalidations across workers.
- **Snapshot storage growth**: Retention job instrumentation with alerts (`privilege_snapshots_table_bytes` threshold); configurable env vars documented; periodic review of downsampling logic.
- **Worker failures**: Background queue integrates exponential backoff (max 5 retries) and emits alerts via existing monitoring (PagerDuty + Prometheus alert rules).

## Dependencies
- Accurate metadata on all FastAPI routes (tags, descriptions, dependency annotations).
- Privilege Metadata Catalog defined and versioned so scopes, feature flags, sensitivity tiers, and rate-limit classes are discoverable.
- Existing auth and RBAC services providing user-role-scope resolution.
- WebUI component library support for tables, filters, and export modals.
- Cache infrastructure (Redis or equivalent) in target deployment environments.
- AuthNZ scheduler running in production environments so nightly retention/metric tasks execute.

## Rollout & Communication
- Release notes targeted at admins; in-app toast linking to documentation.
- Admin onboarding guide and quickstart videos for team leads and end users.
- Document retention policy + metrics knobs in security/compliance handbooks.

## Resolved Questions
- **Historical diffs beyond snapshots?** Deferred to v2. The snapshot store provides point-in-time records; a timeline/diff view would require additional storage and UI work.
- **Sample requests in exports?** No. Exports include endpoint metadata only. Sample curl commands are shown in the self-view UI, not in compliance exports.
- **Third-party provider limitations?** Out of scope for v1. Provider quota visibility would require integration with vendor APIs and is tracked as a future enhancement.
- **Regulatory retention requirements?** The default 12-month weekly retention is configurable via `PRIVILEGE_SNAPSHOT_WEEKLY_RETENTION_DAYS`. Operators with longer requirements should set this env var accordingly. Encrypted snapshot storage is deferred to v2.
