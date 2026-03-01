# Unified Governance Plane Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a shared governance layer that enforces policy decisions across MCP Unified tool execution and ACP prompt/permission flows, with deterministic auditing and gap handling.

**Architecture:** Add a new `app/core/Governance` domain, integrate it into MCP and ACP preflight paths, persist immutable decision traces, and roll out with `off/shadow/enforce` controls. Keep MCP wire compatibility via additive metadata while using a clean ACP contract.

**Tech Stack:** FastAPI, asyncio, Pydantic, existing AuthNZ DB abstractions (SQLite/Postgres), MCP Unified protocol/module system, pytest.

---

## Prerequisites

- Use a dedicated worktree before implementation (recommended by brainstorming workflow).
- Follow @test-driven-development and @verification-before-completion for each task.
- Keep commits small and frequent (one task = one commit).

### Task 1: Scaffold Governance Domain Types + Deterministic Resolver

**Files:**
- Create: `tldw_Server_API/app/core/Governance/__init__.py`
- Create: `tldw_Server_API/app/core/Governance/types.py`
- Create: `tldw_Server_API/app/core/Governance/resolver.py`
- Test: `tldw_Server_API/tests/Governance/test_policy_resolver.py`

**Step 1: Write the failing tests**

```python
def test_action_precedence_deny_beats_warn():
    result = resolve_effective_action([
        CandidateAction(action="warn", priority=10, scope_level=2),
        CandidateAction(action="deny", priority=1, scope_level=2),
    ])
    assert result.action == "deny"

def test_scope_precedence_workspace_beats_org():
    result = resolve_effective_action([
        CandidateAction(action="allow", priority=100, scope_level=1),  # org
        CandidateAction(action="require_approval", priority=1, scope_level=4),  # workspace
    ])
    assert result.action == "require_approval"
```

**Step 2: Run tests to verify failure**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Governance/test_policy_resolver.py -v`
Expected: FAIL with import/name errors.

**Step 3: Write minimal implementation**

```python
@dataclass(frozen=True)
class CandidateAction:
    action: Literal["allow", "warn", "require_approval", "deny"]
    priority: int
    scope_level: int

def resolve_effective_action(candidates: list[CandidateAction]) -> EffectiveAction:
    # scope desc, priority desc, then action precedence deny>require_approval>warn>allow
    ...
```

**Step 4: Run tests to verify pass**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Governance/test_policy_resolver.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Governance/__init__.py \
        tldw_Server_API/app/core/Governance/types.py \
        tldw_Server_API/app/core/Governance/resolver.py \
        tldw_Server_API/tests/Governance/test_policy_resolver.py
git commit -m "feat(governance): add core action resolver with deterministic precedence"
```

### Task 2: Add Governance Store with Schema Initialization + Gap Dedupe

**Files:**
- Create: `tldw_Server_API/app/core/Governance/store.py`
- Create: `tldw_Server_API/tests/Governance/test_governance_store_schema.py`
- Create: `tldw_Server_API/tests/Governance/test_governance_gap_dedupe.py`

**Step 1: Write failing tests**

```python
async def test_ensure_schema_creates_required_tables(tmp_path):
    store = GovernanceStore(sqlite_path=str(tmp_path / "gov.db"))
    await store.ensure_schema()
    assert await store.table_exists("governance_rules")
    assert await store.table_exists("governance_gaps")

async def test_open_gap_upsert_deduplicates_same_fingerprint(tmp_path):
    store = GovernanceStore(sqlite_path=str(tmp_path / "gov.db"))
    await store.ensure_schema()
    a = await store.upsert_open_gap(...)
    b = await store.upsert_open_gap(...)
    assert a.id == b.id
```

**Step 2: Run tests to verify failure**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Governance/test_governance_store_schema.py tldw_Server_API/tests/Governance/test_governance_gap_dedupe.py -v`
Expected: FAIL (store not implemented).

**Step 3: Write minimal implementation**

```python
class GovernanceStore:
    async def ensure_schema(self) -> None:
        # CREATE TABLE IF NOT EXISTS governance_rules...
        # CREATE TABLE IF NOT EXISTS governance_gaps...
        # CREATE UNIQUE INDEX ... WHERE status='open'
        ...

    async def upsert_open_gap(self, payload: GapUpsert) -> GapRecord:
        # insert-or-select on fingerprint+scope+category+open
        ...
```

**Step 4: Re-run tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Governance/test_governance_store_schema.py tldw_Server_API/tests/Governance/test_governance_gap_dedupe.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Governance/store.py \
        tldw_Server_API/tests/Governance/test_governance_store_schema.py \
        tldw_Server_API/tests/Governance/test_governance_gap_dedupe.py
git commit -m "feat(governance): add schema bootstrap and gap dedupe store"
```

### Task 3: Implement Governance Service (Query/Validate/Resolve + Fallback)

**Files:**
- Create: `tldw_Server_API/app/core/Governance/service.py`
- Create: `tldw_Server_API/tests/Governance/test_governance_service.py`

**Step 1: Write failing tests**

```python
async def test_validate_change_uses_shared_fallback_mode():
    svc = GovernanceService(store=FakeStore(), policy_loader=FakePolicy("warn_only"))
    out = await svc.validate_change(...)
    assert out.status in {"warn", "allow"}
    assert out.fallback_reason == "backend_unavailable"

async def test_query_knowledge_returns_category_source():
    out = await svc.query_knowledge(query="auth rules", category="security", ...)
    assert out.category_source in {"explicit", "metadata", "pattern", "default"}
```

**Step 2: Run tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Governance/test_governance_service.py -v`
Expected: FAIL.

**Step 3: Implement minimal service**

```python
class GovernanceService:
    async def query_knowledge(...): ...
    async def validate_change(...): ...
    async def resolve_gap(...): ...
    def resolve_fallback(...): ...
```

**Step 4: Re-run tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Governance/test_governance_service.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Governance/service.py \
        tldw_Server_API/tests/Governance/test_governance_service.py
git commit -m "feat(governance): add service APIs and shared fallback resolver"
```

### Task 4: Add MCP Governance Module (`governance.*` tools)

**Files:**
- Create: `tldw_Server_API/app/core/MCP_unified/modules/implementations/governance_module.py`
- Modify: `tldw_Server_API/Config_Files/mcp_modules.yaml`
- Test: `tldw_Server_API/app/core/MCP_unified/tests/test_governance_module.py`

**Step 1: Write failing module tests**

```python
async def test_governance_tools_are_listed():
    tools = await GovernanceModule(...).get_tools()
    assert {t["name"] for t in tools} >= {
        "governance.query_knowledge",
        "governance.validate_change",
        "governance.resolve_gap",
    }
```

**Step 2: Run tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/app/core/MCP_unified/tests/test_governance_module.py -v`
Expected: FAIL.

**Step 3: Implement module**

```python
class GovernanceModule(BaseModule):
    async def get_tools(self) -> list[dict[str, Any]]: ...
    async def execute_tool(self, tool_name: str, arguments: dict[str, Any], context=None) -> Any: ...
```

**Step 4: Re-run tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/app/core/MCP_unified/tests/test_governance_module.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/MCP_unified/modules/implementations/governance_module.py \
        tldw_Server_API/Config_Files/mcp_modules.yaml \
        tldw_Server_API/app/core/MCP_unified/tests/test_governance_module.py
git commit -m "feat(mcp): add governance module tools"
```

### Task 5: Integrate MCP Protocol Preflight + Recursion Guard (MCP Wire Compatible)

**Files:**
- Modify: `tldw_Server_API/app/core/MCP_unified/protocol.py`
- Test: `tldw_Server_API/app/core/MCP_unified/tests/test_protocol_governance_preflight.py`

**Step 1: Write failing integration tests**

```python
async def test_non_governance_tool_invokes_preflight():
    ...
    assert governance_called is True

async def test_governance_tools_bypass_preflight_but_keep_rbac():
    ...
    assert preflight_called is False
    assert rbac_checked is True

async def test_wire_compat_adds_governance_details_in_error_data_only():
    ...
    assert resp.error.code == existing_code
    assert "governance" in (resp.error.data or {})
```

**Step 2: Run tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/app/core/MCP_unified/tests/test_protocol_governance_preflight.py -v`
Expected: FAIL.

**Step 3: Implement protocol changes**

```python
if tool_name.startswith("governance.") or context.metadata.get("governance_bypass"):
    skip_governance = True
...
preflight = await governance_service.validate_change(...)
if preflight.action == "deny":
    raise PermissionError(...)
```

**Step 4: Re-run tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/app/core/MCP_unified/tests/test_protocol_governance_preflight.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/MCP_unified/protocol.py \
        tldw_Server_API/app/core/MCP_unified/tests/test_protocol_governance_preflight.py
git commit -m "feat(mcp): enforce governance preflight with recursion guard and compat metadata"
```

### Task 6: Integrate ACP Governance Coordinator (Prompt + Permission Paths)

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py`
- Modify: `tldw_Server_API/app/core/Agent_Client_Protocol/runner_client.py`
- Modify: `tldw_Server_API/app/core/Agent_Client_Protocol/sandbox_runner_client.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_governance_coordinator.py`

**Step 1: Write failing ACP tests**

```python
def test_prompt_denied_by_governance_returns_blocked_error(...): ...
def test_permission_request_uses_single_unified_approval_path(...): ...
def test_governance_require_approval_plus_batch_tier_creates_one_prompt(...): ...
```

**Step 2: Run tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_acp_governance_coordinator.py -v`
Expected: FAIL.

**Step 3: Implement coordinator + hook points**

```python
decision = await governance_service.validate_change(surface="acp_permission", ...)
effective = coordinator.merge(decision, tier_decision)
if effective.action == "deny": ...
if effective.action == "require_approval": ...
```

**Step 4: Re-run tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_acp_governance_coordinator.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py \
        tldw_Server_API/app/core/Agent_Client_Protocol/runner_client.py \
        tldw_Server_API/app/core/Agent_Client_Protocol/sandbox_runner_client.py \
        tldw_Server_API/tests/Agent_Client_Protocol/test_acp_governance_coordinator.py
git commit -m "feat(acp): add unified governance approval coordinator"
```

### Task 7: Add Governance Metrics, Audit Trace Persistence, and Rollout Controls

**Files:**
- Create: `tldw_Server_API/app/core/Governance/metrics.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/monitoring/metrics.py`
- Modify: `tldw_Server_API/app/core/config.py`
- Test: `tldw_Server_API/tests/Governance/test_governance_metrics_and_rollout.py`

**Step 1: Write failing tests**

```python
def test_rollout_modes_resolve_off_shadow_enforce(): ...
def test_metrics_use_low_cardinality_labels_only(): ...
def test_audit_trace_persists_policy_and_rule_revision_refs(): ...
```

**Step 2: Run tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Governance/test_governance_metrics_and_rollout.py -v`
Expected: FAIL.

**Step 3: Implement minimal changes**

```python
class GovernanceRolloutMode(str, Enum): OFF="off"; SHADOW="shadow"; ENFORCE="enforce"
...
metrics.inc_checks(surface=..., category=..., status=...)
```

**Step 4: Re-run tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Governance/test_governance_metrics_and_rollout.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Governance/metrics.py \
        tldw_Server_API/app/core/MCP_unified/monitoring/metrics.py \
        tldw_Server_API/app/core/config.py \
        tldw_Server_API/tests/Governance/test_governance_metrics_and_rollout.py
git commit -m "feat(governance): add rollout controls metrics and audit trace fields"
```

### Task 8: End-to-End Verification, Security Scan, and Documentation

**Files:**
- Modify: `Docs/MCP/Unified/Developer_Guide.md`
- Modify: `Docs/Development/Agent_Client_Protocol.md`
- Create: `Docs/MCP/Unified/Governance_Operations.md`

**Step 1: Run focused MCP/ACP/Governance tests**

Run:
`source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Governance tldw_Server_API/app/core/MCP_unified/tests/test_governance_module.py tldw_Server_API/app/core/MCP_unified/tests/test_protocol_governance_preflight.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_governance_coordinator.py -v`

Expected: PASS.

**Step 2: Run Bandit on touched paths**

Run:
`source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Governance tldw_Server_API/app/core/MCP_unified tldw_Server_API/app/core/Agent_Client_Protocol tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py -f json -o /tmp/bandit_governance.json`

Expected: No new high-severity findings in changed code.

**Step 3: Update docs with rollout and compatibility notes**

```markdown
- MCP wire compatibility remains intact; governance details are additive.
- ACP uses unified governance approval contract (no legacy shim).
- Rollout modes: off, shadow, enforce.
```

**Step 4: Final verification run**

Run: `source .venv/bin/activate && python -m pytest -m "unit or integration" tldw_Server_API/tests/Governance tldw_Server_API/tests/Agent_Client_Protocol -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add Docs/MCP/Unified/Developer_Guide.md \
        Docs/Development/Agent_Client_Protocol.md \
        Docs/MCP/Unified/Governance_Operations.md
git commit -m "docs(governance): add MCP ACP governance rollout and operations guidance"
```

## Notes for Execution

- Keep each task isolated; do not batch multiple tasks into one commit.
- If a task reveals schema or API drift, update this plan before coding further.
- If blocked after three attempts on one step, stop and reassess with alternatives.

