"""
Lint/test gate: Write-capable tools must set metadata.category to 'ingestion' or 'management'.

This complements the validator override guard by ensuring module authors
explicitly categorize write tools for rate limiting and policy enforcement.
"""

import pytest

from tldw_Server_API.app.core.MCP_unified.modules.base import BaseModule, ModuleConfig
from tldw_Server_API.app.core.MCP_unified.modules.implementations.media_module import MediaModule
from tldw_Server_API.app.core.MCP_unified.modules.implementations.notes_module import NotesModule
from tldw_Server_API.app.core.MCP_unified.modules.implementations.prompts_module import PromptsModule
from tldw_Server_API.app.core.MCP_unified.modules.implementations.knowledge_module import KnowledgeModule
from tldw_Server_API.app.core.MCP_unified.modules.implementations.characters_module import CharactersModule
from tldw_Server_API.app.core.MCP_unified.modules.implementations.chats_module import ChatsModule
from tldw_Server_API.app.core.MCP_unified.modules.implementations.template_module import TemplateModule


@pytest.mark.asyncio
async def test_write_tools_have_ingestion_or_management_category():
    modules = [
        MediaModule(ModuleConfig(name="media")),
        NotesModule(ModuleConfig(name="notes")),
        PromptsModule(ModuleConfig(name="prompts")),
        KnowledgeModule(ModuleConfig(name="knowledge")),
        CharactersModule(ModuleConfig(name="characters")),
        ChatsModule(ModuleConfig(name="chats")),
        TemplateModule(ModuleConfig(name="template")),
    ]

    violations = []
    for mod in modules:
        tools = await mod.get_tools()
        for tool in tools:
            # Use shared helper to determine write-capable status
            if mod.is_write_tool_def(tool):
                meta = (tool.get("metadata") or {}) if isinstance(tool, dict) else {}
                category = str(meta.get("category") or "").lower()
                if category not in {"ingestion", "management"}:
                    violations.append((mod.name, tool.get("name"), category))

    assert not violations, (
        "Write-capable tools must set metadata.category to 'ingestion' or 'management':\n" +
        "\n".join(f"module={m}, tool={t}, category='{c or 'missing'}'" for m, t, c in violations)
    )
