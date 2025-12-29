# Claims Reviewer Workflow Implementation Plan

## Goals
- Add review state management to claims.
- Provide reviewer/admin APIs for queue, review updates, and audit history.
- Capture review actions for analytics and feedback loops.

## Data Model
- Claims table additions:
  - `review_status` (TEXT) default `pending`
  - `reviewer_id` (INTEGER, nullable)
  - `reviewed_at` (DATETIME, nullable)
  - `review_notes` (TEXT, nullable)
  - `review_version` (INTEGER, default 1)
  - `review_reason_code` (TEXT, nullable)
- `ClaimsReviewLog`:
  - `id` (PK), `claim_id`, `old_status`, `new_status`, `old_text`, `new_text`,
    `reviewer_id`, `notes`, `reason_code`, `action_ip`, `action_user_agent`, `created_at`.
- `ClaimsReviewRules`:
  - `id` (PK), `user_id`, `priority`, `predicate_json`, `reviewer_id`, `review_group`,
    `active`, `created_at`, `updated_at`.
- `ClaimsReviewExtractorMetricsDaily`:
  - `id` (PK), `user_id`, `report_date`, `extractor`, `extractor_version`,
    `total_reviewed`, `approved_count`, `rejected_count`, `flagged_count`,
    `reassigned_count`, `edited_count`, `reason_code_counts_json`,
    `created_at`, `updated_at`.

## API Surface
- `GET /api/v1/claims/review-queue`
- `PATCH /api/v1/claims/{claim_id}/review`
- `GET /api/v1/claims/{claim_id}/history`
- `POST /api/v1/claims/review/bulk`
- `GET/POST/PATCH/DELETE /api/v1/claims/review/rules`
- `GET /api/v1/claims/review/analytics`
- `GET /api/v1/claims/review/metrics`
  - Pagination: offset/limit with defaults `limit=25`, `offset=0`, max `limit=100`.
  - Filters for review queue: `status`, `reviewer_id`, `review_group`, `priority`,
    `created_after`, `created_before`, `reviewed_after`, `reviewed_before`,
    `sort` (default `created_at desc`).
  - Bulk review constraints: max 50 claim updates per request; reject over-limit
    with 400 and a clear error message.
  - Rules validation on POST/PATCH: validate `predicate_json` schema, allowed
    fields/operators, and guardrails on predicate depth/complexity.

## Workflow Rules
- Default state: `pending`.
- Valid transitions: `pending -> approved|flagged|rejected|reassigned`.
- `reassigned` requires reviewer_id or review_group to be set.
- Optimistic locking via `review_version` on PATCH.

## Review Metrics Aggregation
- Nightly job aggregates `claims_review_log` into `ClaimsReviewExtractorMetricsDaily`.
- Per-extractor breakdown includes approval/rejection/flag counts, edit counts, and reason-code motifs.
- The dashboard payload includes a `review_extractor_metrics` summary for the requested window.
- Scheduler is controlled by:
  - `CLAIMS_REVIEW_METRICS_SCHEDULER_ENABLED`
  - `CLAIMS_REVIEW_METRICS_INTERVAL_SEC`
  - `CLAIMS_REVIEW_METRICS_LOOKBACK_DAYS`

## Access Control
- `claims.reviewer` permission for queue, review updates on assigned claims.
- `claims.admin` permission for bulk actions, rule management, analytics, and
  cross-claim visibility.

## Testing
- Unit tests for transition validation and optimistic lock handling.
- API tests for review queue filtering, review update, and history entries.
- Scheduler tests for nightly extractor metrics aggregation and idempotent upsert behavior.
- Authorization tests: reviewers cannot access claims outside assignment scope
  or edit/delete rules they do not own.
- Bulk operation atomicity: partial failures do not commit any updates.
- Audit trail completeness: `ClaimsReviewLog` records every state transition
  with correct reviewer and timestamps.
