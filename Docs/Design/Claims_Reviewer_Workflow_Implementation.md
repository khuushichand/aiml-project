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

## API Surface
- `GET /api/v1/claims/review-queue`
- `PATCH /api/v1/claims/{claim_id}/review`
- `GET /api/v1/claims/{claim_id}/history`
- `POST /api/v1/claims/review/bulk`
- `GET/POST/PATCH/DELETE /api/v1/claims/review/rules`
- `GET /api/v1/claims/review/analytics`

## Workflow Rules
- Default state: `pending`.
- Valid transitions: `pending -> approved|flagged|rejected|reassigned`.
- `reassigned` requires reviewer_id or review_group to be set.
- Optimistic locking via `review_version` on PATCH.

## Access Control
- `claims.reviewer` permission for queue, review updates on assigned claims.
- `claims.admin` permission for bulk actions, rule management, analytics, and
  cross-claim visibility.

## Testing
- Unit tests for transition validation and optimistic lock handling.
- API tests for review queue filtering, review update, and history entries.
