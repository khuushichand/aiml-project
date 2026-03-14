# Admin UI BYOK Validation And Retention Preview Authoritative Design

**Date:** 2026-03-12
**Status:** Approved
**Branch:** `codex/admin-ui-byok-retention-authoritative`

## Goal

Close the remaining two production-readiness gaps in the admin UI by:

- replacing the BYOK dashboard's placeholder validation/telemetry path with authoritative backend-backed validation runs and shared history
- replacing the retention-policy impact estimate fallback with a real backend dry-run preview that must be used before destructive saves

## Problem Summary

Two admin surfaces on current `dev` still fall short of truthful production behavior:

1. `admin-ui/app/byok/page.tsx` still labels part of the page as placeholder telemetry and explicitly hides batch validation until backend support exists.
2. `admin-ui/components/data-ops/RetentionPoliciesSection.tsx` falls back to a locally estimated impact preview when the backend preview route is unavailable.

These are not cosmetic gaps:

- BYOK operators cannot authoritatively validate key health at scale or rely on shared validation history.
- Retention-policy changes are destructive, but the current UI can still display a non-authoritative estimate and keep the preview/save workflow alive.

## Current Backend Constraints

### BYOK

The backend already has:

- admin BYOK endpoints for listing, testing, upserting, and deleting keys
- metrics that expose BYOK resolution and missing-credential counts
- audit logs that can support recent admin activity views

The backend does **not** currently expose:

- a batch validation run model
- a shared validation history/status API
- a Jobs-backed validation worker

### Retention

The backend already has:

- `GET /admin/retention-policies`
- `PUT /admin/retention-policies/{policy_key}`
- service logic that validates retention-policy ranges and applies overrides

The backend does **not** currently expose:

- `POST /admin/retention-policies/{policy_key}/preview`
- an authoritative count of affected rows/files before a policy change
- a way to bind a reviewed preview to the later destructive save

## Chosen Architecture

### 1. Dedicated BYOK validation-run model

Add a control-plane `byok_validation_runs` table in AuthNZ-backed admin persistence.

Each run stores:

- `id`
- `status` as `queued | running | complete | failed`
- `org_id` nullable
- `provider` nullable
- `keys_checked`
- `valid_count`
- `invalid_count`
- `error_count`
- `requested_by_user_id`
- `requested_by_label`
- `job_id`
- `scope_summary`
- `error_message`
- `created_at`
- `started_at`
- `completed_at`

Runs store only aggregate/redacted results. They do **not** persist raw key material, provider credential payloads, or verbose per-key error blobs.

### 2. Jobs-backed BYOK batch validation

Use Jobs because this is an admin-visible operational workflow that needs durable shared status/history.

Flow:

1. The UI creates a validation run through a new admin BYOK endpoint.
2. Backend validates scope and active-run exclusivity.
3. Backend records the run and enqueues a Jobs task.
4. The worker scans the targeted keys, performs provider validation with conservative concurrency, and updates the run row with aggregate counts.
5. The UI polls run detail/history until a terminal state is reached.

V1 allows at most one active validation run globally. This keeps provider traffic predictable and prevents confusing overlapping histories.

### 3. Narrower authoritative telemetry promise for BYOK

V1 does **not** try to invent perfect historical observability for every BYOK card.

Instead:

- the validation sweep and recent validation history become authoritative
- existing metrics-backed and audit-backed cards remain only if their source is already real
- cards that would still overpromise after this work are renamed or removed rather than left as placeholders

If the current “Key Activity” card still reflects only partial data after implementation, it should be renamed to something narrower such as recent validation activity or recent admin key events.

### 4. Backend retention dry-run preview

Add:

- `POST /api/v1/admin/retention-policies/{policy_key}/preview`

The preview response returns authoritative counts for the proposed change:

- `policy_key`
- `current_days`
- `new_days`
- `counts.audit_log_entries`
- `counts.job_records`
- `counts.backup_files`
- `preview_signature`
- `expires_at`

The preview uses the same auth/scope rules and validation path as the eventual update endpoint.

### 5. Preview/save binding for retention

The retention save flow needs a backend binding between the reviewed preview and the later destructive update.

V1 uses a signed, time-bounded preview token/signature:

- preview computes a `preview_signature` over `policy_key`, `current_days`, `new_days`, actor identity, and a freshness window
- `PUT /admin/retention-policies/{policy_key}` accepts `preview_signature`
- backend verifies the signature before applying the update

This prevents saving a different value from the one the operator previewed, and avoids introducing another stateful server-side draft store.

## API Design

### BYOK

Add endpoints under the existing admin BYOK surface:

- `POST /api/v1/admin/byok/validation-runs`
- `GET /api/v1/admin/byok/validation-runs`
- `GET /api/v1/admin/byok/validation-runs/{run_id}`

Create request fields:

- `org_id` optional
- `provider` optional

Create semantics:

- require BYOK to be enabled
- preserve admin/org scope enforcement
- reject when another validation run is active
- create run row and enqueue worker job

Read semantics:

- list/detail return aggregate counts, timestamps, status, scope summary, and any bounded failure message

### Retention

Add:

- `POST /api/v1/admin/retention-policies/{policy_key}/preview`

Extend:

- `PUT /api/v1/admin/retention-policies/{policy_key}`

Update request fields become:

- `days`
- `preview_signature`

Update semantics:

- reject missing or invalid signature
- reject expired signature
- reject mismatched policy/current/new values
- then apply the existing retention update logic

## UI Design

### BYOK page

Replace the current placeholder validation framing in `admin-ui/app/byok/page.tsx` with:

- a `Run validation sweep` control
- latest validation-run status
- recent validation history
- aggregate counts from the selected run

Keep the existing per-key admin actions:

- add/update shared key
- test shared key
- revoke/delete key

The page should no longer say validation sweep support is hidden. It should instead show:

- current run state when a run exists
- a truthful empty state when no runs have been created yet

### Retention policies

Keep the existing preview-before-save workflow, but make it authoritative:

- `Preview impact` must call the backend preview endpoint
- preview failure shows an error and leaves save disabled
- no local estimate fallback remains
- save requires:
  - a successful backend preview for the exact value
  - a matching backend `preview_signature`
  - the destructive confirmation checkbox

The preview row should no longer mention “estimated locally.”

## Failure Semantics

### BYOK

- create failure: no fake history row, no success toast
- worker failure: run is marked `failed`, bounded error message stored on the run
- reload during execution: page rediscovers run state from backend history/detail

### Retention

- preview failure: no estimate fallback, save remains disabled
- update failure after successful preview: current form value remains in memory, preview stays valid while the value is unchanged and the signature has not expired
- changed value after preview: previous signature is invalidated client-side and the operator must preview again

## Security And Safety Constraints

- BYOK validation runs never store secrets or raw credential fields
- provider-side validation errors are redacted before persistence
- validation worker uses bounded concurrency per provider
- only one active BYOK validation run exists at a time in v1
- retention preview and update use the same auth/scope rules
- retention update fails closed without a valid backend preview signature

## Deferred / Out Of Scope For V1

- detailed persisted per-key BYOK validation result tables
- multi-run BYOK concurrency beyond the single active run
- historical reconstruction of all BYOK activity before validation runs existed
- retention preview for datasets not already represented by current cleanup logic

## Testing Strategy

### Backend

- repo tests for BYOK validation runs
- service/API tests for BYOK run create/list/detail and active-run exclusivity
- worker tests for BYOK status transitions and aggregate result recording
- retention preview endpoint tests for valid preview, invalid range, unknown policy, and preview-signature verification

### Frontend

- BYOK page tests for creating/polling validation runs and rendering real history
- retention section tests for backend-only preview and preview-signature-bound save

### Verification

- targeted pytest for the new BYOK and retention backend slices
- targeted vitest for `admin-ui/app/byok/page.tsx` and `RetentionPoliciesSection.tsx`
- Bandit on touched backend files
