# __init__.py
"""
Chunking module for text processing and segmentation.
Provides various strategies for splitting text into manageable chunks.
"""

from .base import (
    ChunkingMethod,
    ChunkMetadata,
    ChunkResult,
    ChunkerConfig,
    BaseChunkingStrategy,
)

from .exceptions import (
    ChunkingError,
    InvalidInputError,
    InvalidChunkingMethodError,
    TokenizerError,
    TemplateError,
    LanguageNotSupportedError,
    ChunkSizeError,
    ProcessingError,
    ConfigurationError,
    CacheError,
)

from .chunker import (
    Chunker,
    create_chunker,
)
from .constants import FRONTMATTER_SENTINEL_KEY

# Default chunking options for backward compatibility
DEFAULT_CHUNK_OPTIONS = {
    'method': 'words',
    'max_size': 400,
    'overlap': 200,
    'language': 'en',
    'adaptive': False,
    'multi_level': False,
    'semantic_similarity_threshold': 0.7,
    'semantic_overlap_sentences': 2,
    'json_chunkable_data_key': 'data',
    'summarization_detail': 0.5,
    'tokenizer_name_or_path': 'gpt2',
    'enable_frontmatter_parsing': True,
    'frontmatter_sentinel_key': FRONTMATTER_SENTINEL_KEY,
    # Proposition-specific defaults
    'proposition_engine': 'heuristic',  # 'heuristic' | 'spacy' | 'llm' | 'auto'
    'proposition_aggressiveness': 1,
    'proposition_min_proposition_length': 15,
    'proposition_prompt_profile': 'generic',  # 'generic' | 'claimify' | 'gemma_aps'
}

# Override defaults from system config if available (system-level toggles)
try:
    from tldw_Server_API.app.core.config import load_and_log_configs
    _cfg = load_and_log_configs()
    if isinstance(_cfg, dict):
        _c = _cfg.get('chunking_config', {}) or {}
        if isinstance(_c, dict):
            DEFAULT_CHUNK_OPTIONS['proposition_engine'] = _c.get('proposition_engine', DEFAULT_CHUNK_OPTIONS['proposition_engine'])
            DEFAULT_CHUNK_OPTIONS['proposition_prompt_profile'] = _c.get('proposition_prompt_profile', DEFAULT_CHUNK_OPTIONS['proposition_prompt_profile'])
            try:
                DEFAULT_CHUNK_OPTIONS['proposition_aggressiveness'] = int(_c.get('proposition_aggressiveness', DEFAULT_CHUNK_OPTIONS['proposition_aggressiveness']))
            except Exception:
                pass
            try:
                DEFAULT_CHUNK_OPTIONS['proposition_min_proposition_length'] = int(_c.get('proposition_min_proposition_length', DEFAULT_CHUNK_OPTIONS['proposition_min_proposition_length']))
            except Exception:
                pass
except Exception:
    # Config not available; keep in-module defaults
    pass

# For backward compatibility with existing code
# These will be implemented as we port more functionality
def improved_chunking_process(text: str,
                             chunk_options: dict = None,
                             tokenizer_name_or_path: str = None,
                             llm_call_func = None,
                             llm_api_config: dict = None) -> list:
    """
    Backward compatibility function for improved chunking process.

    Args:
        text: Text to chunk
        chunk_options: Dictionary of chunking options
        tokenizer_name_or_path: Optional tokenizer (not used in new API)
        llm_call_func: Optional LLM function for methods like rolling_summarize
        llm_api_config: Optional LLM configuration

    Returns:
        List of chunk dictionaries with text and metadata
    """
    options = chunk_options or {}

    # Extract options
    method = options.get('method', 'words')
    max_size = options.get('max_size', 400)
    overlap = options.get('overlap', 200)
    language = options.get('language', 'en')
    code_mode = str(options.get('code_mode', 'auto')).lower() if str(method).lower() == 'code' else None

    # Create chunker with LLM support if provided
    chunker = Chunker(llm_call_func=llm_call_func, llm_config=llm_api_config)
    # Remove duplicates from options
    filtered_options = {k: v for k, v in options.items()
                       if k not in ['method', 'max_size', 'overlap', 'language']}
    chunks = chunker.chunk_text_with_metadata(
        text=text,
        method=method,
        max_size=max_size,
        overlap=overlap,
        language=language,
        **filtered_options
    )

    # Convert to expected format
    result = []
    for chunk in chunks:
        result.append({
            'text': chunk.text,
            'metadata': {
                'index': chunk.metadata.index,
                'start_index': chunk.metadata.start_char,
                'end_index': chunk.metadata.end_char,
                'word_count': chunk.metadata.word_count,
                'language': chunk.metadata.language,
                # Standardized keys for consistency across endpoints
                'chunk_method': method,
                'max_size': max_size,
                'overlap': overlap,
                **({'code_mode_used': code_mode} if code_mode is not None else {}),
            }
        })

    return result


def chunk_for_embedding(text: str, file_name: str, **kwargs) -> list:
    """
    Backward compatibility function for chunking for embeddings.

    Args:
        text: Text to chunk
        file_name: Name of the file being processed
        **kwargs: Additional options

    Returns:
        List of chunk dictionaries suitable for embedding
    """
    # Create chunker with embedding-optimized settings
    chunker = Chunker()

    # Use semantic chunking if available, otherwise sentences
    method = kwargs.get('method', 'sentences')
    max_size = kwargs.get('max_size', 512)  # Good size for embeddings
    overlap = kwargs.get('overlap', 50)

    # Remove duplicates from kwargs
    filtered_kwargs = {k: v for k, v in kwargs.items()
                      if k not in ['method', 'max_size', 'overlap']}

    chunks = chunker.chunk_text_with_metadata(
        text=text,
        method=method,
        max_size=max_size,
        overlap=overlap,
        **filtered_kwargs
    )

    # Format for embedding
    result = []
    import hashlib as _hashlib
    for chunk in chunks:
        # Stable chunk UID constructed from file name, offsets, and content hash
        try:
            start_c = getattr(chunk.metadata, 'start_char', None)
        except Exception:
            start_c = None
        try:
            end_c = getattr(chunk.metadata, 'end_char', None)
        except Exception:
            end_c = None
        txt = chunk.text
        content_sig = _hashlib.sha1((txt or '').encode('utf-8')).hexdigest()[:12]
        file_sig = _hashlib.md5((file_name or '').encode('utf-8')).hexdigest()[:8]
        chunk_uid = f"ck_{file_sig}_{start_c if start_c is not None else 's'}_{end_c if end_c is not None else 'e'}_{content_sig}"
        # Fielded metadata
        try:
            # Prefer v2 Chunker fields when present
            ancestry_titles = list(getattr(chunk.metadata, 'ancestry_titles', []) or [])
        except Exception:
            ancestry_titles = []
        headings = ancestry_titles if isinstance(ancestry_titles, list) else []
        # Basic captions placeholder (can be filled by upstream parsers)
        captions = []
        result.append({
            'text': chunk.text,
            'text_for_embedding': f"File: {file_name}\n{chunk.text}",
            'metadata': {
                'file_name': file_name,
                'chunk_index': chunk.metadata.index,
                'start_char': chunk.metadata.start_char,
                'end_char': chunk.metadata.end_char,
                'chunk_uid': chunk_uid,
                # Structured/fielded metadata for indexing/boosting
                'headings': headings,
                'captions': captions,
            }
        })

    return result


# Public helper to flatten hierarchical trees (legacy or v2-bridged)
def flatten_hierarchical(tree: dict) -> list:
    """Flatten a hierarchical chunk tree to a list of {'text','metadata'}.

    Uses the v2 chunker implementation; failures return an empty list.
    """
    try:
        return Chunker().flatten_hierarchical(tree)
    except Exception:
        return []


# Enhanced chunk support for RAG integration
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from enum import Enum


class ChunkType(Enum):
    """Enumeration of chunk types for structure-aware chunking."""
    TEXT = "text"
    PARAGRAPH = "paragraph"
    CODE = "code"
    TABLE = "table"
    HEADER = "header"
    LIST = "list"
    QUOTE = "quote"
    METADATA = "metadata"


@dataclass
class EnhancedChunk:
    """Enhanced chunk with type and position tracking for RAG."""
    id: str
    content: str
    chunk_type: ChunkType
    start_char: int  # Position in original document
    end_char: int    # Position in original document
    chunk_index: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "chunk_type": self.chunk_type.value if isinstance(self.chunk_type, Enum) else self.chunk_type,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "chunk_index": self.chunk_index,
            "metadata": self.metadata,
            "parent_id": self.parent_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnhancedChunk':
        """Create from dictionary."""
        chunk_type = data.get("chunk_type", "text")
        if isinstance(chunk_type, str):
            try:
                chunk_type = ChunkType(chunk_type)
            except ValueError:
                chunk_type = ChunkType.TEXT

        return cls(
            id=data["id"],
            content=data["content"],
            chunk_type=chunk_type,
            start_char=data.get("start_char", 0),
            end_char=data.get("end_char", len(data["content"])),
            chunk_index=data.get("chunk_index", 0),
            metadata=data.get("metadata", {}),
            parent_id=data.get("parent_id")
        )


__all__ = [
    # Main classes
    'Chunker',
    'create_chunker',

    # Configuration
    'ChunkerConfig',
    'ChunkingMethod',

    # Results
    'ChunkResult',
    'ChunkMetadata',

    # Exceptions
    'ChunkingError',
    'InvalidInputError',
    'InvalidChunkingMethodError',
    'TokenizerError',
    'TemplateError',
    'LanguageNotSupportedError',
    'ChunkSizeError',
    'ProcessingError',
    'ConfigurationError',
    'CacheError',

    # Backward compatibility
    'improved_chunking_process',
    'chunk_for_embedding',
    'EnhancedChunk',
    'ChunkType',

    # Base classes for extensions
    'BaseChunkingStrategy',
]

__version__ = '2.0.0'
