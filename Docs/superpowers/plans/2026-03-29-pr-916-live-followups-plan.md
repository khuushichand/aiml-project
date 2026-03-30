## Stage 1: Confirm Remaining PR Issues
**Goal**: Re-check the live PR state and isolate the issues that are still actionable on the current head.
**Success Criteria**: Remaining failures/comments are reduced to a concrete list with root-cause evidence.
**Tests**: GitHub API check-run inspection, review comment inspection, local code-path inspection.
**Status**: Complete

## Stage 2: Fix CodeQL Proxy Alert
**Goal**: Remove the remaining SSRF-style CodeQL finding in the CDP workflow proxy path.
**Success Criteria**: Proxy request construction pins the backend origin at the sink, rejects non-API requests, and has regression coverage.
**Tests**: Targeted Vitest coverage for the proxy request builder.
**Status**: Complete

## Stage 3: Reproduce And Fix UX Smoke Gate
**Goal**: Reproduce the failing UX smoke workflow locally and patch the underlying regression.
**Success Criteria**: The failing smoke step is identified, fixed, and the targeted smoke command passes locally.
**Tests**: Matching frontend smoke command(s) from `.github/workflows/frontend-ux-gates.yml`.
**Status**: Complete

## Stage 4: Verify And Publish
**Goal**: Verify the touched scope, update the plan, and push the follow-up commit to the PR branch.
**Success Criteria**: Relevant tests pass, Bandit is clean for touched Python scope if any, and the branch is pushed.
**Tests**: `git diff --check`, targeted frontend tests, targeted smoke command(s), additional checks as needed.
**Status**: Complete
