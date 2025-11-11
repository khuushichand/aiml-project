"""
chat_commands_schemas.py

Pydantic schemas for the Chat Commands discovery endpoint.
"""
from __future__ import annotations

from typing import List
from pydantic import BaseModel, Field


class ChatCommandInfo(BaseModel):
    """Represents a single slash command available to the user."""
    name: str = Field(..., description="Command name without the leading slash")
    description: str = Field(..., description="Brief description of what the command does")
    required_permission: str | None = Field(
        None,
        description="Permission required to invoke this command when RBAC enforcement is enabled",
    )


class ChatCommandsListResponse(BaseModel):
    """Container for a list of available chat commands."""
    commands: List[ChatCommandInfo] = Field(..., description="List of available commands")
