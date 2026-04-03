## Stage 1: Validate Review Scope
**Goal**: Confirm which PR comments are technically correct for this codebase and branch.
**Success Criteria**: Each open review comment is classified as implement, partially implement, or reply with technical rationale.
**Tests**: N/A
**Status**: Complete

## Stage 2: Add Regression Tests
**Goal**: Capture the valid review findings with failing tests before changing production code.
**Success Criteria**: Tests cover single-rule fetch after update, invalid condition type rejection, deterministic update field handling, and malformed threshold handling.
**Tests**: `python -m pytest tldw_Server_API/tests/Watchlists/test_watchlist_alert_rules.py -v`
**Status**: Complete

## Stage 3: Implement Minimal Fixes
**Goal**: Update the API and core watchlist alert-rule modules to satisfy the validated review items.
**Success Criteria**: Shared condition types/constants exist, update path returns or fetches a single rule, malformed thresholds no longer crash evaluation, and update column handling is explicit/stable.
**Tests**: `python -m pytest tldw_Server_API/tests/Watchlists/test_watchlist_alert_rules.py -v`
**Status**: Complete

## Stage 4: Verify and Respond
**Goal**: Run security/test verification and reply on the PR threads.
**Success Criteria**: Targeted tests pass, Bandit reports no new issues in touched files, and each open review thread gets an accurate reply.
**Tests**: `python -m pytest tldw_Server_API/tests/Watchlists/test_watchlist_alert_rules.py tldw_Server_API/tests/test_watchlist_alert_rules_paths.py -v`
**Status**: Complete
