## Stage 1: Scope + Design
**Goal**: Define doctor heuristics, outputs, and auto-fix behavior.
**Success Criteria**: Doctor actions and confirmation flow documented in the plan.
**Tests**: N/A (design stage).
**Status**: Complete

## Stage 2: Implement Doctor Heuristics
**Goal**: Detect missing .env keys, gitignore entries, ffmpeg absence, invalid DATABASE_URL, and port conflicts.
**Success Criteria**: `doctor` emits structured JSON actions and supports dry-run + confirmation.
**Tests**: Unit tests covering each heuristic.
**Status**: Complete

## Stage 3: Integration Tests
**Goal**: Validate end-to-end doctor run with applied fixes in tmpdir.
**Success Criteria**: Doctor applies env/gitignore fixes when confirmed.
**Tests**: Integration test for `doctor --yes`.
**Status**: Complete

## Stage 4: Docs + PRD Updates
**Goal**: Update wizard docs and PRD Stage 6 status.
**Success Criteria**: Docs mention new doctor behavior and flags; PRD updated.
**Tests**: N/A (doc stage).
**Status**: Complete
