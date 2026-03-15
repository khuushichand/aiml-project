# Sandbox Subsystem Review Findings

Date: 2026-03-08
Base commit reviewed: `0c13998e9`
Scope: `tldw_Server_API/app/core/Sandbox/` and `tldw_Server_API/app/api/v1/endpoints/sandbox.py`

## Findings

### [P1] Docker runner exceptions after admission leave runs stuck in `starting`

- Type: Bug
- Evidence:
  - `tldw_Server_API/app/core/Sandbox/service.py:933-976`
  - `tldw_Server_API/app/core/Sandbox/service.py:993-1023`
  - `tldw_Server_API/app/core/Sandbox/service.py:1238-1250`
- Why it matters:
  - Both Docker execution branches admit the run into `starting` before invoking `DockerRunner.start_run()`.
  - If `start_run()` raises, the background branch only logs `Background docker execution failed` and returns without forcing a terminal state.
  - The foreground branch logs `Docker execution failed; keeping enqueue status`, but the status object is already `starting`, so the final persistence path writes that non-terminal state back to the store unchanged.
  - A stranded `starting` run can consume active-run quota, block accurate status reporting, and require manual cancelation to recover.
- Reproduction:
  - Foreground: patched `DockerRunner.start_run` to raise `RuntimeError("boom")` with `SANDBOX_ENABLE_EXECUTION=1` and `SANDBOX_BACKGROUND_EXECUTION=0`; the returned and stored run both stayed in `starting` with no `finished_at` or failure message.
  - Background: same patch with `SANDBOX_BACKGROUND_EXECUTION=1` and synchronous `_submit_background_worker`; the returned and stored run again stayed in `starting`.

### [P2] `sandbox_runs_started_total` counts rejected requests as started runs

- Type: Bug
- Evidence:
  - `tldw_Server_API/app/api/v1/endpoints/sandbox.py:1086-1093`
- Why it matters:
  - The route increments `sandbox_runs_started_total` before `_service.start_run_scaffold(...)` performs runtime selection, policy validation, queue admission, and idempotency checks.
  - Requests that are rejected with `runtime_unavailable`, `policy_unsupported`, `queue_full`, `invalid_spec_version`, or `idempotency_conflict` are still counted as started runs.
  - This distorts operational dashboards and any failure-rate math that relies on `started_total` as the denominator.

### [P3] The generic runtime capability contract is only partially wired into the subsystem

- Type: Incomplete Item
- Evidence:
  - `tldw_Server_API/app/core/Sandbox/runtime_capabilities.py:9-30`
  - `tldw_Server_API/app/core/Sandbox/policy.py:151-169`
- Why it matters:
  - The repository defines `RuntimeCapabilities` and `RuntimePreflightResult`, but in the reviewed path only Lima preflight meaningfully uses the shared contract object.
  - Runtime selection in `SandboxPolicy.select_runtime()` still relies on ad hoc availability booleans instead of a provider-neutral capability interface.
  - This increases the chance that Docker, Firecracker, and Lima drift apart on admission and error semantics as the subsystem evolves.

## Targeted Test Runs

- `source .venv/bin/activate && python -m pytest -vv tldw_Server_API/tests/sandbox/test_sandbox_api.py::test_runtimes_discovery_shape`
  - Result: PASS

- `source .venv/bin/activate && python -m pytest -vv tldw_Server_API/tests/sandbox/test_run_claim_fencing.py tldw_Server_API/tests/sandbox/test_run_claim_heartbeat.py tldw_Server_API/tests/sandbox/test_execution_concurrency_cap.py tldw_Server_API/tests/sandbox/test_queue_full_429.py`
  - Result: 14 passed

- `source .venv/bin/activate && python -m pytest -vv tldw_Server_API/tests/sandbox/test_runtime_unavailable.py tldw_Server_API/tests/sandbox/test_lima_no_fallback.py tldw_Server_API/tests/sandbox/test_lima_strict_admission.py`
  - Result: 9 passed

- `source .venv/bin/activate && python -m pytest -vv tldw_Server_API/tests/sandbox/test_run_ownership.py tldw_Server_API/tests/sandbox/test_admin_rbac.py tldw_Server_API/tests/sandbox/test_artifact_traversal_integration.py tldw_Server_API/tests/sandbox/test_artifact_content_type_and_path.py tldw_Server_API/tests/sandbox/test_artifact_range.py tldw_Server_API/tests/sandbox/test_ws_resume_edge_cases.py tldw_Server_API/tests/sandbox/test_ws_connection_quotas.py tldw_Server_API/tests/sandbox/test_cancel_endpoint_ws_and_status.py`
  - Result: 9 passed, 1 skipped

## Validation Gaps

- No existing targeted regression test in the reviewed slice covers the “runner raises after admission” path for Docker foreground or background execution. That gap allowed the stuck-`starting` bug above to persist despite the broader queueing and lifecycle suite passing.

- `tldw_Server_API/tests/sandbox/test_artifact_traversal_integration.py::test_artifact_traversal_rejected_under_uvicorn` skipped locally, so the live-server variant of raw-path traversal rejection was not revalidated in this run.
