# Admin UI DSR Authoritative Intake Design

Date: 2026-03-10
Branch: `codex/admin-ui-dsr-authoritative-intake`

## Context

The production-readiness hardening work intentionally disabled the `admin-ui` data subject request workflow because it was not authoritative:

- request history lived in browser `localStorage`
- preview could fall back to synthetic category counts
- create failures could still lead to local success messaging
- export and erasure flows implied completion without backend persistence

The next milestone is not full export/erasure execution. It is a truthful, durable first step that allows admins to preview user data coverage and record DSR requests for review without pretending that destructive or export actions already happened.

## Goals

1. Replace browser-local DSR history with durable backend persistence.
2. Make preview authoritative and fail closed when the target user or requested coverage cannot be resolved.
3. Make request creation idempotent and durable.
4. Re-enable the admin UI DSR surface in safe mode using real backend data.
5. Preserve admin auditability for both preview and request creation.

## Non-Goals

- Performing cross-store export generation in this milestone.
- Performing cross-store erasure/deletion in this milestone.
- Designing a full human review workflow with assignment and approval states.
- Counting unsupported categories with estimates or placeholders.

## Chosen Approach

Add dedicated DSR persistence and endpoints under the existing admin data-ops contract:

- `POST /api/v1/admin/data-subject-requests/preview`
- `POST /api/v1/admin/data-subject-requests`
- `GET /api/v1/admin/data-subject-requests`

This approach keeps the contract aligned with the current admin UI, fits the existing admin routing and audit patterns, and avoids misusing the audit log as the primary request store.

## Persistence Model

DSR records will live in the AuthNZ database, not in a per-user content database.

Rationale:

- DSR records are control-plane metadata, not user content.
- They must be visible to multiple authorized admins.
- The existing admin data-op surfaces already use shared control-plane persistence patterns.
- AuthNZ persistence is already designed to support both SQLite and PostgreSQL.

### `data_subject_requests` table

First-pass fields:

- `id` integer primary key
- `client_request_id` text unique, required
- `requester_identifier` text required
- `resolved_user_id` integer nullable
- `request_type` text required, one of `access`, `export`, `erasure`
- `status` text required, initial milestone uses `recorded`
- `selected_categories` text/json required, default `[]`
- `preview_summary` text/json required
- `coverage_metadata` text/json nullable
- `requested_by_user_id` integer nullable
- `requested_at` timestamp required
- `notes` text nullable

Indexes:

- `client_request_id`
- `requester_identifier`
- `resolved_user_id`
- `request_type`
- `status`
- `requested_at`

## API Behavior

### 1. Preview

`POST /admin/data-subject-requests/preview`

Input:

- `requester_identifier`
- optional category filter if the UI later scopes preview to specific categories

Behavior:

- resolve the requester to a known user
- enforce admin scope against the resolved user
- count only authoritative categories supported by the current backend implementation
- return a normalized summary payload and coverage metadata

Failure semantics:

- `404` if the requester cannot be resolved
- `403` if the admin is not allowed to manage that user
- `422` if unsupported categories are explicitly requested
- `500` only for real backend failures

Preview is not persisted in milestone 1.

### 2. Create

`POST /admin/data-subject-requests`

Input:

- `client_request_id`
- `requester_identifier`
- `request_type`
- `categories`
- optional `notes`

Behavior:

- resolve the requester again on the server
- enforce admin scope again on the resolved user
- recompute the authoritative preview snapshot on the server
- validate the requested categories against supported coverage
- persist the DSR record with status `recorded`
- return the stored record

Important rule:

The server must not trust preview data supplied by the client. `create` always recomputes the preview snapshot before persistence.

Idempotency:

- `client_request_id` is treated as a unique idempotency key
- repeated submits for the same request return the stored record instead of creating duplicates

### 3. List

`GET /admin/data-subject-requests`

Input:

- `limit`
- `offset`
- optional filters such as `request_type`, `status`, `requester_identifier`, `user_id`

Behavior:

- return newest-first paged request history
- apply admin scope filtering so non-platform admins only see manageable users

## Lifecycle Model

Milestone 1 keeps the lifecycle intentionally narrow.

Allowed persisted status:

- `recorded`

Deferred statuses for future work:

- `in_review`
- `completed`
- `rejected`

This avoids inventing states that the system cannot yet transition between honestly.

## Authoritative Category Coverage

Milestone 1 will ship only categories the backend can count cleanly and defensibly.

Expected first-pass candidates:

- `media_records`
- `chat_messages`
- `notes`
- `audit_events`

`embeddings` stays out of scope unless user linkage is straightforward in the existing vector-store path.

If a category cannot be counted authoritatively:

- it is omitted from the summary, or
- it is returned with explicit coverage metadata showing it is unsupported

The API must never fabricate or estimate category counts.

## Access Control

All endpoints remain under the admin router and therefore require admin authentication.

In addition:

- preview, create, and list must enforce the same admin-to-user scope rules used by other admin data-op endpoints
- non-platform admins must not be able to probe unrelated users by email or numeric ID
- list responses must exclude requests outside the caller's allowed scope

## Auditability

Preview and create actions must emit admin audit events using the shared admin audit helper.

Recommended audit shape:

- `resource_type`: `data_subject_request`
- `action`: `data_subject_request.preview` or `data_subject_request.create`
- metadata:
  - `requester_identifier`
  - `resolved_user_id`
  - `request_type`
  - `selected_categories`
  - `client_request_id`

Audit events are evidence, not the primary source of truth for request state.

## Frontend Changes

`admin-ui/components/data-ops/DataSubjectRequestsSection.tsx` will change in these ways:

- remove browser `localStorage` request-log hydration and persistence
- fetch request history from `GET /admin/data-subject-requests`
- use only backend preview data
- remove local JSON export generation
- remove fake erasure completion messaging
- record all request types as stored requests, including `access`

Updated user-facing messaging:

- `access`: show the authoritative preview summary and record the request
- `export`: show `Request recorded for review`
- `erasure`: show `Request recorded for review` after authoritative preview and category validation

## Backend Compatibility Requirements

Because DSR records live in AuthNZ, the implementation must support both configured AuthNZ backends:

- SQLite
- PostgreSQL

That means:

- additive AuthNZ migration support for SQLite
- corresponding additive ensure path for PostgreSQL extras
- repository queries written for both backends

## Testing Strategy

### Backend

- migration coverage for the new DSR table
- preview success and unknown-user failure
- create success with idempotent replay
- list pagination
- admin scope enforcement
- audit emission for preview and create
- SQLite and PostgreSQL compatibility where existing AuthNZ test fixtures support it

### Frontend

- no `localStorage` request log behavior
- no synthetic preview fallback
- no success UI when backend create fails
- request log fetched from the server and refreshed after submit
- `export` and `erasure` success copy changed to `recorded` semantics

## Risks And Follow-On Work

1. Cross-store counting may expose gaps in user linkage for some categories.
2. PostgreSQL support may require explicit additive migration handling beyond the existing SQLite migration path.
3. Full export and full erasure will need a second milestone with stronger workflow, review, and operational safeguards.

## Decision

Proceed with milestone 1 as an authoritative intake, preview, and audit workflow only. Do not claim export generation or erasure execution until the backend can perform those actions across the supported stores coherently and durably.
