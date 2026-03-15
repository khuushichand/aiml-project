# Sandbox Subsystem Review Design

Date: 2026-03-08
Scope: `tldw_Server_API/app/core/Sandbox/` and `tldw_Server_API/app/api/v1/endpoints/sandbox.py`

## Context

The sandbox subsystem is broad enough that an unstructured review would waste time in lower-risk paths. The review should prioritize the internal control plane first, then validate the exposed API contracts against those internal invariants using a focused test slice.

The goal of this review is not to rewrite the subsystem. The goal is to identify:

1. Real bugs or unsafe behavior.
2. Incomplete or scaffolded paths that are operationally risky.
3. Residual risks where correctness depends on assumptions that are weakly enforced or weakly tested.

## Selected Approach

The selected approach is `core-first`.

Review order:

1. `tldw_Server_API/app/core/Sandbox/service.py`
2. `tldw_Server_API/app/core/Sandbox/orchestrator.py`
3. `tldw_Server_API/app/core/Sandbox/store.py`
4. `tldw_Server_API/app/core/Sandbox/policy.py`
5. Runtime and capability seams under `tldw_Server_API/app/core/Sandbox/runners/`
6. `tldw_Server_API/app/api/v1/endpoints/sandbox.py`

This order is intentional. The endpoint layer depends on queueing, ownership, policy, and artifact semantics that are defined in the core layer. Reviewing the API first would make it harder to distinguish a genuine API contract bug from a deeper invariant violation.

## Review Focus Areas

The review will concentrate on the following invariants:

### 1. Ownership and Authorization

- Run ownership is preserved and enforced consistently.
- Session ownership is preserved and enforced consistently.
- Admin-only surfaces remain correctly bounded.
- WebSocket auth and token binding do not open a weaker path than HTTP routes.

### 2. Queueing, Claims, and Concurrency

- Queue admission obeys configured capacity limits.
- Claim acquisition, renewal, and release are safe under concurrent workers.
- Lease expiry and fencing semantics do not allow duplicate execution or status corruption.
- Cancelation and session deletion interact safely with queued or active runs.

### 3. Runtime Selection and Fail-Closed Policy Behavior

- Explicit runtime selection is honored.
- Default runtime behavior is deterministic.
- Unsupported or unavailable runtime states fail closed rather than falling back silently.
- Network-policy enforcement paths behave consistently with the documented contract.

### 4. Artifact and Filesystem Safety

- Artifact paths cannot escape the expected artifact root.
- Range and content-type behavior matches route expectations.
- Session workspaces, uploads, snapshots, and restores preserve isolation boundaries.

### 5. Streaming and Lifecycle Semantics

- Stream ordering, resume, and heartbeat behavior are coherent.
- Connection quotas are enforced and released correctly.
- Run completion, cancelation, and stream termination do not leave leaked state behind.

## Targeted Test Slice

The review includes targeted test runs, but not the full sandbox suite. The first-pass validation set is:

### Queueing, claims, and concurrency

- `tldw_Server_API/tests/sandbox/test_run_claim_fencing.py`
- `tldw_Server_API/tests/sandbox/test_run_claim_heartbeat.py`
- `tldw_Server_API/tests/sandbox/test_execution_concurrency_cap.py`
- `tldw_Server_API/tests/sandbox/test_queue_full_429.py`

### Ownership and admin boundaries

- `tldw_Server_API/tests/sandbox/test_run_ownership.py`
- `tldw_Server_API/tests/sandbox/test_admin_rbac.py`

### Artifact and path safety

- `tldw_Server_API/tests/sandbox/test_artifact_traversal_integration.py`
- `tldw_Server_API/tests/sandbox/test_artifact_content_type_and_path.py`
- `tldw_Server_API/tests/sandbox/test_artifact_range.py`

### Runtime and policy behavior

- `tldw_Server_API/tests/sandbox/test_runtime_unavailable.py`
- `tldw_Server_API/tests/sandbox/test_lima_no_fallback.py`
- `tldw_Server_API/tests/sandbox/test_lima_strict_admission.py`

### WebSocket and lifecycle behavior

- `tldw_Server_API/tests/sandbox/test_ws_resume_edge_cases.py`
- `tldw_Server_API/tests/sandbox/test_ws_connection_quotas.py`
- `tldw_Server_API/tests/sandbox/test_cancel_endpoint_ws_and_status.py`

If static review reveals a suspicious path without matching coverage, that gap will be called out explicitly as a missing or incomplete test area.

## Classification Rules

Findings will be split into three buckets:

### Bug

Behavior that is incorrect, unsafe, internally inconsistent, or contradicted by surrounding contracts, tests, or documentation.

### Incomplete Item

An intentionally partial, scaffolded, or stubbed path that is reachable or relied upon in a way that creates operational or maintenance risk.

### Residual Risk

A path that may be intentional, but where enforcement, verification, or coverage is too weak to trust confidently without follow-up.

## Output Format

The review output should be findings-first and ordered by severity. Each finding should include:

- a concise title
- why the behavior is risky or incorrect
- a tight file reference
- whether it is a bug, incomplete item, or residual risk

The review should also include:

- the targeted tests that were run
- any failures observed
- any validation gaps that could not be resolved locally

## Exit Criteria

The review is complete when:

1. The core control plane and endpoint layer have both been inspected.
2. The targeted test slice has been run or any blockers have been documented.
3. Findings are separated cleanly from intentional scaffolding.
4. Unvalidated areas are called out explicitly rather than implied as safe.
