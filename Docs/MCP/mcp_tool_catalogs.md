## MCP Tool Catalogs — Minimal Design (v0.1)

Goal
- Introduce first-class, named tool catalogs to group MCP tools for discovery without breaking existing flows.
- Allow admin/org/team owners to create catalogs and entries; clients can request tools filtered by catalog.

Scope (Minimal Spike)
- Data model: two SQLite tables (AuthNZ DB) — `tool_catalogs` and `tool_catalog_entries`.
- Admin API: CRUD-lite endpoints to list/create/delete catalogs and manage entries.
- MCP: Extend `tools/list` to accept a `catalog` (name) or `catalog_id` filter.
- Backward compatible: if no catalog specified, behavior unchanged.

Data Model
- tool_catalogs
  - id INTEGER PK
  - name TEXT NOT NULL (unique per scope)
  - description TEXT NULL
  - org_id INTEGER NULL REFERENCES organizations(id) ON DELETE SET NULL
  - team_id INTEGER NULL REFERENCES teams(id) ON DELETE SET NULL
  - is_active INTEGER DEFAULT 1
  - created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  - updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  - UNIQUE(name, org_id, team_id)

- tool_catalog_entries
  - id INTEGER PK
  - catalog_id INTEGER NOT NULL REFERENCES tool_catalogs(id) ON DELETE CASCADE
  - tool_name TEXT NOT NULL
  - module_id TEXT NULL  (advisory; discovery uses module registry)
  - created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  - UNIQUE(catalog_id, tool_name)

Notes
- Scope precedence (for name lookup): team > org > global (NULL scope).
- Default deployment uses SQLite; Postgres DDL to be added to the project’s PG schema later.

API Changes
1) MCP tools list filter
   - HTTP: `GET /api/v1/mcp/tools?catalog=<name>` or `?catalog_id=<id>`
   - JSON-RPC: `tools/list` accepts params `{ catalog?: string, catalog_id?: number }`
   - Server filters returned tools to those present in the catalog after RBAC.

2) Admin endpoints (all require admin)
   - `GET  /api/v1/admin/mcp/tool_catalogs` — list catalogs (optional `org_id`, `team_id` filters)
   - `POST /api/v1/admin/mcp/tool_catalogs` — create catalog
   - `DELETE /api/v1/admin/mcp/tool_catalogs/{catalog_id}` — delete catalog (cascades entries)
   - `GET  /api/v1/admin/mcp/tool_catalogs/{catalog_id}/entries` — list entries
   - `POST /api/v1/admin/mcp/tool_catalogs/{catalog_id}/entries` — add entry `{ tool_name, module_id? }`
- `DELETE /api/v1/admin/mcp/tool_catalogs/{catalog_id}/entries/{tool_name}` — remove entry

3) Org/Team management endpoints (manager roles)
- Organization-scoped (requires org manager: owner/admin/lead, or global admin):
  - `GET  /api/v1/orgs/{org_id}/mcp/tool_catalogs` — list org catalogs
  - `POST /api/v1/orgs/{org_id}/mcp/tool_catalogs` — create org catalog
  - `POST /api/v1/orgs/{org_id}/mcp/tool_catalogs/{catalog_id}/entries` — add entry
  - `DELETE /api/v1/orgs/{org_id}/mcp/tool_catalogs/{catalog_id}/entries/{tool_name}` — remove entry
  - `DELETE /api/v1/orgs/{org_id}/mcp/tool_catalogs/{catalog_id}` — delete catalog (cascades entries)

- Team-scoped (requires team manager: owner/admin/lead, or global admin):
  - `GET  /api/v1/teams/{team_id}/mcp/tool_catalogs` — list team catalogs
  - `POST /api/v1/teams/{team_id}/mcp/tool_catalogs` — create team catalog
  - `POST /api/v1/teams/{team_id}/mcp/tool_catalogs/{catalog_id}/entries` — add entry
  - `DELETE /api/v1/teams/{team_id}/mcp/tool_catalogs/{catalog_id}/entries/{tool_name}` — remove entry
 - `DELETE /api/v1/teams/{team_id}/mcp/tool_catalogs/{catalog_id}` — delete catalog (cascades entries)

RBAC & Ownership
- Admin endpoints remain admin-only.
- New scoped endpoints require org/team manager roles (owner/admin/lead) or global admin; scope is enforced on all mutations and deletions.
- Execution remains governed by existing AuthNZ RBAC (e.g., `tools.execute:*`). Catalogs only shape discovery.

HTTP Usage Notes
- `GET /api/v1/mcp/tools` accepts catalog filters:
  - `catalog`: catalog name; resolved by precedence `team > org > global` using authenticated context
  - `catalog_id`: numeric id; takes precedence over `catalog` when both provided
- If the catalog name/id can’t be resolved, the server fails open (no catalog filter). RBAC is still enforced, and `canExecute` reflects effective permissions.

Migration
- Add migration 022 to AuthNZ migrations (SQLite) to create the two tables (with indexes/constraints above).
- Future: add Postgres DDL to `Databases/Postgres/Schema` and include in PG init path.

Backward Compatibility
- No change to default `tools/list` when `catalog` is omitted.
- Existing modules and tool discovery continue to work.

Success Criteria
- Can create a catalog, add tools, and list MCP tools filtered to that catalog.
- Works in default SQLite dev setup; does not break existing MCP flows.
