## Stage 1: CRUD Helpers
**Goal**: Add MediaDatabase CRUD helpers for Data Tables (tables, columns, rows, sources).
**Success Criteria**: Create/list/get/update/delete helpers are implemented with pagination support.
**Tests**: N/A (implementation only).
**Status**: Complete

## Stage 2: Ownership Scoping And Soft Deletes
**Goal**: Ensure helpers support owner scoping and soft delete cascades.
**Success Criteria**: Owner filtering is available for list/get; soft delete updates child records.
**Tests**: N/A (implementation only).
**Status**: Complete

## Stage 3: Tests
**Goal**: Add unit tests for CRUD helpers and pagination behavior.
**Success Criteria**: Tests cover create/list/get/update/delete and row pagination.
**Tests**: `pytest tldw_Server_API/tests/...` (to be defined).
**Status**: Complete
