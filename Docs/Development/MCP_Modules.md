MCP Modules – Adding New Modules
================================

Overview
- Unified MCP supports pluggable modules that expose tools, resources, and prompts via a consistent interface.
- Modules subclass `BaseModule` and are auto-registered via YAML or environment variables.

Quick Start
- Implement a module under `tldw_Server_API/app/core/MCP_unified/modules/implementations/`.
- Add an entry to `tldw_Server_API/Config_Files/mcp_modules.yaml` (or set `MCP_MODULES`).
- Restart the server; verify with `GET /api/v1/mcp/modules` and `/api/v1/mcp/tools`.

Module Interface (Base)
- Required methods:
  - `on_initialize(self)` – setup resources using `self.config.settings`.
  - `on_shutdown(self)` – cleanup.
  - `check_health(self) -> Dict[str, bool]` – fast, resilient checks.
  - `get_tools(self) -> List[Dict[str, Any]]` – MCP tool definitions.
  - `execute_tool(self, tool_name, arguments)` – dispatch to tool logic.
- Optional: `get_resources`, `read_resource`, `get_prompts`, `get_prompt`.

Template Module
- See `modules/implementations/template_module.py` for a minimal example.

Configuration (YAML)
- File: `tldw_Server_API/Config_Files/mcp_modules.yaml`

```
modules:
  - id: media
    class: tldw_Server_API.app.core.MCP_unified.modules.implementations.media_module:MediaModule
    enabled: true
    name: Media
    version: "1.0.0"
    department: media
    timeout_seconds: 30
    max_retries: 3
    circuit_breaker_threshold: 5
    circuit_breaker_timeout: 60
    settings:
      db_path: ./Databases/Media_DB_v2.db
      cache_ttl: 300
```

Environment Variables
- `MCP_MODULES_CONFIG`: Path to YAML file (default: `tldw_Server_API/Config_Files/mcp_modules.yaml`).
- `MCP_MODULES`: Comma-separated `id=module.path:Class` list, e.g.
  - `MCP_MODULES="example=tldw_Server_API.app.core.MCP_unified.modules.implementations.template_module:TemplateModule"`
- Optional default for quick start:
  - `MCP_ENABLE_MEDIA_MODULE=true` registers `MediaModule` if no YAML/env entries are present.

Tool Execution Result
- Tool responses include the serving module name:
  - `{ "content": [...], "module": "Media", "tool": "search_media" }`
- The HTTP endpoint `/api/v1/mcp/tools/execute` returns the module in the response model.

Guidelines
- Keep health checks non-blocking and robust.
- Use `ModuleConfig.settings` for module-level configuration; avoid global config coupling.
- Validate and sanitize inputs (`sanitize_input()` exists in `BaseModule`).
- Favor fast failures and descriptive errors.

Testing
- Register a test module with `ModuleRegistry.register_module()`.
- Use `MCPRequest(method="tools/call", ...)` via `server.handle_http_request()` in tests.

Troubleshooting
- Check logs for module registration errors (class import or config issues).
- Ensure `PyYAML` is installed if using YAML configs.
- Verify tool names and input schemas match between `get_tools` and `execute_tool`.

