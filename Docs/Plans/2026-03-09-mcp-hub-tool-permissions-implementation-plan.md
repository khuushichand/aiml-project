## Stage 1: Policy Storage
**Goal**: Add durable MCP Hub storage for permission profiles and policy assignments.
**Success Criteria**: AuthNZ migrations create the new tables; PostgreSQL ensure path covers the same schema; repo CRUD exists for the new records.
**Tests**: `python -m pytest tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py -v`
**Status**: Complete

## Stage 2: CRUD API Surface
**Goal**: Expose permission profile and policy assignment list/create/update/delete endpoints with grant-authority checks and audit hooks.
**Success Criteria**: MCP Hub management routes support CRUD for both resource types; list routes apply visible-scope filtering; update routes preserve explicit null clearing semantics for nullable fields.
**Tests**: `python -m pytest tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py -v`
**Status**: Complete

## Stage 3: Effective Policy Resolver
**Goal**: Resolve effective MCP tool policy from default, group, persona, and override inputs.
**Success Criteria**: A resolver returns deterministic effective policy and denial/approval metadata from stored MCP Hub state without depending on ACP as the source of truth.
**Tests**: Resolver unit tests for merge order, scope handling, broadening checks, and deny precedence.
**Status**: Not Started

## Stage 4: Runtime Approval Models
**Goal**: Add approval policy storage and runtime elevation handling for MCP tool execution.
**Success Criteria**: Approval modes and temporary elevations can be persisted, resolved, and enforced at execution time with audit logging.
**Tests**: Integration tests for silent allow, approval-required flows, approval expiry, and denial behavior.
**Status**: Not Started

## Stage 5: UI Integration
**Goal**: Rebuild MCP Hub into the primary tool-governance editor and expose effective summaries in persona surfaces.
**Success Criteria**: MCP Hub supports profile editing, assignments, approvals, and credentials; persona UI shows linked policy summaries without owning tool policy.
**Tests**: Frontend component and route tests for profile editing, assignment previews, approval settings, and persona summary rendering.
**Status**: Not Started
