# MCP Tool Catalogs - Quick Reference

Group tools into named catalogs so clients can discover a focused subset instead of thousands at once. Catalogs can be global, organization-scoped, or team-scoped.

## Discovery Filters
- HTTP: `GET /api/v1/mcp/tools?catalog=<name>` or `?catalog_id=<id>` (auth required)
- JSON-RPC: `tools/list` with `{ "catalog": "name" }` or `{ "catalog_id": 42 }`
- Name resolution precedence: team > org > global. When both provided, `catalog_id` takes precedence.
- Discovery responses include `canExecute` per tool. Catalog membership does not grant execute permissions - RBAC still applies.

### Examples
```bash
# By name (resolved with caller context)
curl -H "Authorization: Bearer <token>" \
  "http://127.0.0.1:8000/api/v1/mcp/tools?catalog=research"

# By id (explicit)
curl -H "Authorization: Bearer <token>" \
  "http://127.0.0.1:8000/api/v1/mcp/tools?catalog_id=42"
```

```json
// JSON-RPC
{
  "jsonrpc": "2.0",
  "method": "tools/list",
  "params": { "catalog": "research-kit" },
  "id": 1
}
```

## Managing Catalogs (Summary)
- Admin endpoints (global): create/list/delete catalogs; add/remove entries.
- Org and Team endpoints: allow managers (owner/admin/lead) to manage catalogs in their scope.

See full API and schema in the source docs: `Docs/MCP/mcp_tool_catalogs.md`.
