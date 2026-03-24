# Admin Audio Installer Jobs Provisioning Design

## Summary

This design moves admin audio bundle provisioning off the synchronous request path and onto the core Jobs system.

The current shared admin audio installer works, but its execution model is brittle:

- `POST /api/v1/setup/admin/audio/provision` runs provisioning inline
- `GET /api/v1/setup/admin/install-status` reads a global file-backed snapshot from `install_manager`
- the frontend polls a singleton status endpoint rather than a specific job

That model was acceptable for the first shared installer slice, but it does not scale to:

- longer local installs
- remote admin usage
- richer curated bundles
- the later advanced per-engine installer

This slice makes Jobs the authoritative execution and status system for audio bundle provisioning while keeping the installer UI focused on bundle-first admin operations.

## Goals

- Make admin audio bundle provisioning asynchronous and durable through the core Jobs system.
- Return immediately from provision requests with a concrete `job_id`.
- Make installer status job-aware instead of relying on a global singleton snapshot.
- Preserve meaningful installer-specific status for the shared UI.
- Keep curated bundle provisioning as the only supported install surface in this slice.
- Maintain compatibility for the legacy static `/setup` experience by moving it onto the same backend path.

## Non-Goals

- Exposing the advanced per-engine installer.
- Adding cancel/retry controls beyond rerunning after a terminal state.
- Building a generic Jobs dashboard for audio installs.
- Replacing audio verification with an automatic post-install step.
- Removing the legacy file-backed install snapshot immediately if it is still needed as a transitional fallback.

## Current Constraints

### 1. Provisioning is still synchronous

The current shared admin route in [setup.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/api/v1/endpoints/setup.py) calls `install_manager.execute_audio_bundle(...)` directly through `_execute_audio_bundle_provision(...)`.

That means one request owns the full install lifecycle and must stay alive for the entire operation.

### 2. Install status is a singleton snapshot

[install_manager.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/Setup/install_manager.py) persists progress through `InstallationStatus`, which writes a single status payload to `setup_install_status.json` plus an in-memory fallback.

That is not a durable per-job status model.

### 3. The frontend has no job identity

[useAudioInstaller.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Setup/hooks/useAudioInstaller.ts) polls a fixed admin install-status path and assumes one active installer state for the whole server.

That is not safe if:

- the page reloads mid-install
- the legacy `/setup` UI also triggers provisioning
- later slices add more installer entry points

### 4. Jobs infrastructure already exists

The repository already has durable Jobs patterns for admin-visible work:

- [admin_byok_validation_jobs_worker.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/services/admin_byok_validation_jobs_worker.py)
- [admin_maintenance_rotation_jobs_worker.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/services/admin_maintenance_rotation_jobs_worker.py)
- [worker_sdk.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/Jobs/worker_sdk.py)
- [manager.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/Jobs/manager.py)

This slice should align with that system instead of inventing a setup-local async execution path.

## Design Principles

- Jobs is the source of truth for async installer execution.
- Installer status must be job-aware.
- The shared UI should remain installer-specific, not Jobs-generic.
- One active admin audio provision job at a time.
- Legacy `/setup` should reuse the same backend execution path.
- Verification stays explicit and separate.

## Product Shape

The admin audio installer flow becomes:

1. fetch recommendations
2. choose bundle/profile
3. submit provision request
4. receive `202 Accepted` with `job_id`
5. poll installer status for that job
6. show running/succeeded/failed details
7. run verification manually after success

The UI remains bundle-oriented. It should not expose raw Jobs queue details such as leases or retries.

## Backend Architecture

### 1. New Jobs contract

Introduce a dedicated Jobs job type for audio bundle provisioning:

- domain: `setup`
- queue: configurable, default `default`
- job type: `admin_audio_bundle_provision`

Payload should include:

- `bundle_id`
- `resource_profile`
- `safe_rerun`
- optional requesting admin user id
- optional machine-profile snapshot used when the request was created

### 2. Provision endpoint becomes enqueue-only

`POST /api/v1/setup/admin/audio/provision` should:

- validate the selected bundle/profile
- reject the request with `409 Conflict` if an `admin_audio_bundle_provision` job is already `queued` or `processing`
- enqueue a new Jobs record if no active job exists
- return `202 Accepted` with:
  - `job_id`
  - `state`
  - `bundle_id`
  - `resource_profile`
  - `message`

The legacy `POST /api/v1/setup/audio/provision` route should use the same enqueue path, subject to its existing access rules.

### 3. Install status becomes job-aware

`GET /api/v1/setup/admin/install-status` should stop exposing the file-backed singleton as the primary source.

Recommended contract:

- accept optional `job_id`
- when `job_id` is present, return status for that exact job
- when `job_id` is omitted, return the most recent:
  - `queued`
  - `processing`
  - or latest terminal
  `admin_audio_bundle_provision` job

This keeps page reloads and later installer entry points deterministic.

Installer response shape should remain installer-specific:

- `job_id`
- `state`: `idle | queued | running | succeeded | failed`
- `bundle_id`
- `resource_profile`
- `started_at`
- `finished_at`
- `current_step`
- `message`
- `remediation`
- `steps`
- optional `verification_hint`

### 4. Jobs is authoritative; file snapshot becomes transitional

This slice should make Jobs the authoritative async status layer.

That means:

- worker execution writes progress into the Jobs record
- `install-status` reads from Jobs first
- the old file-backed `InstallationStatus` path should be treated as legacy compatibility only

If a transitional fallback is required, it should be explicitly documented as:

- legacy `/setup` fallback
- not authoritative for the admin shared UI

### 5. Progress model

Jobs `progress_percent` and `progress_message` are useful but insufficient by themselves.

Installer-specific detail should live in the job `result` payload while the job is running and after completion. That payload should include:

- `bundle_id`
- `resource_profile`
- `safe_rerun`
- `current_step`
- `steps`
- `remediation`
- final verification hint

`progress_percent` and `progress_message` should remain coarse mirrors for general Jobs observability and lease heartbeats.

### 6. Worker architecture

Add a dedicated worker/service for `admin_audio_bundle_provision`.

Responsibilities:

- acquire jobs from Jobs
- call the refactored install-manager execution entry point
- emit progress updates into the Jobs record
- complete or fail the job with structured installer result

This slice is incomplete without worker startup wiring. Enqueue-only behavior is not enough.

### 7. Refactor install manager around a progress reporter

`install_manager.execute_audio_bundle(...)` should be split into:

- a reusable execution core
- a progress reporter interface or callback
- a structured result object

The worker should pass a Jobs-backed reporter.

Legacy synchronous or fallback paths may continue to adapt this execution core, but they should not remain the source of truth for shared admin installer status.

## Frontend Architecture

### Shared hook changes

[useAudioInstaller.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Setup/hooks/useAudioInstaller.ts) should track:

- `jobId`
- latest installer snapshot
- whether status is tied to an active job query

Provision should:

- submit bundle/profile
- read `job_id` from the `202` response
- store it locally
- start polling `install-status?job_id=...`

On page reload:

- if no local `jobId` is present, the hook can still call `install-status` without a job id and accept the latest active/recent audio job
- if the response includes a job id, the hook should adopt it and continue polling specifically

### Shared panel behavior

The shared installer panel remains the same surface conceptually, but now:

- provisioning enters a queued/running state via job response
- polling persists across repeated running snapshots
- success enables `Verify`
- failure shows remediation and allows rerun
- `409 active job` must show a clean message rather than a generic error

## Concurrency Rules

Only one active admin audio provision job should be allowed at a time.

Definition of active:

- Jobs record with:
  - domain `setup`
  - job type `admin_audio_bundle_provision`
  - status `queued` or `processing`

Behavior:

- new provision requests during active execution return `409 Conflict`
- new requests are allowed once the previous job is terminal

This rule should apply regardless of whether the request came from:

- shared admin UI
- legacy static `/setup`

## Legacy `/setup` Compatibility

The static `/setup` flow should continue to work, but it should ride the same async backend path.

That means the static setup JS may need small response-shape updates to handle:

- `202 Accepted`
- `job_id`
- async polling

This is in scope for the slice if legacy `/setup` compatibility is a requirement.

## Risks And Improvements

### Risk: hybrid status model

If the worker updates Jobs but the status endpoint still primarily reads the file snapshot, the UI will have ambiguous state and race conditions.

Improvement:

- Jobs-first read path
- explicit legacy-only fallback

### Risk: worker not started

If the service is not wired into application startup, jobs will enqueue and never run.

Improvement:

- explicit worker startup and enablement documentation
- tests that cover actual handler execution, not only enqueue

### Risk: stale recommendation vs runtime environment

Bundle recommendations may be computed before provision begins.

Improvement:

- validate bundle/profile again at enqueue time
- optionally store the machine-profile snapshot as non-authoritative context in the job payload

### Risk: partial installs

Provisioning can fail after some dependencies or assets are already present.

Improvement:

- preserve remediation in structured job result
- keep `safe_rerun` semantics available

## Testing Strategy

Backend:

- provision returns `202` plus `job_id`
- active job conflict returns `409`
- install-status reads specific job by `job_id`
- install-status latest-job fallback is deterministic
- worker updates progress and result through Jobs
- legacy route still works against async responses if compatibility is retained

Frontend:

- provision stores `job_id` and starts job-specific polling
- repeated running snapshots do not break polling
- success enables verify
- failure renders remediation
- `409` conflict is rendered cleanly

Compatibility:

- both extension and WebUI still mount the same shared component
- static `/setup` compatibility is covered if that route is still expected to provision bundles

## Outcome

After this slice:

- admin audio bundle provisioning is durable and async
- the shared installer UI no longer depends on long request timeouts
- installer status is tied to a specific job instead of a global singleton snapshot
- the platform is ready for the later advanced per-engine installer slice
