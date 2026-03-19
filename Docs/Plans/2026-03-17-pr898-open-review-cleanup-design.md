# PR 898 Open Review Cleanup Design

## Context

PR 898 already contains the first round of production-readiness fixes at commit `1b35062ee`, but the pull request still has open review comments.

Those comments split into three categories:

- Remaining correctness gaps on the live PR branch.
- Low-risk review cleanup and test hygiene comments.
- Broader Jobs and Stripe DB-boundary refactors that have already been implemented separately in PR 908.

This pass keeps PR 898 narrowly scoped. It clears the remaining product and review issues without backporting the repository-boundary redesign from PR 908.

## Goals

- Fix the remaining correctness and reliability issues still open on PR 898.
- Fold in the low-risk bot-review cleanup items that are reasonable to land on the same branch.
- Update PR 898 review threads so the architecture comments are explicitly closed out by reference to PR 908.
- Preserve the current user-visible behavior of PR 898 except where an open review comment identifies a real bug.

## Non-Goals

- Moving Jobs fair-share DB access into `DB_Management` on PR 898.
- Moving Stripe metering SQL and schema ownership into `DB_Management` on PR 898.
- Reworking PR 898 into the broader repository/session architecture already staged in PR 908.

## Scope

### 1. API and Policy Fixes

- `storage_quota_guard.py`
  - Log when quota enforcement falls back to `user_id = 0`.
  - Replace the header-assignment `try/except` with `contextlib.suppress`.
- `consent.py`
  - Cache the `ConsentManager` instance instead of rebuilding it per request.
- `consent_schemas.py`
  - Use typed datetime fields for temporal values.
- `main.py`
  - Route the consent router through `_include_if_enabled(...)`.
  - Replace the eager f-string in the minimal-app logger call with Loguru lazy formatting.
- `ingest_jobs.py`
  - Add a second storage-quota enforcement check after remote content is staged so URL-only submits cannot bypass the pre-check.

### 2. Jobs and Stripe Correctness Fixes

- `JobManager.create_job()`
  - Stop coercing `owner_user_id` to `int` during fair-share checks.
  - Raise `BadRequestError` instead of `ValueError` for admission-control rejections.
- `stripe_metering_service.py`
  - Pass real `datetime.date` values to PostgreSQL DATE bindings.
  - Only swallow the Stripe “resource missing” case when retrieving subscription items; re-raise the other Stripe API failures.
  - Make `is_enabled` reflect both env configuration and Stripe runtime availability.

### 3. Test and Review Cleanup

- Make the metering “yesterday” tests deterministic.
- Apply the fixture/style/test-helper cleanups still open in:
  - `tests/AuthNZ/test_audit_chain_integration.py`
  - `tests/Billing/test_overage_enforcement_integration.py`
  - `tests/Billing/test_storage_quota_guard.py`
  - `tests/Jobs/test_fair_share_integration.py`
  - `tests/test_stripe_metering.py`
- Add the missing fair-share test marker and tighten the notify-only overage tests so they do not pass accidentally because of default thresholds.

## Approach

### Keep PR 898 narrow

The existing open threads on raw SQL and connection reuse in `JobManager` and `StripeMeteringService` are technically valid, but they are architecture comments now covered by PR 908. Reimplementing that redesign in PR 898 would broaden scope and create duplicate review surface.

Instead, this pass will:

- fix the correctness bugs directly on `feat/production-readiness-gaps`,
- land the cheap cleanup items that are still open on the same branch,
- and resolve the three architecture threads with an explicit pointer to PR 908.

### Prefer targeted fixes over large refactors

Where a comment points to a real bug, the implementation should stay local:

- ingest quota hard-stop added to the staging path instead of a wider ingestion redesign,
- fair-share owner handling fixed in-place,
- Stripe metering date and exception behavior corrected in the service without backporting the repository boundary,
- test cleanup folded into the existing test modules rather than moving everything into new helper layers.

## Risks

- The URL-ingest quota fix touches a user-facing path and must be tested carefully against the existing staging flow.
- Changing consent datetime schema types could affect tests or response serialization if any callers rely on raw strings.
- The “fix every open issue” scope includes some low-value cleanup; care is needed to keep those changes boring and non-invasive.

## Verification Plan

- Targeted red/green tests for each correctness fix where feasible.
- Expanded regression covering:
  - consent endpoints
  - audit chain integration
  - overage enforcement
  - storage quota guard
  - fair-share integration
  - stripe metering
- Bandit on touched backend files before final push.

## Review Thread Handling

- Resolve PR 898 architecture threads `2936292840`, `2936295005`, and `2936295007` with a note that the DB-boundary redesign is implemented and ready in PR 908.
- Resolve the remaining open PR 898 threads directly against the new code changes in this pass.
