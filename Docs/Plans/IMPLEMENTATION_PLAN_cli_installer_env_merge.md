## Stage 1: Align PRD Status
**Goal**: Mark Stage 1 as In Progress and link this plan from the PRD.
**Success Criteria**: PRD Stage 1 status updated; PRD references this plan file.
**Tests**: N/A
**Status**: Complete

## Stage 2: Env Merge + Key Generation
**Goal**: Implement .env merge/update with backups, masking, and single-user key generation.
**Success Criteria**: .env updates are idempotent, deduped, and backed up; SINGLE_USER_API_KEY is generated when missing.
**Tests**: Unit tests for merge/idempotency/masking/backups.
**Status**: Complete

## Stage 3: CLI Integration + Tests
**Goal**: Wire env updates into CLI flows and add integration tests.
**Success Criteria**: CLI updates .env reliably and tests cover create/update/backup paths.
**Tests**: CLI integration tests using temporary directories.
**Status**: Complete
