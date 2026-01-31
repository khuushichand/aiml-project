"""Knowledge management adapters.

This module includes adapters for knowledge CRUD operations:
- notes: Manage notes (create, get, list, update, delete, search)
- prompts: Manage prompts (get, list, create, update, search)
- collections: Manage collections
- chunking: Chunk text using various strategies
- claims_extract: Extract claims from text
- voice_intent: Voice intent detection
"""

from __future__ import annotations

from typing import Any, Dict

from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.knowledge._config import (
    ChunkingConfig,
    ClaimsExtractConfig,
    CollectionsConfig,
    NotesConfig,
    PromptsConfig,
    VoiceIntentConfig,
)


@registry.register(
    "notes",
    category="knowledge",
    description="Manage notes",
    parallelizable=True,
    tags=["knowledge", "notes"],
    config_model=NotesConfig,
)
async def run_notes_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Manage notes within a workflow step.

    Config:
      - action: Literal["create", "get", "list", "update", "delete", "search"]
      - note_id: Optional[str] (for get/update/delete)
      - title: Optional[str] (templated, for create/update)
      - content: Optional[str] (templated, for create/update)
      - query: Optional[str] (templated, for search)
      - limit: int = 100
      - offset: int = 0
      - expected_version: Optional[int] (for update/delete)
    Output:
      - {"note": {...}, "notes": [...], "success": bool}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_notes_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "prompts",
    category="knowledge",
    description="Manage prompts",
    parallelizable=True,
    tags=["knowledge", "prompts"],
    config_model=PromptsConfig,
)
async def run_prompts_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Manage prompts within a workflow step.

    Config:
      - action: Literal["get", "list", "create", "update", "search"]
      - prompt_id: Optional[int]
      - name: Optional[str] (templated)
      - content: Optional[str] (templated)
      - query: Optional[str] (templated, for search)
    Output:
      - {"prompt": {...}, "prompts": [...], "success": bool}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_prompts_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "collections",
    category="knowledge",
    description="Manage collections",
    parallelizable=True,
    tags=["knowledge", "collections"],
    config_model=CollectionsConfig,
)
async def run_collections_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Manage collections within a workflow step.

    Config:
      - action: Literal["create", "get", "list", "update", "delete", "add_items", "remove_items"]
      - collection_id: Optional[str]
      - name: Optional[str] (templated)
      - description: Optional[str] (templated)
      - item_ids: Optional[List[str]] (for add_items/remove_items)
    Output:
      - {"collection": {...}, "collections": [...], "success": bool}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_collections_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "chunking",
    category="knowledge",
    description="Chunk text content",
    parallelizable=True,
    tags=["knowledge", "chunking"],
    config_model=ChunkingConfig,
)
async def run_chunking_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Chunk text using various strategies.

    Config:
      - text: Optional[str] (templated, defaults to last.text or last.content)
      - method: Literal["words", "sentences", "tokens", "structure_aware", "fixed_size"] = "sentences"
      - max_size: int = 400
      - overlap: int = 50
      - language: Optional[str]
    Output:
      - {"chunks": [...], "count": int, "text": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_chunking_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "claims_extract",
    category="knowledge",
    description="Extract claims from text",
    parallelizable=True,
    tags=["knowledge", "extraction"],
    config_model=ClaimsExtractConfig,
)
async def run_claims_extract_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract factual claims from text.

    Config:
      - text: Optional[str] (templated, defaults to last.text)
      - provider: str - LLM provider
      - model: str - Model to use
      - max_claims: int (default: 10)
    Output:
      - {"claims": [...], "count": int}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_claims_extract_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "voice_intent",
    category="knowledge",
    description="Voice intent detection",
    parallelizable=False,
    tags=["knowledge", "voice"],
    config_model=VoiceIntentConfig,
)
async def run_voice_intent_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Detect intent from voice/text input.

    Config:
      - text: Optional[str] (templated)
      - intents: List[str] - Possible intents to match
      - provider: str - LLM provider
      - model: str - Model to use
    Output:
      - {"intent": str, "confidence": float, "parameters": {...}}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_voice_intent_adapter as _legacy
    return await _legacy(config, context)
