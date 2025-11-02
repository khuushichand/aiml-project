# MCP Unified - User Guide

> Part of the MCP Unified documentation set. See `Docs/MCP/Unified/README.md` for the full guide index.

## Table of Contents
1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Using the WebSocket Interface](#using-the-websocket-interface)
4. [Using the HTTP API](#using-the-http-api)
5. [Tool Discovery & Catalogs](#tool-discovery--catalogs)
6. [Available Tools](#available-tools)
7. [Authentication](#authentication)
8. [Examples](#examples)
9. [Troubleshooting](#troubleshooting)

## Overview

The Model Context Protocol (MCP) Unified module provides a standardized interface for interacting with TLDW's media processing, search, and analysis capabilities. It supports both WebSocket (for real-time communication) and HTTP (for simpler integrations).

### Key Features
- 🔍 **Media Search**: Search through ingested content
- 📝 **Transcription Access**: Retrieve and search transcripts
- 🤖 **AI Integration**: Leverage LLM capabilities for analysis
- 📊 **RAG Search**: Advanced retrieval-augmented generation
- 🔐 **Secure Access**: JWT-based authentication with role-based permissions

## Getting Started

### Prerequisites
- TLDW server running with MCP Unified module enabled
- API credentials (if authentication is enabled)
- WebSocket or HTTP client

### Quick Start

1. **Check Server Health**
   ```bash
   curl http://localhost:8000/api/v1/mcp/health
   ```
   Response: `{"status": "healthy"}`

2. **Authenticate and List Tools**
   Tools listing requires authentication. Use either a bearer token (AuthNZ or MCP demo token) or an API key.

   - Bearer token:
     ```bash
     curl -H "Authorization: Bearer <token>" \
       http://localhost:8000/api/v1/mcp/tools
     ```
   - Single-user API key:
     ```bash
     curl -H "X-API-KEY: <your_single_user_api_key>" \
       http://localhost:8000/api/v1/mcp/tools
     ```

## Using the WebSocket Interface

### Connection
Connect to the WebSocket endpoint:
```
ws://localhost:8000/api/v1/mcp/ws
```

Auth for WebSocket:
- Preferred: send `Authorization: Bearer <token>` (header) or use the subprotocol `bearer,<token>`.
- Query tokens (`?token=...` or `?api_key=...`) are disabled by default; enable only for legacy clients (`MCP_WS_ALLOW_QUERY_AUTH=1`).

Pass an optional `client_id` as a query parameter for observability.

### Example WebSocket Client (JavaScript)
```javascript
// Subprotocol-based auth: results in header "Sec-WebSocket-Protocol: bearer,<token>"
const token = "<jwt or access token>";
const ws = new WebSocket('ws://localhost:8000/api/v1/mcp/ws?client_id=my-app', ['bearer', token]);

ws.onopen = () => {
    // Initialize connection
    ws.send(JSON.stringify({
        jsonrpc: "2.0",
        method: "initialize",
        params: {
            clientInfo: {
                name: "My Application",
                version: "1.0.0"
            }
        },
        id: 1
    }));
};

ws.onmessage = (event) => {
    const response = JSON.parse(event.data);
    console.log('Received:', response);
};

// Call a tool
function callTool(toolName, args) {
    ws.send(JSON.stringify({
        jsonrpc: "2.0",
        method: "tools/call",
        params: {
            name: toolName,
            arguments: args
        },
        id: Date.now()
    }));
}
```

### Example WebSocket Client (Python)
```python
import websocket
import json

def on_message(ws, message):
    response = json.loads(message)
    print(f"Received: {response}")

def on_open(ws):
    # Initialize connection
    ws.send(json.dumps({
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "clientInfo": {
                "name": "Python Client",
                "version": "1.0.0"
            }
        },
        "id": 1
    }))

headers = ["Authorization: Bearer <token>"]
ws = websocket.WebSocketApp(
    "ws://localhost:8000/api/v1/mcp/ws",
    on_open=on_open,
    on_message=on_message,
    header=headers,
)
ws.run_forever()
```

## Using the HTTP API

### Basic Request Format
All HTTP requests use POST to `/api/v1/mcp/request`:

```bash
curl -X POST http://localhost:8000/api/v1/mcp/request \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "params": {},
    "id": 1
  }'
```

### Convenience Endpoints

#### List Tools
```bash
GET /api/v1/mcp/tools
```

Tips
- 403 without auth indicates RBAC is enforced; pass `Authorization` or `X-API-KEY`.
- Add `catalog` or `catalog_id` to filter discovery (see next section).

#### Execute Tool
```bash
POST /api/v1/mcp/tools/execute
{
    "tool_name": "media.search",
    "arguments": {
        "query": "machine learning",
        "limit": 10
    }
}
```

#### Server Status
```bash
GET /api/v1/mcp/status
```

## Available Tools

The exact tool set depends on enabled modules. Common examples include:

### Media
- `media.search` - full-text search over media content
- `media.get` - retrieve media content or snippet by id

Example
```json
{
  "tool_name": "media.search",
  "arguments": { "query": "your search query", "limit": 10 }
}
```

### Knowledge Tools (Unified)

#### knowledge.search
Unified FTS search across Notes, Media, Chats, Characters, and Prompts.
```json
{
  "tool_name": "knowledge.search",
  "arguments": {
    "query": "topic or question",
    "limit": 20,
    "sources": ["notes", "media", "chats", "characters", "prompts"],
    "snippet_length": 300,
    "filters": { "media": { "media_types": ["pdf", "html"], "order_by": "relevance" } }
  }
}
```

#### knowledge.get
Retrieve a specific item by source + id. Supports retrieval modes:
`snippet`, `full`, `chunk`, `chunk_with_siblings`, and `auto`.
```json
{
  "tool_name": "knowledge.get",
  "arguments": {
    "source": "media",
    "id": 123,
    "retrieval": { "mode": "chunk_with_siblings", "max_tokens": 6000, "chars_per_token": 4 }
  }
}
```

Notes:
- When prechunked media exists, `media.search` attempts to return a precise `loc` with `chunk_index`.
- `media.get` anchors by `chunk_index`/`chunk_uuid` when available and expands to sibling chunks under the token budget; otherwise it falls back to on-the-fly chunking.

## Authentication

### Getting a Token

Production: obtain an AuthNZ JWT via the primary AuthNZ flow (outside MCP), or use an API key.

Development/demo only: enable the MCP demo token endpoint, then request a token using the configured secret.
```bash
export MCP_ENABLE_DEMO_AUTH=1
export MCP_DEMO_AUTH_SECRET='<strong-secret>'

POST /api/v1/mcp/auth/token
{ "username": "admin", "password": "<strong-secret>" }
```

### Using the Token

#### WebSocket
Prefer header or subprotocol:
- Header: `Authorization: Bearer <token>`
- Subprotocol: `Sec-WebSocket-Protocol: bearer,<token>`

#### HTTP
Include in Authorization header:
```bash
curl -H "Authorization: Bearer eyJ..." \
  http://localhost:8000/api/v1/mcp/tools
```

## Examples

### Example 1: Search and Retrieve

```python
import requests
import json

# Search across knowledge sources
token = "<bearer token>"
base = "http://localhost:8000/api/v1/mcp/tools/execute"
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

resp = requests.post(
    base,
    headers=headers,
    json={
        "tool_name": "knowledge.search",
        "arguments": {"query": "artificial intelligence", "limit": 5}
    },
)
results = resp.json()["result"]["results"]
first = results[0]

# Retrieve full content for the first hit (source + id)
resp2 = requests.post(
    base,
    headers=headers,
    json={
        "tool_name": "knowledge.get",
        "arguments": {"source": first["source"], "id": first["id"], "retrieval": {"mode": "full"}}
    },
)
print(resp2.json()["result"])  # { meta, content, attachments }
```

### Example 2: Session Defaults via Safe Config

You can provide per-session defaults (e.g., snippet lengths) via a base64-encoded JSON config.

HTTP initialize with `mcp-session-id` negotiation and safe config:
```bash
cfg=$(printf '{"snippet_length": 200, "chars_per_token": 4}' | base64)
curl -i -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/mcp/request?config=$cfg" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{"clientInfo":{"name":"demo"}},"id":1}'
```
The response includes an `mcp-session-id` header. Reuse it on subsequent requests to apply the same safe config automatically.

## Troubleshooting

### Common Issues

#### Connection Refused
- **Check**: Is the server running?
- **Solution**: Start the server with MCP module enabled
- **Verify**: `curl http://localhost:8000/api/v1/mcp/health`

#### Authentication Failed
- **Check**: Are environment variables set?
- **Solution**: Set `MCP_JWT_SECRET` and `MCP_API_KEY_SALT`; ensure you pass `Authorization` or `X-API-KEY`.
- **Verify**: Check server logs for authentication errors

#### Tool Not Found
- **Check**: Is the module registered?
- **Solution**: Verify module initialization in server logs
- **List tools**: `GET /api/v1/mcp/tools`

#### Rate Limit Exceeded
- **Check**: Current rate limits
- **Solution**: Implement exponential backoff
- **Headers**: Check `X-RateLimit-Remaining` in response

### Debug Mode
Enable debug logging:
```bash
export MCP_LOG_LEVEL=DEBUG
```

### Support
- Check server logs for detailed error messages
- Review API documentation at `http://localhost:8000/docs`
- Consult the Developer Guide for advanced usage
## Tool Discovery & Catalogs

Large deployments can organize tools into named catalogs to avoid dumping thousands of tools at once. Discovery accepts a catalog filter; RBAC still gates execution.

- HTTP
  - By name (resolved with precedence team > org > global):
    ```bash
    curl -H "Authorization: Bearer <token>" \
      "http://localhost:8000/api/v1/mcp/tools?catalog=research"
    ```
  - By id (takes precedence over name):
    ```bash
    curl -H "Authorization: Bearer <token>" \
      "http://localhost:8000/api/v1/mcp/tools?catalog_id=42"
    ```

- JSON-RPC
  ```json
  {
    "jsonrpc": "2.0",
    "method": "tools/list",
    "params": { "catalog": "research" },
    "id": 1
  }
  ```

Results include `canExecute` per tool to reflect your effective permissions. See `Docs/MCP/mcp_tool_catalogs.md` for creating and managing catalogs (global, org, team).
