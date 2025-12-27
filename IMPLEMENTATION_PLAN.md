## Stage 1: Review Delta Data Model
**Goal**: Persist nightly extractor delta summaries for claims review corrections.
**Success Criteria**: New table(s) exist with per-extractor metrics (approval rate, edit rate, correction motifs) and can be written/read via MediaDatabase helpers.
**Tests**: Unit test for DB helpers (SQLite); migration coverage for Postgres schema ensure.
**Status**: Complete

## Stage 2: Nightly Aggregation Job
**Goal**: Implement a scheduled job that aggregates corrections from `claims_review_log` and `claims` into the new metrics table.
**Success Criteria**: Job runs on schedule, writes aggregates for each user DB, and is resilient to empty/no-op days.
**Tests**: Scheduler unit test with a seeded DB, asserts metrics rows written and idempotent.
**Status**: Complete

## Stage 3: API + Analytics Wiring
**Goal**: Expose aggregated metrics via a read-only API endpoint and optionally include in existing analytics export/dashboard responses.
**Success Criteria**: Endpoint returns expected metrics filtered by date range and extractor, and the analytics export can include the summary.
**Tests**: API integration test for the new endpoint and export payload check.
**Status**: Complete

## Stage 4: Docs + PRD Sync
**Goal**: Update reviewer workflow docs to mark nightly delta reporting and correction pipeline status.
**Success Criteria**: PRD and ops docs reflect the new job, env flags, and API surface.
**Tests**: N/A
**Status**: Not Started
