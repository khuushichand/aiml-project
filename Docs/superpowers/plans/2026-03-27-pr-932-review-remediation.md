# PR 932 Review Remediation Plan

## Stage 1: Verify Current Unresolved Threads
**Goal**: Separate genuinely open PR issues from outdated-but-unresolved review threads.
**Success Criteria**: Open review threads are grouped by file and priority, and stale threads are identified for follow-up replies instead of unnecessary code churn.
**Tests**: `gh api graphql` review thread query, targeted source inspection.
**Status**: Complete

## Stage 2: Fix Backend Correctness and API Contract Issues
**Goal**: Address current backend bugs and API modeling gaps that can lead to incorrect behavior, hidden failures, or unsafe persistence.
**Success Criteria**: Touched admin endpoints/services use validated models, surface failures correctly, and pass targeted backend tests.
**Tests**: Targeted `pytest` runs for admin budgets, admin tools, admin sessions MFA, admin usage, voice assistant, and related DB/service tests.
**Status**: Complete

## Stage 3: Fix Backend Persistence and Migration Gaps
**Goal**: Close schema/index/backfill issues that can break existing deployments or silently drop new data.
**Success Criteria**: Storage and migration code preserves new fields, backfills existing databases safely, and adds required indexes.
**Tests**: Targeted `pytest` runs for affected DB management and admin service modules.
**Status**: Complete

## Stage 4: Fix Frontend State, Polling, and Accessibility Issues
**Goal**: Address unresolved admin UI issues involving stale async state, overlapping polling, optimistic rollback, and missing accessibility semantics.
**Success Criteria**: High-signal admin UI issues are fixed in code and covered by existing or new focused tests where practical.
**Tests**: Targeted frontend unit tests and, if available, project type checks for touched admin-ui files.
**Status**: Complete

## Stage 5: Verify, Bandit, and Summarize Remaining Threads
**Goal**: Run verification on touched scope and identify any unresolved threads that should be answered/resolved instead of further code changes.
**Success Criteria**: Fresh verification output exists for tests and Bandit, and the remaining unresolved thread set is explained clearly.
**Tests**: Focused `pytest`, relevant frontend verification, and `python -m bandit -r <touched_paths>`.
**Status**: Complete
