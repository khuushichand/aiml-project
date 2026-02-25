# Workflow Orchestration Hardening (Track 2) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Harden workflows orchestration for ACP-centric pipelines by enforcing state contracts, bounded reliability controls, and reason-coded observability.

**Architecture:** Implement state contract enforcement in the workflow engine first, then layer retry/cancel/loop reliability behavior on top of stable contracts, then add metrics/events aligned to the finalized reason-code model. Keep `acp_stage` outputs schema-versioned and validate every adapter return path before persistence. Roll out strict behavior behind enforceable flags (`log_only -> soft_enforce -> hard_enforce`).

**Tech Stack:** FastAPI, Python 3.11, Workflows Engine (`engine.py`), Workflows DB (`Workflows_DB.py`), ACP adapter (`adapters/integration/acp.py`), pytest.

---

## Execution Notes

- Follow `@test-driven-development` for each behavior change.
- Before completion claims, follow `@verification-before-completion`.
- Follow-on issue tracking already created:
  - Track 1 epic: [#772](https://github.com/rmusser01/tldw_server/issues/772)
  - Track 3 epic: [#773](https://github.com/rmusser01/tldw_server/issues/773)

### Task 1: Add State Contract Constants and Guard Helper

**Files:**
- Modify: `tldw_Server_API/app/core/Workflows/engine.py`
- Create: `tldw_Server_API/tests/Workflows/test_engine_state_contracts.py`

**Step 1: Write the failing test**

```python
import pytest
from tldw_Server_API.app.core.Workflows.engine import _is_allowed_transition


def test_state_contract_rejects_invalid_transition():
    assert _is_allowed_transition("running", "queued") is False
```

**Step 2: Run test to verify it fails**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Workflows/test_engine_state_contracts.py::test_state_contract_rejects_invalid_transition`
Expected: FAIL (`ImportError` or missing helper).

**Step 3: Write minimal implementation**

```python
_ALLOWED_TRANSITIONS = {
    "queued": {"running", "cancelled", "failed"},
    "running": {"waiting_human", "waiting_approval", "succeeded", "failed", "cancelled"},
    "waiting_human": {"running", "failed", "cancelled"},
    "waiting_approval": {"running", "failed", "cancelled"},
}


def _is_allowed_transition(current: str, target: str) -> bool:
    return target in _ALLOWED_TRANSITIONS.get(current, set())
```

**Step 4: Run test to verify it passes**

Run: same command as Step 2.
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Workflows/engine.py tldw_Server_API/tests/Workflows/test_engine_state_contracts.py
git commit -m "test(workflows): add state transition guard contract tests"
```

### Task 2: Enforce Transition Guard in Run/Step Status Updates

**Files:**
- Modify: `tldw_Server_API/app/core/Workflows/engine.py`
- Modify: `tldw_Server_API/tests/Workflows/test_engine_hardening.py`
- Modify: `tldw_Server_API/tests/Workflows/test_workflows_api.py`

**Step 1: Write the failing test**

```python
def test_invalid_transition_sets_invariant_violation(client_with_wf):
    # force a path that attempts an invalid transition
    ...
    assert run_data["status_reason"] == "invariant_violation"
```

**Step 2: Run test to verify it fails**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Workflows/test_engine_hardening.py -k invariant_violation`
Expected: FAIL (`status_reason` not normalized).

**Step 3: Write minimal implementation**

```python
# engine.py
if not _is_allowed_transition(current_status, target_status):
    self._append_event(run_id, "transition_rejected", {"from": current_status, "to": target_status})
    self.db.update_run_status(run_id, status="failed", status_reason="invariant_violation", ended_at=self._now_iso())
    return
```

**Step 4: Run tests to verify pass**

Run:
- `python -m pytest -v tldw_Server_API/tests/Workflows/test_engine_hardening.py -k invariant_violation`
- `python -m pytest -v tldw_Server_API/tests/Workflows/test_workflows_api.py -k status_reason`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Workflows/engine.py tldw_Server_API/tests/Workflows/test_engine_hardening.py tldw_Server_API/tests/Workflows/test_workflows_api.py
git commit -m "feat(workflows): enforce state transition guard with invariant violation handling"
```

### Task 3: Add Idempotent Lifecycle Mutation Helper

**Files:**
- Modify: `tldw_Server_API/app/core/Workflows/engine.py`
- Modify: `tldw_Server_API/tests/Workflows/test_workflows_idempotency_ttl.py`
- Create: `tldw_Server_API/tests/Workflows/test_engine_idempotent_lifecycle.py`

**Step 1: Write the failing test**

```python
def test_duplicate_cancel_request_is_already_applied(client_with_wf):
    ...
    first = client.post(f"/api/v1/workflows/runs/{run_id}/cancel").json()
    second = client.post(f"/api/v1/workflows/runs/{run_id}/cancel").json()
    assert second.get("result") == "already_applied"
```

**Step 2: Run test to verify it fails**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Workflows/test_engine_idempotent_lifecycle.py`
Expected: FAIL.

**Step 3: Write minimal implementation**

```python
# engine.py
self._op_cache: set[str] = set()

def _apply_once(self, op_key: str) -> bool:
    if op_key in self._op_cache:
        return False
    self._op_cache.add(op_key)
    return True
```

Use `_apply_once(...)` in pause/resume/cancel paths and surface `already_applied` payloads.

**Step 4: Run tests to verify pass**

Run:
- `python -m pytest -v tldw_Server_API/tests/Workflows/test_engine_idempotent_lifecycle.py`
- `python -m pytest -v tldw_Server_API/tests/Workflows/test_workflows_idempotency_ttl.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Workflows/engine.py tldw_Server_API/tests/Workflows/test_engine_idempotent_lifecycle.py tldw_Server_API/tests/Workflows/test_workflows_idempotency_ttl.py
git commit -m "feat(workflows): add idempotent lifecycle operation handling"
```

### Task 4: Version and Validate ACP Stage Output Contract

**Files:**
- Modify: `tldw_Server_API/app/core/Workflows/adapters/integration/acp.py`
- Modify: `tldw_Server_API/tests/Workflows/adapters/test_integration_adapters.py`
- Modify: `tldw_Server_API/tests/Workflows/test_workflows_extras.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_acp_stage_output_includes_schema_version(...):
    result = await run_acp_stage_adapter(...)
    assert result["acp_output_schema_version"] == "1.0"
```

**Step 2: Run test to verify it fails**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Workflows/adapters/test_integration_adapters.py -k acp_output_schema_version`
Expected: FAIL.

**Step 3: Write minimal implementation**

```python
_ACP_OUTPUT_SCHEMA_VERSION = "1.0"

payload["acp_output_schema_version"] = _ACP_OUTPUT_SCHEMA_VERSION
```

Add `_validate_acp_output_contract(payload)` before returns.

**Step 4: Run tests to verify pass**

Run:
- `python -m pytest -v tldw_Server_API/tests/Workflows/adapters/test_integration_adapters.py -k acp_stage`
- `python -m pytest -v tldw_Server_API/tests/Workflows/test_workflows_extras.py -k acp`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Workflows/adapters/integration/acp.py tldw_Server_API/tests/Workflows/adapters/test_integration_adapters.py tldw_Server_API/tests/Workflows/test_workflows_extras.py
git commit -m "feat(workflows): version and validate acp_stage output contract"
```

### Task 5: Implement Retry Classifier and Non-Retriable Taxonomy

**Files:**
- Modify: `tldw_Server_API/app/core/Workflows/engine.py`
- Modify: `tldw_Server_API/tests/Workflows/test_engine_retry_cancel_delay.py`
- Create: `tldw_Server_API/tests/Workflows/test_engine_retry_classifier.py`

**Step 1: Write the failing test**

```python
def test_retry_classifier_blocks_governance_errors():
    assert _is_retriable_error("acp_governance_blocked") is False
```

**Step 2: Run test to verify it fails**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Workflows/test_engine_retry_classifier.py`
Expected: FAIL.

**Step 3: Write minimal implementation**

```python
_NON_RETRIABLE_REASONS = {
    "validation_error",
    "authz_error",
    "acp_governance_blocked",
    "session_access_denied",
    "invariant_violation",
}
```

Route retry branch through `_is_retriable_error(reason_code)`.

**Step 4: Run tests to verify pass**

Run:
- `python -m pytest -v tldw_Server_API/tests/Workflows/test_engine_retry_classifier.py`
- `python -m pytest -v tldw_Server_API/tests/Workflows/test_engine_retry_cancel_delay.py -k retry`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Workflows/engine.py tldw_Server_API/tests/Workflows/test_engine_retry_classifier.py tldw_Server_API/tests/Workflows/test_engine_retry_cancel_delay.py
git commit -m "feat(workflows): add reason-code based retry classifier"
```

### Task 6: Harden Cancel Propagation and Acknowledgement Eventing

**Files:**
- Modify: `tldw_Server_API/app/core/Workflows/engine.py`
- Modify: `tldw_Server_API/tests/Workflows/test_engine_hardening.py`
- Modify: `tldw_Server_API/tests/Workflows/test_engine_retry_cancel_delay.py`

**Step 1: Write the failing test**

```python
def test_cancel_records_ack_event(client_with_wf):
    ...
    events = client.get(f"/api/v1/workflows/runs/{run_id}/events").json()
    assert any(e["event_type"] == "cancel_acknowledged" for e in events)
```

**Step 2: Run test to verify it fails**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Workflows/test_engine_retry_cancel_delay.py -k cancel_acknowledged`
Expected: FAIL.

**Step 3: Write minimal implementation**

```python
self._append_event(run_id, "cancel_acknowledged", {"step_id": step_id, "reason": "cancelled_by_user"})
```

Emit before terminal cancellation update.

**Step 4: Run tests to verify pass**

Run:
- `python -m pytest -v tldw_Server_API/tests/Workflows/test_engine_retry_cancel_delay.py -k cancel`
- `python -m pytest -v tldw_Server_API/tests/Workflows/test_engine_hardening.py -k cancel`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Workflows/engine.py tldw_Server_API/tests/Workflows/test_engine_retry_cancel_delay.py tldw_Server_API/tests/Workflows/test_engine_hardening.py
git commit -m "feat(workflows): add cancellation acknowledgement events"
```

### Task 7: Add Review Loop Guard Contract and Escalation Code

**Files:**
- Modify: `tldw_Server_API/app/core/Workflows/adapters/integration/acp.py`
- Modify: `tldw_Server_API/tests/Workflows/adapters/test_integration_adapters.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_review_loop_guard_returns_reason_code(...):
    result = await run_acp_stage_adapter(...)
    assert result["error"] == "review_loop_exceeded"
```

**Step 2: Run test to verify it fails**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Workflows/adapters/test_integration_adapters.py -k review_loop`
Expected: FAIL.

**Step 3: Write minimal implementation**

```python
if current >= maximum:
    return _normalize_error_payload(
        status="blocked",
        error_type="review_loop_exceeded",
        message="review_loop_exceeded",
        ...,
    )
```

**Step 4: Run tests to verify pass**

Run: `python -m pytest -v tldw_Server_API/tests/Workflows/adapters/test_integration_adapters.py -k review_loop`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Workflows/adapters/integration/acp.py tldw_Server_API/tests/Workflows/adapters/test_integration_adapters.py
git commit -m "feat(workflows): enforce review loop guard reason-code contract"
```

### Task 8: Add Observability Metrics for Reason-Coded Outcomes

**Files:**
- Modify: `tldw_Server_API/app/core/Workflows/metrics.py`
- Modify: `tldw_Server_API/app/core/Workflows/engine.py`
- Create: `tldw_Server_API/tests/Workflows/test_engine_observability.py`

**Step 1: Write the failing test**

```python
def test_reason_code_metric_emitted(monkeypatch):
    calls = []
    monkeypatch.setattr("...increment_counter", lambda name, labels=None: calls.append((name, labels)))
    ...
    assert any(name == "workflows_run_terminal_reasons_total" for name, _ in calls)
```

**Step 2: Run test to verify it fails**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Workflows/test_engine_observability.py`
Expected: FAIL.

**Step 3: Write minimal implementation**

```python
r.register_metric(MetricDefinition(
    name="workflows_run_terminal_reasons_total",
    type=MetricType.COUNTER,
    description="Workflow terminal outcomes by reason code",
    labels=["tenant", "reason_code"],
))
```

Emit in engine terminal paths.

**Step 4: Run tests to verify pass**

Run:
- `python -m pytest -v tldw_Server_API/tests/Workflows/test_engine_observability.py`
- `python -m pytest -v tldw_Server_API/tests/Workflows/test_engine_hardening.py -k event`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Workflows/metrics.py tldw_Server_API/app/core/Workflows/engine.py tldw_Server_API/tests/Workflows/test_engine_observability.py
git commit -m "feat(workflows): add reason-coded run outcome metrics"
```

### Task 9: Emit Structured Transition Events with Stable Keys

**Files:**
- Modify: `tldw_Server_API/app/core/Workflows/engine.py`
- Modify: `tldw_Server_API/tests/Workflows/test_workflows_api.py`
- Modify: `tldw_Server_API/tests/Workflows/test_engine_hardening.py`

**Step 1: Write the failing test**

```python
def test_transition_event_contains_reason_code(client_with_wf):
    ...
    transition_events = [e for e in events if e["event_type"] == "run_status_transition"]
    assert "reason_code" in transition_events[-1]["payload"]
```

**Step 2: Run test to verify it fails**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Workflows/test_workflows_api.py -k run_status_transition`
Expected: FAIL.

**Step 3: Write minimal implementation**

```python
self._append_event(run_id, "run_status_transition", {
    "from": prev_status,
    "to": next_status,
    "reason_code": reason_code,
    "attempt": attempt,
})
```

**Step 4: Run tests to verify pass**

Run:
- `python -m pytest -v tldw_Server_API/tests/Workflows/test_workflows_api.py -k run_status_transition`
- `python -m pytest -v tldw_Server_API/tests/Workflows/test_engine_hardening.py -k transition`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Workflows/engine.py tldw_Server_API/tests/Workflows/test_workflows_api.py tldw_Server_API/tests/Workflows/test_engine_hardening.py
git commit -m "feat(workflows): emit structured run transition events with reason codes"
```

### Task 10: Final Verification, Security Scan, and Documentation Linking

**Files:**
- Modify: `tldw_Server_API/app/core/Workflows/README.md`
- Modify: `Docs/Plans/2026-02-25-workflow-hardening-followon-tracks-design.md`

**Step 1: Add failing doc-link check (if absent) or TODO check test**

```python
# If no doc-link tests exist, add a minimal assertion in an existing docs sanity test file.
```

**Step 2: Run full targeted verification**

Run:
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Workflows/test_engine_state_contracts.py tldw_Server_API/tests/Workflows/test_engine_idempotent_lifecycle.py tldw_Server_API/tests/Workflows/test_engine_retry_classifier.py tldw_Server_API/tests/Workflows/test_engine_observability.py tldw_Server_API/tests/Workflows/adapters/test_integration_adapters.py -k "acp_stage or review_loop"`
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Workflows/engine.py tldw_Server_API/app/core/Workflows/adapters/integration/acp.py tldw_Server_API/app/core/Workflows/metrics.py -f json -o /tmp/bandit_workflow_hardening.json`

Expected:
- Tests pass.
- Bandit has no new findings in touched code.

**Step 3: Commit final plan/README alignment changes**

```bash
git add tldw_Server_API/app/core/Workflows/README.md Docs/Plans/2026-02-25-workflow-hardening-followon-tracks-design.md
git commit -m "docs(workflows): document hardening contracts, reason codes, and rollout modes"
```

