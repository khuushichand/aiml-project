## Stage 1: Document Approved Fix Scope
**Goal**: Capture the validated design and concrete implementation scope for the follow-up review fixes.
**Success Criteria**: Design doc and implementation plan exist in `Docs/Plans/`.
**Tests**: None.
**Status**: Complete

## Stage 2: Add Regression Tests
**Goal**: Add failing tests for enterprise API-key login rejection, single-user privileged-action fallback, and stale auth bootstrap.
**Success Criteria**: New tests fail against the current implementation for the intended reasons.
**Tests**:
- `admin-ui/lib/auth.test.ts`
- `admin-ui/app/api/auth/apikey/route` tests or equivalent backend-facing coverage
- `tldw_Server_API/tests/Admin/...` guardrail coverage
**Status**: Complete

## Stage 3: Implement Fixes
**Goal**: Update auth route, auth bootstrap, and privileged-action verification to match the approved design.
**Success Criteria**: All new tests pass with minimal production changes.
**Tests**: Stage 2 suite.
**Status**: Complete

## Stage 4: Verify and Prepare Branch
**Goal**: Run the relevant frontend and backend verification suite and confirm the branch is ready for another review pass.
**Success Criteria**: Lint, test, build, targeted pytest, and bandit succeed.
**Tests**:
- `bun run lint`
- `bun run test`
- `bun run build`
- targeted `pytest`
- targeted `bandit`
**Status**: Complete
