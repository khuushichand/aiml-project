# MCP Hub Credential Slot Bindings Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add explicit named credential slots to managed MCP Hub external servers, migrate compatible one-secret servers safely, and make profile and assignment bindings slot-aware end-to-end.

**Architecture:** Introduce slot metadata and slot-secret storage alongside the current managed external server model, backfill default slots for compatible single-secret servers, evolve external access and runtime auth hydration to operate on `server + slot set`, then update MCP Hub APIs and UI to manage slot metadata, slot secrets, and slot-level bindings. Keep the current server-level secret path only as a temporary alias for migrated single-slot servers.

**Tech Stack:** FastAPI, AuthNZ SQLite/Postgres migrations, MCP Unified external federation runtime, React, Ant Design, pytest, Vitest, Bandit

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
- Task 9: Not started

### Task 1: Add failing tests for slot storage, slot-aware bindings, and auth templates

**Files:**
- Modify: `tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_auth_bridge.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_external_federation.py`
- Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_slot_access.py`

**Step 1: Write the failing repo tests**

Add tests that expect:

- unique slot name per server
- unique binding per `(target_type, target_id, server_id, slot_name)`
- profile bindings reject `disable`
- bindings reject unknown slots

**Step 2: Write the failing service/API tests**

Add tests that expect:

- managed servers can define slot metadata
- slot-secret configured state appears in responses
- effective external access is slot-aware
- server-level secret writes are rejected for ambiguous multi-slot servers

**Step 3: Write the failing runtime tests**

Add tests that expect:

- auth templates declare required slot names explicitly
- runtime hydration fails when required slots are missing or not granted
- default-slot migrated servers still hydrate through the alias path

**Step 4: Run the focused tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_auth_bridge.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_external_federation.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_slot_access.py \
  -k "slot or external" -v
```

Expected: FAIL.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_auth_bridge.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_external_federation.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_slot_access.py
git commit -m "test: add MCP Hub credential slot coverage"
```

### Task 2: Add slot tables, slot-secret storage, and binding migration scaffolding

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Modify: `tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py`
- Modify: `tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py`

**Step 1: Extend migration tests**

Add coverage for:

- `mcp_external_server_credential_slots`
- `mcp_external_server_slot_secrets`
- `slot_name` column on `mcp_credential_bindings`
- slot-level unique index

**Step 2: Implement additive migrations**

Add migrations that:

- create slot metadata table
- create slot-secret table
- add `slot_name` to bindings
- create slot-aware unique indexes
- preserve current server secret table during transition

**Step 3: Backfill default slot metadata for obvious single-secret servers**

Implement migration logic that:

- creates one default slot for simple managed auth modes
- leaves ambiguous servers unmigrated and non-executable until manually normalized

**Step 4: Run schema tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py \
  tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/AuthNZ/migrations.py \
  tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py \
  tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py \
  tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py
git commit -m "feat: add MCP Hub credential slot schema"
```

### Task 3: Add repo support for slot metadata, slot secrets, and slot-aware bindings

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py`
- Modify: `tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py`

**Step 1: Write the failing repo assertions**

Add tests for:

- slot CRUD
- slot secret set/get/clear
- binding CRUD with `slot_name`
- default-slot alias lookup for migrated servers

**Step 2: Implement minimal repo support**

Add helpers for:

- create/list/update/delete slot metadata
- set/get/clear slot secret
- list slots by server
- list bindings by target and slot
- detect default-slot compatibility for legacy server-secret alias

**Step 3: Keep server-secret reads transitional**

Implement repo reads so:

- slot-secret storage is authoritative when slots exist
- old server-secret storage is readable only for migrated single-slot compatibility

**Step 4: Run repo tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py
git commit -m "feat: add MCP Hub credential slot repo support"
```

### Task 4: Make managed auth hydration and runtime registry slot-aware

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_external_auth_service.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_external_registry_service.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/external_servers/config_schema.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_auth_bridge.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_external_federation.py`

**Step 1: Extend failing runtime tests**

Add tests that expect:

- auth template references explicit `required_slots`
- bearer and API-key templates hydrate from named slots
- unsupported templates fail closed

**Step 2: Implement managed auth template parsing**

Add explicit template handling for:

- `auth.mode`
- `auth.required_slots`
- `auth.slot_bindings`

Keep v1 to one auth template per server.

**Step 3: Implement slot-aware runtime hydration**

Hydrate headers only from:

- granted slot set
- configured slot secrets

Reject runtime execution if any required slot is absent.

**Step 4: Run runtime tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_auth_bridge.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_external_federation.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/services/mcp_hub_external_auth_service.py \
  tldw_Server_API/app/services/mcp_hub_external_registry_service.py \
  tldw_Server_API/app/core/MCP_unified/external_servers/config_schema.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_auth_bridge.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_external_federation.py
git commit -m "feat: add slot-aware managed auth templates"
```

### Task 5: Make effective external access and protocol gating slot-aware

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_external_access_resolver.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/protocol.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_approval_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_slot_access.py`

**Step 1: Write the failing slot-access tests**

Add tests that expect:

- server records include `slots[]`
- assignment disable applies to one slot without disabling every slot on the server
- approval scope includes slot identity when escalation occurs

**Step 2: Implement slot-aware resolution**

Change the resolver to return:

- server aggregate
- slot-level rows with `granted_by`, `disabled_by_assignment`, `secret_available`, `runtime_usable`, and `blocked_reason`

**Step 3: Update protocol gating**

Use slot-aware external access when deciding:

- allow
- block
- require approval

**Step 4: Run slot-access tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_slot_access.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/services/mcp_hub_external_access_resolver.py \
  tldw_Server_API/app/core/MCP_unified/protocol.py \
  tldw_Server_API/app/services/mcp_hub_approval_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_slot_access.py
git commit -m "feat: add slot-aware external access resolution"
```

### Task 6: Add service and API support for slot metadata, slot secrets, and slot bindings

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_service.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py`

**Step 1: Add failing API tests**

Add tests that expect:

- slot CRUD under managed external servers
- slot-secret set/clear routes
- profile slot bindings
- assignment slot grant/disable bindings
- deprecation behavior for server-level secret endpoint

**Step 2: Implement service methods**

Add service support for:

- create/update/delete slot metadata
- set/clear slot secrets
- list slot summaries by server
- resolve default-slot alias eligibility

**Step 3: Implement API routes**

Add nested routes such as:

- `GET /external-servers/{server_id}/credential-slots`
- `POST /external-servers/{server_id}/credential-slots`
- `PUT /external-servers/{server_id}/credential-slots/{slot_name}`
- `DELETE /external-servers/{server_id}/credential-slots/{slot_name}`
- `POST /external-servers/{server_id}/credential-slots/{slot_name}/secret`
- `DELETE /external-servers/{server_id}/credential-slots/{slot_name}/secret`

Also evolve binding routes to take `slot_name`.

**Step 4: Run service and API tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py -k "slot or external" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/services/mcp_hub_service.py \
  tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py
git commit -m "feat: add MCP Hub credential slot APIs"
```

### Task 7: Update the MCP Hub client types and helpers for slot-aware external access

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/mcp-hub.ts`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/policyHelpers.ts`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/policyHelpers.test.ts`

**Step 1: Add failing client/helper tests**

Add tests for:

- managed-slot filtering
- blocked-reason labels for slot-specific failures
- slot-aware effective external access typing

**Step 2: Update client DTOs and helpers**

Add types and client helpers for:

- slot metadata
- slot secret configured summaries
- slot-aware binding responses
- slot-aware effective external access

**Step 3: Run focused UI helper tests**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__/policyHelpers.test.ts
```

Expected: PASS.

**Step 4: Commit**

```bash
git add \
  apps/packages/ui/src/services/tldw/mcp-hub.ts \
  apps/packages/ui/src/components/Option/MCPHub/policyHelpers.ts \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/policyHelpers.test.ts
git commit -m "feat: add MCP Hub slot-aware client types"
```

### Task 8: Build the MCP Hub UI for slot management and slot-level bindings

**Files:**
- Modify: `apps/packages/ui/src/components/Option/MCPHub/ExternalServersTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PermissionProfilesTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PolicyAssignmentsTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PersonaPolicySummary.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/ExternalAccessSummary.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/ExternalServersTab.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PermissionProfilesTab.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PersonaPolicySummary.test.tsx`

**Step 1: Add failing UI tests**

Add tests that expect:

- managed server editor can define slots
- slot secret configured state is visible
- profile editor grants selected slots only
- assignment editor can inherit/grant/disable individual slots
- persona summary shows slot-specific access and blocked reasons

**Step 2: Implement UI changes**

Update:

- External Servers tab with `Credential Slots`
- profile binding card with grouped slot checkboxes
- assignment binding card with per-slot selects
- external access summary with slot-level details

**Step 3: Run focused UI tests**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/ExternalServersTab.test.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/PermissionProfilesTab.test.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/PersonaPolicySummary.test.tsx
```

Expected: PASS.

**Step 4: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/MCPHub/ExternalServersTab.tsx \
  apps/packages/ui/src/components/Option/MCPHub/PermissionProfilesTab.tsx \
  apps/packages/ui/src/components/Option/MCPHub/PolicyAssignmentsTab.tsx \
  apps/packages/ui/src/components/Option/MCPHub/PersonaPolicySummary.tsx \
  apps/packages/ui/src/components/Option/MCPHub/ExternalAccessSummary.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/ExternalServersTab.test.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/PermissionProfilesTab.test.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/PersonaPolicySummary.test.tsx
git commit -m "feat: add MCP Hub credential slot management UI"
```

### Task 9: Run verification, update docs, and prepare the branch for review

**Files:**
- Modify: any touched docs if naming or API details changed

**Step 1: Run backend verification**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py \
  tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py \
  tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_auth_bridge.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_external_federation.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_slot_access.py -v
```

Expected: PASS.

**Step 2: Run focused UI suite**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__
```

Expected: PASS.

**Step 3: Run external federation integration**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/app/core/MCP_unified/tests/test_external_federation_integration.py -v
```

Expected: PASS.

**Step 4: Run Bandit on touched backend scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/core/AuthNZ/migrations.py \
  tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py \
  tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  tldw_Server_API/app/services/mcp_hub_external_auth_service.py \
  tldw_Server_API/app/services/mcp_hub_external_registry_service.py \
  tldw_Server_API/app/services/mcp_hub_external_access_resolver.py \
  tldw_Server_API/app/services/mcp_hub_service.py \
  tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/app/core/MCP_unified/protocol.py \
  -f json -o /tmp/bandit_mcp_hub_slot_bindings.json
```

Expected: no new findings in changed code.

**Step 5: Commit final cleanup**

```bash
git add -A
git commit -m "test: verify MCP Hub credential slot bindings"
```
