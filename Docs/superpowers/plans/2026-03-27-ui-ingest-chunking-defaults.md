## Stage 1: Reproduce UI Default Regression
**Goal**: Add a regression test showing quick-ingest request builders should preserve chunking by default when the common options object is missing or partial.
**Success Criteria**: A focused UI test fails against current behavior.
**Tests**: `bunx vitest run apps/packages/ui/src/services/__tests__/quick-ingest-batch.test.ts -t "defaults perform_chunking to true when common options are omitted"`
**Status**: Complete

## Stage 2: Normalize Chunking Defaults
**Goal**: Patch the UI/request builders to treat `perform_chunking` as enabled unless explicitly set to `false`.
**Success Criteria**: The regression passes and the same default is used across quick-ingest, background runtime, and review/draft processing option snapshots.
**Tests**: `bunx vitest run apps/packages/ui/src/services/__tests__/quick-ingest-batch.test.ts`
**Status**: Complete

## Stage 3: Repair Local Pending AV Rows
**Goal**: Reprocess affected local AV rows that were persisted without chunk rows.
**Success Criteria**: Target media IDs have chunk rows in `UnvectorizedMediaChunks` and no longer rely on late chunking.
**Tests**: Local DB verification queries against `Databases/user_databases/1/Media_DB_v2.db`
**Status**: Complete
