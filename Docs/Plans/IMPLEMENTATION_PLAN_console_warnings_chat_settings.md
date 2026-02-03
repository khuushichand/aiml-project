## Stage 1: Triage and Locate Sources
**Goal**: Identify the concrete components causing each console warning/error.
**Success Criteria**: File/line sources for StrictMode ref warning, 404, update depth, and AntD deprecations are documented.
**Tests**: Targeted ripgrep searches and file inspection.
**Status**: Complete

## Stage 2: Stop Update-Depth Loops
**Goal**: Prevent repeated parent notifications from workspace selection changes.
**Success Criteria**: Workspace selector notifies only on workspace id change in both shared UI and extension copies.
**Tests**: Component inspection plus smoke/e2e test run.
**Status**: Complete

## Stage 3: Remove Deprecations and 404/StrictMode Warnings
**Goal**: Address AntD deprecations, static asset 404s, and StrictMode ref warnings.
**Success Criteria**: Collapse uses `items`, deprecated props are removed, logo image src resolves correctly, and the router shim forwards refs.
**Tests**: Ripgrep checks for deprecated props and a smoke/e2e test run.
**Status**: Complete

## Stage 4: Verify with Tests
**Goal**: Confirm no regressions and that warnings are reduced.
**Success Criteria**: Relevant tests pass locally.
**Tests**: Run targeted frontend tests or the smoke suite if feasible. (`npm run lint` attempted but `npm` is unavailable in this environment.)
**Status**: In Progress
**Notes**: `npm`/Node tooling is not available in this environment, so frontend tests and linting could not be executed here.
