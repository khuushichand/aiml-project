## Stage 1: Baseline and Target Selection
**Goal**: Confirm current BLE001 total and identify highest-offender files.
**Success Criteria**: `ruff --select BLE001 --statistics` captured and top offenders listed.
**Tests**: `ruff check --select BLE001 --statistics tldw_Server_API`; per-file ranking command.
**Status**: Complete

## Stage 2: Fix Highest Offender Group (9-count files)
**Goal**: Remove BLE001 in current 9-count files one by one using explicit exception types.
**Success Criteria**: Each touched file has zero BLE001 in file-level check.
**Tests**: `ruff check --select BLE001 <file>` for each edited file.
**Status**: Complete

## Stage 3: Re-run and Continue with New Largest Offenders
**Goal**: Re-rank after each batch and repeat on next largest files.
**Success Criteria**: Global BLE001 total decreases and next targets identified.
**Tests**: global stats + ranking command after each batch.
**Status**: In Progress

## Stage 4: Final Verification and Report
**Goal**: Provide final counts, edited files, and residual hotspots.
**Success Criteria**: User has updated total, what changed, and next best targets.
**Tests**: final `ruff --select BLE001 --statistics`.
**Status**: Not Started
