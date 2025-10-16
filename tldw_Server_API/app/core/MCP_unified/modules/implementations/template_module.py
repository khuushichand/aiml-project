"""
Template Module for Unified MCP

Use this as a starting point for new MCP modules.
"""

from typing import Dict, Any, List
from loguru import logger

from ..base import BaseModule, ModuleConfig, create_tool_definition


class TemplateModule(BaseModule):
    """Example module showing the minimal required interface"""

    async def on_initialize(self) -> None:
        # Initialize resources using self.config.settings
        logger.info(f"Initializing module: {self.name}")

    async def on_shutdown(self) -> None:
        # Cleanup resources
        logger.info(f"Shutting down module: {self.name}")

    async def check_health(self) -> Dict[str, bool]:
        # Keep checks quick and resilient
        return {"initialized": True, "dependencies_ok": True}

    async def get_tools(self) -> List[Dict[str, Any]]:
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

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], context: Any | None = None) -> Any:
        # Sanitize inputs and dispatch
        args = self.sanitize_input(arguments)
        if tool_name == "echo":
            return args.get("message", "")
        raise ValueError(f"Unknown tool: {tool_name}")
