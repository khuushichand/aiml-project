"""Knowledge management adapters.

This module includes adapters for knowledge operations:
- notes: Manage notes
- prompts: Manage prompts
- collections: Manage collections
- chunking: Chunk text content
- claims_extract: Extract claims from text
- voice_intent: Voice intent detection
"""

from tldw_Server_API.app.core.Workflows.adapters.knowledge.crud import (
    run_notes_adapter,
    run_prompts_adapter,
    run_collections_adapter,
    run_chunking_adapter,
    run_claims_extract_adapter,
    run_voice_intent_adapter,
)

__all__ = [
    "run_notes_adapter",
    "run_prompts_adapter",
    "run_collections_adapter",
    "run_chunking_adapter",
    "run_claims_extract_adapter",
    "run_voice_intent_adapter",
]
