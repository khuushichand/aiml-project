# Task 5 Billing Schema Retirement Plan

## Stage 1: Lock OSS Expectations
**Goal**: Capture the fresh-install and runtime behavior Task 5 requires.
**Success Criteria**: Targeted tests fail because fresh OSS paths still create or depend on billing schema/repo code.
**Tests**: `python -m pytest tldw_Server_API/tests/AuthNZ/unit/test_subscription_plan_defaults.py tldw_Server_API/tests/Billing/test_billing_package_imports.py tldw_Server_API/tests/AuthNZ/unit/test_admin_budgets_service_backend_selection.py -v`
**Status**: In Progress

## Stage 2: Retire Fresh Billing Bootstrap
**Goal**: Stop fresh OSS migrations/bootstrap helpers from creating public billing tables, without dropping existing tables.
**Success Criteria**: SQLite/Postgres bootstrap paths no longer create billing-focused schema for fresh OSS installs; compatibility comments remain non-destructive.
**Tests**: Stage 1 tests plus any directly affected migration-focused tests.
**Status**: Not Started

## Stage 3: Decouple Remaining Runtime Paths
**Goal**: Make budget/quota runtime work without billing plan/subscription tables and retire public repo usage where practical.
**Success Criteria**: Admin budget helpers and billing package imports no longer require `billing_repo` or billing tables for fresh OSS runtime.
**Tests**: Stage 1 tests plus targeted admin budget tests.
**Status**: Not Started

## Stage 4: Verify And Finalize
**Goal**: Validate the touched scope and produce an isolated commit.
**Success Criteria**: Targeted pytest and Bandit checks pass; git diff is limited to Task 5 scope; commit created.
**Tests**: Targeted pytest command(s) and `python -m bandit -r <touched_paths> -f json -o /tmp/bandit_task5_billing_schema_retirement.json`
**Status**: Not Started
