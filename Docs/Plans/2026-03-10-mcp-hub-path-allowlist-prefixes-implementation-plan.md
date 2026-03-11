# MCP Hub Path Allowlist Prefixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add inline workspace-relative path allowlist prefixes to MCP Hub policy documents, enforce them as an additional narrowing layer on top of existing path scope, include them in approval scoping, and expose them as a first-class guided-editor field.

**Architecture:** Extend policy documents with `path_allowlist_prefixes`, normalize and validate them on backend write paths, keep them as replacement fields in the resolver, compile them into absolute allowed roots under `workspace_root` during path enforcement, and add normalized allowlist context to approval scope hashing and UI previews.

**Tech Stack:** FastAPI, existing MCP Hub/AuthNZ services, MCP Unified runtime, React, Ant Design, pytest, Vitest, Bandit

## Status

- Task 1: Not started
- Task 2: Not started
- Task 3: Not started
- Task 4: Not started
- Task 5: Not started
- Task 6: Not started
- Task 7: Not started

---

### Task 1: Add failing tests for allowlist policy behavior and editor expectations

**Files:**
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/policyHelpers.test.ts`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyDocumentEditor.test.tsx`

**Step 1: Add backend policy tests**

Cover:

- profiles, assignments, and overrides preserve `path_allowlist_prefixes`
- `path_allowlist_prefixes` uses replacement semantics, not union semantics
- effective-policy preview exposes the active list

**Step 2: Add UI tests**

Cover:

- allowlists are treated as first-class guided fields
- switching path scope to `none` clears allowlist state
- advanced-field warnings do not trigger for `path_allowlist_prefixes`

**Step 3: Run the focused tests to verify failure**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py -k allowlist -v
```

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__/policyHelpers.test.ts apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyDocumentEditor.test.tsx
```

Expected: FAIL.

### Task 2: Add backend normalization and validation for allowlist prefixes

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_service.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py`

**Step 1: Add a shared backend normalizer**

Normalize:

- trim whitespace
- backslash to slash
- strip leading `./`
- reject absolute paths
- reject `..`
- dedupe and sort

Apply it to:

- profile policy documents
- assignment inline policy documents
- assignment override policy documents

**Step 2: Add validation behavior**

Reject invalid allowlist entries with a clear `400`.

**Step 3: Run focused backend tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py -k "allowlist or path_scope" -v
```

Expected: PASS.

### Task 3: Extend broadened-access detection for path scope and allowlist widening

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py`

**Step 1: Update grant-authority delta logic**

Detect widening when:

- `cwd_descendants -> workspace_root`
- allowlist removed
- allowlist expanded from a smaller set to a larger one

Keep narrowing always allowed.

**Step 2: Add tests**

Cover:

- widening allowlist requires grant authority
- narrowing allowlist does not
- wider path scope requires grant authority

**Step 3: Run focused tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py -k "grant and allowlist" -v
```

Expected: PASS.

### Task 4: Add runtime allowlist enforcement on top of existing path scope

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_path_enforcement_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_path_enforcement_service.py`

**Step 1: Add failing enforcement tests**

Cover:

- candidate must remain within both scope root and allowlist root
- `src` does not match `src2`
- allowlist miss returns `path_outside_allowlist_scope`
- no allowlist preserves current behavior

**Step 2: Implement canonical allowlist matching**

Compile normalized allowlist prefixes into absolute allowed roots under `workspace_root`.

Evaluate candidates with the same ancestry predicate already used for path scope.

**Step 3: Run focused enforcement tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_path_enforcement_service.py -k allowlist -v
```

Expected: PASS.

### Task 5: Extend approval scope hashing and reasons for allowlist misses

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_approval_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_approval_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py`

**Step 1: Extend scope payload**

Include normalized allowlist context in the approval fingerprint for path-related decisions.

**Step 2: Add reason-specific behavior**

Ensure allowlist misses surface as:

- `path_outside_allowlist_scope`

and remain approvable under the current path-scope elevation model.

**Step 3: Run focused tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_approval_service.py tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py -k "allowlist or path_outside_allowlist_scope" -v
```

Expected: PASS.

### Task 6: Expose allowlists as first-class guided-editor fields and preview state

**Files:**
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PolicyDocumentEditor.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/policyHelpers.ts`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PolicyAssignmentsTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PersonaPolicySummary.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/policyHelpers.test.ts`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyDocumentEditor.test.tsx`

**Step 1: Add guided-editor controls**

Show `Allowed workspace paths` when `path_scope_mode` is not `none`.

Normalize UI display to match backend output.

**Step 2: Update editor helper behavior**

- make `path_allowlist_prefixes` first-class
- clear it when scope becomes `none`
- preserve replacement semantics in preview copy

**Step 3: Update summary surfaces**

Show active normalized allowlist prefixes in effective summaries where path scope is already shown.

**Step 4: Run focused UI tests**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__/policyHelpers.test.ts apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyDocumentEditor.test.tsx
```

Expected: PASS.

### Task 7: Run verification, update docs, and checkpoint

**Files:**
- Modify: `Docs/Plans/2026-03-10-mcp-hub-path-allowlist-prefixes-design.md`
- Modify: `Docs/Plans/2026-03-10-mcp-hub-path-allowlist-prefixes-implementation-plan.md`

**Step 1: Run focused backend verification**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_path_enforcement_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_approval_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py -v
```

**Step 2: Run focused UI verification**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__
```

**Step 3: Run Bandit on touched backend scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/app/services/mcp_hub_service.py \
  tldw_Server_API/app/services/mcp_hub_path_enforcement_service.py \
  tldw_Server_API/app/services/mcp_hub_approval_service.py
```

Expected: no new findings in touched code.

**Step 4: Update doc status**

Mark this design and plan as implemented and record any deliberate deferrals.

**Step 5: Commit**

```bash
git add Docs/Plans/2026-03-10-mcp-hub-path-allowlist-prefixes-design.md Docs/Plans/2026-03-10-mcp-hub-path-allowlist-prefixes-implementation-plan.md
git commit -m "docs: add MCP Hub path allowlist prefixes plan"
```
