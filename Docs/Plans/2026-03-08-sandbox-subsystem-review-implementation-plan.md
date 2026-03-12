# Sandbox Subsystem Review Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Execute a focused, evidence-driven review of the sandbox subsystem and sandbox API endpoints, producing findings for bugs, risky incomplete items, and residual risks.

**Architecture:** Review the internal control plane before the API layer so endpoint behavior is evaluated against the actual queueing, ownership, policy, store, and artifact invariants. Use a targeted pytest slice to confirm or falsify the highest-risk assumptions instead of relying on static inspection alone.

**Tech Stack:** Python 3.11, FastAPI, pytest, loguru, in-memory/SQLite/Postgres sandbox stores, Docker/Firecracker/Lima sandbox runners.

---

### Task 1: Establish the Sandbox Review Harness

**Files:**
- Inspect: `tldw_Server_API/tests/sandbox/conftest.py`
- Inspect: `tldw_Server_API/tests/sandbox/test_sandbox_api.py`
- Inspect: `tldw_Server_API/app/api/v1/endpoints/sandbox.py`

**Step 1: Confirm the sandbox test harness assumptions**

Read:
```bash
sed -n '1,240p' tldw_Server_API/tests/sandbox/conftest.py
sed -n '1,220p' tldw_Server_API/tests/sandbox/test_sandbox_api.py
```
Expected: clear understanding of auth defaults, fake execution defaults, stream-hub resets, and TestClient patching used by sandbox tests.

**Step 2: Run a baseline sandbox API smoke test**

Run:
```bash
source .venv/bin/activate && python -m pytest -vv \
  tldw_Server_API/tests/sandbox/test_sandbox_api.py::test_runtimes_discovery_shape
```
Expected: PASS. If this fails, stop and document the environment or harness problem before deeper review.

**Step 3: Record baseline review constraints**

Capture in working notes:
- whether fake Docker execution is enabled
- whether WS signed URLs are disabled
- whether auth is operating in sandbox single-user test mode

### Task 2: Audit Run Lifecycle, Queueing, and Claim Semantics

**Files:**
- Inspect: `tldw_Server_API/app/core/Sandbox/service.py`
- Inspect: `tldw_Server_API/app/core/Sandbox/orchestrator.py`
- Test: `tldw_Server_API/tests/sandbox/test_run_claim_fencing.py`
- Test: `tldw_Server_API/tests/sandbox/test_run_claim_heartbeat.py`
- Test: `tldw_Server_API/tests/sandbox/test_execution_concurrency_cap.py`
- Test: `tldw_Server_API/tests/sandbox/test_queue_full_429.py`

**Step 1: Read the core run-start and cancelation paths**

Inspect these functions:
- `SandboxService.start_run_scaffold`
- `SandboxService._run_with_claim_lease`
- `SandboxService.cancel_run`
- `SandboxOrchestrator.enqueue_run`
- `SandboxOrchestrator.try_claim_run`
- `SandboxOrchestrator.renew_run_claim`
- `SandboxOrchestrator.try_admit_run_start`
- `SandboxOrchestrator._prune_queue_ttl`

Expected: a written list of invariants for enqueue, claim, execution admission, lease renewal, and cancellation.

**Step 2: Run queueing and claim tests**

Run:
```bash
source .venv/bin/activate && python -m pytest -vv \
  tldw_Server_API/tests/sandbox/test_run_claim_fencing.py \
  tldw_Server_API/tests/sandbox/test_run_claim_heartbeat.py \
  tldw_Server_API/tests/sandbox/test_execution_concurrency_cap.py \
  tldw_Server_API/tests/sandbox/test_queue_full_429.py
```
Expected: PASS. Any failure becomes a first-class review finding or a blocking regression if it prevents further trust in lifecycle behavior.

**Step 3: Cross-check the implementation against the tests**

For any surprising branch or swallowed exception, trace supporting references:
```bash
rg -n "try_claim_run|renew_run_claim|release_run_claim|try_admit_run_start|cancel_run" \
  tldw_Server_API/app/core/Sandbox/service.py \
  tldw_Server_API/app/core/Sandbox/orchestrator.py
```
Expected: evidence for whether the code matches the tested contract or leaves an uncovered path.

### Task 3: Audit Store, Policy, and Runtime Fail-Closed Behavior

**Files:**
- Inspect: `tldw_Server_API/app/core/Sandbox/store.py`
- Inspect: `tldw_Server_API/app/core/Sandbox/policy.py`
- Inspect: `tldw_Server_API/app/core/Sandbox/runtime_capabilities.py`
- Inspect: `tldw_Server_API/app/core/Sandbox/runners/docker_runner.py`
- Inspect: `tldw_Server_API/app/core/Sandbox/runners/firecracker_runner.py`
- Inspect: `tldw_Server_API/app/core/Sandbox/runners/lima_runner.py`
- Inspect: `tldw_Server_API/app/core/Sandbox/runners/lima_enforcer.py`
- Test: `tldw_Server_API/tests/sandbox/test_runtime_unavailable.py`
- Test: `tldw_Server_API/tests/sandbox/test_lima_no_fallback.py`
- Test: `tldw_Server_API/tests/sandbox/test_lima_strict_admission.py`

**Step 1: Compare store semantics across backends**

Inspect the concrete implementations of:
- `check_idempotency`
- `store_idempotency`
- `put_run` / `update_run`
- `try_claim_run` / `renew_run_claim` / `release_run_claim`
- `try_admit_run_start`
- `get_run_owner` / `get_session_owner`

Expected: note any semantic drift between `InMemoryStore`, `SQLiteStore`, and `PostgresStore`, especially around ownership, timestamps, and lease handling.

**Step 2: Inspect runtime selection and strict-policy enforcement**

Review the policy and runner paths for:
- default runtime parsing
- `runtime_unavailable` vs `policy_unsupported` behavior
- no-fallback guarantees
- Lima strict admission and enforcement readiness

Expected: a short matrix of documented versus actual fail-closed behavior by runtime.

**Step 3: Run runtime and policy tests**

Run:
```bash
source .venv/bin/activate && python -m pytest -vv \
  tldw_Server_API/tests/sandbox/test_runtime_unavailable.py \
  tldw_Server_API/tests/sandbox/test_lima_no_fallback.py \
  tldw_Server_API/tests/sandbox/test_lima_strict_admission.py
```
Expected: PASS. Any mismatch between policy code and tests should be captured as either a bug or a risky incomplete path.

### Task 4: Audit Endpoint Ownership, Artifact Safety, and Stream Lifecycle

**Files:**
- Inspect: `tldw_Server_API/app/api/v1/endpoints/sandbox.py`
- Test: `tldw_Server_API/tests/sandbox/test_run_ownership.py`
- Test: `tldw_Server_API/tests/sandbox/test_admin_rbac.py`
- Test: `tldw_Server_API/tests/sandbox/test_artifact_traversal_integration.py`
- Test: `tldw_Server_API/tests/sandbox/test_artifact_content_type_and_path.py`
- Test: `tldw_Server_API/tests/sandbox/test_artifact_range.py`
- Test: `tldw_Server_API/tests/sandbox/test_ws_resume_edge_cases.py`
- Test: `tldw_Server_API/tests/sandbox/test_ws_connection_quotas.py`
- Test: `tldw_Server_API/tests/sandbox/test_cancel_endpoint_ws_and_status.py`

**Step 1: Read the route guards and ownership checks**

Inspect:
- `SandboxArtifactGuardRoute`
- `_require_run_owner`
- `_require_session_owner`
- `_resolve_sandbox_ws_user_id`
- `download_artifact`
- `stream_run_logs`
- admin list/detail endpoints

Expected: a map of which routes trust raw path inspection, stored ownership, admin status, or websocket token binding.

**Step 2: Run endpoint and stream tests**

Run:
```bash
source .venv/bin/activate && python -m pytest -vv \
  tldw_Server_API/tests/sandbox/test_run_ownership.py \
  tldw_Server_API/tests/sandbox/test_admin_rbac.py \
  tldw_Server_API/tests/sandbox/test_artifact_traversal_integration.py \
  tldw_Server_API/tests/sandbox/test_artifact_content_type_and_path.py \
  tldw_Server_API/tests/sandbox/test_artifact_range.py \
  tldw_Server_API/tests/sandbox/test_ws_resume_edge_cases.py \
  tldw_Server_API/tests/sandbox/test_ws_connection_quotas.py \
  tldw_Server_API/tests/sandbox/test_cancel_endpoint_ws_and_status.py
```
Expected: PASS. If a test fails, trace whether the issue is route logic, shared core state, or harness assumptions.

**Step 3: Trace any uncovered endpoint branches**

Use targeted search for error-prone branches:
```bash
rg -n "PermissionError|HTTPException|invalid_path|range|quota|resume|heartbeat|cancel" \
  tldw_Server_API/app/api/v1/endpoints/sandbox.py
```
Expected: identify branches that are reachable but not clearly covered by the selected tests.

### Task 5: Synthesize Findings and Deliver the Review

**Files:**
- Create: `docs/plans/2026-03-08-sandbox-subsystem-review-findings.md`
- Reference: `docs/plans/2026-03-08-sandbox-subsystem-review-design.md`

**Step 1: Draft the findings report**

Write the report with these sections:
```markdown
# Sandbox Subsystem Review Findings

## Findings
- [Severity] Title
  - Type: Bug | Incomplete Item | Residual Risk
  - Evidence: file path + line
  - Why it matters

## Targeted Test Runs
- command
- result

## Validation Gaps
- gap
```

**Step 2: Validate every finding against evidence**

Before delivering the review, ensure each finding has:
- one specific file reference
- one concrete behavioral claim
- a classification that matches the design doc rules

Expected: no vague findings, no “might be bad” commentary without evidence, and no mixing of intentional scaffolding with confirmed defects.

**Step 3: Deliver the user-facing review**

Respond in findings-first order:
- highest-severity findings first
- then open questions or assumptions
- then a short summary of tests run and any remaining gaps

Expected: a concise review that behaves like a code review, not a changelog or architecture essay.
