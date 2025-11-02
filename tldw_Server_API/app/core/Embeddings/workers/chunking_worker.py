# chunking_worker.py
# Worker for processing text chunking tasks

import hashlib
import json as _json
import os
import re
from typing import Any, Dict, List, Optional

from loguru import logger
import unicodedata

# Optional v2 chunker for consistent chunk semantics
try:
    from tldw_Server_API.app.core.Chunking.chunker import Chunker as V2Chunker
    from tldw_Server_API.app.core.Chunking.templates import TemplateManager
except Exception:  # graceful import failure for isolated tests/envs
    V2Chunker = None  # type: ignore
    TemplateManager = None  # type: ignore

from ..queue_schemas import (
    ChunkData,
    ChunkingMessage,
    EmbeddingMessage,
    JobStatus,
    ChunkingConfig,
)
from .base_worker import BaseWorker, WorkerConfig
from tldw_Server_API.app.core.Utils.pydantic_compat import model_dump_compat
from ..messages import normalize_message
from tldw_Server_API.app.core.Chunking.constants import (
    ensure_frontmatter_metadata,
    prepend_frontmatter,
)


class _ChunkString(str):
    """String subclass that carries boundary whitespace preservation hints."""

    def __new__(cls, value: str, leading_preserve: bool = False, trailing_preserve: bool = False):
        obj = str.__new__(cls, value)
        obj._chunk_leading_preserve = leading_preserve
        obj._chunk_trailing_preserve = trailing_preserve
        return obj


class ChunkingWorker(BaseWorker):
    """Worker that processes text chunking tasks

    Behavior:
    - Uses the v2 Chunker (words-based) by default for consistency with API/templates,
      producing chunks with accurate start/end offsets.
    - Gracefully falls back to simple character-based chunking with optional
      separator-aware splits if Chunker is unavailable.
    """

    def __init__(self, config: WorkerConfig):
        super().__init__(config)
        self.embedding_queue = config.queue_name.replace("chunking", "embedding")
        # Initialize v2 chunker if available
        self._v2_chunker = None
        self._template_mgr = None
        if V2Chunker is not None:
            try:
                self._v2_chunker = V2Chunker()
                logger.debug("Initialized v2 Chunker for embeddings chunking worker")
            except Exception as e:
                logger.warning(f"Failed to initialize v2 Chunker; will use simple chunking. Error: {e}")
        if TemplateManager is not None:
            try:
                self._template_mgr = TemplateManager()
            except Exception as e:
                logger.warning(f"Failed to initialize TemplateManager; templates will be unavailable. Error: {e}")

    def _parse_message(self, data: Dict[str, Any]) -> ChunkingMessage:
        """Parse raw message data into ChunkingMessage"""
        norm = normalize_message("chunking", data)
        return ChunkingMessage(**norm)

    async def process_message(self, message: ChunkingMessage) -> Optional[EmbeddingMessage]:
        """Process chunking message and create chunks"""
        logger.bind(job_id=message.job_id, stage="chunking").info(
            f"Processing chunking job {message.job_id} for media {message.media_id}"
        )

        source_metadata: Dict[str, Any] = {}
        if isinstance(message.source_metadata, dict):
            source_metadata = ensure_frontmatter_metadata(message.source_metadata)

        try:
            # Update job status
            await self._update_job_status(message.job_id, JobStatus.CHUNKING)

            # Perform chunking
            chunks = self._chunk_text(
                prepend_frontmatter(message.content, source_metadata),
                message.chunking_config,
            )

            # Create chunk data objects
            chunk_data_list = []
            for i, (chunk_text, start_idx, end_idx) in enumerate(chunks):
                chunk_id = self._generate_chunk_id(message.job_id, i)
                # Compute normalized content hash to enable cross-run embedding caching
                norm_txt = self._normalize_for_hash(chunk_text)
                content_hash = hashlib.sha256(norm_txt.encode('utf-8')).hexdigest()

                chunk_data = ChunkData(
                    chunk_id=chunk_id,
                    content=chunk_text,
                    metadata={
                        **source_metadata,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "content_type": message.content_type,
                        "content_hash": content_hash,
                        "hash_norm": "ws_v1"
                    },
                    start_index=start_idx,
                    end_index=end_idx,
                    sequence_number=i
                )
                chunk_data_list.append(chunk_data)

            # Update job progress
            await self._update_job_progress(message.job_id, 25, len(chunks))

            # Create embedding message for next stage
            embedding_message = EmbeddingMessage(
                job_id=message.job_id,
                user_id=message.user_id,
                media_id=message.media_id,
                priority=message.priority,
                user_tier=message.user_tier,
                created_at=message.created_at,
                idempotency_key=message.idempotency_key,
                dedupe_key=message.dedupe_key,
                operation_id=message.operation_id,
                trace_id=message.trace_id,
                chunks=chunk_data_list,
                embedding_model_config={},  # Populated later by embedding worker
                model_provider=""  # Populated later by embedding worker
            )

            logger.bind(job_id=message.job_id, stage="chunking").info(
                f"Created {len(chunks)} chunks for job {message.job_id}"
            )
            return embedding_message

        except Exception as e:
            logger.error(f"Error chunking content for job {message.job_id}: {e}")
            raise

    async def _send_to_next_stage(self, result: EmbeddingMessage):
        """Send chunked data to embedding queue"""
        # Priority routing: optional
        target_queue = self.embedding_queue
        try:
            if str(os.getenv("EMBEDDINGS_PRIORITY_ENABLED", "false")).lower() in ("1", "true", "yes"):
                # Check operator override first
                pr = None
                try:
                    key = f"embeddings:priority:override:{result.job_id}"
                    pr = await self.redis_client.get(key)
                except Exception:
                    pr = None
                # Map numeric priority to bucket when no override
                if not pr:
                    p = int(getattr(result, 'priority', 50) or 50)
                    if p >= 75:
                        pr = 'high'
                    elif p <= 25:
                        pr = 'low'
                    else:
                        pr = 'normal'
                target_queue = f"{self.embedding_queue}:{pr}"
        except Exception:
            target_queue = self.embedding_queue

        payload = model_dump_compat(result)
        try:
            fields = {k: (v if isinstance(v, str) else _json.dumps(v)) for k, v in payload.items()}
        except Exception:
            fields = {k: str(v) for k, v in payload.items()}
        await self.redis_client.xadd(target_queue, fields)
        logger.debug(f"Sent job {result.job_id} to embedding queue")

    def _chunk_text(self, text: str, *args, **kwargs) -> List[tuple[str, int, int]]:
        """Chunk helper supporting both legacy and v2-config signatures.

        - New: _chunk_text(text, cfg: ChunkingConfig)
        - Legacy: _chunk_text(text, chunk_size: int, overlap: int, separator: str)
        """
        # Build config from args/kwargs
        cfg: Optional[ChunkingConfig] = None
        if args:
            first = args[0]
            if isinstance(first, ChunkingConfig):
                cfg = first
            else:
                # Legacy positional: chunk_size, overlap, separator
                chunk_size = int(first)
                overlap = int(args[1]) if len(args) > 1 else 0
                separator = str(args[2]) if len(args) > 2 else "\n"
                # For very small legacy sizes, keep direct fallback semantics
                if chunk_size < 100:
                    return self._legacy_char_chunk(text, chunk_size, overlap, separator)
                cfg = ChunkingConfig(chunk_size=chunk_size, overlap=overlap, separator=separator)
        if cfg is None:
            # Attempt kwargs
            if 'cfg' in kwargs and isinstance(kwargs['cfg'], ChunkingConfig):
                cfg = kwargs['cfg']
            else:
                chunk_size = int(kwargs.get('chunk_size', 1000))
                overlap = int(kwargs.get('overlap', 200))
                separator = str(kwargs.get('separator', "\n"))
                if chunk_size < 100:
                    return self._legacy_char_chunk(text, chunk_size, overlap, separator)
                cfg = ChunkingConfig(chunk_size=chunk_size, overlap=overlap, separator=separator)
        """
        Split text into chunks with overlap.
        Returns list of (chunk_text, start_index, end_index) tuples.

        Order of precedence when v2 Chunker is available:
        1) If a template_name is provided, use TemplateManager to process text.
        2) Else, if a method is provided, use v2 Chunker with that method.
        3) Else, default to v2 Chunker with words-based chunking (char→word mapping).
        If v2 Chunker or TemplateManager are unavailable, use the legacy
        character-based fallback.
        """
        if not text:
            return []

        # Prefer v2 chunker for consistency with API/templates
        if self._v2_chunker is not None:
            try:
                # 1) Template path
                if getattr(cfg, 'template_name', None) and self._template_mgr is not None:
                    processed = self._template_mgr.process(text, cfg.template_name)
                    out: List[tuple[str, int, int]] = []
                    cursor = 0
                    for item in (processed or []):
                        if isinstance(item, dict) and 'text' in item:
                            chunk_text = str(item.get('text', '')).strip()
                        else:
                            chunk_text = str(item).strip()
                        if not chunk_text:
                            continue
                        idx = text.find(chunk_text, cursor)
                        if idx == -1:
                            idx = text.find(chunk_text)
                        if idx == -1:
                            continue
                        start_idx = idx
                        end_idx = idx + len(chunk_text)
                        out.append((chunk_text, start_idx, end_idx))
                        cursor = end_idx
                    if out:
                        return out

                # 2) Method path
                method = (cfg.method or 'words')
                unit = (cfg.unit or None)
                language = getattr(cfg, 'language', None)

                # If unit explicitly chars, use fallback
                if unit == 'chars' and method != 'tokens':
                    raise RuntimeError('fallback_char_unit')

                # Determine sizes (map char→words when unit is unspecified and default method 'words')
                chunk_size_val = int(cfg.chunk_size)
                overlap_val = int(cfg.overlap)
                if unit is None and method == 'words':
                    chunk_size_val = max(1, chunk_size_val // 5)
                    overlap_val = max(0, overlap_val // 5)

                results = self._v2_chunker.chunk_text_with_metadata(
                    text,
                    method=method,
                    max_size=chunk_size_val,
                    overlap=overlap_val,
                    language=language,
                )
                out2: List[tuple[str, int, int]] = []
                for r in results:
                    start_idx = int(getattr(r.metadata, 'start_char', 0) or 0)
                    end_idx = int(getattr(r.metadata, 'end_char', start_idx + len(r.text)) or (start_idx + len(r.text)))
                    if r.text and 0 <= start_idx <= end_idx <= len(text):
                        out2.append((r.text, start_idx, end_idx))
                if out2:
                    adjusted: List[tuple[str, int, int]] = []
                    last_end = 0
                    for idx, (chunk_text, start_idx, end_idx) in enumerate(out2):
                        adj_start = start_idx
                        adj_end = end_idx
                        if adj_start < last_end:
                            adj_start = last_end
                        if adj_start >= adj_end:
                            continue
                        if idx < len(out2) - 1:
                            next_start = out2[idx + 1][1]
                            if next_start > adj_end:
                                adj_end = next_start
                        if adj_start > last_end:
                            back = adj_start
                            while back > last_end and text[back - 1].isspace():
                                back -= 1
                            if back < adj_start:
                                adj_start = back
                        chunk_slice = text[adj_start:adj_end]
                        if not chunk_slice:
                            continue
                        trimmed_leading = False
                        if adj_start == 0 and chunk_slice:
                            offset = len(chunk_slice) - len(chunk_slice.lstrip())
                            if offset:
                                chunk_slice = chunk_slice[offset:]
                                adj_start += offset
                                trimmed_leading = True
                        leading_flag = adj_start > 0 and text[adj_start - 1].isspace()
                        if trimmed_leading:
                            leading_flag = False
                        trimmed_trailing = False
                        if adj_end >= len(text) and chunk_slice:
                            rstripped = chunk_slice.rstrip()
                            if len(rstripped) != len(chunk_slice):
                                trimmed_trailing = True
                            adj_end = adj_start + len(rstripped)
                            chunk_slice = rstripped
                        if not chunk_slice:
                            continue
                        trailing_flag = False
                        if adj_end < len(text) and text[adj_end].isspace():
                            remainder = text[adj_end:]
                            trailing_flag = any(not ch.isspace() for ch in remainder)
                        if trimmed_trailing:
                            trailing_flag = False
                        adjusted.append((_ChunkString(chunk_slice, leading_flag, trailing_flag), adj_start, adj_end))
                        last_end = adj_end
                if adjusted:
                    return adjusted
            except Exception as e:
                logger.warning(f"v2 chunker failed; falling back to simple chunking. Error: {e}")

        # Fallback: simple character-based chunking with optional separator awareness
        return self._legacy_char_chunk(text, int(cfg.chunk_size), int(cfg.overlap), cfg.separator or '')

    def _legacy_char_chunk(self, text: str, chunk_size: int, overlap: int, separator: str) -> List[tuple[str, int, int]]:
        """Legacy character-based chunking with optional separator-awareness."""
        chunks: List[tuple[str, int, int]] = []
        if not text:
            return chunks
        cursor = 0
        text_length = len(text)
        while cursor < text_length:
            chunk_start = cursor
            chunk_end = min(cursor + max(1, chunk_size), text_length)
            if chunk_end < text_length and separator:
                search_start = max(chunk_start, chunk_end - int(max(1, chunk_size) * 0.2))
                last_separator = text.rfind(separator, search_start, chunk_end)
                if last_separator != -1:
                    chunk_end = last_separator + len(separator)
            chunk = text[chunk_start:chunk_end]
            adj_start = chunk_start
            adj_end = chunk_end
            trimmed_leading = False
            if adj_start == 0 and chunk:
                offset = len(chunk) - len(chunk.lstrip())
                if offset:
                    chunk = chunk[offset:]
                    adj_start += offset
                    trimmed_leading = True
            trimmed_trailing = False
            if adj_end >= text_length and chunk:
                trimmed = chunk.rstrip()
                if len(trimmed) != len(chunk):
                    trimmed_trailing = True
                adj_end = adj_start + len(trimmed)
                chunk = trimmed
            if chunk:
                leading_flag = adj_start > 0 and text[adj_start - 1].isspace()
                if trimmed_leading:
                    leading_flag = False
                trailing_flag = False
                if adj_end < text_length and text[adj_end].isspace():
                    remainder = text[adj_end:]
                    trailing_flag = any(not ch.isspace() for ch in remainder)
                if trimmed_trailing:
                    trailing_flag = False
                chunks.append((_ChunkString(chunk, leading_flag, trailing_flag), adj_start, adj_end))
            cursor = adj_end - max(0, overlap) if adj_end < text_length else text_length
        return chunks

    def _generate_chunk_id(self, job_id: str, chunk_index: int) -> str:
        """Generate unique chunk ID"""
        data = f"{job_id}:{chunk_index}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _normalize_for_hash(self, text: str, *, preserve_boundary_whitespace: bool = False) -> str:
        """Normalize text for stable hashing across ingests.

        - Unicode NFC normalization
        - Strip leading/trailing whitespace
        - Collapse internal whitespace to a single space
        - Lowercase
        """
        leading_hint = getattr(text, "_chunk_leading_preserve", False)
        trailing_hint = getattr(text, "_chunk_trailing_preserve", False)
        if not isinstance(text, str):
            text = str(text or "")
        original = text
        t = unicodedata.normalize('NFC', original)
        has_leading_ws = bool(t) and t[0].isspace()
        has_trailing_ws = bool(t) and t[-1].isspace()
        t = re.sub(r"\s+", " ", t)
        if not preserve_boundary_whitespace and not leading_hint and not trailing_hint:
            t = t.strip()
        t = t.lower()
        apply_leading = leading_hint or (preserve_boundary_whitespace and has_leading_ws)
        apply_trailing = trailing_hint or (preserve_boundary_whitespace and has_trailing_ws)
        if apply_leading and t and not t.startswith(" "):
            t = " " + t
        if apply_trailing and t and not t.endswith(" "):
            t = t + " "
        if not preserve_boundary_whitespace and not leading_hint and not trailing_hint:
            t = t.strip()
        return t

    async def _update_job_progress(self, job_id: str, percentage: float, total_chunks: int):
        """Update job progress information"""
        job_key = f"job:{job_id}"
        await self.redis_client.hset(
            job_key,
            mapping={
                "progress_percentage": percentage,
                "total_chunks": total_chunks
            }
        )
