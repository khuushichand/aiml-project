"""
Template Module for Unified MCP

Use this as a starting point for new MCP modules.
"""

from typing import Any

from loguru import logger

from ..base import BaseModule, create_tool_definition


class TemplateModule(BaseModule):
    """Example module showing the minimal required interface"""

    async def on_initialize(self) -> None:
        # Initialize resources using self.config.settings
        logger.info(f"Initializing module: {self.name}")

    async def on_shutdown(self) -> None:
        # Cleanup resources
        logger.info(f"Shutting down module: {self.name}")

    async def check_health(self) -> dict[str, bool]:
        # Keep checks quick and resilient
        return {"initialized": True, "dependencies_ok": True}

    async def get_tools(self) -> list[dict[str, Any]]:
        # Define tools with JSON Schema input definitions
        return [
            create_tool_definition(
                name="echo",
                description="Echoes the provided message",
                parameters={
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                },
                metadata={"category": "utility", "auth_required": False},
            ),
        ]

    async def execute_tool(self, tool_name: str, arguments: dict[str, Any], context: Any | None = None) -> Any:
        # Sanitize inputs and dispatch
        args = self.sanitize_input(arguments)
        if tool_name == "echo":
            return args.get("message", "")
        raise ValueError(f"Unknown tool: {tool_name}")
