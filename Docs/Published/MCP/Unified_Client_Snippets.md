# MCP Unified - Client Snippets

Quick examples to auth, initialize, discover tools, and call tools.

## Prerequisites
- MCP Unified served at `/api/v1/mcp`
- Auth token (preferred) or API key

## HTTP JSON-RPC
```bash
# Initialize (optional): returns mcp-session-id header
cfg=$(printf '{"snippet_length": 200}' | base64)
curl -i -H "Authorization: Bearer <token>" \
  "http://127.0.0.1:8000/api/v1/mcp/request?config=$cfg" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{"clientInfo":{"name":"demo"}},"id":1}'

# List tools (RBAC-filtered; add &catalog=... or &catalog_id=...)
curl -H "Authorization: Bearer <token>" \
  "http://127.0.0.1:8000/api/v1/mcp/tools"

# Execute tool (convenience endpoint)
curl -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"tool_name":"media.search","arguments":{"query":"test","limit":5}}' \
  http://127.0.0.1:8000/api/v1/mcp/tools/execute
```

## WebSocket (JS)
```javascript
const token = "<jwt>";
const ws = new WebSocket("ws://127.0.0.1:8000/api/v1/mcp/ws?client_id=demo", ["bearer", token]);
ws.onopen = () => {
  ws.send(JSON.stringify({ jsonrpc: "2.0", method: "initialize", params: { clientInfo: { name: "demo" } }, id: 1 }));
  ws.send(JSON.stringify({ jsonrpc: "2.0", method: "tools/list", id: 2 }));
  ws.send(JSON.stringify({ jsonrpc: "2.0", method: "tools/call", params: { name: "media.search", arguments: { query: "hello", limit: 3 } }, id: 3 }));
};
```

## Notes
- Discovery supports catalogs: `?catalog=name` or `?catalog_id=id`.
- `canExecute` reflects RBAC; catalogs don’t grant execution.
- Prefer WS headers/subprotocol for auth; query tokens are disabled by default.
