# MCP Hub Generic Workspace Root Resolution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend MCP Hub path-scoped enforcement to trusted direct MCP/API callers by resolving `workspace_root` from sandbox-owned workspace metadata instead of requiring a sandbox session id.

**Architecture:** Add a trusted workspace-root resolver over existing sandbox store state, ingest direct-caller `workspace_id` and `cwd` through explicit MCP HTTP headers, and feed the existing path-scope service with canonical server-owned workspace roots.

**Tech Stack:** FastAPI, MCP Unified endpoint layer, MCP protocol, sandbox store/service, pytest, Bandit

---

## Status

- Task 1: Complete
- Task 2: Complete
- Task 3: Complete
- Task 4: Complete
- Task 5: Complete
- Task 6: Complete

### Task 1: Add failing tests for trusted direct workspace resolution

**Files:**
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_path_scope_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_unified_endpoint.py` or the closest direct HTTP MCP endpoint suite

**Step 1: Add failing resolver tests**

Add tests that expect:

- direct caller with `user_id + workspace_id` resolves a trusted `workspace_root`
- unknown `workspace_id` returns `workspace_root_unavailable`
- conflicting candidate workspace paths return `workspace_root_ambiguous`
- `cwd` outside the resolved root returns `cwd_outside_workspace_scope`

**Step 2: Add failing endpoint metadata-ingress tests**

Add tests that expect:

- `x-tldw-workspace-id` is copied into MCP request metadata
- `x-tldw-cwd` is copied into MCP request metadata
- `/mcp/tools/execute` and JSON-RPC ingress both behave the same way

**Step 3: Run focused tests and confirm failure**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_path_scope_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_unified_endpoint.py -k "workspace or path_scope or tools_execute" -v
```

Expected: FAIL.

### Task 2: Add a trusted workspace-root resolver over sandbox state

**Files:**
- Add: `tldw_Server_API/app/services/mcp_hub_workspace_root_resolver.py`
- Modify: `tldw_Server_API/app/core/Sandbox/service.py` or sandbox store helpers if needed
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_path_scope_service.py`

**Step 1: Build the resolver**

Implement a small service that:

- prefers exact sandbox-session lookup when `session_id` is present
- otherwise resolves `(user_id, workspace_id)` against trusted sandbox records
- canonicalizes `workspace_path`
- rejects ambiguous or untrusted matches

**Step 2: Keep the first version narrow**

Use existing sandbox-owned data only. Do not add a new global workspace registry in this PR.

**Step 3: Run focused resolver tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_path_scope_service.py -v
```

Expected: PASS.

### Task 3: Integrate the resolver into MCP Hub path scope

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_path_scope_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_path_scope_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py`

**Step 1: Replace session-only lookup**

Update path-scope resolution so it:

- uses sandbox session root when available
- otherwise uses the new trusted workspace-root resolver
- returns structured reasons:
  - `workspace_root_unavailable`
  - `workspace_root_ambiguous`
  - `workspace_root_untrusted`
  - `cwd_outside_workspace_scope`

**Step 2: Preserve existing path enforcement behavior**

Do not change path extraction or approval logic here beyond feeding it a better `workspace_root`.

**Step 3: Run focused path-scope tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_path_scope_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py -k "workspace or path_scope" -v
```

Expected: PASS.

### Task 4: Add explicit direct MCP/API workspace metadata ingress

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_unified_endpoint.py`
- Modify: relevant MCP endpoint schema/tests if needed
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_unified_endpoint.py`

**Step 1: Add trusted headers**

Add optional request headers:

- `x-tldw-workspace-id`
- `x-tldw-cwd`

Copy them into request metadata after authentication for:

- JSON-RPC request endpoint
- `/mcp/tools/execute`

**Step 2: Keep request-body semantics unchanged**

Do not add workspace-root semantics to tool arguments or JSON-RPC params.

**Step 3: Run focused endpoint tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_unified_endpoint.py -k "workspace or tools_execute" -v
```

Expected: PASS.

### Task 5: Add direct-caller protocol coverage

**Files:**
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py`

**Step 1: Cover direct request context**

Add protocol tests that verify:

- path-scoped tool calls work for a direct caller when metadata includes trusted `workspace_id`
- the same calls fail closed when no trusted root exists
- direct caller `cwd_descendants` remains narrower than `workspace_root`

**Step 2: Keep existing sandbox-backed path tests green**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py -v
```

Expected: PASS.

### Task 6: Full verification and Bandit

**Files:**
- No new files expected

**Step 1: Run focused verification**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_path_scope_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_unified_endpoint.py -v

source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/services/mcp_hub_workspace_root_resolver.py \
  tldw_Server_API/app/services/mcp_hub_path_scope_service.py \
  tldw_Server_API/app/api/v1/endpoints/mcp_unified_endpoint.py \
  -f json -o /tmp/bandit_mcp_hub_generic_workspace_root_resolution.json
```

Expected:

- focused pytest suites PASS
- Bandit reports no new findings in touched code

---

## Definition Of Done

- Direct MCP/API callers can participate in trusted MCP Hub path-scope enforcement using server-known `workspace_id`
- Raw absolute client-supplied workspace roots remain unsupported
- Resolver fails closed on missing, ambiguous, or untrusted workspace mappings
- Existing sandbox-session-based path scope continues to work
- Direct MCP ingress carries trusted `workspace_id` and `cwd` metadata consistently
