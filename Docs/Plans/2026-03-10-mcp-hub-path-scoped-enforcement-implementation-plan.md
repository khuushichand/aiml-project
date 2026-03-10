# MCP Hub Path-Scoped Enforcement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the first enforceable MCP Hub local path-scope model for sandbox-backed ACP/persona sessions, including workspace-derived scope fields, explicit phase-one path-enforceable tool support, runtime approval escalation when safe enforcement is impossible, and MCP Hub UI updates.

**Architecture:** Extend MCP Hub policy documents with scalar path-scope fields, add a runtime path-scope resolver anchored to sandbox-backed session workspace roots, expand the tool registry with explicit extraction hints, and enforce workspace-root or `cwd_descendants` boundaries only for an explicit first-wave allowlist of tools. Reuse sandbox path-canonicalization semantics and make path-related approvals use path-aware scope keys.

**Tech Stack:** FastAPI, existing MCP Hub/AuthNZ services, MCP Unified runtime, sandbox services, React, Ant Design, pytest, Vitest, Bandit

---

### Task 1: Add failing tests for path-scope policy fields and registry schema support

**Files:**
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_tool_registry.py`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/policyHelpers.test.ts`

**Step 1: Add backend API tests for new policy fields**

Add failing tests that expect MCP Hub profiles, assignments, overrides, and effective-policy preview to preserve:

- `path_scope_mode`
- `path_scope_enforcement`

Assert they behave as scalar replacement fields rather than list unions.

**Step 2: Add failing registry tests**

Expect registry entries to expose:

- `path_argument_hints`

Also add assertions that heuristic/fallback entries are not automatically considered phase-one path-enforceable.

**Step 3: Add failing UI helper tests**

Expect the simple/guided editor helpers to preserve advanced fields while adding path-scope fields.

**Step 4: Run the focused tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_tool_registry.py -k "path_scope or path_argument_hints" -v
```

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__/policyHelpers.test.ts
```

Expected: FAIL.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_tool_registry.py apps/packages/ui/src/components/Option/MCPHub/__tests__/policyHelpers.test.ts
git commit -m "test: add MCP Hub path-scope coverage"
```

### Task 2: Extend shared schemas and registry output for path extraction hints

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_tool_registry.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `apps/packages/ui/src/services/tldw/mcp-hub.ts`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_tool_registry.py`

**Step 1: Add normalized path hint support**

Extend registry derivation with:

- `path_argument_hints`

Normalize only simple supported shapes for phase one.

**Step 2: Tighten phase-one path enforcement trust**

Do not rely on broad heuristic category defaults alone. Add an explicit server-side allowlist or equivalent explicit metadata requirement for the first-wave path-enforceable tools.

**Step 3: Update shared schemas**

Add `path_argument_hints` to backend response schemas and frontend types.

**Step 4: Run the registry tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_tool_registry.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/mcp_hub_tool_registry.py tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py apps/packages/ui/src/services/tldw/mcp-hub.ts tldw_Server_API/tests/MCP_unified/test_mcp_hub_tool_registry.py
git commit -m "feat: add MCP Hub path extraction hints"
```

### Task 3: Add path-scope policy support to the resolver and policy APIs

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_policy_resolver.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py`

**Step 1: Preserve new scalar fields through policy resolution**

Ensure effective policy preview and runtime resolution carry:

- `path_scope_mode`
- `path_scope_enforcement`

These keys must remain replacement fields, not part of `_UNION_LIST_KEYS`.

**Step 2: Add resolver-focused tests**

Write tests for:

- default/group/persona replacement order
- override replacement of `path_scope_mode`
- no accidental union semantics

**Step 3: Run the focused resolver tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py -k path_scope -v
```

Expected: PASS.

**Step 4: Commit**

```bash
git add tldw_Server_API/app/services/mcp_hub_policy_resolver.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py
git commit -m "feat: add MCP Hub path-scope policy resolution"
```

### Task 4: Add a sandbox-backed path-scope runtime resolver

**Files:**
- Create: `tldw_Server_API/app/services/mcp_hub_path_scope_service.py`
- Modify: `tldw_Server_API/app/core/Sandbox/service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_path_scope_service.py`

**Step 1: Add failing path-scope runtime tests**

Cover:

- resolve `workspace_root` from sandbox-backed session id
- normalize `cwd` beneath `workspace_root`
- reject `cwd` outside `workspace_root`
- return a structured `workspace_root_unavailable` result when no trusted root exists

**Step 2: Implement the path-scope service**

Add a focused service that:

- accepts session metadata and effective policy
- resolves sandbox-backed `workspace_root`
- normalizes `cwd`
- returns a structured scope object

Keep this phase scoped to traffic where the server can prove the concrete root.

**Step 3: Run the new service tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_path_scope_service.py -v
```

Expected: PASS.

**Step 4: Commit**

```bash
git add tldw_Server_API/app/services/mcp_hub_path_scope_service.py tldw_Server_API/app/core/Sandbox/service.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_path_scope_service.py
git commit -m "feat: add MCP Hub sandbox path scope resolver"
```

### Task 5: Add the tool path extractor and first-wave path enforcement

**Files:**
- Create: `tldw_Server_API/app/services/mcp_hub_path_enforcement.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_approval_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_path_enforcement.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_approval_service.py`

**Step 1: Add failing enforcement tests**

Cover:

- allow path-enforceable tool inside `workspace_root`
- deny or escalate when path escapes `workspace_root`
- deny or escalate when path escapes `cwd_descendants`
- escalate for local-file tools that are not explicitly path-enforceable
- escalate when path extraction fails

**Step 2: Add path extraction support**

Use `path_argument_hints` to extract only simple supported shapes:

- `path`
- `file_path`
- `target_path`
- `cwd`
- `paths`
- `file_paths`
- `files[].path`

Do not guess beyond those shapes in this PR.

**Step 3: Add path-aware approval scoping**

For path-related approvals, incorporate into the approval scope:

- tool name
- reason code
- scope mode
- workspace root identity
- normalized path fingerprint

Do not reuse the generic coarse approval key for this path-specific branch.

**Step 4: Run the focused tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_path_enforcement.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_approval_service.py -k "path or scope" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/mcp_hub_path_enforcement.py tldw_Server_API/app/services/mcp_hub_approval_service.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_path_enforcement.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_approval_service.py
git commit -m "feat: add MCP Hub path-scoped tool enforcement"
```

### Task 6: Wire enforcement into MCP runtime execution

**Files:**
- Modify: `tldw_Server_API/app/core/MCP_unified/protocol.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_protocol.py`
- Modify: `tldw_Server_API/tests/Persona/test_persona_ws.py`

**Step 1: Add failing runtime tests**

Expect:

- path-scoped policy to be checked before execution for supported session traffic
- out-of-scope paths to trigger structured approval payloads
- unsupported traffic without a trusted workspace root to escalate rather than silently allow

**Step 2: Integrate the path-scope service and path enforcer**

Run the new checks after effective-policy resolution and before tool execution proceeds.

**Step 3: Preserve existing non-path policy behavior**

Ensure this PR does not change behavior for:

- non-local tools
- profiles without path-scope fields
- existing approval flows outside the path-enforcement branch

**Step 4: Run the focused runtime tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_protocol.py tldw_Server_API/tests/Persona/test_persona_ws.py -k "path_scope or approval" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/MCP_unified/protocol.py tldw_Server_API/tests/MCP_unified/test_protocol.py tldw_Server_API/tests/Persona/test_persona_ws.py
git commit -m "feat: enforce MCP Hub path scope at runtime"
```

### Task 7: Add MCP Hub editor and summary support for path scope

**Files:**
- Modify: `apps/packages/ui/src/components/Option/MCPHub/policyHelpers.ts`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PermissionProfilesTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PolicyAssignmentsTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PersonaPolicySummary.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/ToolCatalogsTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PermissionProfilesTab.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/ToolCatalogsTab.test.tsx`

**Step 1: Add guided editor controls**

For policies with local filesystem capability, add:

- `No additional path restriction`
- `Workspace root`
- `Current folder and descendants`

Preserve advanced/manual fields.

**Step 2: Add catalog badges**

Show:

- `path-enforceable`
- warning badge for local-file tools that still require approval fallback

**Step 3: Add summary display**

Show active path scope and approval-fallback status in effective-policy and persona summaries.

**Step 4: Run the focused UI suite**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/MCPHub/policyHelpers.ts apps/packages/ui/src/components/Option/MCPHub/PermissionProfilesTab.tsx apps/packages/ui/src/components/Option/MCPHub/PolicyAssignmentsTab.tsx apps/packages/ui/src/components/Option/MCPHub/PersonaPolicySummary.tsx apps/packages/ui/src/components/Option/MCPHub/ToolCatalogsTab.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/PermissionProfilesTab.test.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/ToolCatalogsTab.test.tsx
git commit -m "feat: add MCP Hub path scope editor and summaries"
```

### Task 8: Verify, document follow-ups, and harden the touched scope

**Files:**
- Modify: `Docs/Plans/2026-03-10-mcp-hub-path-scoped-enforcement-design.md`
- Modify: `Docs/Plans/2026-03-10-mcp-hub-path-scoped-enforcement-implementation-plan.md`

**Step 1: Run the focused backend and frontend suites**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_tool_registry.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_path_scope_service.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_path_enforcement.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_approval_service.py tldw_Server_API/tests/MCP_unified/test_protocol.py tldw_Server_API/tests/Persona/test_persona_ws.py -v
```

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__
```

**Step 2: Run Bandit on the touched backend scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/services/mcp_hub_tool_registry.py tldw_Server_API/app/services/mcp_hub_path_scope_service.py tldw_Server_API/app/services/mcp_hub_path_enforcement.py tldw_Server_API/app/services/mcp_hub_approval_service.py tldw_Server_API/app/core/MCP_unified/protocol.py -f json -o /tmp/bandit_mcp_hub_path_scope.json
```

Fix new findings in changed code before finishing.

**Step 3: Record deferred follow-ups**

Document any intentionally deferred work, especially:

- non-sandbox workspace-root resolution
- arbitrary path allowlists
- multi-root workspace support
- broader direct MCP/API caller support

**Step 4: Commit**

```bash
git add Docs/Plans/2026-03-10-mcp-hub-path-scoped-enforcement-design.md Docs/Plans/2026-03-10-mcp-hub-path-scoped-enforcement-implementation-plan.md
git commit -m "docs: finalize MCP Hub path-scoped enforcement plan"
```
