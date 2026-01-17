## Stage 1: Export wiring plan
**Goal**: Define the export endpoint contract and reuse File_Artifacts service paths.
**Success Criteria**: Plan covers response shape, async handling, and limits.
**Tests**: N/A.
**Status**: Complete

## Stage 2: Endpoint + payload mapping
**Goal**: Implement data tables export endpoint and map Media DB rows into File_Artifacts payloads.
**Success Criteria**: Endpoint returns file_id + export status (ready/pending) and respects ownership.
**Tests**: Unit test for row/column mapping; integration test for export flow.
**Status**: Complete

## Stage 3: Documentation + cleanup
**Goal**: Update design doc stage status and add export docs/tests coverage.
**Success Criteria**: Stage 5 marked complete; tests passing.
**Tests**: Export integration tests for csv/json; xlsx optional if openpyxl installed.
**Status**: Complete
