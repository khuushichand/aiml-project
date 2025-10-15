# MCP Unified Modules Guide

> Part of the MCP Unified documentation set. See `Docs/MCP/Unified/README.md` for the full guide index.

## Overview

- Unified MCP exposes tools, resources, and prompts through pluggable modules.
- Each module subclasses `BaseModule` and is registered through YAML configuration or environment variables.

## Quick Start

1. Implement the module under `tldw_Server_API/app/core/MCP_unified/modules/implementations/`.
2. Add a module entry to `tldw_Server_API/Config_Files/mcp_modules.yaml` (or define `MCP_MODULES`).
3. Restart the server and verify availability with `GET /api/v1/mcp/modules` and `/api/v1/mcp/tools`.

## Module Interface

### Required methods

- `on_initialize(self)` – set up resources using `self.config.settings`.
- `on_shutdown(self)` – release or persist resources.
- `check_health(self) -> Dict[str, bool]` – resilient health probes.
- `get_tools(self) -> List[Dict[str, Any]]` – JSON schema describing the module tools.
- `execute_tool(self, tool_name, arguments)` – dispatch execution logic.

### Optional helpers

- `get_resources`, `read_resource`
- `get_prompts`, `get_prompt`

## Template Module

- Review `modules/implementations/template_module.py` for a minimal implementation pattern.

## Configuration (YAML)

- Default file: `tldw_Server_API/Config_Files/mcp_modules.yaml`

```yaml
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

## Environment Variables

- `MCP_MODULES_CONFIG` – override path to the YAML configuration (defaults to `tldw_Server_API/Config_Files/mcp_modules.yaml`).
- `MCP_MODULES` – comma-separated definitions (`id=module.path:Class`), e.g. `MCP_MODULES="example=tldw_Server_API.app.core.MCP_unified.modules.implementations.template_module:TemplateModule"`.
- Optional accelerator: `MCP_ENABLE_MEDIA_MODULE=true` registers `MediaModule` when no YAML or explicit environment configuration is provided.

## Tool Execution Result

- Tool responses include module metadata, e.g. `{ "content": [...], "module": "Media", "tool": "search_media" }`.
- The HTTP endpoint `/api/v1/mcp/tools/execute` returns the module name in the response model.

## Guidelines

- Keep health checks non-blocking and degrade gracefully.
- Store module-level settings in `ModuleConfig.settings`; avoid global config coupling.
- Sanitize inputs with `sanitize_input()` provided on `BaseModule`.
- Prefer fast failures with descriptive error reporting.

## Testing

- Register a test module via `ModuleRegistry.register_module()`.
- Exercise flows with `MCPRequest(method="tools/call", ...)` routed through `server.handle_http_request()`.

## Troubleshooting

- Inspect logs when module registration fails (class import or configuration issues).
- Ensure `PyYAML` is installed when using YAML configurations.
- Confirm tool names and input schemas match between `get_tools` and `execute_tool`.
