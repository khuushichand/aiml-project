# MCP Hub Managed Auth Template Editor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a first-class managed auth template editor for MCP Hub external servers, compile template mappings into parser-compatible transport config, and make server readiness/status template-aware for websocket and stdio transports.

**Architecture:** Extend managed external server config with a single structured auth-template mapping model, validate and compile those mappings into `websocket.headers` or `stdio.env` before runtime parser/adapter construction, then expose template presence/validity through MCP Hub APIs and the external-server UI. Keep legacy alias-based server secrets only as transitional fallback for managed servers without a template.

**Tech Stack:** FastAPI, AuthNZ SQLite/Postgres persistence, MCP Unified external federation runtime, React, Ant Design, pytest, Vitest, Bandit

---

## Status

- Task 1: Not started
- Task 2: Not started
- Task 3: Not started
- Task 4: Not started
- Task 5: Not started
- Task 6: Not started
- Task 7: Not started
- Task 8: Not started

### Task 1: Add failing tests for managed auth-template validation and compilation

**Files:**
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_auth_bridge.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_external_federation.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py`
- Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_auth_template_status.py`

**Step 1: Write failing bridge/runtime tests**

Add tests that expect:

- websocket header mappings compile from slot values
- stdio env mappings compile from slot values
- duplicate `(target_type, target_name)` mappings are rejected
- required mappings fail when slot grant or slot secret is missing

**Step 2: Write failing service/API tests**

Add tests that expect:

- external server responses expose `auth_template_present`
- external server responses expose `auth_template_valid`
- external server responses expose `auth_template_blocked_reason`
- auth-template update endpoints round-trip correctly

**Step 3: Run the focused tests to confirm failure**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_auth_bridge.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_external_federation.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_auth_template_status.py \
  -k "template or auth" -v
```

Expected: FAIL.

**Step 4: Commit**

```bash
git add \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_auth_bridge.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_external_federation.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_auth_template_status.py
git commit -m "test: add MCP Hub auth template coverage"
```

### Task 2: Add auth-template schema and managed config validation

**Files:**
- Modify: `tldw_Server_API/app/core/MCP_unified/external_servers/config_schema.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py`

**Step 1: Add managed auth-template schema models**

Define typed request/response models for:

- template mapping rows
- auth-template update payload
- external server template status fields

**Step 2: Extend external server config validation**

Add schema-level validation for:

- supported `target_type`
- non-empty `target_name`
- valid `slot_name`
- unique `(target_type, target_name)`

**Step 3: Run targeted schema/API tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py \
  -k "template or external_server" -v
```

Expected: PASS once implemented.

**Step 4: Commit**

```bash
git add \
  tldw_Server_API/app/core/MCP_unified/external_servers/config_schema.py \
  tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py
git commit -m "feat: add MCP Hub managed auth template schema"
```

### Task 3: Make auth bridge compile headers and env from template mappings

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_external_auth_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_auth_bridge.py`

**Step 1: Write minimal template compilation logic**

Implement bridge behavior that:

- reads template mappings from managed config
- derives required-slot set from mappings where `required=true`
- applies prefix/suffix formatting
- returns:
  - `headers`
  - `env`

**Step 2: Enforce strict validation**

Fail with clear errors for:

- missing slot references
- duplicate targets
- unsupported target types
- required slot secret missing

**Step 3: Run bridge tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_auth_bridge.py -v
```

Expected: PASS.

**Step 4: Commit**

```bash
git add \
  tldw_Server_API/app/services/mcp_hub_external_auth_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_auth_bridge.py
git commit -m "feat: compile MCP Hub auth templates"
```

### Task 4: Compile auth templates into runtime transport config

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_external_registry_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_external_federation.py`

**Step 1: Update runtime registry compilation**

Compile template output into:

- `websocket.headers`
- `stdio.env`

Then force parser-facing auth mode to `none`.

**Step 2: Add strict precedence**

Implement:

- if template exists, template compilation wins
- old default-slot alias fallback is ignored once a template exists

**Step 3: Run runtime registry tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_external_federation.py -v
```

Expected: PASS.

**Step 4: Commit**

```bash
git add \
  tldw_Server_API/app/services/mcp_hub_external_registry_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_external_federation.py
git commit -m "feat: compile MCP Hub auth templates into runtime config"
```

### Task 5: Add service/API support for template CRUD and readiness status

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py`
- Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_auth_template_status.py`

**Step 1: Add template-aware server summary helpers**

Implement service-level readiness reporting:

- `auth_template_present`
- `auth_template_valid`
- `auth_template_blocked_reason`

**Step 2: Add MCP Hub endpoints**

Add or extend routes for:

- get/update managed server auth template
- returning server list/detail rows with template status

**Step 3: Map status reasons consistently**

Use a small stable reason set:

- `no_auth_template`
- `auth_template_invalid`
- `required_slot_not_granted`
- `required_slot_secret_missing`
- `unsupported_template_transport_target`

**Step 4: Run service/API tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_auth_template_status.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/services/mcp_hub_service.py \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_auth_template_status.py
git commit -m "feat: add MCP Hub auth template API"
```

### Task 6: Update MCP Hub client types and server editor UI

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/mcp-hub.ts`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/ExternalServersTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/policyHelpers.ts`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/ExternalServersTab.test.tsx`

**Step 1: Extend client types**

Add UI types for:

- auth template mappings
- auth template update payloads
- auth template status fields on external servers

**Step 2: Add guided auth-template editor**

In `ExternalServersTab.tsx`, add:

- transport-aware mapping editor
- slot picker
- target type/name editor
- prefix/suffix fields
- required toggle

**Step 3: Show readiness in the server list**

Add list/status badges for:

- No auth template
- Template valid
- Template invalid
- Missing required slot secret

**Step 4: Run focused UI tests**

Run:

```bash
bunx vitest run \
  src/components/Option/MCPHub/__tests__/ExternalServersTab.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/services/tldw/mcp-hub.ts \
  apps/packages/ui/src/components/Option/MCPHub/ExternalServersTab.tsx \
  apps/packages/ui/src/components/Option/MCPHub/policyHelpers.ts \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/ExternalServersTab.test.tsx
git commit -m "feat: add MCP Hub auth template editor"
```

### Task 7: Run full verification and Bandit

**Files:**
- Modify if needed based on failures in touched files only

**Step 1: Run backend verification**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_auth_bridge.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_external_federation.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_auth_template_status.py -v
```

Expected: PASS.

**Step 2: Run UI verification**

Run:

```bash
bunx vitest run src/components/Option/MCPHub/__tests__
```

Expected: PASS.

**Step 3: Run Bandit on the touched backend scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/core/MCP_unified/external_servers/config_schema.py \
  tldw_Server_API/app/services/mcp_hub_external_auth_service.py \
  tldw_Server_API/app/services/mcp_hub_external_registry_service.py \
  tldw_Server_API/app/services/mcp_hub_service.py \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py
```

Expected: No new findings.

**Step 4: Commit any required follow-up fixes**

```bash
git add <touched files>
git commit -m "fix: polish MCP Hub auth template flow"
```

### Task 8: Update plan status, summarize, and prepare branch for review

**Files:**
- Modify: `Docs/Plans/2026-03-10-mcp-hub-managed-auth-template-editor-implementation-plan.md`
- Modify if needed: `Docs/Plans/2026-03-10-mcp-hub-managed-auth-template-editor-design.md`

**Step 1: Mark completed tasks in the plan**

Update the status list so the plan reflects implementation reality.

**Step 2: Re-run `git status --short`**

Run:

```bash
git status --short
```

Expected: clean worktree or only intentional doc updates.

**Step 3: Prepare the branch for review**

If implementation is complete, move to code review / PR creation flow.

**Step 4: Commit the final doc status update**

```bash
git add \
  Docs/Plans/2026-03-10-mcp-hub-managed-auth-template-editor-implementation-plan.md \
  Docs/Plans/2026-03-10-mcp-hub-managed-auth-template-editor-design.md
git commit -m "docs: update MCP Hub auth template plan status"
```
