# Admin UI Maintenance Rotation Authoritative Design

**Date:** 2026-03-12
**Status:** Approved
**Branch:** `codex/admin-ui-maintenance-rotation-authoritative`

## Goal

Replace the simulated maintenance key-rotation workflow in `admin-ui` with an authoritative, backend-backed admin workflow that:

- uses shared server state instead of `localStorage`
- performs real dry-run and execute operations against the Jobs crypto rotation path
- exposes durable status/history across admins
- fails closed when confirmation or server-side key material is unavailable

## Problem Summary

The current maintenance rotation surface is not production-safe:

- `admin-ui/components/data-ops/MaintenanceSection.tsx` persists run state/history in `localStorage`
- the UI advances progress on a client timer and can fabricate fallback runs when the backend path is unavailable
- `admin-ui/lib/api-client.ts` calls `/admin/jobs/crypto/rotate` without the request body the backend actually requires
- `tldw_Server_API/app/api/v1/endpoints/jobs_admin.py` requires real `old_key_b64`, `new_key_b64`, scoped filters, and `X-Confirm: true` for destructive execution

That means an operator can be shown a completed or in-progress rotation that was never authoritatively requested, queued, or completed by shared backend state.

## Current Backend Constraints

The underlying Jobs crypto rotation path already exists:

- `JobManager.rotate_encryption_keys(...)` performs the actual row scan and re-encryption
- `/api/v1/admin/jobs/crypto/rotate` is a low-level admin endpoint around that operation
- `jobs_crypto_rotate_service.py` demonstrates the existing environment-backed key source model

The low-level endpoint expects raw key material. The current UI does not collect or submit those values. Therefore the authoritative redesign must define key source handling explicitly instead of leaving it implicit.

## Chosen Architecture

### 1. Dedicated authoritative run model

Add a control-plane `maintenance_rotation_runs` model in AuthNZ-backed admin persistence.

Each run stores:

- `id`
- `mode` as `dry_run | execute`
- `status` as `queued | running | complete | failed`
- `domain`
- `queue`
- `job_type`
- `fields_json`
- `limit`
- `affected_count`
- `requested_by_user_id`
- `requested_by_label`
- `confirmation_recorded`
- `job_id`
- `scope_summary`
- `key_source`
- `error_message`
- `created_at`
- `started_at`
- `completed_at`

The run record stores submitted scope and operator/audit context, but it does **not** persist raw key material.

### 2. Jobs-backed execution

Use Jobs for execution because this is an admin-visible operational workflow that needs shared status and operator history.

Flow:

1. UI submits a dry-run or execute request to a new admin maintenance endpoint.
2. Backend validates scope, key-source availability, confirmation, and active-run exclusivity.
3. Backend creates a `maintenance_rotation_runs` row.
4. Backend enqueues a Jobs task referencing the run id.
5. A dedicated worker loads the run record, resolves the configured key source server-side, performs the real rotation via `JobManager.rotate_encryption_keys(...)`, and updates the run status/affected count/error.
6. UI polls run detail/history endpoints and renders authoritative state only.

### 3. Server-side key source only

V1 will not accept browser-submitted raw key material as the main execution path.

Instead:

- the worker resolves old/new rotation keys from server-side configured sources
- initial implementation will use the existing env-backed Jobs rotation key model unless a secret-manager-backed slot already exists by the time implementation starts
- the run record stores only which server-side key source was used, not the secret values themselves

If the required key source is not configured, both dry-run and execute requests fail closed.

### 4. Single active execute run

V1 allows at most one active execute run globally.

Rationale:

- overlapping execute rotations are unsafe and operationally confusing
- it keeps state and UI simpler for the first authoritative pass

Dry-runs may be allowed concurrently later, but v1 should prefer one active run total unless implementation shows clear value in splitting the rule.

## API Design

Keep the existing low-level `/admin/jobs/crypto/rotate` endpoint as an internal/operator API, but remove `admin-ui`’s direct dependency on it.

Add new authoritative endpoints under the admin maintenance surface:

- `POST /api/v1/admin/maintenance/rotation-runs`
- `GET /api/v1/admin/maintenance/rotation-runs`
- `GET /api/v1/admin/maintenance/rotation-runs/{run_id}`

### Create request

Fields:

- `mode`: `dry_run | execute`
- `domain`: optional
- `queue`: optional
- `job_type`: optional
- `fields`: subset of `payload | result`
- `limit`
- `confirmed`: required for `execute`, ignored or false for `dry_run`

### Create semantics

- enforce admin/domain scope using the same domain validation model as the low-level jobs admin path
- reject execute requests without explicit confirmation
- reject requests if server-side key source is unavailable
- reject execute requests if another execute rotation is already active
- create run record first, then enqueue the worker job

### Read semantics

List and detail responses return:

- run mode and status
- submitted scope
- human-readable `scope_summary`
- key-source label
- timestamps
- affected count when available
- error message when failed

## UI Design

Replace the simulated rotation wizard in `MaintenanceSection.tsx` with a real two-step backend-backed flow.

### Form step

Collect:

- mode: dry-run or execute
- domain
- queue
- job type
- fields (`payload`, `result`)
- limit

### Confirmation step

- dry-run: standard confirmation
- execute: explicit destructive confirmation acknowledgment

The UI shows the exact scoped request being submitted. No vague generic “rotation” action remains.

### After submit

- close the wizard on successful run creation
- show latest run status from backend
- show recent run history from backend
- poll run detail while status is `queued` or `running`

### UI behavior removed

- no `localStorage` rotation state/history
- no simulated progress timer
- no fallback fabricated run on backend failure
- no body-less `rotateJobCrypto()` helper

## Failure Semantics

- run creation failure: wizard remains open, form values remain in memory only, no local history row
- worker failure: run is marked `failed`, `error_message` is stored and rendered
- reload during execution: UI rediscoveres the run through backend history/detail
- dry-run and execute are both authoritative records and must be clearly distinguishable in history

## Security And Audit

- raw rotation keys are never stored in `maintenance_rotation_runs`
- execute mode requires explicit confirmation in the create request
- create requests and terminal worker outcomes emit admin audit events
- domain scope enforcement is preserved on create

## Deferred / Out Of Scope For V1

- canceling in-flight runs
- retry endpoint
- browser-provided raw key entry
- migrating old `localStorage` state/history into shared backend records

## Testing Strategy

### Backend

- repo tests for run create/list/detail/update
- API tests for create/list/detail validation and confirmation semantics
- worker tests for dry-run and execute result handling
- audit tests for create and terminal transitions

### Frontend

- replace `MaintenanceSection` local-storage tests with backend-backed create/poll/history tests
- assert real request body submission
- assert no fake fallback run on API failure

### Integration

- one end-to-end admin path for dry-run
- one execute denial/failure path proving no fake success state appears
