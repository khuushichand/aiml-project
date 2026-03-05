# Kanban Safe Orchestrator Workflow Primitives Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a policy-enforced Kanban workflow control plane (status model, transitions, approvals, leases, idempotency, events, and MCP primitives) suitable for safe autonomous orchestration.

**Architecture:** Introduce dedicated workflow tables in Kanban DB, add transactional DB methods for state transitions and approvals, expose REST endpoints for workflow control, then expose MCP primitives that call those DB methods with strict CAS + lease + idempotency checks. Preserve existing board/list/card behavior while making workflow status the canonical orchestrator state.

**Tech Stack:** FastAPI, SQLite (Kanban DB), Pydantic schemas, MCP Unified module system, pytest.

---

### Task 1: Add Workflow Schema and DB Migration Hooks

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Kanban_DB.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_kanban_module.py`
- Create: `tldw_Server_API/tests/kanban/test_workflow_schema_bootstrap.py`

**Step 1: Write the failing test**

```python
def test_workflow_tables_exist_after_db_init(tmp_path):
    db = KanbanDB(db_path=str(tmp_path / "kanban.db"), user_id="u1")
    # query sqlite_master and assert workflow tables exist
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/kanban/test_workflow_schema_bootstrap.py::test_workflow_tables_exist_after_db_init`
Expected: FAIL due missing workflow tables.

**Step 3: Write minimal implementation**

- Extend `_get_schema_sql()` with:
  - `board_workflow_policies`
  - `board_workflow_statuses`
  - `board_workflow_transitions`
  - `kanban_card_workflow_state`
  - `kanban_card_workflow_events`
  - `kanban_card_workflow_approvals`
  - workflow idempotency uniqueness constraints/indexes.

**Step 4: Run test to verify it passes**

Run same pytest command.
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/Kanban_DB.py tldw_Server_API/tests/kanban/test_workflow_schema_bootstrap.py
git commit -m "feat(kanban): add workflow control tables to schema"
```

### Task 2: Implement Policy and Runtime State DB Methods

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Kanban_DB.py`
- Create: `tldw_Server_API/tests/kanban/test_workflow_policy_state_db.py`

**Step 1: Write the failing test**

```python
def test_upsert_and_get_workflow_policy_roundtrip(db):
    # upsert policy + statuses + transitions
    # fetch and assert normalized structure
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/kanban/test_workflow_policy_state_db.py::test_upsert_and_get_workflow_policy_roundtrip`
Expected: FAIL due missing DB methods.

**Step 3: Write minimal implementation**

Add DB methods:
- `upsert_workflow_policy(...)`
- `get_workflow_policy(board_id)`
- `list_workflow_statuses(board_id)`
- `list_workflow_transitions(board_id)`
- `get_card_workflow_state(card_id)`
- `patch_card_workflow_state(card_id, ..., expected_version, lease_owner, idempotency_key)`

**Step 4: Run test to verify it passes**

Run same pytest command.
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/Kanban_DB.py tldw_Server_API/tests/kanban/test_workflow_policy_state_db.py
git commit -m "feat(kanban): add workflow policy and runtime state DB methods"
```

### Task 3: Implement Lease, Transition, Approval, and Event DB Operations

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Kanban_DB.py`
- Create: `tldw_Server_API/tests/kanban/test_workflow_transition_contract.py`

**Step 1: Write the failing test**

```python
def test_transition_requires_lease_and_expected_version(db):
    # attempt transition without lease -> lease_required
    # with lease but wrong version -> version_conflict
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/kanban/test_workflow_transition_contract.py::test_transition_requires_lease_and_expected_version`
Expected: FAIL due missing transition engine.

**Step 3: Write minimal implementation**

Add DB methods:
- `claim_card_workflow(...)`
- `release_card_workflow(...)`
- `transition_card_workflow(...)` (atomic policy enforcement)
- `decide_card_workflow_approval(...)`
- `list_card_workflow_events(...)`
- `list_stale_workflow_claims(...)`
- `force_reassign_workflow_claim(...)`

Implement strict projection behavior (`projection_failed`) for invalid mapped list targets.

**Step 4: Run test to verify it passes**

Run same pytest command and then full new workflow DB tests.
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/Kanban_DB.py tldw_Server_API/tests/kanban/test_workflow_transition_contract.py
git commit -m "feat(kanban): add transactional workflow transition and approval engine"
```

### Task 4: Add REST Schemas and Workflow Endpoints

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/kanban_schemas.py`
- Create: `tldw_Server_API/app/api/v1/endpoints/kanban/kanban_workflow.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/kanban/__init__.py`
- Create: `tldw_Server_API/tests/kanban/test_workflow_endpoints.py`

**Step 1: Write the failing endpoint test**

```python
def test_transition_endpoint_enforces_policy_and_returns_structured_error(client):
    # POST transition and assert error code payload for lease/version failures
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/kanban/test_workflow_endpoints.py::test_transition_endpoint_enforces_policy_and_returns_structured_error`
Expected: FAIL (route missing).

**Step 3: Write minimal implementation**

Add endpoints:
- policy get/upsert
- statuses list
- transitions list
- task state get/patch
- claim/release
- transition
- approval decide
- events list
- pause/resume/drain
- stale claims list
- force reassign

Ensure required fields on writes: `expected_version`, `idempotency_key`, `correlation_id` (for orchestrator write paths).

**Step 4: Run test to verify it passes**

Run same endpoint test, then full `test_workflow_endpoints.py`.
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/kanban_schemas.py tldw_Server_API/app/api/v1/endpoints/kanban/kanban_workflow.py tldw_Server_API/app/api/v1/endpoints/kanban/__init__.py tldw_Server_API/tests/kanban/test_workflow_endpoints.py
git commit -m "feat(kanban-api): expose workflow control endpoints"
```

### Task 5: Extend MCP Kanban Module with Workflow Primitives

**Files:**
- Modify: `tldw_Server_API/app/core/MCP_unified/modules/implementations/kanban_module.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/tests/test_kanban_module.py`

**Step 1: Write the failing MCP test**

```python
async def test_kanban_workflow_transition_tool_requires_expected_version_and_idempotency(...):
    # call tool with missing args and assert validation error
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -v tldw_Server_API/app/core/MCP_unified/tests/test_kanban_module.py -k workflow`
Expected: FAIL (tool names missing).

**Step 3: Write minimal implementation**

Add MCP tools:
- `kanban.workflow.policy.get`
- `kanban.workflow.policy.upsert`
- `kanban.workflow.statuses.list`
- `kanban.workflow.transitions.list`
- `kanban.workflow.task.state.get`
- `kanban.workflow.task.state.patch`
- `kanban.workflow.task.claim`
- `kanban.workflow.task.release`
- `kanban.workflow.task.transition`
- `kanban.workflow.task.approval.decide`
- `kanban.workflow.task.events.list`
- `kanban.workflow.control.pause`
- `kanban.workflow.control.resume`
- `kanban.workflow.control.drain`
- `kanban.workflow.recovery.list_stale_claims`
- `kanban.workflow.recovery.force_reassign`

Wire validation and execution handlers to DB methods.

**Step 4: Run test to verify it passes**

Run same pytest command and full MCP kanban test file.
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/MCP_unified/modules/implementations/kanban_module.py tldw_Server_API/app/core/MCP_unified/tests/test_kanban_module.py
git commit -m "feat(mcp-kanban): add safe workflow-control primitives"
```

### Task 6: Add Concurrency, Idempotency, and Projection Regression Tests

**Files:**
- Create: `tldw_Server_API/tests/kanban/test_workflow_idempotency_and_concurrency.py`
- Create: `tldw_Server_API/tests/kanban/test_workflow_projection_failures.py`

**Step 1: Write failing tests**

```python
def test_reused_idempotency_key_replays_without_duplicate_event(...): ...
def test_projection_fails_when_target_list_archived(...): ...
```

**Step 2: Run tests to verify fail**

Run: `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/kanban/test_workflow_idempotency_and_concurrency.py tldw_Server_API/tests/kanban/test_workflow_projection_failures.py`
Expected: FAIL until behavior finalized.

**Step 3: Implement minimal fixes**

Adjust DB/API/MCP flow as needed for deterministic behavior.

**Step 4: Re-run tests**

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/kanban/test_workflow_idempotency_and_concurrency.py tldw_Server_API/tests/kanban/test_workflow_projection_failures.py tldw_Server_API/app/core/DB_Management/Kanban_DB.py tldw_Server_API/app/api/v1/endpoints/kanban/kanban_workflow.py tldw_Server_API/app/core/MCP_unified/modules/implementations/kanban_module.py
git commit -m "test(kanban-workflow): lock idempotency, concurrency, and projection contracts"
```

### Task 7: Documentation Updates

**Files:**
- Modify: `Docs/MCP/Unified/User_Guide.md`
- Modify: `Docs/Published/User_Guides/WebUI_Extension/Kanban_Board_Guide.md`
- Create: `Docs/Prompts/Skills/kanban/SKILL.md`
- Modify: `Docs/MCP/mcp_tool_catalogs.md` (if tool-catalog examples need workflow grouping references)

**Step 1: Write docs-focused failing checks**

- Add/extend docs test or lint checks if available.
- At minimum, run markdown lint/spell/link checks used by project.

**Step 2: Run docs checks and capture failures**

Run project docs validation command(s).
Expected: FAIL before updates.

**Step 3: Update docs**

- Document workflow primitives, safety contract, and orchestrator usage.
- Add skill file using tldw MCP primitives for safe Kanban orchestration.

**Step 4: Re-run docs checks**

Expected: PASS.

**Step 5: Commit**

```bash
git add Docs/MCP/Unified/User_Guide.md Docs/Published/User_Guides/WebUI_Extension/Kanban_Board_Guide.md Docs/Prompts/Skills/kanban/SKILL.md Docs/MCP/mcp_tool_catalogs.md
git commit -m "docs(kanban): add safe orchestrator workflow and skill guidance"
```

### Task 8: Final Verification and Security Gate

**Files:**
- No new files required; run verification on touched scope.

**Step 1: Run targeted test suites**

```bash
source .venv/bin/activate && \
python -m pytest -v \
  tldw_Server_API/tests/kanban \
  tldw_Server_API/app/core/MCP_unified/tests/test_kanban_module.py
```

**Step 2: Run Bandit on touched code**

```bash
source .venv/bin/activate && \
python -m bandit -r \
  tldw_Server_API/app/core/DB_Management/Kanban_DB.py \
  tldw_Server_API/app/api/v1/endpoints/kanban/kanban_workflow.py \
  tldw_Server_API/app/core/MCP_unified/modules/implementations/kanban_module.py \
  -f json -o /tmp/bandit_kanban_workflow.json
```

**Step 3: Fix any new findings**

Address only new issues introduced by this work.

**Step 4: Final status check**

```bash
git status
```

Expected: clean working tree.

**Step 5: Commit any final adjustments**

```bash
git add -A
git commit -m "chore(kanban-workflow): final verification and hardening"
```

## Notes for Implementation

- Keep workflow status independent from list movement; list updates are projection side-effects only.
- Never bypass transition policy checks in API or MCP layers.
- Keep stable machine-readable error codes for orchestrator retry logic.
- Maintain backward compatibility for existing Kanban CRUD APIs.
