## Stage 1: Refresh Merge State
**Goal**: Fetch the latest `origin/dev` and reproduce the PR conflict locally.
**Success Criteria**: Local merge attempt shows the exact conflicted files.
**Tests**: `git fetch origin dev`, `git merge --no-commit --no-ff origin/dev`
**Status**: In Progress

## Stage 2: Resolve Conflicted Files
**Goal**: Reconcile `dev` changes with the companion branch without dropping reviewed companion behavior.
**Success Criteria**: All conflict markers removed and intended behavior preserved.
**Tests**: targeted file inspection, `git diff --check`
**Status**: Not Started

## Stage 3: Verify Integration
**Goal**: Run focused backend/frontend verification for the touched conflict areas.
**Success Criteria**: Relevant tests pass and Bandit shows no new findings in touched backend files.
**Tests**: targeted `pytest`, `vitest`/Playwright if needed, `python -m bandit -r <touched_backend_paths>`
**Status**: Not Started

## Stage 4: Finalize Branch
**Goal**: Commit the conflict resolution and confirm PR mergeability.
**Success Criteria**: Merge commit created locally, branch clean, PR no longer conflicting after push.
**Tests**: `git status --short --branch`, PR mergeability check
**Status**: Not Started
