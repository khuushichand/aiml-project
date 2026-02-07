## Stage 1: Inventory Remaining Runtime Truthiness Checks
**Goal**: Enumerate non-test callsites still using hardcoded truthy sets.
**Success Criteria**: Concrete path list and counts captured from grep.
**Tests**: N/A
**Status**: Complete

## Stage 2: Normalize Service/API Layer Checks
**Goal**: Replace hardcoded truthy checks in app services and API endpoint/dependency modules with shared helpers.
**Success Criteria**: No hardcoded truthy-set checks remain in touched service/api files.
**Tests**: Focused pytest for route/config/auth startup semantics.
**Status**: Complete

## Stage 3: Normalize Core Module Checks
**Goal**: Replace remaining hardcoded truthy checks in core modules with shared helpers where applicable.
**Success Criteria**: Runtime callsites reduced to intentional canonical helpers only.
**Tests**: Focused pytest for auth/evals/prompt/services slices.
**Status**: Complete

## Stage 4: Verify and Report Residual Backlog
**Goal**: Re-run grep + focused tests and report exact remaining work (if any).
**Success Criteria**: Deterministic pass/fail summary with counts.
**Tests**: pytest subset + grep counts.
**Status**: Complete
