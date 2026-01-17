## Stage 1: Decide + Document
**Goal**: Record the chosen template API surface and align PRDs.
**Success Criteria**: PRDs reflect `/api/v1/outputs/templates` as canonical for watchlists templates; legacy `/watchlists/templates` noted as fallback.
**Tests**: None.
**Status**: Complete

## Stage 2: Backend Integration
**Goal**: Allow watchlists outputs to resolve DB-backed templates by name with file-based fallback.
**Success Criteria**: Watchlists output generation uses output templates when available and falls back to file templates; unsupported formats are rejected.
**Tests**: Unit/integration tests for watchlists outputs with DB template names (if added).
**Status**: Complete

## Stage 3: Frontend Alignment
**Goal**: Update watchlists UI to list templates from `/api/v1/outputs/templates`.
**Success Criteria**: Template dropdown loads DB templates (excluding mp3) and help text references `/outputs/templates`.
**Tests**: Frontend smoke (manual).
**Status**: Complete

## Stage 4: Validate References
**Goal**: Ensure docs and code references are consistent.
**Success Criteria**: No remaining mismatched template API references in PRDs or watchlists UI.
**Tests**: None.
**Status**: Complete
