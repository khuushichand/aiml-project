# Adding New MCP Tools (Modules)

This guide explains how to add a new tool to the MCP Unified stack so it can be executed via the server-side tool executor (and from the Tools API). Tools are provided by MCP “modules”.

## Overview

- Implement a module class that extends `BaseModule` and lives under the allowed namespace:
  - `tldw_Server_API.app.core.MCP_unified.modules.implementations`
- Provide tool definitions via `get_tools()` with JSON-schema’d inputs.
- Implement `execute_tool(tool_name, arguments)` to run your logic.
- (For write tools) override `validate_tool_arguments` and mark your tool as write-capable via metadata or name heuristics.
- Register the module in `mcp_modules.yaml` and restart the server.

## Module Skeleton

```python
# tldw_Server_API/app/core/MCP_unified/modules/implementations/my_module.py
from __future__ import annotations
from typing import Any, Dict, List
from tldw_Server_API.app.core.MCP_unified.modules.base import BaseModule, ModuleConfig, create_tool_definition

class MyModule(BaseModule):
    async def on_initialize(self) -> None:
        # Perform any initialization (load models, open connections, etc.)
        pass

    async def check_health(self) -> Dict[str, bool]:
        # Return fine-grained checks
        return {"initialized": True}

    async def get_tools(self) -> List[Dict[str, Any]]:
        return [
            create_tool_definition(
                name="my.echo",
                description="Echo a message",
                parameters={
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                },
                metadata={"category": "read"},  # read|ingestion|management
            ),
            create_tool_definition(
                name="my.create_item",
                description="Create an item (write) with a required id",
                parameters={
                    "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
                    "required": ["id", "name"],
                },
                metadata={"category": "management"},  # treated as write-capable
            ),
        ]

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], context: Any = None) -> Any:
        if tool_name == "my.echo":
            return {"echo": str(arguments.get("message", ""))}
        if tool_name == "my.create_item":
            # Perform a write; honor idempotency using context if needed
            # Persist or call downstream systems safely
            return {"ok": True, "id": int(arguments["id"]) }
        raise ValueError(f"Unknown tool: {tool_name}")

    def validate_tool_arguments(self, tool_name: str, arguments: Dict[str, Any]):
        # Optional extra validation beyond JSON schema (enforced for write tools)
        if tool_name == "my.create_item":
            if int(arguments.get("id", -1)) < 0:
                raise ValueError("id must be non-negative")
```

Notes
- `metadata.category` influences write detection (`ingestion`/`management` are considered write).
- The base class provides `sanitize_input()` and `is_write_tool_def()` helpers.
- Concurrency/circuit breaker and per-call timeouts are handled by the base class.

## Registering the Module

Use `Config_Files/mcp_modules.yaml` (or env `MCP_MODULES`, see `Docs/MCP/Unified/Using_Modules_YAML.md`).

```yaml
modules:
  - id: my_module
    class: tldw_Server_API.app.core.MCP_unified.modules.implementations.my_module:MyModule
    enabled: true
    name: "My Module"
    version: "1.0.0"
    department: "lab"
    max_concurrent: 8
    # Module-specific settings are available as self.config.settings
    settings:
      greeting: "hello"
```

Restart the server. On startup, the MCP server loads modules from this YAML. The server only autoloads modules under `modules.implementations` for safety.

## Permissions (RBAC)

- The MCP protocol enforces per-tool permission `tools.execute:{tool_name}` (or wildcard) and module read permission.
- Grant via Admin RBAC endpoints/console. For quick testing, assign `tools.execute:*` to your role.
- The Tools API (`POST /api/v1/tools/execute`) also requires the endpoint-level `tools.execute:*` permission.

## Testing Your Tool

- List tools: `GET /api/v1/tools` - check your tool appears and `canExecute` is true.
- Dry-run validate: `POST /api/v1/tools/execute` with `{"tool_name":"my.echo","arguments":{"message":"hi"},"dry_run":true}`.
- Execute: `POST /api/v1/tools/execute` with arguments; observe the result.

## Write-Tool Safety

- To enable write tools in production, ensure your MCP policy allows them (see `Docs/MCP/Unified/System_Admin_Guide.md`).
- The protocol enforces:
  - optional JSON schema validation (`validate_input_schema`),
  - custom validator via `validate_tool_arguments`,
  - idempotency (pass `idempotency_key` via the Tools API when applicable),
  - rate limits and circuit breaker per module.

## Surfacing Results in Chat (optional)

If you later enable Chat auto-execution:
- Chat can call your tool through the server executor and record a `role=tool` message.
- The legacy WebUI now renders tool calls and tool results under assistant messages for transparency.

## References

- Base API: `tldw_Server_API/app/core/MCP_unified/modules/base.py`
- Module registry: `tldw_Server_API/app/core/MCP_unified/modules/registry.py`
- MCP protocol: `tldw_Server_API/app/core/MCP_unified/protocol.py`
- Tools API: `Docs/API-related/Tools_API_Documentation.md`
