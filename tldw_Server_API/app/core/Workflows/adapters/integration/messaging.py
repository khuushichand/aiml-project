"""Messaging and app integration adapters.

This module includes adapters for application-specific integrations:
- kanban: Manage Kanban boards
- chatbooks: Manage chatbooks (export/import)
- character_chat: Chat with AI characters

Note: These adapters are complex with many inline helper functions.
They delegate to the legacy implementations for full functionality.
"""

from __future__ import annotations

from typing import Any, Dict

from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.integration._config import (
    KanbanConfig,
    ChatbooksConfig,
    CharacterChatConfig,
)


@registry.register(
    "kanban",
    category="integration",
    description="Manage Kanban boards",
    parallelizable=True,
    tags=["integration", "kanban"],
    config_model=KanbanConfig,
)
async def run_kanban_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Read/write Kanban boards, lists, and cards for workflow steps.

    Config:
      - action: str (required) e.g. board.list, board.create, list.create, card.update
      - entity ids: board_id, list_id, card_id
      - include flags: include_archived, include_deleted, include_details
      - create/update fields: name, description, title, metadata, activity_retention_days
      - card fields: due_date, start_date, due_complete, priority, position
      - move/copy: target_list_id, new_client_id, new_title, copy_checklists, copy_labels
      - search/filter: query, label_ids, priority, limit, offset
    Output: action-specific payload (board/list/card/etc.)
    """
    # This adapter is complex with many inline helpers. Delegate to legacy.
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_kanban_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "chatbooks",
    category="integration",
    description="Manage chatbooks",
    parallelizable=False,
    tags=["integration", "chatbooks"],
    config_model=ChatbooksConfig,
)
async def run_chatbooks_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Export and import chatbooks within a workflow step.

    Config:
      - action: Literal["export", "import", "list_jobs", "get_job", "preview"]
      - content_types: Optional[List[str]] (for export: "conversations", "notes", "prompts", "media")
      - name: Optional[str] (templated, for export)
      - description: Optional[str] (templated, for export)
      - file_path: Optional[str] (for import)
      - job_id: Optional[str] (for get_job)
    Output:
      - {"job_id": str, "status": str, "artifact_uri": str}
    """
    # This adapter is complex. Delegate to legacy.
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_chatbooks_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "character_chat",
    category="integration",
    description="Character chat",
    parallelizable=True,
    tags=["integration", "chat"],
    config_model=CharacterChatConfig,
)
async def run_character_chat_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Chat with AI characters using character cards within a workflow step.

    Config:
      - action: Literal["start", "message", "load"] (default: "message")
      - character_id: Optional[int] - for start
      - conversation_id: Optional[str] - for message/load
      - message: Optional[str] (templated) - for message action
      - api_name: Optional[str] - LLM provider
      - temperature: float = 0.8
      - user_name: Optional[str] - user display name for placeholders
    Output:
      - {"response": str, "conversation_id": str, "character_name": str, "turn_count": int}
    """
    # This adapter is complex. Delegate to legacy.
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_character_chat_adapter as _legacy
    return await _legacy(config, context)
