# base.py
"""
Base classes and protocols for the chunking system.
Provides abstract interfaces and common functionality for all chunking strategies.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Protocol, Union, Generator
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class ChunkingMethod(Enum):
    """Enumeration of available chunking methods."""
    WORDS = "words"
    SENTENCES = "sentences"
    PARAGRAPHS = "paragraphs"
    PROPOSITIONS = "propositions"
    TOKENS = "tokens"
    SEMANTIC = "semantic"
    JSON = "json"
    XML = "xml"
    EBOOK_CHAPTERS = "ebook_chapters"
    ROLLING_SUMMARIZE = "rolling_summarize"
    FIXED_SIZE = "fixed_size"
    CODE = "code"
    STRUCTURE_AWARE = "structure_aware"


@dataclass
class ChunkMetadata:
    """Metadata for a text chunk."""
    index: int
    start_char: int
    end_char: int
    word_count: int
    token_count: Optional[int] = None
    section: Optional[str] = None
    language: Optional[str] = None
    overlap_with_previous: int = 0
    overlap_with_next: int = 0
    char_count: Optional[int] = None  # Add for compatibility
    sentence_count: Optional[int] = None  # Add for compatibility
    method: Optional[str] = None  # Add chunking method used
    options: Optional[Dict[str, Any]] = field(default=None)  # Add options used

    def __post_init__(self):
        """Calculate derived fields if not provided."""
        if self.char_count is None and self.end_char is not None and self.start_char is not None:
            self.char_count = self.end_char - self.start_char


@dataclass
class ChunkResult:
    """Result of a chunking operation."""
    text: str
    metadata: ChunkMetadata


class ChunkingStrategy(Protocol):
    """Protocol for chunking strategies."""

    def chunk(self,
              text: str,
              max_size: int,
              overlap: int = 0,
              **options) -> List[str]:
        """
        Chunk text according to the strategy.

        Args:
            text: Text to chunk
            max_size: Maximum size of each chunk
            overlap: Overlap between chunks
            **options: Strategy-specific options

        Returns:
            List of text chunks
        """
        ...

    def chunk_with_metadata(self,
                           text: str,
                           max_size: int,
                           overlap: int = 0,
                           **options) -> List[ChunkResult]:
        """
        Chunk text and return with metadata.

        Args:
            text: Text to chunk
            max_size: Maximum size of each chunk
            overlap: Overlap between chunks
            **options: Strategy-specific options

        Returns:
            List of ChunkResult objects
        """
        ...


class BaseChunkingStrategy(ABC):
    """Base class for chunking strategies."""

    def __init__(self, language: str = 'en'):
        """
        Initialize the chunking strategy.

        Args:
            language: Language code for text processing
        """
        self.language = language
        self._cache = {}
        logger.debug(f"Initialized {self.__class__.__name__} for language: {language}")

    # ---------------- Common helpers: config + grapheme boundaries ----------------
    @staticmethod
    def _get_chunking_bool(key: str, default: bool) -> bool:
        try:
            import os
            v = os.getenv(key.upper())
            if v is None:
                from tldw_Server_API.app.core.config import load_comprehensive_config
                cp = load_comprehensive_config()
                if hasattr(cp, 'has_section') and cp.has_section('Chunking'):
                    v = cp.get('Chunking', key, fallback=str(default))
            s = str(v).strip().lower() if v is not None else str(default).lower()
            return s in ("1", "true", "yes", "on", "y")
        except Exception:
            return default

    def _strict_grapheme_mode(self, options: dict | None = None) -> bool:
        if options and 'strict_grapheme_end_expansion' in options:
            try:
                return bool(options.get('strict_grapheme_end_expansion'))
            except Exception:
                pass
        return self._get_chunking_bool('strict_grapheme_end_expansion', False)

    def _expand_end_to_grapheme_boundary(self, text: str, end: int, *, options: dict | None = None) -> int:
        """Expand end index so that we don't split grapheme clusters.

        Default mode (strict=False):
        - Includes trailing combining marks (Mn/Me), variation selectors, and
          other zero-width non-joiners (Cf except ZWJ).
        Strict mode (strict=True):
        - Additionally includes Zero Width Joiner (ZWJ) sequences (ZWJ + next
          base and trailing marks) and emoji skin tone modifiers.
        """
        import unicodedata as _ud

        strict = self._strict_grapheme_mode(options)
        n = len(text)
        i = min(max(0, end), n)

        def _is_vs(cp: int) -> bool:
            return (0xFE00 <= cp <= 0xFE0F) or (0xE0100 <= cp <= 0xE01EF)

        def _is_combining(ch: str) -> bool:
            cat = _ud.category(ch)
            return cat in ("Mn", "Me")

        def _is_skin_tone(cp: int) -> bool:
            return 0x1F3FB <= cp <= 0x1F3FF

        while i < n:
            ch = text[i]
            cp = ord(ch)
            cat = _ud.category(ch)
            if _is_combining(ch) or _is_vs(cp) or (cat == 'Cf' and (cp != 0x200D)):
                i += 1
                continue
            if strict and _is_skin_tone(cp):
                i += 1
                # include any following marks after modifier
                while i < n:
                    ch2 = text[i]
                    cp2 = ord(ch2)
                    cat2 = _ud.category(ch2)
                    if _is_combining(ch2) or _is_vs(cp2) or (cat2 == 'Cf' and cp2 != 0x200D):
                        i += 1
                    else:
                        break
                continue
            if (cp == 0x200D) and strict:
                # Include ZWJ and next codepoint + trailing marks
                i += 1
                if i < n:
                    i += 1
                    while i < n:
                        ch2 = text[i]
                        cp2 = ord(ch2)
                        cat2 = _ud.category(ch2)
                        if _is_combining(ch2) or _is_vs(cp2) or (cat2 == 'Cf' and cp2 != 0x200D):
                            i += 1
                        else:
                            break
                continue
            break
        return i

    @abstractmethod
    def chunk(self,
              text: str,
              max_size: int,
              overlap: int = 0,
              **options) -> List[str]:
        """
        Chunk text according to the strategy.

        Args:
            text: Text to chunk
            max_size: Maximum size of each chunk
            overlap: Overlap between chunks
            **options: Strategy-specific options

        Returns:
            List of text chunks
        """
        pass

    def chunk_with_metadata(self,
                           text: str,
                           max_size: int,
                           overlap: int = 0,
                           **options) -> List[ChunkResult]:
        """
        Chunk text and return with metadata.

        Args:
            text: Text to chunk
            max_size: Maximum size of each chunk
            overlap: Overlap between chunks
            **options: Strategy-specific options

        Returns:
            List of ChunkResult objects
        """
        chunks = self.chunk(text, max_size, overlap, **options)
        results = []
        current_pos = 0

        for i, chunk in enumerate(chunks):
            # Find chunk position in original text
            chunk_start = text.find(chunk, current_pos)
            if chunk_start == -1:
                chunk_start = current_pos
            chunk_end = chunk_start + len(chunk)
            # Expand to avoid splitting grapheme clusters in metadata
            try:
                chunk_end = self._expand_end_to_grapheme_boundary(text, chunk_end, options=options)
            except Exception:
                pass

            metadata = ChunkMetadata(
                index=i,
                start_char=chunk_start,
                end_char=chunk_end,
                word_count=len(chunk.split()),
                language=self.language,
                overlap_with_previous=overlap if i > 0 else 0,
                overlap_with_next=overlap if i < len(chunks) - 1 else 0
            )

            results.append(ChunkResult(text=chunk, metadata=metadata))
            current_pos = chunk_end - overlap if overlap > 0 else chunk_end

        return results

    def validate_parameters(self, text: str, max_size: int, overlap: int):
        """
        Validate chunking parameters.

        Args:
            text: Text to chunk
            max_size: Maximum size of each chunk
            overlap: Overlap between chunks

        Raises:
            ValueError: If parameters are invalid

        Notes:
            This method performs validation only. Implementations must re-clamp
            `overlap` at the strategy level to ensure forward progress, i.e.,
            when `overlap >= max_size` set `overlap = max_size - 1` before
            windowing. Do not rely on this helper to mutate caller state.
        """
        if not isinstance(text, str):
            raise ValueError(f"Text must be a string, got {type(text).__name__}")

        if not text.strip():
            logger.debug("Empty text provided for chunking")
            return False

        if max_size <= 0:
            raise ValueError(f"max_size must be positive, got {max_size}")

        if overlap < 0:
            raise ValueError(f"overlap cannot be negative, got {overlap}")

        if overlap >= max_size:
            logger.warning(f"Overlap ({overlap}) >= max_size ({max_size}), adjusting to max_size - 1")
            overlap = max_size - 1

        return True

    def chunk_generator(self,
                       text: str,
                       max_size: int,
                       overlap: int = 0,
                       **options) -> Generator[str, None, None]:
        """
        Generator version of chunk for memory efficiency.

        Args:
            text: Text to chunk
            max_size: Maximum size of each chunk
            overlap: Overlap between chunks
            **options: Strategy-specific options

        Yields:
            Individual text chunks
        """
        chunks = self.chunk(text, max_size, overlap, **options)
        for chunk in chunks:
            yield chunk


class ChunkerConfig:
    """Configuration for the chunking system."""

    def __init__(self,
                 default_method: ChunkingMethod = ChunkingMethod.WORDS,
                 default_max_size: int = 400,
                 default_overlap: int = 200,
                 language: str = 'en',
                 enable_cache: bool = True,
                 cache_size: int = 100,
                 cache_copy_on_access: bool = True,
                 cache_max_text_length: int = 2_000_000,
                 min_text_length_to_cache: int = 0,
                 max_text_length_to_cache: int = 2_000_000,
                 max_text_size: int = 100_000_000,  # 100MB
                 enable_metrics: bool = True,
                 verbose_logging: bool = False,
                 # Execution/concurrency knobs (used by AsyncChunker; optional here)
                 max_workers: int = 4,
                 max_concurrent: int = 10):
        """
        Initialize chunker configuration.

        Args:
            default_method: Default chunking method
            default_max_size: Default maximum chunk size
            default_overlap: Default overlap between chunks
            language: Default language for text processing
            enable_cache: Whether to enable caching
            cache_size: Maximum cache size
            max_text_size: Maximum text size to process
            enable_metrics: Whether to collect metrics
            max_workers: Default worker threads for async execution helpers
            max_concurrent: Default concurrency semaphore for async helpers
        """
        # Convert string to enum if needed
        if isinstance(default_method, str):
            try:
                default_method = ChunkingMethod(default_method)
            except ValueError:
                logger.warning(f"Unknown chunking method '{default_method}', using default")
                default_method = ChunkingMethod.WORDS

        # Basic validations
        if not isinstance(default_max_size, int) or default_max_size <= 0:
            raise ValueError(f"default_max_size must be a positive integer, got {default_max_size}")
        if not isinstance(default_overlap, int) or default_overlap < 0:
            raise ValueError(f"default_overlap must be a non-negative integer, got {default_overlap}")
        if not isinstance(cache_size, int) or cache_size <= 0:
            raise ValueError(f"cache_size must be a positive integer, got {cache_size}")
        if not isinstance(max_text_size, int) or max_text_size <= 0:
            raise ValueError(f"max_text_size must be a positive integer, got {max_text_size}")
        if not isinstance(cache_max_text_length, int) or cache_max_text_length <= 0:
            raise ValueError(f"cache_max_text_length must be a positive integer, got {cache_max_text_length}")
        if not isinstance(min_text_length_to_cache, int) or min_text_length_to_cache < 0:
            raise ValueError(f"min_text_length_to_cache must be a non-negative integer, got {min_text_length_to_cache}")
        if not isinstance(max_text_length_to_cache, int) or max_text_length_to_cache <= 0:
            raise ValueError(f"max_text_length_to_cache must be a positive integer, got {max_text_length_to_cache}")
        if not isinstance(max_workers, int) or max_workers <= 0:
            raise ValueError(f"max_workers must be a positive integer, got {max_workers}")
        if not isinstance(max_concurrent, int) or max_concurrent <= 0:
            raise ValueError(f"max_concurrent must be a positive integer, got {max_concurrent}")

        self.default_method = default_method
        self.default_max_size = default_max_size
        self.default_overlap = default_overlap
        self.language = language
        self.enable_cache = enable_cache
        self.cache_size = cache_size
        self.cache_copy_on_access = bool(cache_copy_on_access)
        self.cache_max_text_length = cache_max_text_length
        # New cache policy thresholds (preferred)
        self.min_text_length_to_cache = min_text_length_to_cache
        self.max_text_length_to_cache = max_text_length_to_cache
        self.max_text_size = max_text_size
        self.enable_metrics = enable_metrics
        self.verbose_logging = bool(verbose_logging)
        # Execution/concurrency knobs (used by AsyncChunker)
        self.max_workers = max_workers
        self.max_concurrent = max_concurrent

        # Allow config.txt overrides for selected settings (no ENV toggles)
        try:
            from tldw_Server_API.app.core.config import load_comprehensive_config
            cp = load_comprehensive_config()
            if hasattr(cp, 'has_section') and cp.has_section('Chunking'):
                try:
                    v = cp.get('Chunking', 'cache_copy_on_access', fallback=None)
                    if v is not None:
                        self.cache_copy_on_access = str(v).strip().lower() in {"1","true","yes","on"}
                except Exception:
                    pass
                try:
                    v = cp.get('Chunking', 'verbose_logging', fallback=None)
                    if v is not None:
                        self.verbose_logging = str(v).strip().lower() in {"1","true","yes","on"}
                except Exception:
                    pass
        except Exception:
            # Config loading is optional here; safe to ignore
            pass

        logger.info(f"ChunkerConfig initialized with method={self.default_method.value if hasattr(self.default_method, 'value') else self.default_method}, "
                   f"max_size={default_max_size}, overlap={default_overlap}")


    # Note: Exceptions for the chunking module live in
    # tldw_Server_API.app.core.Chunking.exceptions. This file intentionally
    # avoids duplicating those definitions.
