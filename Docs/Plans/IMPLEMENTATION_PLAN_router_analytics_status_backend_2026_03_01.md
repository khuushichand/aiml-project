## Stage 1: Router Analytics Contract and Schema Baseline
**Goal**: Define backend-facing request/response schemas for router analytics status surfaces.
**Success Criteria**: Admin schemas include range query, status payload, breakdown payload, and metadata payload models used by backend + frontend.
**Tests**: `tldw_Server_API/tests/Admin/test_router_analytics_schemas.py`
**Status**: Complete

## Stage 2: Usage Log Schema Enrichment for Router Analytics Dimensions
**Goal**: Extend AuthNZ usage schema to persist status-tab breakdown dimensions.
**Success Criteria**: `llm_usage_log` supports `remote_ip`, `user_agent`, `token_name`, and `conversation_id`; migration is additive and backward compatible for SQLite/Postgres.
**Tests**:
- `tldw_Server_API/tests/AuthNZ_SQLite/test_authnz_llm_usage_log_router_columns_sqlite.py`
- `tldw_Server_API/tests/AuthNZ_Postgres/test_authnz_llm_usage_log_router_columns_pg.py`
**Status**: Complete

## Stage 3: Usage Write-Path Enrichment
**Goal**: Populate new router analytics dimensions at write time from request context.
**Success Criteria**: Usage logging includes resolved client IP, user agent, token name derivation, and optional conversation id in supported call paths.
**Tests**: `tldw_Server_API/tests/Usage/test_usage_tracker_sqlite.py`
**Status**: Complete

## Stage 4: Router Analytics Aggregate Service (Status + Breakdowns)
**Goal**: Implement backend aggregation service for status KPIs, timeseries, and status breakdown tables.
**Success Criteria**:
- New admin service returns `RouterAnalyticsStatusResponse`.
- New admin service returns `RouterAnalyticsBreakdownsResponse`.
- Aggregation respects range window and optional provider/model/token filters.
- Backend supports SQLite and Postgres paths.
**Tests**:
- `tldw_Server_API/tests/Admin/test_router_analytics_service.py`
**Status**: Complete

## Stage 5: Admin Router Analytics Endpoints (Status Delivery Slice)
**Goal**: Expose Stage 4 aggregates via additive `/api/v1/admin/router-analytics/*` endpoints.
**Success Criteria**:
- Endpoints: `status`, `status/breakdowns`, and `meta`.
- Existing `/admin/usage` and `/admin/llm-usage*` endpoints unchanged.
- Admin scope restrictions (`org_id`) are applied consistently with current admin services.
**Tests**:
- `tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py`
- `tldw_Server_API/tests/Admin/test_admin_split_openapi_contract.py`
**Status**: Complete

## Stage 6: Verification and Security Scan
**Goal**: Validate touched scope and ensure no new security findings are introduced.
**Success Criteria**:
- Targeted pytest suites pass for touched scope.
- Bandit scan run on touched files; any new findings resolved.
**Tests**:
- `python -m pytest -q tldw_Server_API/tests/Admin/test_router_analytics_schemas.py tldw_Server_API/tests/Admin/test_router_analytics_service.py tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py tldw_Server_API/tests/Admin/test_admin_split_openapi_contract.py`
- `python -m bandit -r tldw_Server_API/app/services/admin_router_analytics_service.py tldw_Server_API/app/api/v1/endpoints/admin/admin_router_analytics.py tldw_Server_API/app/api/v1/endpoints/admin/__init__.py -f json -o /tmp/bandit_router_analytics_status_backend.json`
**Status**: Complete
