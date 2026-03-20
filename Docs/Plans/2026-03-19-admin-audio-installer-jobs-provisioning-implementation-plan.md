# Admin Audio Installer Jobs Provisioning Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move admin audio bundle provisioning onto the core Jobs system with job-aware installer status, explicit worker execution, and shared UI polling by `job_id`.

**Architecture:** Introduce a `setup/admin_audio_bundle_provision` Jobs contract, refactor install-manager execution behind a progress reporter, expose async `202` provision responses plus job-aware status reads, and update the shared `AudioInstallerPanel` to poll by `job_id`. Keep curated bundles only and preserve legacy `/setup` compatibility through the same backend path.

**Tech Stack:** FastAPI, core Jobs, WorkerSDK, setup/install manager modules, React shared UI, Vitest, pytest.

---

## Stage 1: Jobs Contract And Status Read Path
**Goal**: Define the audio provision job type, enqueue API, and installer-specific status projection.
**Success Criteria**:
- `POST /api/v1/setup/admin/audio/provision` returns `202` with `job_id`
- `GET /api/v1/setup/admin/install-status` supports `job_id` and latest-job fallback
- concurrent active provision requests return `409`
**Tests**:
- `tldw_Server_API/tests/Setup/test_setup_audio_installer_jobs_api.py`
- updates to `tldw_Server_API/tests/Setup/test_setup_audio_installer_lifecycle_api.py`
**Status**: Not Started

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/setup.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/setup.py` or local endpoint models if needed
- Create/Modify: `tldw_Server_API/app/services/admin_audio_installer_jobs_worker.py`
- Test: `tldw_Server_API/tests/Setup/test_setup_audio_installer_jobs_api.py`

**Implementation notes:**
- Add a stable job type constant, queue helper, and enqueue helper.
- Define active jobs as `queued` or `processing`.
- Return installer-specific response shape, not raw Jobs rows.
- Make latest-job fallback deterministic and scoped to the audio installer job type.

---

## Stage 2: Refactor Install Manager For Jobs-Owned Progress
**Goal**: Split install-manager execution from the old global snapshot model so worker execution can report structured progress into Jobs.
**Success Criteria**:
- install-manager exposes a reusable execution core with progress callbacks or a reporter interface
- worker can update Jobs `progress_percent`, `progress_message`, and installer-specific `result`
- old file snapshot is no longer the primary admin status source
**Tests**:
- `tldw_Server_API/tests/Setup/test_audio_bundle_install_jobs_worker.py`
- updated verification of structured result/remediation
**Status**: Not Started

**Files:**
- Modify: `tldw_Server_API/app/core/Setup/install_manager.py`
- Modify: `tldw_Server_API/app/services/admin_audio_installer_jobs_worker.py`
- Test: `tldw_Server_API/tests/Setup/test_audio_bundle_install_jobs_worker.py`

**Implementation notes:**
- Keep the execution core in `install_manager.py`.
- Add a small progress reporter interface or callback contract.
- Persist installer detail into job `result` while running and at completion.
- Keep the old file snapshot only as a transitional fallback if needed for legacy setup compatibility.

---

## Stage 3: Worker Startup And Legacy `/setup` Compatibility
**Goal**: Ensure enqueued audio provision jobs actually run and the legacy setup installer uses the same async path.
**Success Criteria**:
- dedicated audio installer Jobs worker is startable from app services
- legacy `/api/v1/setup/audio/provision` uses the same enqueue path
- legacy install-status path remains functional with the new projection
**Tests**:
- startup/worker unit coverage if service boot hooks are testable
- `tldw_Server_API/tests/Setup/test_setup_audio_installer_lifecycle_api.py`
- integration coverage for legacy route compatibility
**Status**: Not Started

**Files:**
- Create: `tldw_Server_API/app/services/admin_audio_installer_jobs_worker.py`
- Modify: startup/service registration files discovered during implementation
- Modify: `tldw_Server_API/app/api/v1/endpoints/setup.py`
- Test: `tldw_Server_API/tests/Setup/test_setup_audio_installer_lifecycle_api.py`

**Implementation notes:**
- Follow the existing worker pattern from BYOK/admin maintenance workers.
- Document or wire enablement clearly.
- If legacy static `/setup` expects synchronous success today, update it to handle `202` plus polling.

---

## Stage 4: Shared UI Job-Aware Polling
**Goal**: Update the shared React audio installer to provision asynchronously and poll by `job_id`.
**Success Criteria**:
- `useAudioInstaller` stores `jobId`
- provision transitions into polling against `install-status?job_id=...`
- page reload can recover by adopting the latest active/recent job
- `409 active job` and terminal failures render cleanly
**Tests**:
- `apps/packages/ui/src/components/Option/Setup/__tests__/AudioInstallerPanel.test.tsx`
- targeted tests for `useAudioInstaller.ts`
**Status**: Not Started

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Setup/hooks/useAudioInstaller.ts`
- Modify: `apps/packages/ui/src/components/Option/Setup/AudioInstallerPanel.tsx`
- Test: `apps/packages/ui/src/components/Option/Setup/__tests__/AudioInstallerPanel.test.tsx`

**Implementation notes:**
- Keep the UI installer-specific; do not surface raw Jobs internals.
- Preserve current remediation and verification UX.
- Treat `job_id` as the primary polling anchor once known.

---

## Stage 5: Verification, Regression, And Security
**Goal**: Prove the async installer works across backend and shared UI surfaces without introducing new findings.
**Success Criteria**:
- backend async installer tests pass
- shared UI tests pass
- touched backend/frontend scope is Bandit-clean
- docs/plan status updated accurately
**Tests**:
- focused pytest on setup/jobs/audio installer tests
- focused Vitest on `AudioInstallerPanel` scope
- `python -m py_compile` on touched backend modules
- Bandit on touched backend/frontend paths
**Status**: Not Started

**Suggested verification commands:**

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Setup/test_setup_audio_installer_jobs_api.py \
  tldw_Server_API/tests/Setup/test_setup_audio_installer_lifecycle_api.py \
  tldw_Server_API/tests/Setup/test_audio_bundle_install_jobs_worker.py -q
```

```bash
bunx vitest run \
  apps/packages/ui/src/components/Option/Setup/__tests__/AudioInstallerPanel.test.tsx
```

```bash
source .venv/bin/activate && python -m py_compile \
  tldw_Server_API/app/api/v1/endpoints/setup.py \
  tldw_Server_API/app/core/Setup/install_manager.py \
  tldw_Server_API/app/services/admin_audio_installer_jobs_worker.py
```

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/setup.py \
  tldw_Server_API/app/core/Setup/install_manager.py \
  tldw_Server_API/app/services/admin_audio_installer_jobs_worker.py \
  apps/packages/ui/src/components/Option/Setup \
  -f json -o /tmp/bandit_admin_audio_installer_jobs.json
```

---

## Notes

- Jobs is the authoritative status layer for this slice.
- The file-backed install snapshot may remain only as a compatibility fallback during migration.
- Advanced per-engine installer work stays out of scope until this async execution model is stable.
