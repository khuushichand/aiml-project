## Stage 1: Catalog + Catalog Endpoint
**Goal**: Add a YAML-backed user profile config catalog and expose it via `/api/v1/users/profile/catalog`.
**Success Criteria**: Catalog loads/validates; endpoint returns catalog with ETag + cache headers; unit + endpoint tests pass.
**Tests**: `tldw_Server_API/tests/UserProfile/test_user_profile_catalog.py`
**Status**: Complete

## Stage 2: Profile Read Service + Read Endpoints
**Goal**: Implement `UserProfileService` and read endpoints for self/admin.
**Success Criteria**: `/api/v1/users/me/profile` and `/api/v1/admin/users/{user_id}/profile` return aggregated sections with filters.
**Tests**: Integration tests for self/admin profile retrieval, section filtering, and scope enforcement.
**Status**: Complete

## Stage 3: Preferences Overrides + Update Endpoints
**Goal**: Add user config overrides storage and PATCH endpoints (self/admin).
**Success Criteria**: Catalog-driven validation, per-key editability enforcement, optimistic version handling.
**Tests**: Unit tests for merge logic + validation; integration tests for PATCH semantics and permissions.
**Status**: Complete

## Stage 4: Bulk Update + Deprecations
**Goal**: Implement bulk update with dry-run/audit and deprecate legacy endpoints.
**Success Criteria**: Bulk update semantics + audit events; legacy endpoints emit deprecation headers and can be gated by flag.
**Tests**: Integration tests for bulk filters/dry-run; deprecation header tests.
**Status**: Complete

## Stage 5: Effective Config + Optimistic Lock
**Goal**: Add effective_config layering and enforce profile_version optimistic locks.
**Success Criteria**: effective_config section returns layered values; update endpoints return 409 on version mismatch.
**Tests**: Profile read effective_config tests; profile update conflict tests.
**Status**: Complete
