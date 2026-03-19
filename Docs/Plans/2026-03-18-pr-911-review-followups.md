## Stage 1: Triage PR Feedback
**Goal**: Verify each open PR #911 review finding against the current branch and reduce it to an actionable worklist.
**Success Criteria**: Every open comment is classified as `fix`, `reply-only`, or `already-covered`.
**Tests**: None
**Status**: Complete

## Stage 2: Fix Correctness and Reliability Findings
**Goal**: Land the confirmed runtime/session/claims rebuild fixes first.
**Success Criteria**: The request-scoped media DB session flow, runtime factory behavior, and claims rebuild selection logic are corrected with targeted regression coverage.
**Tests**: Focused pytest for `DB_Deps`, runtime factory, and claims startup/rebuild paths.
**Status**: Complete

## Stage 3: Fix Low-Risk Review Hygiene Items
**Goal**: Resolve the remaining accepted helper-script, typing, transaction, and docstring review findings without broadening scope.
**Success Criteria**: Accepted review comments are either fixed in code or rebutted with evidence.
**Tests**: Focused pytest for touched helpers/modules plus Bandit on touched Python scope.
**Status**: Complete

## Stage 4: Push and Respond on PR
**Goal**: Push the follow-up batch and close the review loop on GitHub.
**Success Criteria**: Branch is pushed, PR comments are replied to in-thread, and remaining non-actionable comments are explicitly answered.
**Tests**: `git status --short` clean after push
**Status**: In Progress
