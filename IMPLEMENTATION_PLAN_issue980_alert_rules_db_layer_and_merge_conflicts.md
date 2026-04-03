## Stage 1: Define Refactor Target
**Goal**: Capture the DB-layer refactor and merge-resolution work in a branch-local plan.
**Success Criteria**: Plan file exists with concrete stages for DB refactor, verification, and merge-conflict handling.
**Tests**: N/A
**Status**: Complete

## Stage 2: Add Refactor Guard Test
**Goal**: Add or extend tests so the CRUD path is exercised through the DB_Management module boundary.
**Success Criteria**: A focused test fails before the refactor because the expected DB helper API is incomplete or unused.
**Tests**: `python -m pytest tldw_Server_API/tests/test_watchlist_alert_rules.py -k db -v`
**Status**: Complete

## Stage 3: Move CRUD Persistence Into DB_Management
**Goal**: Move alert-rule CRUD SQL into `watchlist_alert_rules_db.py` and keep `alert_rules.py` focused on business logic and evaluation.
**Success Criteria**: `alert_rules.py` no longer performs direct alert-rule CRUD SQL or schema SQL; DB helpers own that persistence.
**Tests**: `python -m pytest tldw_Server_API/tests/test_watchlist_alert_rules.py -v`
**Status**: Complete

## Stage 4: Verify Security and Merge Current Dev
**Goal**: Verify the touched scope, merge `dev` into the PR branch, and resolve conflicts without regressing the alert-rule changes.
**Success Criteria**: Branch merges cleanly, targeted tests pass, and Bandit reports no new findings in touched files.
**Tests**: `python -m pytest tldw_Server_API/tests/test_watchlist_alert_rules.py -v`
**Tests**: `python -m bandit -r tldw_Server_API/app/api/v1/endpoints/watchlist_alert_rules.py tldw_Server_API/app/core/Watchlists/alert_rules.py tldw_Server_API/app/core/DB_Management/watchlist_alert_rules_db.py -f json -o /tmp/bandit_issue980_alert_rules.json`
**Status**: Complete
