## Stage 1: Reconfirm Open PR Threads
**Goal**: Map each unresolved PR thread to the current `origin/dev` code and classify it as an active bug or an outdated thread.
**Success Criteria**: Every unresolved thread has a concrete disposition backed by local code inspection and live GitHub alert data.
**Tests**: GitHub GraphQL review-thread query, GitHub code-scanning alert inspection, local source inspection.
**Status**: Complete

## Stage 2: Add Regression Coverage
**Goal**: Capture the still-open path-validation and public-error-sanitization regressions with targeted tests.
**Success Criteria**: New or updated tests fail on the current head for the active issues only.
**Tests**: Targeted pytest cases for setup/audio sanitization and DB path validation.
**Status**: Complete

## Stage 3: Fix Active PR Findings
**Goal**: Remove the remaining valid CodeQL findings and align code paths with the intended trust boundaries.
**Success Criteria**: Active sink paths no longer accept untrusted filesystem paths or expose exception-derived diagnostics to clients.
**Tests**: Targeted pytest coverage plus focused local checks of the changed code paths.
**Status**: Complete

## Stage 4: Verify, Push, And Resolve Threads
**Goal**: Verify the touched scope, push the fix commit(s), and note which threads can now be resolved versus which are outdated-only.
**Success Criteria**: Verification passes, the branch is pushed, and the remaining thread state is reduced to only items awaiting GitHub reanalysis or manual resolution.
**Tests**: Targeted pytest, Bandit on touched Python scope, `git diff --check`, optional GitHub thread re-query.
**Status**: Complete
