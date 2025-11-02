VS Code Sandbox Extension (Stub)
================================

This is a minimal stub extension for triggering sandbox runs from VS Code, per the PRD. It wires a command that posts to the server's `/api/v1/sandbox/runs` endpoint and opens an output channel for logs.

Status: Stub - not published, build scripts omitted. Use as a starting point.

Configuration
- `tldw.sandbox.serverUrl` - Base URL (e.g., http://127.0.0.1:8000)
- `tldw.sandbox.apiKey` - X-API-KEY (single-user) or Bearer token for multi-user

Commands
- `tldw.sandbox.run` - Prompts for a command array and optional base image, then POSTs to `/sandbox/runs`.

Notes
- For live logs, the extension can connect to `WS /api/v1/sandbox/runs/{id}/stream` (not implemented in stub).
- For MCP integration, use the `sandbox.run` tool via the MCP Unified module.
