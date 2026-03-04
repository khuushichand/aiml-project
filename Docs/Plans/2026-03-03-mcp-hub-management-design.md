# MCP Hub Management Design (WebUI + Extension)

Date: 2026-03-03  
Status: Approved (brainstorming complete)

## 1. Summary

Design a unified MCP management hub shared by WebUI and extension. The hub provides full CRUD management for:

1. ACP MCP server profiles (reusable session presets)
2. MCP tool catalogs and entries
3. External federation MCP servers (including secret-backed auth)

The page is visible to all authenticated users, but all actions are authorized server-side with claim/RBAC enforcement. Secrets are direct-input, encrypted at rest, and write-only on read paths.

## 2. Goals

1. Provide one operational control plane for MCP-related setup, replacing manual file/DB edits.
2. Preserve strong safety/compliance guarantees through RBAC, secure secret handling, and audit logging.
3. Reuse existing shared UI route/component architecture so WebUI and extension behave consistently.

## 3. Non-Goals (v1)

1. Human approval workflows for configuration mutations.
2. Secret reveal/export functionality after save.
3. Reworking existing MCP runtime execution semantics; this design focuses on management/control surfaces.

## 4. Confirmed Product Decisions

1. Scope mode: unified hub with tabs for all three domains.
2. Visibility: all authenticated users can access page; permission errors handled in-line.
3. Capability depth: full CRUD across all tabs.
4. Secret UX: direct secret input allowed.
5. Routes: expose the same hub at both `/mcp-hub` and `/settings/mcp-hub`.
6. ACP server setup model: reusable profiles (not session-only editing).
7. Persistence: database-backed config service for external federation server definitions.
8. Secret read policy: write-only retrieval (never return plaintext once stored).
9. v1 success focus: operational control + safety/compliance.

## 5. Architecture

### 5.1 UI Architecture

1. Implement `McpHubPage` in `apps/packages/ui` so both WebUI and extension consume the same feature.
2. Register two entry routes:
   - Workspace route: `/mcp-hub`
   - Settings route: `/settings/mcp-hub`
3. Render a single three-tab layout:
   - `ACP Profiles`
   - `Tool Catalogs`
   - `External Servers`

### 5.2 Backend Architecture

1. Add a DB-backed MCP management control plane for ACP profiles + external server registry.
2. Reuse existing catalog management endpoints where possible for tool catalog CRUD.
3. Add orchestration endpoints for status/test actions where existing APIs are insufficient.
4. Treat backend authorization as source of truth; UI never assumes permission.

### 5.3 Security/Crypto Architecture

1. Reuse existing BYOK envelope encryption helpers for external-server secret storage.
2. Store only encrypted secret blobs in DB.
3. Return masked/key-hint metadata only on read.
4. Emit audit events for all mutations and connectivity tests.

## 6. Component Design

### 6.1 `McpHubPage`

Responsibilities:

1. Tab shell, route-context title/breadcrumb logic.
2. Initial capability/context load.
3. Shared error/status rail for operations.

### 6.2 `AcpProfilesTab`

Responsibilities:

1. List/create/update/delete reusable ACP MCP server profiles.
2. Manage profile payload of one-or-more server definitions (`websocket` and `stdio`).
3. Surface profile references intended for ACP session-create integration.

### 6.3 `ToolCatalogsTab`

Responsibilities:

1. Scope-aware management (`global`, `org`, `team`) based on user visibility.
2. Catalog CRUD and entry CRUD.
3. Claim-aware disabled states and clear authorization failure feedback.

### 6.4 `ExternalServersTab`

Responsibilities:

1. Full CRUD for external federation server definitions:
   - transport
   - policy
   - timeout/retry/circuit-breaker
2. Secret write/replace operations (never reveal stored secret).
3. Connectivity/discovery test action with normalized result classes.

### 6.5 Shared Utility Components

1. `CapabilityGuard` wrappers for action-level gating and messaging.
2. `OperationStatusRail` for save/test/sync lifecycle feedback.

## 7. Data Model (Proposed)

### 7.1 ACP Profile Tables

1. `mcp_acp_profiles`
   - `id`
   - `name`
   - `description`
   - `owner_scope_type` (`user|org|team|global`)
   - `owner_scope_id`
   - `created_by`
   - `updated_by`
   - `created_at`
   - `updated_at`
2. `mcp_acp_profile_servers`
   - `id`
   - `profile_id` FK
   - `server_name`
   - `transport_type`
   - `config_json` (non-secret connection/server details)
   - `sort_order`

### 7.2 External Server Tables

1. `mcp_external_servers`
   - `id` (stable server identifier)
   - `name`
   - `enabled`
   - `transport_type`
   - `config_json` (non-secret transport/policy/timeouts/retries/circuit-breaker)
   - `owner_scope_type`
   - `owner_scope_id`
   - `created_by`
   - `updated_by`
   - `created_at`
   - `updated_at`
2. `mcp_external_server_secrets`
   - `server_id` FK
   - `encrypted_blob`
   - `key_hint`
   - `updated_by`
   - `updated_at`

### 7.3 Catalog Data

1. Reuse existing tool catalog schema/endpoints.
2. No v1 schema rework required beyond existing scope model.

## 8. API Surface (Proposed)

### 8.1 ACP Profiles

1. `GET /api/v1/mcp/hub/acp-profiles`
2. `POST /api/v1/mcp/hub/acp-profiles`
3. `PATCH /api/v1/mcp/hub/acp-profiles/{profile_id}`
4. `DELETE /api/v1/mcp/hub/acp-profiles/{profile_id}`

### 8.2 External Servers

1. `GET /api/v1/mcp/hub/external-servers`
2. `POST /api/v1/mcp/hub/external-servers`
3. `PATCH /api/v1/mcp/hub/external-servers/{server_id}`
4. `DELETE /api/v1/mcp/hub/external-servers/{server_id}`
5. `POST /api/v1/mcp/hub/external-servers/{server_id}/secret`
6. `POST /api/v1/mcp/hub/external-servers/{server_id}/test`

### 8.3 Tool Catalogs

1. Reuse:
   - `/api/v1/mcp/tool_catalogs`
   - `/api/v1/orgs/{org_id}/mcp/tool_catalogs*`
   - `/api/v1/teams/{team_id}/mcp/tool_catalogs*`
2. Hub UI acts as a scope-aware frontend over this existing surface.

## 9. Permissions Model

1. Page-level access: authenticated users can load hub.
2. Action-level access: enforced per endpoint via existing claim/RBAC dependencies.
3. UI behavior on deny:
   - keep page visible
   - disable or roll back denied action
   - show required permission hint when available

## 10. Error Handling

1. `400/422`: field-level validation mapping in forms.
2. `403`: in-line permission guidance, no silent failures.
3. `404`: scoped not-found responses (especially org/team catalog ownership checks).
4. `409`: duplicate/conflict handling with rename/retry hints.
5. External test failures normalized into:
   - auth failed
   - network/connectivity failed
   - protocol/handshake failed
   - discovery failed

## 11. Testing Plan

### 11.1 Backend

1. Unit tests for ACP profile services/repos.
2. Unit tests for external server validation/serialization logic.
3. Secret handling tests proving no plaintext on read responses/log payloads.
4. Authorization tests for all mutation endpoints.
5. Integration tests covering successful CRUD + denial/error cases.

### 11.2 Frontend

1. Route tests for both `/mcp-hub` and `/settings/mcp-hub`.
2. Tab/form behavior tests for all three tabs.
3. Permission-denied UX tests.
4. Secret lifecycle tests (set/replace, no reveal).

### 11.3 Security Verification

1. Bandit run on touched backend paths before completion.
2. Audit event assertion tests for mutation/test actions.

## 12. Rollout Notes

1. Add route as beta-labeled navigation item initially.
2. Keep fallback messaging if federation runtime is unavailable.
3. Integrate ACP profile selection into session-create flow in follow-up implementation stage.

## 13. Acceptance Criteria

1. Authenticated users can open MCP Hub from both routes.
2. Authorized users can perform full CRUD on ACP profiles, catalogs, and external servers.
3. External server secrets are accepted, encrypted, and never returned in plaintext.
4. Audit records exist for create/update/delete/test operations.
5. WebUI and extension show equivalent behavior using shared UI components.

