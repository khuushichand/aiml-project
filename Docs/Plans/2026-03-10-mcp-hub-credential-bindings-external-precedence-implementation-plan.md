# MCP Hub Credential Bindings And External-Server Precedence Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make MCP Hub the canonical executable source for external MCP servers, add server-level credential bindings for profiles and assignments, and relegate file/env-defined external servers to read-only migration inventory.

**Architecture:** Split external server handling into managed executable servers and legacy inventory-only discovery, add a managed auth hydration bridge from MCP Hub secret storage to runtime transport config, tighten the credential-binding schema for server-level grants and assignment disables, and expand MCP Hub UI to manage servers, imports, and bindings.

**Tech Stack:** FastAPI, MCP Unified external federation runtime, AuthNZ migrations/repo layer, React, Ant Design, pytest, Vitest, Bandit

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

### Task 1: Add failing tests for external server state, binding invariants, and managed auth hydration

**Files:**
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py`
- Modify: `tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py`
- Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_access.py`
- Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_auth_bridge.py`

**Step 1: Write failing repo tests**

Add tests that expect:

- unique binding per `(binding_target_type, binding_target_id, external_server_id)`
- `disable` bindings to be rejected for profile targets
- legacy or superseded servers to be rejected for new bindings

**Step 2: Write failing service/API tests**

Add tests that expect:

- external server responses to expose source-state fields
- import marks legacy rows as superseded
- effective external access shows profile grants and assignment disables

**Step 3: Write failing runtime auth tests**

Add tests that expect:

- managed bearer-token config hydrates auth from MCP Hub secret storage
- unsupported managed auth shapes fail closed

**Step 4: Run the focused tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_access.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_auth_bridge.py -k "external or binding" -v
```

Expected: FAIL.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_access.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_auth_bridge.py
git commit -m "test: add MCP Hub external binding coverage"
```

### Task 2: Tighten schema and repo support for managed/legacy server states and binding invariants

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py`
- Modify: `tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py`
- Modify: `tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py`
- Modify: `tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py`

**Step 1: Add migration coverage**

Extend schema tests to expect:

- `server_source`
- `legacy_source_ref`
- `superseded_by_server_id`
- `binding_mode`
- unique binding constraint on target plus server

**Step 2: Implement migration changes**

Add additive migrations for SQLite and Postgres that:

- extend `mcp_external_servers`
- tighten `mcp_credential_bindings`
- keep `credential_ref` as a reserved constant for v1

**Step 3: Implement repo support**

Add repo helpers for:

- create/update/list managed and legacy server rows
- import/supersede operations
- create/update/delete/list credential bindings
- effective binding lookup per profile and assignment

**Step 4: Run schema and repo tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/migrations.py tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py
git commit -m "feat: add MCP Hub external binding storage"
```

### Task 3: Add service and API support for legacy inventory, import, and binding CRUD

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_service.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py`

**Step 1: Add failing API tests**

Add tests that expect:

- external server responses to include source-state metadata
- `import legacy server` endpoint to create managed canonical rows
- binding endpoints for profiles and assignments
- cross-scope binding rejection for lower-scope private servers

**Step 2: Implement service logic**

Add service methods for:

- listing managed plus legacy inventory
- importing legacy entries
- upserting profile bindings
- upserting assignment bindings
- deleting bindings
- resolving effective external access summaries

**Step 3: Implement API endpoints**

Add or extend endpoints for:

- list external servers with source-state fields
- import legacy server to MCP Hub
- list/create/delete profile bindings
- list/create/delete assignment bindings

Keep mutation guards consistent with existing MCP Hub policy endpoints.

**Step 4: Run focused service and API tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py -k "external or binding or import" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/mcp_hub_service.py tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py
git commit -m "feat: add MCP Hub external binding APIs"
```

### Task 4: Add the managed auth hydration bridge and managed executable registry

**Files:**
- Create: `tldw_Server_API/app/services/mcp_hub_external_auth_service.py`
- Create: `tldw_Server_API/app/services/mcp_hub_external_registry_service.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/external_servers/config_schema.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/external_servers/manager.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/external_servers/transports/websocket_adapter.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_auth_bridge.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_external_federation.py`

**Step 1: Add failing runtime tests**

Add tests that expect:

- managed external registry loads DB-backed servers only
- legacy inventory rows do not become executable adapters
- managed bearer/API-key auth is hydrated from MCP Hub secret storage
- unsupported managed auth shapes fail closed

**Step 2: Implement managed auth hydration**

Add a focused service that:

- reads the encrypted secret payload
- decrypts it using the existing BYOK helpers
- hydrates supported auth shapes for runtime use

**Step 3: Implement managed executable registry**

Add a registry/service that:

- loads managed DB-backed server definitions
- excludes legacy and superseded rows
- builds runtime config objects for the external federation manager

**Step 4: Run runtime tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_auth_bridge.py tldw_Server_API/tests/MCP_unified/test_mcp_protocol_external_federation.py -k "managed or external" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/mcp_hub_external_auth_service.py tldw_Server_API/app/services/mcp_hub_external_registry_service.py tldw_Server_API/app/core/MCP_unified/external_servers/config_schema.py tldw_Server_API/app/core/MCP_unified/external_servers/manager.py tldw_Server_API/app/core/MCP_unified/external_servers/transports/websocket_adapter.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_auth_bridge.py tldw_Server_API/tests/MCP_unified/test_mcp_protocol_external_federation.py
git commit -m "feat: add managed MCP Hub external runtime registry"
```

### Task 5: Rework legacy discovery into inventory-only import data

**Files:**
- Modify: `tldw_Server_API/app/core/MCP_unified/modules/implementations/external_federation_module.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/external_servers/manager.py`
- Create: `tldw_Server_API/app/services/mcp_hub_external_legacy_inventory.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_external_federation.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py`

**Step 1: Add failing precedence tests**

Add tests that expect:

- file/env servers still appear in MCP Hub inventory
- file/env-only servers do not become executable runtime tools
- imported managed rows with the same `server_id` take precedence cleanly

**Step 2: Implement legacy inventory discovery**

Add a small service that parses file/env registry config and emits read-only
inventory rows for MCP Hub without registering them as executable runtime tools.

**Step 3: Rewire the module**

Update the external federation module so executable runtime discovery comes from the
managed registry, not directly from `MCP_EXTERNAL_SERVERS_CONFIG`.

**Step 4: Run the precedence tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_protocol_external_federation.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py -k "legacy or superseded or import" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/MCP_unified/modules/implementations/external_federation_module.py tldw_Server_API/app/core/MCP_unified/external_servers/manager.py tldw_Server_API/app/services/mcp_hub_external_legacy_inventory.py tldw_Server_API/tests/MCP_unified/test_mcp_protocol_external_federation.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py
git commit -m "feat: split legacy inventory from external runtime execution"
```

### Task 6: Add effective external-access resolution and persona/profile summaries

**Files:**
- Create: `tldw_Server_API/app/services/mcp_hub_external_access_resolver.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_policy_resolver.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_access.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py`

**Step 1: Add failing resolver tests**

Add tests that expect:

- profile grants appear in effective external access
- assignment `grant` adds to inherited access
- assignment `disable` removes inherited access
- missing secrets or external capability gating mark a server unavailable with a reason

**Step 2: Implement resolver support**

Add external-access summary resolution that combines:

- effective tool/capability policy
- binding state
- managed/superseded state
- secret availability

**Step 3: Run the focused resolver tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_access.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py -k "external_access or binding" -v
```

Expected: PASS.

**Step 4: Commit**

```bash
git add tldw_Server_API/app/services/mcp_hub_external_access_resolver.py tldw_Server_API/app/services/mcp_hub_policy_resolver.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_access.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py
git commit -m "feat: add MCP Hub effective external access summaries"
```

### Task 7: Build the MCP Hub UI for external servers, import, and bindings

**Files:**
- Modify: `apps/packages/ui/src/components/Option/MCPHub/ExternalServersTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PermissionProfilesTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PolicyAssignmentsTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PersonaPolicySummary.tsx`
- Modify: `apps/packages/ui/src/services/tldw/mcp-hub.ts`
- Create: `apps/packages/ui/src/components/Option/MCPHub/__tests__/externalServersTab.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/policyHelpers.test.ts`

**Step 1: Add failing UI tests**

Add tests that expect:

- External Servers tab shows managed, legacy, and superseded states
- legacy rows expose `Import to MCP Hub`
- bindings in profile and assignment editors exclude legacy rows
- summaries explain blocked reasons such as missing secret or disabled by assignment

**Step 2: Implement client DTO updates**

Extend the MCP Hub client with:

- external server source-state fields
- import action
- binding CRUD helpers
- effective external-access summary types

**Step 3: Implement UI changes**

Update the tab and editors to support:

- full managed server CRUD
- secret set/clear
- import flow
- profile binding editor
- assignment binding editor with disable state
- effective summary rendering

**Step 4: Run the focused UI tests**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__/externalServersTab.test.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/policyHelpers.test.ts
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/MCPHub/ExternalServersTab.tsx apps/packages/ui/src/components/Option/MCPHub/PermissionProfilesTab.tsx apps/packages/ui/src/components/Option/MCPHub/PolicyAssignmentsTab.tsx apps/packages/ui/src/components/Option/MCPHub/PersonaPolicySummary.tsx apps/packages/ui/src/services/tldw/mcp-hub.ts apps/packages/ui/src/components/Option/MCPHub/__tests__/externalServersTab.test.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/policyHelpers.test.ts
git commit -m "feat: add MCP Hub external binding management UI"
```

### Task 8: Run verification, update docs, and prepare the branch for review

**Files:**
- Modify: `Docs/Plans/2026-03-10-mcp-hub-credential-bindings-external-precedence-design.md`
- Modify: `Docs/Plans/2026-03-10-mcp-hub-credential-bindings-external-precedence-implementation-plan.md`
- Modify: any touched documentation files if API/UI names changed during implementation

**Step 1: Run the focused backend test suite**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_access.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_auth_bridge.py tldw_Server_API/tests/MCP_unified/test_mcp_protocol_external_federation.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py -v
```

Expected: PASS.

**Step 2: Run the focused UI test suite**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__
```

Expected: PASS.

**Step 3: Run Bandit on touched backend files**

Run:

```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py tldw_Server_API/app/services/mcp_hub_service.py tldw_Server_API/app/services/mcp_hub_external_auth_service.py tldw_Server_API/app/services/mcp_hub_external_registry_service.py tldw_Server_API/app/services/mcp_hub_external_legacy_inventory.py tldw_Server_API/app/services/mcp_hub_external_access_resolver.py tldw_Server_API/app/core/MCP_unified/modules/implementations/external_federation_module.py tldw_Server_API/app/core/MCP_unified/external_servers/manager.py tldw_Server_API/app/core/MCP_unified/external_servers/transports/websocket_adapter.py -f json -o /tmp/bandit_mcp_hub_external_bindings.json
```

Expected: `0` new findings in changed code.

**Step 4: Update the plan statuses**

Mark completed tasks and note any follow-up work left out of scope, such as:

- per-secret slot bindings
- automatic env secret import
- broader transport auth support

**Step 5: Commit**

```bash
git add Docs/Plans/2026-03-10-mcp-hub-credential-bindings-external-precedence-design.md Docs/Plans/2026-03-10-mcp-hub-credential-bindings-external-precedence-implementation-plan.md
git commit -m "docs: record MCP Hub external binding verification"
```
