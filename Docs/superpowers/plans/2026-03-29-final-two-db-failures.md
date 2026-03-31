## Stage 1: Confirm Remaining Failure Contracts
**Goal**: Reproduce the last two failing tests and identify whether each is a wrapper regression or a real schema bug.
**Success Criteria**: Exact failing assertions and implementation touchpoints are identified.
**Tests**: `python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py::test_media_db_api_permanently_delete_item_delegates_to_helper tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py::test_media_postgres_migration_reaches_v11_and_restores_mediafiles_table -q`
**Status**: Complete

## Stage 2: Restore API Delegation Contract
**Goal**: Make `media_db.api.permanently_delete_item` delegate to the maintenance helper without freezing the helper reference at import time.
**Success Criteria**: The API import test can monkeypatch the helper and still observe delegated calls.
**Tests**: `python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py::test_media_db_api_permanently_delete_item_delegates_to_helper -q`
**Status**: Complete

## Stage 3: Make Postgres Table Lookup Match Folded Identifiers Safely
**Goal**: Allow PostgreSQL `table_exists()` checks using mixed-case caller names to find unquoted folded-lowercase tables without breaking code that intentionally distinguishes quoted CamelCase tables.
**Success Criteria**: `table_exists("MediaFiles")` succeeds when the actual Postgres table is the unquoted folded `mediafiles`, while lowercase-only lookups remain exact.
**Tests**: `python -m pytest -q tldw_Server_API/tests/DB_Management/test_database_backends.py -k table_exists -q`
**Status**: Complete

## Stage 4: Verify and Security Check
**Goal**: Run focused regression tests and Bandit for the touched scope.
**Success Criteria**: Focused pytest passes and Bandit reports no new findings in modified files.
**Tests**: Focused pytest for the touched DB tests; `python -m bandit -r <touched_paths> -f json -o /tmp/bandit_final_two_db_failures.json`
**Status**: Complete
