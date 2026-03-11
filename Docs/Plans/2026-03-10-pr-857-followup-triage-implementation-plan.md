## Stage 1: Triage Current PR Blockers
**Goal**: Identify which remaining PR #857 blockers are actionable branch issues versus unrelated or stale CI noise.
**Success Criteria**: Unresolved review threads and failing checks are enumerated with evidence for each.
**Tests**: `gh pr checks 857 --repo rmusser01/tldw_server`, `gh api graphql ... reviewThreads ...`
**Status**: Complete

## Stage 2: Patch Verified Branch Issues
**Goal**: Implement the smallest fixes for blockers that are confirmed to belong to the PR branch.
**Success Criteria**: The unresolved review thread is addressed in code, and any branch-local CI regression identified by reproduction is fixed.
**Tests**: Focused tests for touched files and flows.
**Status**: Complete

## Stage 3: Verify And Update PR
**Goal**: Re-run focused verification, run Bandit on touched Python scope, and push the follow-up branch state.
**Success Criteria**: Relevant local checks pass and the PR can be updated with a factual status of remaining external blockers, if any.
**Tests**: Focused frontend/backend checks plus Bandit on touched Python files.
**Status**: Complete

## Stage 4: Repair Post-Merge CI Regressions
**Goal**: Fix the remaining GitHub CI failures introduced by the `dev` merge so PR #857 is buildable again.
**Success Criteria**: `UX Smoke Gate` root-cause build failures are resolved locally, `run-pre-commit` no longer rewrites touched files, and the branch is ready to re-push.
**Tests**: Focused route/helper vitest coverage, `bun run build` for `apps/tldw-frontend`, and local pre-commit on touched files.
**Status**: In Progress
