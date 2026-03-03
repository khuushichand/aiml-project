# MCP Hub Management

MCP Hub is the shared management surface used by the WebUI and browser extension for MCP-related configuration.

## UI Routes

- `/mcp-hub`
- `/settings/mcp-hub`

Both routes render the same MCP Hub page and tabs.

## Scope

MCP Hub currently covers:

- ACP profile management
- External MCP server registry management
- Secret write/update for external servers (write-only reads)
- Tool catalog management via existing catalog endpoints (see `Docs/MCP/mcp_tool_catalogs.md`)

## Auth and Permissions

- All MCP Hub endpoints require an authenticated principal.
- Read/list endpoints are available to authenticated users.
- Mutation endpoints require admin role, `system.configure`, or wildcard `*` permission.

## API Endpoints

### ACP Profiles

- `GET /api/v1/mcp/hub/acp-profiles` - list profiles
- `POST /api/v1/mcp/hub/acp-profiles` - create profile
- `PUT /api/v1/mcp/hub/acp-profiles/{profile_id}` - update profile
- `DELETE /api/v1/mcp/hub/acp-profiles/{profile_id}` - delete profile

### External Servers

- `GET /api/v1/mcp/hub/external-servers` - list external servers
- `POST /api/v1/mcp/hub/external-servers` - create server
- `PUT /api/v1/mcp/hub/external-servers/{server_id}` - update server
- `DELETE /api/v1/mcp/hub/external-servers/{server_id}` - delete server
- `POST /api/v1/mcp/hub/external-servers/{server_id}/secret` - set or rotate secret

## Secret Handling

- Secrets are encrypted before persistence.
- Secret plaintext is not returned by read/list endpoints.
- API responses expose only metadata (`secret_configured`, optional `key_hint`, timestamps).

## Audit Events

MCP Hub mutation flows emit audit events, including:

- `mcp_hub.acp_profile.create|update|delete`
- `mcp_hub.external_server.create|update|delete`
- `mcp_hub.external_secret.update`
