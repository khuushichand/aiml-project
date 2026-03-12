# MCP Hub External Slot Runtime Approval Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make external runtime approval slot-aware and fail closed, so approvals cover only exact already-bound/configured slot bundles, while missing bindings and missing secrets hard-deny with explicit messaging.

**Architecture:** Extend external-access evaluation with auth-template-derived requested slot sets, short-circuit hard-deny cases before generic approval evaluation, add slot-set-aware approval scoping, and render explicit external approval / deny messaging in the persona runtime UI.

**Tech Stack:** FastAPI, MCP Unified protocol layer, MCP Hub approval service, MCP Hub external access/auth services, React, Vitest, pytest, Bandit

---

## Status

- Task 1: Complete
- Task 2: Complete
- Task 3: Complete
- Task 4: Complete
- Task 5: Complete
- Task 6: Complete

### Task 1: Add failing protocol and UI tests for external slot approval semantics

**Files:**
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_slot_access.py`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Add backend failing tests**

Add tests that expect:

- missing required bound slot yields hard deny and no approval payload
- missing required slot secret yields hard deny and no approval payload
- already-bound/configured slot bundle yields approval-required under approval mode
- approval scope changes when requested slot set changes
- approval scope changes when tool name changes

**Step 2: Add UI failing tests**

Add tests that expect:

- external approval cards show server + slot set
- missing-binding hard deny shows explicit message and no approval controls
- missing-secret hard deny shows explicit message and no approval controls

**Step 3: Run focused tests to confirm failure**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_slot_access.py -k "external or slot or approval" -v

bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: FAIL.

### Task 2: Extend external-access evaluation with requested slot-bundle state

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_external_access_resolver.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_slot_access.py`

**Step 1: Add requested-slot-aware state**

Extend the external slot/server response model to capture:

- `requested_slots`
- `bound_slots`
- `missing_bound_slots`
- `missing_secret_slots`

Use the managed auth template as the source of `requested_slots`.

**Step 2: Preserve existing summary behavior where possible**

Do not remove current server/slot summaries; augment them so protocol can make
exact slot-bundle decisions.

**Step 3: Run focused external access tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_slot_access.py -v
```

Expected: PASS.

### Task 3: Short-circuit hard-deny external cases before generic approval

**Files:**
- Modify: `tldw_Server_API/app/core/MCP_unified/protocol.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py`

**Step 1: Refine external access classification**

In protocol external evaluation:

- hard deny `required_slot_not_granted`
- hard deny `required_slot_secret_missing`
- only return approval candidates for already-bound/configured slot sets

**Step 2: Avoid generic missing-tool outcomes**

Ensure external tool execution surfaces MCP policy denial reasons instead of
falling through to generic `Tool not found` where possible.

**Step 3: Run focused protocol tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py -k "external or approval" -v
```

Expected: PASS.

### Task 4: Add slot-set-aware approval scoping

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_approval_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py`

**Step 1: Extend approval scope payload hashing**

Add normalized sorted `requested_slots` to approval scope fingerprinting for
external slot usage.

**Step 2: Keep approval scope tool-specific**

Do not broaden reuse across tools or servers.

**Step 3: Run focused protocol/approval tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py -k "scope or approval or external" -v
```

Expected: PASS.

### Task 5: Update persona runtime UI for external approval and hard deny messaging

**Files:**
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Render external approval context**

For approval-required external cases, show:

- server id/name
- requested slot set
- explicit confirmation copy

**Step 2: Render hard-deny external messages**

For missing binding or missing secret:

- no approval controls
- explicit reason text
- affected slot names

**Step 3: Run focused UI tests**

Run:

```bash
bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

### Task 6: Full verification and Bandit

**Files:**
- No new files expected

**Step 1: Run full focused verification**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_slot_access.py -v

bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx

source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/core/MCP_unified/protocol.py \
  tldw_Server_API/app/services/mcp_hub_approval_service.py \
  tldw_Server_API/app/services/mcp_hub_external_access_resolver.py \
  tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  -f json -o /tmp/bandit_mcp_hub_external_slot_runtime_approval.json
```

Expected:

- focused pytest suites PASS
- persona Vitest suite PASS
- Bandit reports no new findings in touched code

---

## Definition Of Done

- External runtime approval applies only to exact already-bound/configured slot bundles
- Missing bindings hard-deny with explicit reason and no approval payload
- Missing secrets hard-deny with explicit reason and no approval payload
- Approval key includes normalized requested slot sets
- Persona runtime UI shows external approval slot context clearly
- Persona runtime UI shows explicit hard-deny external messages without approval controls
- Focused pytest, Vitest, and Bandit verification pass
