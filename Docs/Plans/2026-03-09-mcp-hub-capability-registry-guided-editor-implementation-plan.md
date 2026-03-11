# MCP Hub Capability Registry And Guided Editor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a derived MCP Hub tool capability registry, enrich the Catalog tab with registry metadata, and ship a registry-backed guided policy editor without introducing a second source of truth for tool metadata.

**Architecture:** Build a server-side registry read service that normalizes MCP tool definitions into a canonical DTO, expose it through MCP Hub APIs, and use that DTO in both the Catalog tab and new simple-mode policy authoring. Keep advanced/manual policy editing intact and add round-trip guards so unsupported policy shapes are not silently flattened.

**Tech Stack:** FastAPI, Pydantic, existing MCP Unified tool-definition metadata, React, Ant Design, Vitest, pytest

---

### Task 1: Add the failing backend tests for the derived registry

**Files:**
- Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_tool_registry.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py`

**Step 1: Write the failing registry normalization tests**

Add tests that cover:

- explicit metadata normalization for a built-in tool
- conservative fallback for a tool with incomplete metadata
- module grouping output
- risk class derivation for execution and management tools

Include concrete assertions for:

- `tool_name`
- `module`
- `risk_class`
- `capabilities`
- `metadata_source`
- `metadata_warnings`

**Step 2: Run the backend registry tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_tool_registry.py -v
```

Expected:

- failure because the registry service does not exist yet

**Step 3: Write the failing API tests for registry-backed catalog output**

Extend the MCP Hub policy API tests to assert that catalog/registry endpoints return normalized metadata fields used by the UI.

**Step 4: Run the API tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py -k registry -v
```

Expected:

- failure because the endpoint/schema additions do not exist yet

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/MCP_unified/test_mcp_hub_tool_registry.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py
git commit -m "test: add MCP Hub tool registry coverage"
```

### Task 2: Implement the derived registry service and schemas

**Files:**
- Create: `tldw_Server_API/app/services/mcp_hub_tool_registry.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/modules/base.py`

**Step 1: Implement minimal registry service**

Add a read service that:

- enumerates MCP tool definitions
- normalizes tool metadata into a canonical DTO
- applies conservative fallback classification
- groups entries by module

**Step 2: Add registry response schemas**

Add Pydantic models for:

- registry entry
- registry module group
- registry listing response

**Step 3: Normalize existing tool metadata instead of inventing a new store**

Use existing tool definition metadata and helper heuristics from MCP Unified base code. Only add normalization helpers required to make the registry output stable and explicit.

**Step 4: Run the registry tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_tool_registry.py -v
```

Expected:

- pass

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/mcp_hub_tool_registry.py tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py tldw_Server_API/app/core/MCP_unified/modules/base.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_tool_registry.py
git commit -m "feat: add MCP Hub tool capability registry"
```

### Task 3: Expose registry-backed MCP Hub APIs and enrich catalog output

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py`

**Step 1: Add read endpoints for registry data**

Add endpoints for:

- listing registry entries
- listing grouped modules
- returning enriched catalog data used by MCP Hub

Do not add write endpoints for registry editing.

**Step 2: Keep the DTO shared**

Make sure the Catalog tab and the upcoming simple-mode editor can both use the same response shape without separate transformation logic.

**Step 3: Run focused API tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py -v
```

Expected:

- pass

**Step 4: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py tldw_Server_API/app/services/mcp_hub_service.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py
git commit -m "feat: expose MCP Hub tool registry APIs"
```

### Task 4: Add failing frontend tests for the guided editor and enriched catalog

**Files:**
- Create: `apps/packages/ui/src/components/Option/MCPHub/__tests__/ToolCatalogsTab.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PermissionProfilesTab.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx`
- Modify: `apps/packages/ui/src/services/tldw/mcp-hub.ts`

**Step 1: Add failing catalog tests**

Write tests asserting the Catalog tab renders:

- module labels
- risk badges
- capability tags
- warning state for unclassified tools

**Step 2: Add failing simple-mode editor tests**

Write tests asserting:

- simple-mode controls generate the expected policy document
- built-in presets use registry-backed mappings
- advanced-fields-present blocks destructive simple-mode rewriting

**Step 3: Run the frontend tests to verify they fail**

Run from `apps/packages/ui`:

```bash
bunx vitest run src/components/Option/MCPHub/__tests__/ToolCatalogsTab.test.tsx src/components/Option/MCPHub/__tests__/PermissionProfilesTab.test.tsx src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx
```

Expected:

- failures because the registry-backed UI and DTOs are not implemented yet

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Option/MCPHub/__tests__/ToolCatalogsTab.test.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/PermissionProfilesTab.test.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx apps/packages/ui/src/services/tldw/mcp-hub.ts
git commit -m "test: add guided MCP Hub editor coverage"
```

### Task 5: Implement registry-backed Catalog tab and shared frontend DTOs

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/mcp-hub.ts`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/ToolCatalogsTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/index.tsx`

**Step 1: Add typed client support for registry endpoints**

Define client types for registry entries and module groups. Add API functions for fetching enriched catalog data.

**Step 2: Replace the current thin catalog rendering**

Update the Catalog tab to render:

- module/group organization
- risk badge
- capability chips
- warnings for inferred or incomplete metadata

**Step 3: Run catalog tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/Option/MCPHub/__tests__/ToolCatalogsTab.test.tsx
```

Expected:

- pass

**Step 4: Commit**

```bash
git add apps/packages/ui/src/services/tldw/mcp-hub.ts apps/packages/ui/src/components/Option/MCPHub/ToolCatalogsTab.tsx apps/packages/ui/src/components/Option/MCPHub/index.tsx
git commit -m "feat: enrich MCP Hub catalog with registry metadata"
```

### Task 6: Implement guided simple mode for permission profiles

**Files:**
- Modify: `apps/packages/ui/src/components/Option/MCPHub/policyHelpers.ts`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PermissionProfilesTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PermissionProfilesTab.test.tsx`

**Step 1: Replace hardcoded capability-only authoring with shared simple-mode helpers**

Add helpers that:

- map simple-mode toggles to policy documents
- generate built-in preset payloads from registry metadata
- detect advanced-only policy fields that cannot round-trip safely

**Step 2: Update the profile editor**

Add:

- simple mode as the default
- advanced mode as an opt-in
- warning state when advanced fields are present

Do not remove raw editing support.

**Step 3: Run the profile editor tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/Option/MCPHub/__tests__/PermissionProfilesTab.test.tsx
```

Expected:

- pass

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Option/MCPHub/policyHelpers.ts apps/packages/ui/src/components/Option/MCPHub/PermissionProfilesTab.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/PermissionProfilesTab.test.tsx
git commit -m "feat: add guided MCP Hub profile editor"
```

### Task 7: Implement guided simple mode for policy assignments

**Files:**
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PolicyAssignmentsTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx`
- Modify: `apps/packages/ui/src/services/tldw/mcp-hub.ts`

**Step 1: Reuse the same simple-mode generation model in assignments**

Assignments should support:

- referencing a profile
- manual simple-mode configuration
- advanced/manual fallback when needed

**Step 2: Keep effective preview intact**

Do not rebuild the effective preview into provenance mode yet. This PR only needs the guided editor.

**Step 3: Run the assignment tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx
```

Expected:

- pass

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Option/MCPHub/PolicyAssignmentsTab.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx apps/packages/ui/src/services/tldw/mcp-hub.ts
git commit -m "feat: add guided MCP Hub assignment editor"
```

### Task 8: Align runtime sensitivity checks with the registry where safe

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_approval_service.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/protocol.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_approval_service.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/tests/test_protocol_allowed_tools.py`

**Step 1: Replace ad hoc sensitivity decisions only where the registry already has stable data**

Use registry-backed `risk_class` and normalized capability hints to support `ask_on_sensitive_actions`.

Do not replace existing `allowed_tools` execution gates.

**Step 2: Add parity tests**

Add tests proving:

- sensitive tools trigger approval based on registry risk class
- unknown/unclassified tools fail conservatively where intended

**Step 3: Run the focused backend tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_approval_service.py tldw_Server_API/app/core/MCP_unified/tests/test_protocol_allowed_tools.py -v
```

Expected:

- pass

**Step 4: Commit**

```bash
git add tldw_Server_API/app/services/mcp_hub_approval_service.py tldw_Server_API/app/core/MCP_unified/protocol.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_approval_service.py tldw_Server_API/app/core/MCP_unified/tests/test_protocol_allowed_tools.py
git commit -m "feat: align MCP approvals with tool registry risk"
```

### Task 9: Run full verification and security validation

**Files:**
- No new files

**Step 1: Run the backend verification suite**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_tool_registry.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_approval_service.py tldw_Server_API/app/core/MCP_unified/tests/test_protocol_allowed_tools.py -v
```

Expected:

- all tests pass

**Step 2: Run the focused frontend verification suite**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/Option/MCPHub/__tests__/ToolCatalogsTab.test.tsx src/components/Option/MCPHub/__tests__/PermissionProfilesTab.test.tsx src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx
```

Expected:

- all tests pass

**Step 3: Run Bandit on touched backend files**

Run:

```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/services/mcp_hub_tool_registry.py tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py tldw_Server_API/app/services/mcp_hub_approval_service.py tldw_Server_API/app/core/MCP_unified/protocol.py -f json -o /tmp/bandit_mcp_hub_registry.json
```

Expected:

- zero new findings in touched code

**Step 4: Commit the final verification-only changes if needed**

```bash
git add <any updated test snapshots or touched files>
git commit -m "test: verify MCP Hub registry-guided editor flow"
```

### Task 10: Update docs and PR summary

**Files:**
- Modify: `Docs/Plans/2026-03-09-mcp-hub-capability-registry-guided-editor-design.md`
- Modify: `README.md` or relevant MCP Hub docs only if the implementation changes user-visible setup

**Step 1: Update design doc status notes**

Record any implementation deviations needed to stay aligned with runtime enforcement reality.

**Step 2: Prepare PR summary**

Summarize:

- new registry service
- catalog enrichment
- guided editor
- runtime sensitivity alignment
- known deferred items

**Step 3: Commit docs**

```bash
git add Docs/Plans/2026-03-09-mcp-hub-capability-registry-guided-editor-design.md README.md
git commit -m "docs: summarize MCP Hub capability registry rollout"
```

---

Plan complete and saved to `Docs/Plans/2026-03-09-mcp-hub-capability-registry-guided-editor-implementation-plan.md`. Two execution options:

1. Subagent-Driven (this session) - I dispatch fresh subagent per task, review between tasks, fast iteration
2. Parallel Session (separate) - Open new session with executing-plans, batch execution with checkpoints

Which approach?
