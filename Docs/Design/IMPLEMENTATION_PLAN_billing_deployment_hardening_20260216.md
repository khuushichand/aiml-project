## Stage 1: Harden Billing Schema Bootstrap
**Goal**: Ensure PostgreSQL billing bootstrap creates all runtime billing tables.
**Success Criteria**: `ensure_billing_tables_pg` covers webhook/events, payments, and billing audit tables.
**Tests**: Add unit coverage for billing DDL table set.
**Status**: Complete

## Stage 2: Fix Webhook Subscription Lifecycle Robustness
**Goal**: Remove silent no-op on checkout completion and eliminate unsafe free-plan fallback ID.
**Success Criteria**: checkout webhook ensures org subscription row exists; deleted webhook handles missing free plan safely.
**Tests**: Add/extend unit tests for missing subscription row and missing free plan handling.
**Status**: Complete

## Stage 3: Normalize Stripe Error Handling at API Boundary
**Goal**: Map Stripe SDK errors to controlled HTTP responses.
**Success Criteria**: checkout/portal endpoints consistently return controlled 5xx for Stripe provider failures.
**Tests**: Add endpoint unit tests to assert mapped status code.
**Status**: Complete

## Stage 4: Fail Closed for Org-less Billing Enforcement in Multi-user Mode
**Goal**: Prevent permissive billing bypass when org context is absent in multi-user mode.
**Success Criteria**: billing deps enforce org context unless single-user mode.
**Tests**: Add dependency unit tests for multi-user fail-closed and single-user allow behavior.
**Status**: Complete

## Stage 5: Verification
**Goal**: Validate with Billing tests in project venv.
**Success Criteria**: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Billing` completes.
**Tests**: Billing suite run.
**Status**: In Progress
