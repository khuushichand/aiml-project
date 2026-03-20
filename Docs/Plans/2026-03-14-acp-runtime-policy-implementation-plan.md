# ACP Runtime Policy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make MCP Hub effective policy the authoritative ACP runtime policy source by adding ACP policy snapshots, fingerprint-based refresh, backward-compatible ACP payload expansion, and runner integration that uses MCP Hub-backed allow/ask/deny decisions.

**Architecture:** Add an `ACPRuntimePolicyService` that builds normalized MCP Hub policy context from ACP session state, resolves effective policy into an ACP snapshot, persists lightweight snapshot metadata with ACP sessions, and refreshes snapshots conservatively with per-session singleflight locking. Keep ACP profiles as execution config plus hints, integrate snapshot authority into the existing ACP runner governance and permission paths, and expand ACP schemas/UI with backward-compatible policy summary and provenance fields.

**Tech Stack:** FastAPI, Pydantic, SQLite ACP session persistence, MCP Hub policy resolver, ACP runner clients, React, TypeScript, Vitest, pytest, Bandit

---

## Status

- Task 1: Complete
- Task 2: Complete
- Task 3: Complete
- Task 4: Complete
- Task 5: Complete
- Task 6: Complete

### Task 1: Add ACP session snapshot persistence

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ACP_Sessions_DB.py`
- Modify: `tldw_Server_API/app/services/admin_acp_sessions_service.py`
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sessions_db.py`
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_session_store.py`

**Step 1: Write the failing persistence tests**

Add tests that expect ACP session rows and `SessionRecord` serialization to include:

- `policy_snapshot_version`
- `policy_snapshot_fingerprint`
- `policy_snapshot_refreshed_at`
- `policy_summary`
- `policy_provenance_summary`
- `policy_refresh_error`

Example test shape:

```python
def test_register_session_persists_policy_snapshot_fields(tmp_path):
    db = ACPSessionsDB(db_path=str(tmp_path / "acp_sessions.db"))
    row = db.register_session(
        session_id="s1",
        user_id=7,
        policy_snapshot_version="v1",
        policy_snapshot_fingerprint="abc123",
        policy_summary={"allowed": 2, "denied": 1},
    )
    assert row["policy_snapshot_fingerprint"] == "abc123"
    assert row["policy_summary"] == {"allowed": 2, "denied": 1}
```

**Step 2: Run the focused tests to confirm they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sessions_db.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_session_store.py -v
```

Expected: FAIL because the DB schema and session serialization do not expose snapshot fields yet.

**Step 3: Implement the minimal persistence changes**

Update `ACP_Sessions_DB.py` to:

- bump `_SCHEMA_VERSION`
- add nullable columns for snapshot fingerprint/version/refresh metadata
- store `policy_summary` and `policy_provenance_summary` as JSON text
- deserialize them in `_row_to_dict`
- allow `register_session()` and update helpers to set or clear those fields

Update `admin_acp_sessions_service.py` to:

- extend `SessionRecord`
- expose the new fields in `to_info_dict()` and `to_detail_dict()`

**Step 4: Re-run the focused tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sessions_db.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_session_store.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/DB_Management/ACP_Sessions_DB.py \
  tldw_Server_API/app/services/admin_acp_sessions_service.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sessions_db.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_session_store.py
git commit -m "feat: persist ACP policy snapshot metadata"
```

### Task 2: Add the ACP runtime policy service and normalized context builder

**Files:**
- Create: `tldw_Server_API/app/services/acp_runtime_policy_service.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_service.py`
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_integration_persistence.py`
- Create: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_runtime_policy_service.py`

**Step 1: Write the failing runtime-policy tests**

Add tests that expect:

- normalized MCP Hub metadata is built from ACP session context
- ACP profile config stays separate from authoritative policy
- runtime policy service returns a snapshot with fingerprint, summary, provenance summary, and resolved policy
- changing effective policy input changes the fingerprint

Example test shape:

```python
@pytest.mark.asyncio
async def test_build_snapshot_uses_normalized_context(service, session_record):
    snapshot = await service.build_snapshot(session_record, user_id=42)
    assert snapshot.context_summary["persona_id"] == "persona-1"
    assert "resolved_policy_document" in snapshot.model_dump()
    assert snapshot.policy_snapshot_fingerprint
```

**Step 2: Run the focused tests to confirm they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_runtime_policy_service.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_integration_persistence.py -v
```

Expected: FAIL because the service and snapshot model do not exist yet.

**Step 3: Implement the runtime policy service**

Create `acp_runtime_policy_service.py` with:

- snapshot dataclasses or models
- normalized ACP-to-MCP-Hub metadata builder
- fingerprint computation from canonical resolved policy plus context
- snapshot summary/provenance summary derivation
- refresh helpers that can compare the cached fingerprint against a newly resolved one

Wire any ACP profile lookups through existing MCP Hub service/repo access rather than inventing a second ACP profile loader.

**Step 4: Re-run the focused tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_runtime_policy_service.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_integration_persistence.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/services/acp_runtime_policy_service.py \
  tldw_Server_API/app/services/mcp_hub_service.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_runtime_policy_service.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_integration_persistence.py
git commit -m "feat: add ACP runtime policy snapshots"
```

### Task 3: Integrate MCP Hub-backed snapshot authority into ACP runner governance

**Files:**
- Modify: `tldw_Server_API/app/core/Agent_Client_Protocol/runner_client.py`
- Modify: `tldw_Server_API/app/core/Agent_Client_Protocol/sandbox_runner_client.py`
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sandbox_runner_client.py`
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_governance_coordinator.py`
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_websocket.py`

**Step 1: Write the failing runner tests**

Add tests that expect:

- denied tools are blocked immediately from the runtime snapshot
- approval-required tools create permission requests with governance payload
- auto-allowed tools bypass manual approval even when legacy tier is not `auto`
- one refresh runs per session when concurrent permission checks happen
- prompt governance still works, but tool authority comes from the snapshot result

Example test shape:

```python
@pytest.mark.asyncio
async def test_permission_request_uses_runtime_snapshot_authority(client):
    outcome = await client._decide_tool_permission(
        session_id="s1",
        tool_name="fs.write",
        tool_arguments={"path": "x"},
    )
    assert outcome["action"] == "prompt"
    assert outcome["policy_snapshot_fingerprint"] == "abc123"
```

**Step 2: Run the focused tests to confirm they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sandbox_runner_client.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_governance_coordinator.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_websocket.py -v
```

Expected: FAIL because runner clients still rely on legacy tier heuristics and do not consume policy snapshots.

**Step 3: Implement minimal runner integration**

Update the runner clients to:

- load or refresh ACP policy snapshots through `ACPRuntimePolicyService`
- treat MCP Hub snapshot authority as the source of `approve`, `prompt`, or `deny`
- keep `tier` as optional UI metadata only
- attach governance reason, narrowing reason, provenance summary, and snapshot fingerprint to permission requests
- guard refresh with a per-session singleflight lock or shared task map

Keep existing ACP prompt-governance checks, but ensure they no longer decide tool allowlists independently.

**Step 4: Re-run the focused tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sandbox_runner_client.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_governance_coordinator.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_websocket.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/Agent_Client_Protocol/runner_client.py \
  tldw_Server_API/app/core/Agent_Client_Protocol/sandbox_runner_client.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sandbox_runner_client.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_governance_coordinator.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_websocket.py
git commit -m "feat: enforce ACP runtime policy snapshots"
```

### Task 4: Expand ACP schemas and endpoints with backward-compatible policy fields

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/agent_client_protocol.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py`
- Modify: `tldw_Server_API/app/services/admin_acp_sessions_service.py`
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_endpoints.py`
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_status_schema.py`

**Step 1: Write the failing schema/API tests**

Add tests that expect:

- session create/list/detail responses expose optional policy snapshot fields
- permission request payloads expose optional `approval_requirement`, `governance_reason`, `deny_reason`, `provenance_summary`, `runtime_narrowing_reason`, and `policy_snapshot_fingerprint`
- existing `tier` remains present for compatibility

Example test shape:

```python
def test_permission_request_schema_keeps_tier_and_adds_policy_fields():
    payload = ACPWSPermissionRequestMessage(
        request_id="r1",
        session_id="s1",
        tool_name="web.search",
        tier="individual",
        approval_requirement="approval_required",
        policy_snapshot_fingerprint="abc123",
    )
    assert payload.tier == ACPPermissionTier.INDIVIDUAL
    assert payload.policy_snapshot_fingerprint == "abc123"
```

**Step 2: Run the focused tests to confirm they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_endpoints.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_status_schema.py -v
```

Expected: FAIL because the new optional fields are not in the schemas or endpoint responses.

**Step 3: Implement the schema and endpoint changes**

Update the Pydantic models and endpoint serialization to:

- keep old fields intact
- add new optional policy snapshot summary/provenance fields
- include snapshot metadata in session list/detail/create responses
- include richer permission request fields without changing current message types

**Step 4: Re-run the focused tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_endpoints.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_status_schema.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/api/v1/schemas/agent_client_protocol.py \
  tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py \
  tldw_Server_API/app/services/admin_acp_sessions_service.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_endpoints.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_status_schema.py
git commit -m "feat: expose ACP policy snapshot metadata"
```

### Task 5: Update ACP frontend client, store, and UI surfaces

**Files:**
- Modify: `apps/packages/ui/src/services/acp/types.ts`
- Modify: `apps/packages/ui/src/services/acp/client.ts`
- Modify: `apps/packages/ui/src/store/acp-sessions.ts`
- Modify: `apps/packages/ui/src/routes/option-acp-playground.tsx`
- Modify: `apps/packages/ui/src/services/acp/__tests__/client.test.ts`
- Modify: `apps/packages/ui/src/store/__tests__/acp-sessions.test.ts`

**Step 1: Write the failing frontend tests**

Add tests that expect:

- ACP session responses with policy summary/provenance fields are parsed safely
- permission request payloads retain `tier` and expose snapshot/provenance details
- ACP session store surfaces snapshot refresh state to the playground UI

Example test shape:

```ts
it("keeps tier while exposing policy snapshot metadata", () => {
  const message: ACPWSPermissionRequestMessage = {
    type: "permission_request",
    request_id: "r1",
    session_id: "s1",
    tool_name: "web.search",
    tool_arguments: {},
    tier: "individual",
    policy_snapshot_fingerprint: "abc123",
    approval_requirement: "approval_required",
  }
  expect(message.tier).toBe("individual")
  expect(message.policy_snapshot_fingerprint).toBe("abc123")
})
```

**Step 2: Run the focused frontend tests to confirm they fail**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/services/acp/__tests__/client.test.ts \
  apps/packages/ui/src/store/__tests__/acp-sessions.test.ts
```

Expected: FAIL because the TS types and store do not include the new policy fields yet.

**Step 3: Implement the minimal frontend changes**

Update ACP frontend types and state handling to:

- add optional session snapshot summary/provenance fields
- add optional permission-request governance fields
- preserve `tier`
- surface snapshot refresh state and compact policy summary in the ACP playground/session views

Keep the default UI compact; detailed provenance can remain behind an expandable view.

**Step 4: Re-run the focused frontend tests**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/services/acp/__tests__/client.test.ts \
  apps/packages/ui/src/store/__tests__/acp-sessions.test.ts
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/services/acp/types.ts \
  apps/packages/ui/src/services/acp/client.ts \
  apps/packages/ui/src/store/acp-sessions.ts \
  apps/packages/ui/src/routes/option-acp-playground.tsx \
  apps/packages/ui/src/services/acp/__tests__/client.test.ts \
  apps/packages/ui/src/store/__tests__/acp-sessions.test.ts
git commit -m "feat: show ACP policy snapshot state"
```

### Task 6: Add integration parity, audit coverage, and final verification

**Files:**
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_integration_stub.py`
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_e2e_smoke.py`
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_session_management.py`
- Modify: `Docs/Plans/2026-03-14-acp-runtime-policy-implementation-plan.md`

**Step 1: Write the failing integration tests**

Add tests that expect:

- changing MCP Hub effective policy inputs changes ACP behavior after refresh
- permission decisions record the snapshot fingerprint used
- failed refreshes fail closed for risky actions
- older ACP clients still work when new optional fields are present

Example test shape:

```python
@pytest.mark.asyncio
async def test_policy_refresh_applies_updated_mcp_hub_permissions(acp_env):
    first = await acp_env.request_tool("web.search")
    assert first["action"] == "approve"

    await acp_env.update_mcp_hub_policy(deny=["web.search"])
    second = await acp_env.request_tool("web.search", force_refresh=True)
    assert second["action"] == "deny"
    assert second["policy_snapshot_fingerprint"] != first["policy_snapshot_fingerprint"]
```

**Step 2: Run the focused integration tests to confirm they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_integration_stub.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_session_management.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_e2e_smoke.py -v
```

Expected: FAIL because parity, audit, and refresh-closed behavior are not fully wired yet.

**Step 3: Implement the final integration and audit wiring**

Ensure:

- permission decisions persist or emit snapshot fingerprint/version data
- refresh-failure paths deny or require approval for risky actions
- integration fixtures can mutate effective policy inputs and observe ACP refresh behavior
- the plan status is updated as tasks complete

**Step 4: Run the final verification suite**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_runtime_policy_service.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sessions_db.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_session_store.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sandbox_runner_client.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_governance_coordinator.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_websocket.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_endpoints.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_status_schema.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_integration_stub.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_session_management.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_e2e_smoke.py -v

bunx vitest run \
  apps/packages/ui/src/services/acp/__tests__/client.test.ts \
  apps/packages/ui/src/store/__tests__/acp-sessions.test.ts

source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/services/acp_runtime_policy_service.py \
  tldw_Server_API/app/core/Agent_Client_Protocol/runner_client.py \
  tldw_Server_API/app/core/Agent_Client_Protocol/sandbox_runner_client.py \
  tldw_Server_API/app/api/v1/schemas/agent_client_protocol.py \
  tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py \
  tldw_Server_API/app/core/DB_Management/ACP_Sessions_DB.py \
  tldw_Server_API/app/services/admin_acp_sessions_service.py -f json -o /tmp/bandit_acp_runtime_policy.json

git diff --check
```

Expected: all tests PASS, Bandit reports `0 issues` in touched code, and `git diff --check` is clean.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_integration_stub.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_e2e_smoke.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_session_management.py \
  Docs/Plans/2026-03-14-acp-runtime-policy-implementation-plan.md
git commit -m "test: cover ACP runtime policy refresh integration"
```
