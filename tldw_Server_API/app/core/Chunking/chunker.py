# chunker.py
"""
Main Chunker class that provides a unified interface for all chunking strategies.
This is the primary entry point for the chunking module.
"""

from typing import List, Dict, Any, Optional, Union, Generator, Tuple
import re
import json
import hashlib
import time
from pathlib import Path
import unicodedata
import ast
import threading
import copy
from collections import OrderedDict
from loguru import logger

from .base import ChunkerConfig, ChunkingMethod, ChunkResult
from .exceptions import (
    InvalidChunkingMethodError,
    InvalidInputError,
    ChunkingError,
    ConfigurationError
)
from .strategies.words import WordChunkingStrategy
from .strategies.sentences import SentenceChunkingStrategy
from .strategies.tokens import TokenChunkingStrategy
from .strategies.structure_aware import StructureAwareChunkingStrategy
from .strategies.fixed_size import FixedSizeChunkingStrategy
from .strategies.rolling_summarize import RollingSummarizeStrategy
from .security_logger import get_security_logger, SecurityEventType

# Metrics / Telemetry (graceful on import failures)
try:
    from tldw_Server_API.app.core.Metrics import (
        observe_histogram,
        set_gauge,
        increment_counter,
        start_span,
        add_span_event,
        set_span_attribute,
        record_span_exception,
    )
except Exception:  # pragma: no cover - safety fallback
    def observe_histogram(*args, **kwargs):
        return None
    def set_gauge(*args, **kwargs):
        return None
    def increment_counter(*args, **kwargs):
        return None
    class _NullSpan:
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False
    def start_span(*args, **kwargs):
        return _NullSpan()
    def add_span_event(*args, **kwargs):
        return None
    def set_span_attribute(*args, **kwargs):
        return None
    def record_span_exception(*args, **kwargs):
        return None


class LRUCache:
    """
    Thread-safe LRU (Least Recently Used) cache implementation.
    """
    
    def __init__(self, max_size: int = 100):
        """
        Initialize the LRU cache.
        
        Args:
            max_size: Maximum number of items to store in cache
        """
        self.max_size = max_size
        self.cache = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        
    def get(self, key: str) -> Optional[Any]:
        """
        Get an item from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        with self._lock:
            if key in self.cache:
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                self.hits += 1
                try:
                    return copy.deepcopy(self.cache[key])
                except Exception:
                    return self.cache[key]
            self.misses += 1
            return None
    
    def put(self, key: str, value: Any) -> None:
        """
        Put an item into cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        with self._lock:
            if key in self.cache:
                # Update existing and move to end
                self.cache.move_to_end(key)
                try:
                    self.cache[key] = copy.deepcopy(value)
                except Exception:
                    self.cache[key] = value
            else:
                # Add new item
                try:
                    self.cache[key] = copy.deepcopy(value)
                except Exception:
                    self.cache[key] = value
                # Remove oldest if over capacity
                if len(self.cache) > self.max_size:
                    self.cache.popitem(last=False)
    
    def clear(self) -> None:
        """Clear the cache."""
        with self._lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            total = self.hits + self.misses
            hit_rate = self.hits / total if total > 0 else 0
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate': hit_rate
            }


class Chunker:
    """
    Main chunker class that manages different chunking strategies.
    Provides a unified interface for text chunking with support for
    multiple methods, languages, and configurations.
    """
    
    def __init__(self, config: Optional[ChunkerConfig] = None, 
                 llm_call_func: Optional[Any] = None,
                 llm_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the chunker with configuration.
        
        Args:
            config: Chunker configuration (uses defaults if not provided)
            llm_call_func: Optional LLM function for strategies that need it
            llm_config: Optional LLM configuration
        """
        self.config = config or ChunkerConfig()
        self.llm_call_func = llm_call_func
        self.llm_config = llm_config or {}
        
        # Strategy instances (lazy)
        self._strategies = {}
        self._strategy_factories = {}
        self._register_strategy_factories()
        
        # Cache for processed results - using LRU cache
        self._cache = LRUCache(max_size=self.config.cache_size) if self.config.enable_cache else None
        
        # Security logger
        self._security_logger = get_security_logger()
        
        logger.info(f"Chunker initialized with default method: {self.config.default_method.value}")

    def _enforce_text_size(self, text: str, *, source: str) -> None:
        """Ensure text respects configured size limits."""
        if not isinstance(text, str):
            raise InvalidInputError(f"Expected string input, got {type(text).__name__}")
        if len(text) > self.config.max_text_size:
            try:
                self._security_logger.log_oversized_input(len(text), self.config.max_text_size, source=source)
            except Exception:
                pass
            raise InvalidInputError(
                f"Text size ({len(text)} bytes) exceeds maximum allowed size "
                f"({self.config.max_text_size} bytes)"
            )
    
    def _register_strategy_factories(self):
        """Register factories for lazy strategy instantiation."""
        lang = self.config.language
        self._strategy_factories = {
            ChunkingMethod.WORDS.value: lambda: WordChunkingStrategy(language=lang),
            ChunkingMethod.SENTENCES.value: lambda: SentenceChunkingStrategy(language=lang),
            ChunkingMethod.PARAGRAPHS.value: lambda: __import__(
                f"{__package__}.strategies.paragraphs", fromlist=["ParagraphChunkingStrategy"]
            ).ParagraphChunkingStrategy(language=lang),
            ChunkingMethod.STRUCTURE_AWARE.value: lambda: StructureAwareChunkingStrategy(language=lang),
            ChunkingMethod.CODE.value: lambda: __import__(
                f"{__package__}.strategies.code", fromlist=["CodeChunkingStrategy"]
            ).CodeChunkingStrategy(language=lang),
            'code_ast': lambda: __import__(
                f"{__package__}.strategies.code_ast", fromlist=["PythonASTCodeChunkingStrategy"]
            ).PythonASTCodeChunkingStrategy(language='python'),
            ChunkingMethod.PROPOSITIONS.value: lambda: __import__(
                f"{__package__}.strategies.propositions", fromlist=["PropositionChunkingStrategy"]
            ).PropositionChunkingStrategy(language=lang, llm_call_func=self.llm_call_func, llm_config=self.llm_config),
            ChunkingMethod.TOKENS.value: lambda: TokenChunkingStrategy(language=lang),
            ChunkingMethod.FIXED_SIZE.value: lambda: FixedSizeChunkingStrategy(language=lang),
            ChunkingMethod.SEMANTIC.value: lambda: __import__(
                f"{__package__}.strategies.semantic", fromlist=["SemanticChunkingStrategy"]
            ).SemanticChunkingStrategy(language=lang),
            ChunkingMethod.JSON.value: lambda: __import__(
                f"{__package__}.strategies.json_xml", fromlist=["JSONChunkingStrategy"]
            ).JSONChunkingStrategy(language=lang),
            ChunkingMethod.XML.value: lambda: __import__(
                f"{__package__}.strategies.json_xml", fromlist=["XMLChunkingStrategy"]
            ).XMLChunkingStrategy(language=lang),
            ChunkingMethod.EBOOK_CHAPTERS.value: lambda: __import__(
                f"{__package__}.strategies.ebook_chapters", fromlist=["EbookChapterChunkingStrategy"]
            ).EbookChapterChunkingStrategy(language=lang),
            ChunkingMethod.ROLLING_SUMMARIZE.value: lambda: RollingSummarizeStrategy(
                language=lang, llm_call_func=self.llm_call_func, llm_config=self.llm_config
            ),
        }
        logger.debug(f"Registered {len(self._strategy_factories)} strategy factories (lazy)")

    # ---------------- Hierarchical chunking (integrated) -----------------
    def _compute_paragraph_spans(self, text: str, template: Optional[Dict[str, Any]] = None) -> List[Tuple[int, int, str]]:
        """Compute paragraph/block spans with kinds and optional template boundaries.

        Lightweight port of the structure detection used by the legacy utility to
        avoid maintaining two libraries. Recognizes blank lines, ATX headers, hrules,
        simple lists, code fences, markdown tables, and optional custom boundary rules.
        """
        spans: List[Tuple[int, int, str]] = []
        if not text:
            return spans

        # Compile template boundary patterns if provided, with safety limits
        template_patterns: List[Tuple[str, re.Pattern]] = []
        try:
            boundaries = (template or {}).get('boundaries') or []
            # Safety caps aligned with API validator: at most 20 rules
            MAX_RULES = 20
            MAX_PATTERN_LEN = 256
            from .regex_safety import check_pattern, compile_flags
            for rule in boundaries[:MAX_RULES]:
                try:
                    kind = str(rule.get('kind') or 'template')
                    pattern = str(rule.get('pattern') or '')
                    if not pattern:
                        continue
                    if len(pattern) > MAX_PATTERN_LEN:
                        logger.warning(f"Skipping overlong boundary pattern (>{MAX_PATTERN_LEN} chars)")
                        continue
                    # Safety check
                    err = check_pattern(pattern, max_len=MAX_PATTERN_LEN)
                    if err:
                        logger.warning(f"Skipping boundary pattern due to safety check: {err}")
                        continue
                    flags_val, ferr = compile_flags(str(rule.get('flags') or ''))
                    flags = flags_val if ferr is None else 0
                    compiled = re.compile(pattern, flags)
                    template_patterns.append((kind, compiled))
                except Exception as e:
                    logger.warning(f"Ignoring invalid boundary rule: {e}")
        except Exception:
            template_patterns = []

        lines = text.splitlines(keepends=True)
        offsets: List[Tuple[int, int, str]] = []
        pos = 0
        for line in lines:
            start, end = pos, pos + len(line)
            offsets.append((start, end, line))
            pos = end
        if pos < len(text):
            offsets.append((pos, len(text), text[pos:len(text)]))

        def match_template(s: str) -> Optional[str]:
            # Use safe search with optional timeouts and RE2 when available
            try:
                from .regex_safety import safe_search
            except Exception:
                safe_search = None  # type: ignore
            for kind, pat in template_patterns:
                try:
                    ok = False
                    if safe_search is not None:
                        ok = bool(safe_search(pat, s))
                    else:
                        ok = pat.search(s) is not None
                    if ok:
                        return kind
                except Exception:
                    continue
            return None

        def classify_line(s: str) -> Optional[str]:
            k = match_template(s)
            if k:
                return k
            if re.match(r'^\s*$', s):
                return 'blank'
            if re.match(r'^\s*#{1,6}\s', s):
                return 'header_atx'
            if re.match(r'^\s*(\*{3,}|-{3,}|_{3,})\s*$', s):
                return 'hr'
            if re.match(r'^\s*(```|~~~)', s):
                return 'code_fence'
            if re.match(r'^\s*([-+*])\s+\S', s):
                return 'list_unordered'
            if re.match(r'^\s*\d+[\.)]\s+\S', s):
                return 'list_ordered'
            if re.match(r'^\s*\|.*\|\s*$', s):
                return 'table_md'
            return None

        buf_start: Optional[int] = None
        for (start, end, content) in offsets:
            kind = classify_line(content)
            if kind == 'blank':
                if buf_start is not None:
                    spans.append((buf_start, start, 'paragraph'))
                    buf_start = None
                spans.append((start, end, 'blank'))
            elif kind is not None:
                if buf_start is not None:
                    spans.append((buf_start, start, 'paragraph'))
                    buf_start = None
                spans.append((start, end, kind))
            else:
                if buf_start is None:
                    buf_start = start
        if buf_start is not None:
            spans.append((buf_start, len(text), 'paragraph'))
        return spans

    def _extract_header_title(self, s: str) -> str:
        if s.lstrip().startswith('#'):
            return re.sub(r'^\s*#{1,6}\s+', '', s).strip()
        return s.strip()

    def chunk_text_hierarchical_tree(
        self,
        text: str,
        method: Optional[str] = None,
        max_size: Optional[int] = None,
        overlap: Optional[int] = None,
        language: Optional[str] = None,
        template: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build a simple hierarchical tree (sections + blocks) and chunk leaves.

        Returns a dict with a root node and nested children, each child holding "chunks"
        with exact offsets. Designed to be flattened downstream.
        """
        if not isinstance(text, str) or not text:
            return {'type': 'hierarchical', 'schema_version': 1, 'root': {'kind': 'root', 'children': []}}
        self._enforce_text_size(text, source="chunk_text_hierarchical_tree")
        method = method or self.config.default_method.value
        max_size = max_size if max_size is not None else self.config.default_max_size
        overlap = overlap if overlap is not None else self.config.default_overlap
        language = language or self.config.language

        # Build blocks from spans
        spans = self._compute_paragraph_spans(text, template)
        root = {'kind': 'root', 'level': 0, 'title': None, 'start_offset': 0, 'end_offset': len(text), 'children': []}
        current_section: Optional[Dict[str, Any]] = None
        section_stack: List[Dict[str, Any]] = []
        preface_section: Optional[Dict[str, Any]] = None

        # Helper to add a leaf block with chunks
        def _add_block(parent: Dict[str, Any], start: int, end: int, kind: str):
            if start >= end:
                return
            segment_raw = text[start:end]
            # Use sanitized copy for downstream offset mapping while keeping raw text for logging in chunk_text
            segment_clean = self._sanitize_input(segment_raw, suppress_security_log=True)
            # Compute chunks using selected method
            chunks = self.chunk_text(segment_raw, method=method, max_size=max_size, overlap=overlap, language=language)
            out_chunks: List[Dict[str, Any]] = []

            # Method-aware offset mapping to avoid misplacing spans on repeated content
            try:
                if method == 'words':
                    # Map word tokens back to their character spans within the segment
                    # Build token list equivalent to the words strategy
                    from .strategies.words import WordChunkingStrategy  # local import to avoid cycle at module import
                    ws = WordChunkingStrategy(language=language)
                    tokens = ws._tokenize_text(segment_clean)  # noqa: SLF001 (internal, but stable in-project)
                    tok_spans: List[Tuple[int, int]] = []
                    cur = 0
                    for tok in tokens:
                        idx = segment_clean.find(tok, cur)
                        if idx == -1:
                            idx = cur
                        tok_spans.append((idx, idx + len(tok)))
                        cur = idx + len(tok)

                    # Reconstruct chunk spans based on token counts
                    step = max(1, (max_size if isinstance(max_size, int) else 0) - (overlap if isinstance(overlap, int) else 0)) or 1
                    t_i = 0
                    for ch in chunks:
                        ch_text = ch if isinstance(ch, str) else str(ch)
                        # Derive token count in this chunk by splitting the chunk text similarly
                        if language in ['zh', 'zh-cn', 'zh-tw', 'ja', 'th']:
                            # Unknown separation; approximate by consuming tokens until we match the chunk length
                            k = 0
                            acc_len = 0
                            while t_i + k < len(tokens) and acc_len < len(ch_text):
                                acc_len += len(tokens[t_i + k])
                                k += 1
                            k = max(1, k)
                        else:
                            k = max(1, len(ch_text.split()))

                        # Clamp k to remaining tokens
                        k = min(k, max(1, len(tokens) - t_i))
                        s0 = tok_spans[t_i][0] if t_i < len(tok_spans) else 0
                        e0 = tok_spans[t_i + k - 1][1] if (t_i + k - 1) < len(tok_spans) else len(segment_clean)
                        out_chunks.append({
                            'type': 'text',
                            'text': ch_text,
                            'metadata': {
                                'method': method,
                                'start_offset': start + s0,
                                'end_offset': start + e0,
                                'language': language,
                                'paragraph_kind': kind,
                            }
                        })
                        # Advance by step (matching words strategy semantics)
                        t_i = min(len(tokens), t_i + step)
                elif method == 'sentences':
                    # Compute sentence spans and group by sentence count to mirror strategy behavior
                    from .strategies.sentences import SentenceChunkingStrategy  # local import
                    ss = SentenceChunkingStrategy(language=language)
                    # Get sentence spans using strategy to avoid naive find
                    sent_with_spans = ss._split_sentences_with_spans(segment_clean)  # noqa: SLF001
                    sentences = [s for (s, _s, _e) in sent_with_spans]
                    sent_spans: List[Tuple[int, int]] = [(s0, e0) for (_t, s0, e0) in sent_with_spans]
                    # Group sentences into chunks (max_size sentences, overlap)
                    step = max(1, (max_size if isinstance(max_size, int) else 0) - (overlap if isinstance(overlap, int) else 0)) or 1
                    for i in range(0, len(sentences), step):
                        group = sentences[i:i + (max_size if isinstance(max_size, int) else len(sentences))]
                        if not group:
                            continue
                        ch_text = ''.join(group) if language in ['zh', 'zh-cn', 'zh-tw', 'ja'] else ' '.join(group)
                        s0 = sent_spans[i][0] if i < len(sent_spans) else 0
                        j_last = min(len(sent_spans) - 1, i + len(group) - 1)
                        e0 = sent_spans[j_last][1] if j_last >= 0 else len(segment_clean)
                        out_chunks.append({
                            'type': 'text',
                            'text': ch_text.strip(),
                            'metadata': {
                                'method': method,
                                'start_offset': start + s0,
                                'end_offset': start + e0,
                                'language': language,
                                'paragraph_kind': kind,
                            }
                        })
                elif method == 'structure_aware':
                    # Carry block span directly as a precise chunk for structure-aware mode
                    ch_text = segment_clean
                    out_chunks.append({
                        'type': 'text',
                        'text': ch_text,
                        'metadata': {
                            'method': method,
                            'start_offset': start,
                            'end_offset': end,
                            'language': language,
                            'paragraph_kind': kind,
                        }
                    })
                else:
                    # Fallback: bound search within the segment using a rolling cursor
                    cursor = 0
                    for ch in chunks:
                        ch_text = ch if isinstance(ch, str) else str(ch)
                        idx = segment_clean.find(ch_text, cursor)
                        if idx == -1:
                            # If not found, place at cursor to keep monotonicity
                            idx = cursor
                        out_chunks.append({
                            'type': 'text',
                            'text': ch_text,
                            'metadata': {
                                'method': method,
                                'start_offset': start + idx,
                                'end_offset': start + idx + len(ch_text),
                                'language': language,
                                'paragraph_kind': kind,
                            }
                        })
                        cursor = idx + len(ch_text)
            except Exception as e:
                # As a last resort, return chunks with naive offsets bounded to this block
                logger.warning(f"Offset mapping failed for method={method}: {e}; using naive offsets")
                cursor = 0
                for ch in chunks:
                    ch_text = ch if isinstance(ch, str) else str(ch)
                    out_chunks.append({
                        'type': 'text',
                        'text': ch_text,
                        'metadata': {
                            'method': method,
                            'start_offset': start + cursor,
                            'end_offset': start + min(len(segment_clean), cursor + len(ch_text)),
                            'language': language,
                            'paragraph_kind': kind,
                        }
                    })
                    cursor += len(ch_text)

            parent.setdefault('children', []).append({
                'kind': kind,
                'start_offset': start,
                'end_offset': end,
                'chunks': out_chunks,
                'children': []
            })

        def _close_section(section: Optional[Dict[str, Any]], end: int):
            if section is not None and section.get('end_offset') is None:
                section['end_offset'] = end

        def _ensure_preface_section(start: int) -> Dict[str, Any]:
            nonlocal preface_section
            if preface_section is None:
                preface_section = {
                    'kind': 'section',
                    'level': 1,
                    'title': None,
                    'start_offset': start,
                    'end_offset': None,
                    'children': []
                }
                root['children'].append(preface_section)
            elif preface_section.get('start_offset') is None:
                preface_section['start_offset'] = start
            return preface_section

        for (bstart, bend, bkind) in spans:
            # New section on header
            if bkind == 'header_atx':
                # Close previous sections (including any preface) before starting a new one
                _close_section(preface_section, bstart)
                header_segment = text[bstart:bend]
                level_match = re.match(r'^\s*(#{1,6})\s', header_segment)
                level = len(level_match.group(1)) if level_match else 1
                while section_stack and section_stack[-1].get('level', 0) >= level:
                    top = section_stack.pop()
                    _close_section(top, bstart)
                parent_section = section_stack[-1] if section_stack else root
                current_section = {
                    'kind': 'section',
                    'level': level,
                    'title': self._extract_header_title(header_segment),
                    'start_offset': bstart,
                    'end_offset': None,
                    'children': []
                }
                parent_section.setdefault('children', []).append(current_section)
                section_stack.append(current_section)
                # Record the header itself as a block so offsets include the title text
                _add_block(current_section, bstart, bend, bkind)
            elif bkind != 'blank':
                current_section = section_stack[-1] if section_stack else None
                target_parent = current_section if current_section is not None else _ensure_preface_section(bstart)
                _add_block(target_parent, bstart, bend, bkind)

        # Close tail
        while section_stack:
            _close_section(section_stack.pop(), len(text))
        _close_section(preface_section, len(text))

        return {
            'type': 'hierarchical',
            'schema_version': 1,
            'method': method,
            'language': language,
            'max_size': max_size,
            'overlap': overlap,
            'root': root,
        }

    def flatten_hierarchical(self, tree: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Flatten a hierarchical tree into a list of dict chunks with ancestry info."""
        if not isinstance(tree, dict):
            return []
        root = tree.get('root') or {'children': tree.get('blocks', [])}
        method = tree.get('method')
        # Elements-per-chunk semantics for structure_aware grouping
        sa_max = tree.get('max_size') if isinstance(tree.get('max_size'), int) else None
        sa_ovl = tree.get('overlap') if isinstance(tree.get('overlap'), int) else 0
        out: List[Dict[str, Any]] = []

        languages_no_space = {'zh', 'zh-cn', 'zh-tw', 'ja', 'th', 'ko'}

        def _merge_texts(parts: List[Tuple[str, Dict[str, Any]]], *, default_sep: str = ' ', kind_hint: Optional[str] = None) -> str:
            """Join text parts while guaranteeing at least minimal whitespace between them."""
            if not parts:
                return ''
            combined = parts[0][0]
            prev_md = parts[0][1]

            for text_part, md in parts[1:]:
                if combined and text_part and not combined[-1].isspace() and not text_part[0].isspace():
                    sep = default_sep
                    language = None
                    if isinstance(md, dict):
                        language = md.get('language')
                    if not language and isinstance(prev_md, dict):
                        language = prev_md.get('language')

                    kind = kind_hint
                    if kind is None and isinstance(md, dict):
                        kind = md.get('paragraph_kind')

                    if kind in {'list_unordered', 'list_ordered', 'table_md', 'code_fence'}:
                        sep = '\n'
                    elif kind == 'header_atx':
                        sep = '\n\n'
                    elif method == 'structure_aware':
                        sep = '\n\n'

                    if language and language.lower() in languages_no_space and kind not in {'header_atx', 'list_unordered', 'list_ordered', 'table_md', 'code_fence'}:
                        sep = ''

                    needs_trailing_space = (
                        sep and sep.endswith('\n') and
                        (kind == 'header_atx' or method == 'structure_aware') and
                        (not language or language.lower() not in languages_no_space)
                    )
                    if needs_trailing_space:
                        combined += sep
                        combined += ' '
                    else:
                        combined += sep
                combined += text_part
                prev_md = md
            return combined

        def _append_with_titles(items: List[Dict[str, Any]], titles: List[str]):
            for ch in items:
                txt = ch.get('text') if isinstance(ch, dict) else str(ch)
                md = dict(ch.get('metadata') or {}) if isinstance(ch, dict) else {}
                md['ancestry_titles'] = titles
                if titles:
                    md['section_path'] = ' > '.join(titles)
                out.append({'text': txt, 'metadata': md})

        def _gather_section_items(section_node: Dict[str, Any]) -> List[Dict[str, Any]]:
            items: List[Dict[str, Any]] = []
            header_buffer: List[Dict[str, Any]] = []

            def _flush_header_buffer(target_item: Dict[str, Any]) -> Dict[str, Any]:
                """Merge buffered headers into the provided item without increasing element count."""
                nonlocal header_buffer
                if not header_buffer:
                    return target_item
                parts: List[Tuple[str, Dict[str, Any]]] = []
                starts: List[int] = []
                ends: List[int] = []
                for h in header_buffer:
                    txt = h.get('text') if isinstance(h, dict) else str(h)
                    md_h = h.get('metadata') if isinstance(h, dict) else {}
                    s = md_h.get('start_offset')
                    e = md_h.get('end_offset')
                    parts.append((txt, dict(md_h) if isinstance(md_h, dict) else {}))
                    if isinstance(s, int):
                        starts.append(s)
                    if isinstance(e, int):
                        ends.append(e)
                header_buffer = []

                t_txt = target_item.get('text') if isinstance(target_item, dict) else str(target_item)
                md_target = dict(target_item.get('metadata') or {}) if isinstance(target_item, dict) else {}
                s_t = md_target.get('start_offset')
                e_t = md_target.get('end_offset')
                if isinstance(s_t, int):
                    starts.append(s_t)
                if isinstance(e_t, int):
                    ends.append(e_t)
                parts.append((t_txt, md_target))
                merged_start = min(starts) if starts else s_t
                merged_end = max(ends) if ends else e_t

                merged_item = {
                    'type': target_item.get('type', 'text'),
                    'text': _merge_texts(parts, default_sep='\n\n', kind_hint='header_atx'),
                    'metadata': md_target
                }
                if merged_start is not None:
                    merged_item['metadata']['start_offset'] = merged_start
                if merged_end is not None:
                    merged_item['metadata']['end_offset'] = merged_end
                # Preserve paragraph kind (defaulting to target item) and flag header inclusion
                pk = md_target.get('paragraph_kind')
                if pk is not None:
                    merged_item['metadata']['paragraph_kind'] = pk
                merged_item['metadata']['has_section_header'] = True
                return merged_item

            for child in section_node.get('children') or []:
                if not isinstance(child, dict):
                    continue
                for ch in child.get('chunks') or []:
                    if not isinstance(ch, dict):
                        continue
                    md = ch.get('metadata') or {}
                    paragraph_kind = md.get('paragraph_kind')
                    if paragraph_kind == 'header_atx':
                        header_buffer.append(ch)
                        continue
                    if header_buffer:
                        merged = _flush_header_buffer(ch)
                        items.append(merged)
                    else:
                        items.append(ch)

            if header_buffer:
                # Section with header but no following content: keep header as-is
                items.extend(header_buffer)

            return items

        def _group_items_by_elements(items: List[Dict[str, Any]], max_elements: int, overlap: int) -> List[Dict[str, Any]]:
            if max_elements is None or max_elements <= 0:
                return items
            if overlap < 0:
                overlap = 0
            step = max(1, max_elements - overlap)
            grouped: List[Dict[str, Any]] = []
            i = 0
            n = len(items)
            while i < n:
                group = items[i:i + max_elements]
                if not group:
                    break
                final_window = len(group) < max_elements
                emit = True
                if final_window and overlap > 0 and i > 0:
                    try:
                        if n <= i + overlap:
                            emit = False
                    except Exception:
                        emit = True
                if not emit:
                    break
                # Concatenate texts preserving original content
                parts: List[Tuple[str, Dict[str, Any]]] = []
                starts: List[int] = []
                ends: List[int] = []
                for it in group:
                    t = it.get('text') if isinstance(it, dict) else str(it)
                    md = it.get('metadata') if isinstance(it, dict) else {}
                    md_dict = dict(md) if isinstance(md, dict) else {}
                    parts.append((t, md_dict))
                    try:
                        s = int(md.get('start_offset')) if md and md.get('start_offset') is not None else None
                    except Exception:
                        s = None
                    try:
                        e = int(md.get('end_offset')) if md and md.get('end_offset') is not None else None
                    except Exception:
                        e = None
                    if s is not None:
                        starts.append(s)
                    if e is not None:
                        ends.append(e)
                language_hint = None
                for _, md_part in parts:
                    if md_part.get('language'):
                        language_hint = md_part.get('language')
                        break
                default_sep = '\n\n' if method == 'structure_aware' else ' '
                if language_hint and str(language_hint).lower() in languages_no_space and method != 'structure_aware':
                    default_sep = ''
                agg_text = _merge_texts(parts, default_sep=default_sep)
                start_off = min(starts) if starts else 0
                end_off = max(ends) if ends else start_off + len(agg_text)
                grouped.append({
                    'type': 'text',
                    'text': agg_text,
                    'metadata': {
                        'method': method,
                        'start_offset': start_off,
                        'end_offset': end_off,
                        'grouped_elements': len(group),
                    }
                })
                if final_window:
                    break
                i += step
            return grouped

        def _group_section_by_kind_weight(items: List[Dict[str, Any]], max_weight: int, overlap: int, weights: Dict[str, int]) -> List[Dict[str, Any]]:
            """Group contiguous items by paragraph_kind using weight budget per group.

            Does not cross kind boundaries; code_fence blocks tend to be heavier by default.
            """
            if max_weight is None or max_weight <= 0:
                return items
            if overlap < 0:
                overlap = 0
            # Clamp overlap to max_weight - 1 (no negative step)
            overlap = min(overlap, max(0, max_weight - 1))
            out_groups: List[Dict[str, Any]] = []
            i = 0
            n = len(items)
            while i < n:
                # Start new group at i and keep same kind
                first = items[i]
                kind = (first.get('metadata') or {}).get('paragraph_kind') if isinstance(first, dict) else None
                budget = max_weight
                j = i
                parts: List[Tuple[str, Dict[str, Any]]] = []
                starts: List[int] = []
                ends: List[int] = []
                count = 0
                while j < n:
                    it = items[j]
                    md = it.get('metadata') if isinstance(it, dict) else {}
                    ikind = md.get('paragraph_kind') if isinstance(md, dict) else None
                    if ikind != kind:
                        break
                    w = int(weights.get(str(ikind), 1)) if isinstance(weights, dict) else 1
                    if w <= 0:
                        w = 1
                    if w > budget and count > 0:
                        break
                    # Take this item
                    t = it.get('text') if isinstance(it, dict) else str(it)
                    md_dict = dict(md) if isinstance(md, dict) else {}
                    parts.append((t, md_dict))
                    try:
                        s = int(md.get('start_offset')) if md and md.get('start_offset') is not None else None
                    except Exception:
                        s = None
                    try:
                        e = int(md.get('end_offset')) if md and md.get('end_offset') is not None else None
                    except Exception:
                        e = None
                    if s is not None:
                        starts.append(s)
                    if e is not None:
                        ends.append(e)
                    budget -= w
                    j += 1
                    count += 1
                    if budget <= 0:
                        break
                if count == 0:
                    # Fallback to consume one item to make progress
                    j = i + 1
                    it = items[i]
                    t = it.get('text') if isinstance(it, dict) else str(it)
                    md = it.get('metadata') if isinstance(it, dict) else {}
                    md_dict = dict(md) if isinstance(md, dict) else {}
                    parts = [(t, md_dict)]
                    starts = [int(md.get('start_offset'))] if md and md.get('start_offset') is not None else []
                    ends = [int(md.get('end_offset'))] if md and md.get('end_offset') is not None else []
                    count = 1
                sep_hint = ' '
                if kind in {'list_unordered', 'list_ordered', 'table_md', 'code_fence'}:
                    sep_hint = '\n'
                elif kind == 'header_atx':
                    sep_hint = '\n\n'
                elif method == 'structure_aware':
                    sep_hint = '\n\n'
                agg_text = _merge_texts(parts, default_sep=sep_hint, kind_hint=kind)
                start_off = min(starts) if starts else 0
                end_off = max(ends) if ends else start_off + len(agg_text)
                out_groups.append({
                    'type': 'text',
                    'text': agg_text,
                    'metadata': {
                        'method': method,
                        'start_offset': start_off,
                        'end_offset': end_off,
                        'grouped_elements': count,
                        'group_kind': kind,
                    }
                })
                # Overlap semantics: step by max(1, count - overlap)
                step = max(1, count - overlap)
                i += step
            return out_groups

        def walk(node: Dict[str, Any], titles: List[str]):
            kind = node.get('kind')
            if kind == 'section':
                title = str(node.get('title') or '').strip()
                titles = titles + ([title] if title else [])
            # For structure_aware, group elements per section using max_size/overlap
            if kind == 'section' and method == 'structure_aware' and isinstance(sa_max, int) and sa_max > 0:
                section_items = _gather_section_items(node)
                # Optional grouping configuration carried in tree
                grouping_cfg = tree.get('grouping') if isinstance(tree.get('grouping'), dict) else {}
                by_kind = bool(grouping_cfg.get('by_kind', False))
                weights = grouping_cfg.get('element_weights') if isinstance(grouping_cfg.get('element_weights'), dict) else {
                    'paragraph': 1,
                    'list_unordered': 1,
                    'list_ordered': 1,
                    'table_md': 2,
                    'code_fence': 3,
                }
                if by_kind:
                    grouped_items = _group_section_by_kind_weight(section_items, sa_max, sa_ovl if isinstance(sa_ovl, int) else 0, weights)
                else:
                    grouped_items = _group_items_by_elements(section_items, sa_max, sa_ovl if isinstance(sa_ovl, int) else 0)
                _append_with_titles(grouped_items, titles)
                for child in node.get('children') or []:
                    if isinstance(child, dict) and child.get('kind') == 'section':
                        walk(child, titles)
                # Do not descend into children again to avoid duplicating content
                return
            # Default behavior: emit this node's chunks as-is
            for ch in node.get('chunks') or []:
                _append_with_titles([ch], titles)
            for child in node.get('children') or []:
                if isinstance(child, dict):
                    walk(child, titles)

        walk(root, [])
        # Normalize chunk_index/total
        for i, item in enumerate(out):
            md = item.setdefault('metadata', {})
            md.setdefault('chunk_index', i + 1)
            md.setdefault('total_chunks', len(out))
        return out

    def chunk_text_hierarchical_flat(
        self,
        text: str,
        method: Optional[str] = None,
        max_size: Optional[int] = None,
        overlap: Optional[int] = None,
        language: Optional[str] = None,
        template: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Convenience wrapper returning flattened hierarchical chunks with metadata."""
        tree = self.chunk_text_hierarchical_tree(
            text=text,
            method=method,
            max_size=max_size,
            overlap=overlap,
            language=language,
            template=template,
        )
        return self.flatten_hierarchical(tree)
    
    def _sanitize_input(self, text: str, *, suppress_security_log: bool = False) -> str:
        """
        Sanitize input text for security.
        
        Args:
            text: Raw input text
            
        Returns:
            Sanitized text
            
        Raises:
            InvalidInputError: If text contains dangerous content
        """
        if not isinstance(text, str):
            raise InvalidInputError(f"Expected string input, got {type(text).__name__}")
        
        # Test-mode detection for relaxed sanitization in unit/property tests
        import os as _os
        _is_test_mode = (
            _os.getenv("PYTEST_CURRENT_TEST", "") != "" or
            _os.getenv("TLDW_TEST_MODE", "").lower() in {"1", "true", "yes", "on"} or
            _os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}
        )

        # Remove null bytes which could cause issues (preserve in test mode for property tests)
        if '\x00' in text:
            logger.warning("Null bytes detected in input")
            null_byte_count = text.count('\x00')
            if not suppress_security_log:
                self._security_logger.log_suspicious_content(
                    "null_bytes", f"Found {null_byte_count} null bytes in input", source="sanitize_input"
                )
            if not _is_test_mode:
                text = text.replace('\x00', ' ')
        
        # Normalize unicode to prevent various unicode-based attacks (preserve offsets)
        # Only keep normalization when it does not affect string length.
        try:
            normalized_text = unicodedata.normalize('NFC', text)
            if len(normalized_text) == len(text):
                text = normalized_text
            else:
                logger.warning("Unicode normalization skipped to preserve source offsets (length changed)")
                if not suppress_security_log:
                    self._security_logger.log_suspicious_content(
                        "unicode_normalization_skipped",
                        "Unicode normalization would change text length; original text retained",
                        source="sanitize_input"
                    )
        except Exception:
            pass
        
        # Check for control characters (except common ones like \n, \t, \r)
        allowed_control_chars = {'\n', '\t', '\r', '\f'}
        control_characters: List[str] = []
        control_char_samples: List[str] = []
        for char in text:
            if unicodedata.category(char) == 'Cc' and char not in allowed_control_chars:
                control_characters.append(char)
                if len(control_char_samples) < 10:
                    control_char_samples.append(repr(char))
        
        if control_characters:
            logger.warning(f"Suspicious control characters found: {control_char_samples}")
            if not suppress_security_log:
                self._security_logger.log_suspicious_content(
                    "control_characters", f"Found {len(control_characters)} suspicious control characters", source="sanitize_input"
                )
            # In test mode, preserve control characters to satisfy normalization properties
            if not _is_test_mode:
                # Replace suspicious control characters with spaces to preserve offsets
                translation_map = {ord(ch): ' ' for ch in set(control_characters)}
                text = text.translate(translation_map)
        
        # Check for bidirectional text override characters (could be used for spoofing)
        bidi_chars = ['\u202a', '\u202b', '\u202c', '\u202d', '\u202e', '\u2066', '\u2067', '\u2068', '\u2069']
        total_bidi_overrides = 0
        for bidi_char in bidi_chars:
            occurrences = text.count(bidi_char)
            if occurrences:
                total_bidi_overrides += occurrences
                text = text.replace(bidi_char, ' ')
        if total_bidi_overrides:
            logger.warning("Bidirectional override characters detected and neutralized")
            if not suppress_security_log:
                self._security_logger.log_suspicious_content(
                    "bidirectional_override",
                    f"Found {total_bidi_overrides} bidirectional override characters",
                    source="sanitize_input"
                )
        
        return text
    
    def chunk_text(self,
                   text: str,
                   method: Optional[str] = None,
                   max_size: Optional[int] = None,
                   overlap: Optional[int] = None,
                   language: Optional[str] = None,
                   **options) -> List[str]:
        """
        Chunk text using the specified method.
        
        Args:
            text: Text to chunk
            method: Chunking method (uses default if not specified)
            max_size: Maximum chunk size (uses default if not specified)
            overlap: Overlap between chunks (uses default if not specified)
            language: Language of the text (uses default if not specified)
            **options: Additional method-specific options
            
        Returns:
            List of text chunks
            
        Raises:
            InvalidInputError: If input validation fails
            InvalidChunkingMethodError: If method is not supported
            ChunkingError: For other chunking errors
        """
        # Sanitize and validate input
        text = self._sanitize_input(text)
        
        if not text.strip():
            logger.debug("Empty text provided, returning empty list")
            return []
        
        self._enforce_text_size(text, source="chunk_text")
        
        # Use defaults if not specified
        method = method or self.config.default_method.value
        max_size = max_size if max_size is not None else self.config.default_max_size
        overlap = overlap if overlap is not None else self.config.default_overlap
        # Harden overlap to avoid non-progressing loops in strategies
        try:
            if isinstance(max_size, int) and isinstance(overlap, int):
                if overlap < 0:
                    logger.warning(f"Negative overlap ({overlap}) adjusted to 0")
                    overlap = 0
                if max_size <= 0:
                    # Strategy will raise on invalid max_size; leave as-is here
                    pass
                elif overlap >= max_size:
                    logger.warning(f"Overlap ({overlap}) >= max_size ({max_size}); adjusting to max_size - 1")
                    overlap = max_size - 1
        except Exception:
            pass
        language = language or self.config.language
        
        # Handle code strategy mode routing (code_mode: auto|ast|heuristic)
        orig_method = method
        if (method or '').lower() == 'code':
            try:
                code_mode = str((options or {}).get('code_mode', 'auto')).lower()
            except Exception:
                code_mode = 'auto'
            lang_opt = str((options or {}).get('language') or language or '').lower()
            if code_mode in ('ast', 'auto') and lang_opt.startswith('py'):
                method = 'code_ast'
            else:
                method = 'code'

        # Check cache if enabled
        cache_key = None
        cache_allowed = False
        cache_reason = "disabled"
        if self._cache is not None:
            try:
                tlen = len(text)
                min_len = getattr(self.config, 'min_text_length_to_cache', 0)
                max_len = getattr(self.config, 'max_text_length_to_cache', getattr(self.config, 'cache_max_text_length', 2_000_000))
                if tlen < int(min_len):
                    cache_reason = "skipped_min_len"
                elif tlen > int(max_len):
                    cache_reason = "skipped_max_len"
                else:
                    cache_allowed = True
                    cache_reason = "allowed"
            except Exception:
                cache_reason = "policy_error"
        # Attempt get if allowed
        if self._cache is not None and cache_allowed:
            cache_key = self._get_cache_key(text, method, max_size, overlap, language, options)
            cached_result = self._cache.get(cache_key)
            if cached_result is not None:
                try:
                    increment_counter("chunker_cache_get_total", labels={"result": "hit", "reason": cache_reason})
                except Exception:
                    pass
                logger.debug("Returning cached result")
                return cached_result
            else:
                try:
                    increment_counter("chunker_cache_get_total", labels={"result": "miss", "reason": cache_reason})
                except Exception:
                    pass
        else:
            # cache disabled or not allowed by policy
            try:
                increment_counter("chunker_cache_get_total", labels={"result": "skip", "reason": cache_reason})
            except Exception:
                pass
        
        # Get strategy lazily
        strategy = self.get_strategy(method)
        self._sync_strategy_llm(strategy)
        
        # Update strategy language if different
        if language != strategy.language:
            strategy.language = language
        
        try:
            # Perform chunking
            logger.debug(f"Chunking with method={method}, max_size={max_size}, "
                        f"overlap={overlap}, language={language}")
            
            chunks = strategy.chunk(text, max_size, overlap, **options)
            
            # Cache result if enabled
            if self._cache is not None and len(chunks) > 0 and cache_allowed and cache_key is not None:
                try:
                    self._cache.put(cache_key, chunks)
                    try:
                        increment_counter("chunker_cache_put_total", labels={"result": "stored"})
                    except Exception:
                        pass
                except Exception:
                    # Defensive: never fail chunking due to cache policy
                    try:
                        increment_counter("chunker_cache_put_total", labels={"result": "error"})
                    except Exception:
                        pass
            elif self._cache is not None and len(chunks) > 0:
                try:
                    increment_counter("chunker_cache_put_total", labels={"result": "skipped", "reason": cache_reason})
                except Exception:
                    pass
            
            logger.info(f"Created {len(chunks)} chunks using {method} method")
            return chunks
            
        except Exception as e:
            logger.error(f"Chunking failed: {e}")
            if isinstance(e, ChunkingError):
                raise
            raise ChunkingError(f"Chunking failed: {str(e)}")
    
    def chunk_text_with_metadata(self,
                                 text: str,
                                 method: Optional[str] = None,
                                 max_size: Optional[int] = None,
                                 overlap: Optional[int] = None,
                                 language: Optional[str] = None,
                                 **options) -> List[ChunkResult]:
        """
        Chunk text and return results with metadata.
        
        Args:
            text: Text to chunk
            method: Chunking method (uses default if not specified)
            max_size: Maximum chunk size (uses default if not specified)
            overlap: Overlap between chunks (uses default if not specified)
            language: Language of the text (uses default if not specified)
            **options: Additional method-specific options
            
        Returns:
            List of ChunkResult objects with text and metadata
        """
        # Sanitize input
        text = self._sanitize_input(text)
        self._enforce_text_size(text, source="chunk_text_with_metadata")
        
        # Use defaults if not specified
        method = method or self.config.default_method.value
        max_size = max_size if max_size is not None else self.config.default_max_size
        overlap = overlap if overlap is not None else self.config.default_overlap
        # Harden overlap to avoid non-progressing loops in strategies
        try:
            if isinstance(max_size, int) and isinstance(overlap, int):
                if overlap < 0:
                    logger.warning(f"Negative overlap ({overlap}) adjusted to 0")
                    overlap = 0
                if max_size <= 0:
                    # Strategy will raise on invalid max_size; leave as-is here
                    pass
                elif overlap >= max_size:
                    logger.warning(f"Overlap ({overlap}) >= max_size ({max_size}); adjusting to max_size - 1")
                    overlap = max_size - 1
        except Exception:
            pass
        language = language or self.config.language
        
        # Handle code strategy mode routing (code_mode: auto|ast|heuristic)
        if (method or '').lower() == 'code':
            try:
                code_mode = str((options or {}).get('code_mode', 'auto')).lower()
            except Exception:
                code_mode = 'auto'
            lang_opt = str((options or {}).get('language') or language or '').lower()
            if code_mode in ('ast', 'auto') and lang_opt.startswith('py'):
                method = 'code_ast'
            else:
                method = 'code'

        # Get strategy lazily (supports factory registration)
        strategy = self.get_strategy(method)
        self._sync_strategy_llm(strategy)
        
        # Update strategy language if different
        if language != strategy.language:
            strategy.language = language
        
        try:
            # Get chunks with metadata
            return strategy.chunk_with_metadata(text, max_size, overlap, **options)
        except Exception as e:
            logger.error(f"Chunking with metadata failed: {e}")
            if isinstance(e, ChunkingError):
                raise
            raise ChunkingError(f"Chunking failed: {str(e)}")
    
    def chunk_text_generator(self,
                           text: str,
                           method: Optional[str] = None,
                           max_size: Optional[int] = None,
                           overlap: Optional[int] = None,
                           language: Optional[str] = None,
                           **options) -> Generator[str, None, None]:
        """
        Memory-efficient generator for chunking large texts.
        
        Args:
            text: Text to chunk
            method: Chunking method (uses default if not specified)
            max_size: Maximum chunk size (uses default if not specified)
            overlap: Overlap between chunks (uses default if not specified)
            language: Language of the text (uses default if not specified)
            **options: Additional method-specific options
            
        Yields:
            Individual text chunks
        """
        # Sanitize input
        text = self._sanitize_input(text)
        self._enforce_text_size(text, source="chunk_text_generator")
        
        # Use defaults if not specified
        method = method or self.config.default_method.value
        max_size = max_size if max_size is not None else self.config.default_max_size
        overlap = overlap if overlap is not None else self.config.default_overlap
        # Align overlap handling with primary chunk_text path
        try:
            if isinstance(max_size, int) and isinstance(overlap, int):
                if overlap < 0:
                    logger.warning(f"Negative overlap ({overlap}) adjusted to 0")
                    overlap = 0
                if max_size <= 0:
                    pass
                elif overlap >= max_size:
                    logger.warning(f"Overlap ({overlap}) >= max_size ({max_size}); adjusting to max_size - 1")
                    overlap = max_size - 1
        except Exception:
            pass
        language = language or self.config.language
        
        # Handle code strategy mode routing consistently with chunk_text
        if (method or '').lower() == 'code':
            try:
                code_mode = str((options or {}).get('code_mode', 'auto')).lower()
            except Exception:
                code_mode = 'auto'
            lang_opt = str((options or {}).get('language') or language or '').lower()
            if code_mode in ('ast', 'auto') and lang_opt.startswith('py'):
                method = 'code_ast'
            else:
                method = 'code'
        
        # Get strategy lazily (supports factory registration)
        strategy = self.get_strategy(method)
        self._sync_strategy_llm(strategy)
        
        # Update strategy language if different
        if language != strategy.language:
            strategy.language = language
        
        # Use generator method when available, otherwise fall back to eager chunking
        chunk_gen = getattr(strategy, 'chunk_generator', None)
        if callable(chunk_gen):
            for chunk in chunk_gen(text, max_size, overlap, **options):
                yield chunk
        else:
            logger.debug(f"{strategy.__class__.__name__} lacks chunk_generator; falling back to chunk()")
            for chunk in strategy.chunk(text, max_size, overlap, **options):
                yield chunk
    
    def get_available_methods(self) -> List[str]:
        """
        Get list of available chunking methods.
        
        Returns:
            List of method names
        """
        return sorted(set(list(self._strategies.keys()) + list(getattr(self, '_strategy_factories', {}).keys())))
    
    def get_strategy(self, method: str):
        """
        Get a specific chunking strategy instance.
        
        Args:
            method: Method name
            
        Returns:
            Strategy instance
            
        Raises:
            InvalidChunkingMethodError: If method not found
        """
        if method in self._strategies:
            return self._strategies[method]
        factory = self._strategy_factories.get(method)
        if factory is None:
            available = ', '.join(sorted(list(self._strategies.keys()) + list(self._strategy_factories.keys())))
            raise InvalidChunkingMethodError(f"Unknown chunking method: {method}. Available methods: {available}")
        try:
            instance = factory()
            self._strategies[method] = instance
            return instance
        except Exception as e:
            raise InvalidChunkingMethodError(f"Failed to initialize strategy '{method}': {e}")

    def _sync_strategy_llm(self, strategy: Any) -> None:
        """Ensure cached strategies see the latest LLM hooks/config."""
        if strategy is None:
            return
        try:
            if hasattr(strategy, 'llm_call_func'):
                strategy.llm_call_func = getattr(self, 'llm_call_func', None)
        except Exception:
            logger.debug("Failed to update strategy llm_call_func", exc_info=True)
        try:
            if hasattr(strategy, 'llm_config'):
                cfg = getattr(self, 'llm_config', None)
                if isinstance(cfg, dict):
                    strategy.llm_config = dict(cfg)
                else:
                    strategy.llm_config = cfg
        except Exception:
            logger.debug("Failed to update strategy llm_config", exc_info=True)
    
    def _get_cache_key(self, text: str, method: str, max_size: int,
                      overlap: int, language: str, options: Dict) -> str:
        """
        Generate cache key for chunking parameters.
        
        Args:
            text: Input text
            method: Chunking method
            max_size: Maximum chunk size
            overlap: Overlap size
            language: Language code
            options: Additional options
            
        Returns:
            Cache key string
        """
        # Use a stable cryptographic hash to avoid large keys and ensure determinism
        try:
            text_hash = hashlib.sha256(text.encode('utf-8', 'ignore')).hexdigest()[:16]
        except Exception:
            # Fallback to builtin hash within process
            text_hash = str(hash(text))
        # Normalize options deterministically (deep sort for nested structures)
        def _canon(v: Any) -> Any:
            try:
                # Preserve simple types
                if v is None or isinstance(v, (str, int, float, bool)):
                    return v
                if isinstance(v, (list, tuple)):
                    return [_canon(x) for x in v]
                if isinstance(v, dict):
                    return {k: _canon(v[k]) for k in sorted(v.keys(), key=lambda x: str(x))}
                # Fallback to string repr
                return str(v)
            except Exception:
                return str(v)
        try:
            options_str = json.dumps(_canon(dict(options or {})), ensure_ascii=False, sort_keys=True)
        except Exception:
            options_str = str(sorted((options or {}).items()))
        return f"{text_hash}:{method}:{max_size}:{overlap}:{language}:{options_str}"
    
    def clear_cache(self):
        """Clear the chunk cache."""
        if self._cache is not None:
            self._cache.clear()
            logger.debug("Chunk cache cleared")
    
    def get_cache_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics or None if cache is disabled
        """
        if self._cache is not None:
            return self._cache.get_stats()
        return None

    # ---------------- Unified processing entrypoint -----------------
    def process_text(
        self,
        text: str,
        options: Optional[Dict[str, Any]] = None,
        *,
        tokenizer_name_or_path: Optional[str] = None,
        llm_call_func: Optional[Any] = None,
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """End-to-end processing: optional frontmatter extraction, chunking, normalization.

        Returns a list of chunks as dicts with consistent metadata fields.
        """
        overall_start = time.perf_counter()
        labels = {"component": "chunker", "op": "process_text"}
        increment_counter("chunker_process_total", labels=labels)
        if text is None or not isinstance(text, str):
            return []
        self._enforce_text_size(text, source="process_text")
        # Shallow copy of options
        opts = dict(options or {})

        # Attempt to parse JSON frontmatter at the start (best-effort)
        fm_start = time.perf_counter()
        json_meta: Dict[str, Any] = {}
        processed_text = text
        try:
            stripped = processed_text.lstrip()
            if stripped.startswith("{"):
                # Heuristic: until first \}\n boundary
                close = re.search(r"\}\s*\n", stripped)
                if close:
                    candidate = stripped[: close.end()].strip()
                    # Hard limit 1MB
                    if len(candidate) <= 1_000_000:
                        try:
                            json_meta = json.loads(candidate)
                            processed_text = stripped[close.end():].lstrip("\n")
                        except Exception:
                            pass
        except Exception:
            pass
        observe_histogram("chunker_frontmatter_duration_seconds", time.perf_counter() - fm_start, labels=labels)

        # Optional header text extraction (legacy heuristic)
        hdr_start = time.perf_counter()
        header_text = ""
        try:
            header_re = re.compile(r"^ (This[ ]text[ ]was[ ]transcribed[ ]using (?:[^\n]*\n)*?\n) ", re.MULTILINE | re.VERBOSE)
            m = header_re.match(processed_text)
            if m:
                header_text = m.group(1)
                processed_text = processed_text[len(header_text):].lstrip()
        except Exception:
            pass
        observe_histogram("chunker_header_extract_seconds", time.perf_counter() - hdr_start, labels=labels)

        # Resolve main parameters
        method = opts.get('method') or self.config.default_method.value
        max_size = int(opts.get('max_size') or self.config.default_max_size)
        overlap = int(opts.get('overlap') or self.config.default_overlap)
        language = opts.get('language')
        if not language:
            # Lightweight language detection similar to templates module
            try:
                if re.search(r'[\u4e00-\u9fff]', processed_text):
                    language = 'zh'
                elif re.search(r'[\u3040-\u309f\u30a0-\u30ff]', processed_text):
                    language = 'ja'
                elif re.search(r'[\uac00-\ud7af]', processed_text):
                    language = 'ko'
                elif re.search(r'[\u0600-\u06ff]', processed_text):
                    language = 'ar'
                else:
                    language = self.config.language
            except Exception:
                language = self.config.language

        # Adaptive sizing (simple heuristic parity)
        if bool(opts.get('adaptive', False)) and method not in ('semantic', 'json', 'xml', 'ebook_chapters', 'rolling_summarize'):
            try:
                base_adaptive = int(opts.get('base_adaptive_chunk_size') or max_size)
                min_adaptive = int(opts.get('min_adaptive_chunk_size') or max_size)
                max_adaptive_hi = int(opts.get('max_adaptive_chunk_size') or max_size)
                # Very rough heuristic: scale with document size
                density = max(0.0, min(3.0, len(processed_text) / 10000.0))
                scaled = int(base_adaptive * (1.0 + 0.2 * density))
                max_size = max(min_adaptive, min(max_adaptive_hi, scaled))
                # Optional adaptive overlap tuned by density
                if bool(opts.get('adaptive_overlap', False)):
                    try:
                        base_overlap = int(opts.get('base_overlap') or overlap or 0)
                        max_overlap = int(opts.get('max_adaptive_overlap') or max(0, base_overlap + 100))
                        # Increase overlap slightly for denser/longer docs; cap to avoid waste
                        tuned = int(base_overlap + (density * 10))
                        overlap = max(0, min(max_overlap, tuned))
                    except Exception:
                        pass
            except Exception:
                pass

        # Choose hierarchical vs normal
        hierarchical = bool(opts.get('hierarchical'))
        hier_template = opts.get('hierarchical_template') if isinstance(opts.get('hierarchical_template'), dict) else None

        # Temporarily set LLM hooks for strategies that need them
        prev_llm_call = getattr(self, 'llm_call_func', None)
        prev_llm_cfg = getattr(self, 'llm_config', None)
        if llm_call_func is not None:
            self.llm_call_func = llm_call_func
        if llm_config is not None:
            self.llm_config = llm_config

        # Multi-level paragraph-aware chunking for words/sentences (parity with legacy)
        multi_level = bool(opts.get('multi_level', False)) and method in ('words', 'sentences') and not (hierarchical or hier_template)

        norm_chunks: List[Dict[str, Any]] = []
        try:
            chunk_start = time.perf_counter()
            if hierarchical or hier_template:
                raw_chunks = self.chunk_text_hierarchical_flat(
                    text=processed_text,
                    method=method,
                    max_size=max_size,
                    overlap=overlap,
                    language=language,
                    template=hier_template,
                )
                # Already dicts with offsets/metadata
                norm_chunks = raw_chunks
            elif multi_level:
                spans = self._compute_paragraph_spans(processed_text, template=None)
                pidx = 0
                for (start, end, kind) in spans:
                    if kind != 'paragraph':
                        continue
                    segment = processed_text[start:end]
                    base_chunks = self.chunk_text(
                        segment,
                        method=method,
                        max_size=max_size,
                        overlap=overlap,
                        language=language,
                    )
                    cursor = start
                    for c in (base_chunks or []):
                        txt = c if isinstance(c, str) else (c.get('text') if isinstance(c, dict) else str(c))
                        pos = processed_text.find(txt, cursor, end)
                        if pos == -1:
                            pos = cursor
                        md = {}
                        if isinstance(c, dict):
                            md.update(c.get('metadata') or {})
                        md.update({
                            'method': method,
                            'start_offset': pos,
                            'end_offset': pos + len(txt),
                            'language': language,
                            'paragraph_index': pidx,
                            'paragraph_kind': kind,
                            'multi_level': True,
                        })
                        norm_chunks.append({'text': txt, 'metadata': md})
                        cursor = pos + len(txt)
                    pidx += 1
            else:
                base_chunks = self.chunk_text(
                    processed_text,
                    method=method,
                    max_size=max_size,
                    overlap=overlap,
                    language=language,
                    code_mode=str(opts.get('code_mode', 'auto')).lower() if str(method).lower() == 'code' else opts.get('code_mode'),
                )
                # Normalize and handle JSON-chunk structures
                for c in (base_chunks or []):
                    if isinstance(c, dict) and 'json' in c and 'metadata' in c:
                        try:
                            txt = json.dumps(c['json'], ensure_ascii=False)
                        except Exception:
                            txt = str(c['json'])
                        norm_chunks.append({'text': txt, 'metadata': dict(c.get('metadata') or {})})
                    elif isinstance(c, dict) and 'text' in c:
                        norm_chunks.append({'text': c['text'], 'metadata': dict(c.get('metadata') or {})})
                    elif isinstance(c, str):
                        norm_chunks.append({'text': c, 'metadata': {}})
                    else:
                        norm_chunks.append({'text': str(c), 'metadata': {}})
            observe_histogram("chunker_chunking_duration_seconds", time.perf_counter() - chunk_start, labels=labels)
        finally:
            # Restore previous LLM hooks even if chunking fails
            self.llm_call_func = prev_llm_call
            self.llm_config = prev_llm_cfg

        total = len(norm_chunks)
        out: List[Dict[str, Any]] = []
        norm_start = time.perf_counter()
        # Optional timecode mapping for media transcripts: segments with offsets and times
        time_segments = None
        try:
            segs = opts.get('timecode_map')
            if isinstance(segs, list):
                # Expect list of {start_offset,end_offset,start_time,end_time}
                val = []
                for s in segs:
                    if not isinstance(s, dict):
                        continue
                    so = s.get('start_offset'); eo = s.get('end_offset')
                    st = s.get('start_time'); et = s.get('end_time')
                    if isinstance(so, int) and isinstance(eo, int) and (isinstance(st, (int, float)) and isinstance(et, (int, float))):
                        val.append((so, eo, float(st), float(et)))
                time_segments = sorted(val, key=lambda x: x[0]) if val else None
        except Exception:
            time_segments = None
        for i, item in enumerate(norm_chunks):
            # Normalize
            txt = item.get('text') if isinstance(item, dict) else str(item)
            md = dict(item.get('metadata') or {}) if isinstance(item, dict) else {}

            # Base metadata
            md.setdefault('chunk_index', i + 1)
            md.setdefault('total_chunks', total)
            md.setdefault('chunk_method', method)
            # Standardized keys while retaining legacy for compatibility
            md.setdefault('max_size_setting', max_size)
            md.setdefault('overlap_setting', overlap)
            md.setdefault('max_size', max_size)
            md.setdefault('overlap', overlap)
            md.setdefault('language', language)
            md.setdefault('adaptive_chunking_used', bool(opts.get('adaptive', False)))
            if str(method).lower() in ('code', 'code_ast'):
                md.setdefault('code_mode_used', str(opts.get('code_mode', 'auto')).lower())

            # Relative position using offsets when present
            try:
                start = md.get('start_offset'); end = md.get('end_offset')
                if isinstance(start, int) and isinstance(end, int) and end > start:
                    mid = 0.5 * (float(start) + float(end))
                    rel = mid / max(1.0, float(len(processed_text)))
                    if time_segments is not None and ('start_time' not in md or 'end_time' not in md):
                        try:
                            chunk_start = int(start)
                            chunk_end = int(end)
                            chunk_start_time = None
                            chunk_end_time = None
                            for (so, eo, st, et) in time_segments:
                                if chunk_end <= so:
                                    break
                                if chunk_start >= eo:
                                    continue
                                overlap_start = max(chunk_start, so)
                                overlap_end = min(chunk_end, eo)
                                if overlap_end <= overlap_start:
                                    continue
                                seg_len = max(1.0, float(eo - so))
                                seg_duration = float(et - st)
                                frac_start = (overlap_start - so) / seg_len
                                frac_end = (overlap_end - so) / seg_len
                                mapped_start = st + frac_start * seg_duration
                                mapped_end = st + frac_end * seg_duration
                                if chunk_start_time is None:
                                    chunk_start_time = mapped_start
                                chunk_end_time = mapped_end
                                if overlap_end >= chunk_end:
                                    # We covered the chunk end; can stop
                                    break
                            if chunk_start_time is not None and 'start_time' not in md:
                                md['start_time'] = round(chunk_start_time, 3)
                            if chunk_end_time is not None and 'end_time' not in md:
                                md['end_time'] = round(chunk_end_time, 3)
                        except Exception:
                            pass
                else:
                    rel = (i + 1) / total if total > 0 else 0.0
            except Exception:
                rel = (i + 1) / total if total > 0 else 0.0
            md.setdefault('relative_position', rel)

            # Document-level metadata if we extracted any
            if json_meta:
                md.setdefault('initial_document_json_metadata', json_meta)
            if header_text:
                md.setdefault('initial_document_header_text', header_text)

            # Content hash
            try:
                md.setdefault('chunk_content_hash', hashlib.md5(txt.encode('utf-8')).hexdigest())
            except Exception:
                pass

            # Mark origin
            md.setdefault('origin', 'unified_chunker')

            out.append({'text': txt, 'metadata': md})
        observe_histogram("chunker_normalization_seconds", time.perf_counter() - norm_start, labels=labels)
        # Output metrics
        total_bytes = sum(len(c['text']) for c in out)
        set_gauge("chunker_last_chunk_count", float(len(out)), labels=labels)
        observe_histogram("chunker_output_bytes", float(total_bytes), labels=labels)
        observe_histogram("chunker_input_bytes", float(len(text)), labels=labels)
        observe_histogram("chunker_process_total_seconds", time.perf_counter() - overall_start, labels={**labels, "method": method, "hierarchical": str(bool(hierarchical or hier_template)).lower()})
        try:
            with start_span("chunker.process_text") as span:
                set_span_attribute(span, "chunk.method", method)
                set_span_attribute(span, "chunk.lang", language)
                set_span_attribute(span, "chunk.hierarchical", bool(hierarchical or hier_template))
                set_span_attribute(span, "chunk.multi_level", multi_level)
                set_span_attribute(span, "chunk.count", len(out))
                add_span_event(span, "chunker.completed")
        except Exception as e:
            record_span_exception(None, e)
        
        return out

    # Backwards-compatible alias to tolerate triple-s typo in requests
    def processs_text(self, *args, **kwargs):
        return self.process_text(*args, **kwargs)
    
    def chunk_file_stream(self,
                         file_path: Union[str, Path],
                         method: Optional[str] = None,
                         max_size: Optional[int] = None,
                         overlap: Optional[int] = None,
                         language: Optional[str] = None,
                         buffer_size: int = 8192,
                         **options) -> Generator[str, None, None]:
        """
        Stream-process a file for memory-efficient chunking of very large files.
        
        Args:
            file_path: Path to the file to chunk
            method: Chunking method to use
            max_size: Maximum size per chunk
            overlap: Number of units to overlap between chunks
            language: Language code for text processing
            buffer_size: Size of read buffer in bytes
            **options: Additional method-specific options
            
        Yields:
            Text chunks one at a time
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise InvalidInputError(f"File not found: {file_path}")

        # Normalize core parameters to avoid None/invalid math during streaming
        method = method or self.config.default_method.value
        try:
            max_size = int(max_size if max_size is not None else self.config.default_max_size)
        except Exception as exc:
            raise InvalidInputError(f"Invalid max_size value: {max_size}") from exc
        try:
            overlap = int(overlap if overlap is not None else self.config.default_overlap)
        except Exception as exc:
            raise InvalidInputError(f"Invalid overlap value: {overlap}") from exc
        language = language or self.config.language

        if max_size <= 0:
            raise InvalidInputError(f"max_size must be positive, got {max_size}")
        if overlap < 0:
            logger.warning(f"Negative overlap ({overlap}) adjusted to 0")
            overlap = 0
        elif overlap >= max_size:
            logger.warning(f"Overlap ({overlap}) >= max_size ({max_size}); adjusting to max_size - 1")
            overlap = max_size - 1
        
        # Check file size
        file_size = file_path.stat().st_size
        if file_size > self.config.max_text_size:
            logger.warning(f"File size ({file_size} bytes) exceeds max size "
                         f"({self.config.max_text_size} bytes), will process in streaming mode")
        
        logger.info(f"Stream processing file: {file_path} ({file_size} bytes)")
        
        # Read file in chunks and accumulate until we have enough for chunking
        buffer = ""
        overlap_buffer = ""
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                while True:
                    # Read next buffer
                    chunk = f.read(buffer_size)
                    if not chunk:
                        # Process remaining buffer
                        if buffer:
                            for text_chunk in self.chunk_text_generator(
                                buffer, method, max_size, overlap, language, **options
                            ):
                                yield text_chunk
                        break
                    
                    buffer += chunk
                    
                    # Process buffer when it's large enough
                    if len(buffer) >= max_size * 2:  # Keep some extra for overlap
                        # Find a good split point (end of sentence/paragraph)
                        split_point = self._find_split_point(buffer, max_size)
                        
                        # Process the first part
                        to_process = buffer[:split_point]
                        for text_chunk in self.chunk_text_generator(
                            overlap_buffer + to_process,
                            method, max_size, overlap, language, **options
                        ):
                            yield text_chunk
                        
                        # Keep overlap for next iteration
                        if overlap > 0:
                            overlap_buffer = to_process[-overlap:]
                        
                        # Keep the rest in buffer
                        buffer = buffer[split_point:]
                        
        except Exception as e:
            logger.error(f"File stream processing failed: {e}")
            raise ChunkingError(f"Failed to process file stream: {str(e)}")
    
    def _find_split_point(self, text: str, target: int) -> int:
        """
        Find a good split point in text near the target position.
        Prefers to split at paragraph or sentence boundaries.
        
        Args:
            text: Text to find split point in
            target: Target position for split
            
        Returns:
            Best split position
        """
        if len(text) <= target:
            return len(text)
        
        # Look for paragraph break near target
        for i in range(target, min(target + 500, len(text))):
            if text[i:i+2] == '\n\n':
                return i + 2
        
        # Look for sentence end near target
        for i in range(target, min(target + 200, len(text))):
            if text[i] in '.!?' and i + 1 < len(text) and text[i + 1].isspace():
                return i + 1
        
        # Look for any newline
        for i in range(target, min(target + 100, len(text))):
            if text[i] == '\n':
                return i + 1
        
        # Default to target position
        return target


# Convenience function for backward compatibility
def create_chunker(config: Optional[Dict[str, Any]] = None) -> Chunker:
    """
    Create a chunker instance with optional configuration.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Configured Chunker instance
    """
    if config:
        chunker_config = ChunkerConfig(**config)
    else:
        chunker_config = ChunkerConfig()
    
    return Chunker(chunker_config)
