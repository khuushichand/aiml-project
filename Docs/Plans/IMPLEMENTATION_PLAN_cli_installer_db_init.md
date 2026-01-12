## Stage 1: PRD Status + Plan Link
**Goal**: Update PRD statuses for Stage 2/3 and link this plan file.
**Success Criteria**: PRD reflects Stage 2 complete and Stage 3 in progress; plan file is referenced.
**Tests**: N/A
**Status**: Complete

## Stage 2: DB Command Implementation
**Goal**: Implement SQLite structure creation and Postgres connectivity validation in `db` command.
**Success Criteria**: Per-user SQLite files created; shared evaluations DB created; Postgres validation reported or errors clearly.
**Tests**: CLI integration tests for SQLite path creation and multi-user invalid URL error.
**Status**: In Progress

## Stage 3: Tests + Cleanup
**Goal**: Add/adjust tests to cover DB init behavior and error payloads.
**Success Criteria**: Tests pass for SQLite creation and invalid DATABASE_URL paths; optional Postgres check skipped when unavailable.
**Tests**: `tldw_Server_API/tests/wizard` suite passes.
**Status**: Not Started
