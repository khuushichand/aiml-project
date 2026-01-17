## Stage 1: API Schemas
**Goal**: Define Pydantic request/response models for Data Tables endpoints.
**Success Criteria**: Schemas cover generate/list/detail/update/regenerate/job status shapes.
**Tests**: Schema-level validation tests (optional); exercised by integration tests.
**Status**: Complete

## Stage 2: Data Tables Endpoints
**Goal**: Implement CRUD + generate/regenerate + job status/cancel endpoints.
**Success Criteria**: Endpoints return expected shapes, enforce AuthNZ, and scope by owner.
**Tests**: Integration tests for generate/list/get/update/delete and job status/cancel.
**Status**: Complete

## Stage 3: App Wiring + OpenAPI Tags
**Goal**: Wire router into FastAPI app and register OpenAPI tags.
**Success Criteria**: Routes are reachable under `/api/v1/data-tables` and appear in OpenAPI.
**Tests**: Smoke test via TestClient or OpenAPI check.
**Status**: Complete

## Stage 4: Integration Tests
**Goal**: Add API integration tests against a temp Media DB + Jobs DB.
**Success Criteria**: Tests pass for generate/list/get/update/delete and job status/cancel.
**Tests**: New tests under `tldw_Server_API/tests/DataTables/`.
**Status**: Complete
