# database_retrievers.py
"""
Database-specific retrievers for the RAG service.

This module provides specialized retrieval strategies for different data sources,
including media database, notes, prompts, and character cards.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING, Sequence, Literal
from dataclasses import dataclass, field
from enum import Enum
import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

from loguru import logger
import numpy as np

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.backends.fts_translator import FTSQueryTranslator

from .types import Document, DataSource
from .utils import normalize_scores as _normalize_scores
from .vector_stores import (
    VectorStoreFactory,
    VectorStoreConfig,
    VectorStoreType,
    create_from_settings_for_user,
)

if TYPE_CHECKING:
    from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
    from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


@dataclass
class RetrievalConfig:
    """Configuration for database retrieval."""
    max_results: int = 20
    min_score: float = 0.0
    use_fts: bool = True
    use_vector: bool = True
    include_metadata: bool = True
    date_filter: Optional[Tuple[datetime, datetime]] = None
    tags_filter: Optional[List[str]] = None
    source_filter: Optional[List[str]] = None
    # FTS search level: media-level (default) or chunk-level (UnvectorizedMediaChunks)
    fts_level: Literal['media', 'chunk'] = 'media'


class BaseRetriever(ABC):
    """Base class for database-specific retrievers."""

    def __init__(
        self,
        db_path: Optional[str],
        config: Optional[RetrievalConfig] = None,
        *,
        db_adapter: Optional[Any] = None
    ) -> None:
        """Initialise the retriever with optional backend adapters."""
        self.config = config or RetrievalConfig()
        self._db_adapter = db_adapter
        self.db_path = self._validate_path(db_path) if db_path else None
        # Determine production mode from env var used across the project
        try:
            prod_val = str(os.getenv("tldw_production", "false")).strip().lower()
            self._production_mode = prod_val in {"true", "1", "yes", "on", "y"}
        except Exception:
            self._production_mode = False
        # In production, prefer adapters over any raw SQL fallbacks
        if self._production_mode and self._db_adapter is None:
            logger.warning(
                f"Production mode active: no DB adapter provided for {self.__class__.__name__}. "
                "Raw SQL fallback is disabled and calls will fail without an adapter."
            )
        if self._db_adapter is None and self.db_path is None:
            raise ValueError("db_path is required when no database adapter is provided.")

    def _validate_path(self, path: Optional[str]) -> Optional[str]:
        """Validate and normalise database paths while guarding against traversal."""
        if path is None:
            return None
        if '://' in path:
            return path
        try:
            path_obj = Path(path)
            abs_path = path_obj.resolve()
            path_str = str(abs_path)
            suspicious_patterns = [
                '../',
                '..\\',
                '/etc/',
                '/proc/',
                '/sys/',
                '\\System32\\',
                '\\Windows\\',
            ]
            for pattern in suspicious_patterns:
                if pattern in path_str:
                    logger.warning(f"Suspicious path pattern detected: {pattern} in {path_str}")
                    raise ValueError(f"Invalid path: contains suspicious pattern '{pattern}'")
            if abs_path.parts and abs_path.parts[0] == '/' and len(abs_path.parts) > 1:
                restricted_dirs = ['etc', 'proc', 'sys', 'dev', 'boot', 'root']
                if abs_path.parts[1] in restricted_dirs:
                    raise ValueError(f"Access to /{abs_path.parts[1]}/ directory is not allowed")
            parent_dir = abs_path.parent
            if not parent_dir.exists():
                logger.warning(f"Parent directory does not exist: {parent_dir}")
            return str(abs_path)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Path validation error for '{path}': {exc}")
            raise ValueError(f"Invalid database path: {exc}")

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        **kwargs
    ) -> List[Document]:
        """Retrieve documents from database."""
        raise NotImplementedError

    @abstractmethod
    async def get_metadata(self, doc_id: str) -> Dict[str, Any]:
        """Get metadata for a document."""
        raise NotImplementedError

    def _execute_query(
        self,
        query: str,
        params: Tuple = ()
    ) -> List[Dict[str, Any]]:
        """Execute SQL query and return results as dictionaries."""
        if self._db_adapter is not None:
            try:
                cursor = self._db_adapter.execute_query(query, params)  # type: ignore[attr-defined]
                if cursor is None:
                    return []
                fetched = cursor.fetchall() or []
                return [dict(row) if not isinstance(row, dict) else row for row in fetched]
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Backend query error: {exc}")
                return []
        # Disallow raw SQL fallback in production to honor project DB abstraction policy
        if getattr(self, "_production_mode", False):
            raise RuntimeError(
                f"Raw SQL fallback is disabled in production for {self.__class__.__name__}. "
                "Provide a database adapter (e.g., MediaDatabase or CharactersRAGDB)."
            )
        if not self.db_path:
            logger.error("No database path available for direct query execution.")
            return []
        try:
            # Avoid logging raw SQL and params in production to reduce leakage risk
            if not getattr(self, "_production_mode", False):
                logger.debug(f"Executing query: {query[:100]}...")
                logger.debug(f"With params: {params}")
                logger.debug(f"Database path: {self.db_path}")
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                results = cursor.fetchall()
                logger.debug(f"Query returned {len(results)} results")
                return [dict(row) for row in results]
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Database query error: {exc}")
            if not getattr(self, "_production_mode", False):
                logger.error(f"Query was: {query}")
                logger.error(f"Params were: {params}")
                logger.error(f"Database path: {self.db_path}")
            return []


class MediaDBRetriever(BaseRetriever):
    """Retriever for Media_DB (main content database)."""

    def __init__(
        self,
        db_path: Optional[str],
        config: Optional[RetrievalConfig] = None,
        user_id: str = "0",
        media_db: Optional['MediaDatabase'] = None
    ) -> None:
        """Initialize MediaDBRetriever with optional vector store."""
        super().__init__(db_path, config, db_adapter=media_db)
        # Prefer an explicit adapter, otherwise try to attach the canonical MediaDatabase
        attached = None
        own = False
        if media_db is None:
            attached = self._maybe_attach_media_db(db_path)
            own = attached is not None
        self.media_db = media_db or attached
        self._own_media_db = own
        self.user_id = user_id
        self.vector_store = None
        self._initialize_vector_store()

    def _maybe_attach_media_db(self, db_path: Optional[str]):
        """Best-effort: attach MediaDatabase adapter if path points to a Media_DB_v2 file.

        This enables robust retrieval in tests/CI where only the sqlite path is provided.
        """
        if not db_path:
            return None
        try:
            from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase  # type: ignore
            return MediaDatabase(db_path=db_path, client_id="rag_service")
        except Exception:
            return None

    def close(self):
        try:
            if self._own_media_db and self.media_db is not None:
                close_fn = getattr(self.media_db, 'close_connection', None)
                if callable(close_fn):
                    close_fn()
        except Exception:
            pass

    def _initialize_vector_store(self):
        """Initialize vector store adapter if configured."""
        try:
            # Try to get vector store from settings
            from tldw_Server_API.app.core.config import settings
            if settings.get("RAG", {}).get("vector_store_type"):
                self.vector_store = create_from_settings_for_user(
                    settings,
                    self.user_id
                )
                logger.info(f"Vector store adapter initialized for MediaDBRetriever with user_id={self.user_id}")
        except Exception as e:
            logger.warning(f"Could not initialize vector store: {e}")
            self.vector_store = None

    async def retrieve(
        self,
        query: str,
        media_type: Optional[str] = None,
        **kwargs
    ) -> List[Document]:
        """Retrieve documents from the media database."""
        if self.media_db is not None:
            # Branch on FTS level when FTS search is enabled
            try:
                if self.config.use_fts and getattr(self.config, 'fts_level', 'media') == 'chunk':
                    return self._retrieve_chunk_fts(query, media_type, **kwargs)
            except Exception:
                # Fall back gracefully to media-level
                pass
            return self._retrieve_via_backend(query, media_type, **kwargs)

        documents = []

        # Build FTS query
        fts_query = self._build_fts_query(query)

        # Column weights for bm25(title, content)
        title_w = 2.0
        content_w = 1.0
        try:
            from tldw_Server_API.app.core.config import settings as _settings  # type: ignore
            # Allow nested RAG.FTS config or flat vars
            title_w = float((_settings.get("RAG", {}) or {}).get("fts_title_weight", _settings.get("FTS_TITLE_WEIGHT", 2.0)))
            content_w = float((_settings.get("RAG", {}) or {}).get("fts_content_weight", _settings.get("FTS_CONTENT_WEIGHT", 1.0)))
        except Exception:
            pass

        # Build SQL with filters
        sql = """
            SELECT
                m.id,
                m.title,
                m.content,
                m.type,
                m.url,
                m.ingestion_date,
                m.transcription_model,
                bm25(media_fts, ?, ?) as rank
            FROM media_fts
            JOIN media m ON media_fts.rowid = m.id
            WHERE media_fts MATCH ?
        """

        params = [title_w, content_w, fts_query]

        # Add media type filter
        if media_type:
            sql += " AND m.type = ?"
            params.append(media_type)

        # Add date filter
        if self.config.date_filter:
            start_date, end_date = self.config.date_filter
            sql += " AND m.ingestion_date BETWEEN ? AND ?"
            params.extend([start_date.isoformat(), end_date.isoformat()])

        # Optional restriction to specific media IDs
        allowed_media_ids = kwargs.get("allowed_media_ids")
        if allowed_media_ids and isinstance(allowed_media_ids, (list, tuple)):
            placeholders = ",".join(["?"] * len(allowed_media_ids))
            sql += f" AND m.id IN ({placeholders})"
            params.extend(list(allowed_media_ids))

        # Add ordering and limit (bm25: lower is better on SQLite)
        sql += " ORDER BY rank ASC LIMIT ?"
        params.append(self.config.max_results)

        # Execute query and normalize scores to [0,1] (higher is better)
        rows = list(self._execute_query(sql, tuple(params)))
        raw_scores = [float(r["rank"]) if r["rank"] is not None else 0.0 for r in rows]
        # bm25 (SQLite) is lower-better; invert before normalization
        inv_scores = [-s for s in raw_scores]
        norm = _normalize_scores(inv_scores, method="minmax") if rows else []

        # Convert to documents and apply min_score threshold on normalized scores
        min_score = float(self.config.min_score or 0.0)
        for row, score in zip(rows, norm):
            if score < min_score:
                continue
            doc = Document(
                id=str(row["id"]),
                content=row["content"] or "",
                source=DataSource.MEDIA_DB,
                metadata={
                    "title": row.get("title"),
                    "media_type": row.get("type"),
                    "url": row.get("url"),
                    "created_at": row.get("ingestion_date"),
                    "transcription_model": row.get("transcription_model"),
                    "source": "media_db"
                },
                score=float(score)
            )
            documents.append(doc)
        logger.debug(f"Retrieved {len(documents)} documents from Media_DB (normalized scores)")

        return documents

    def _retrieve_chunk_fts(self, query: str, media_type: Optional[str], **kwargs) -> List[Document]:
        """Retrieve chunk-level matches using FTS5 over UnvectorizedMediaChunks.

        For SQLite: uses virtual table `unvectorized_chunks_fts`.
        For Postgres: uses tsvector column on `unvectorized_media_chunks` (created via backend).
        """
        if self.media_db is None:
            return []

        backend_type = getattr(self.media_db, 'backend_type', None)
        if backend_type == BackendType.SQLITE:
            # Ensure FTS virtual table exists; rebuild if empty to prime content
            try:
                ensure = getattr(self.media_db, 'ensure_chunk_fts', None)
                if callable(ensure):
                    self.media_db.ensure_chunk_fts()
                # Optionally prime FTS if empty (cheap count)
                check = getattr(self.media_db, 'maybe_rebuild_chunk_fts_if_empty', None)
                if callable(check):
                    self.media_db.maybe_rebuild_chunk_fts_if_empty()
            except Exception as exc:
                logger.debug(f"Chunk FTS ensure/rebuild skipped: {exc}")

        params: List[Any] = []
        if backend_type == BackendType.SQLITE:
            # Build SQLite FTS query and SQL
            fts_query = self._build_fts_query(query)
            sql = """
                SELECT
                    u.uuid AS chunk_uuid,
                    u.id   AS chunk_rowid,
                    u.media_id,
                    u.chunk_text,
                    u.start_char,
                    u.end_char,
                    u.chunk_type,
                    u.chunk_index,
                    m.title,
                    m.type AS media_type,
                    m.url,
                    bm25(unvectorized_chunks_fts) AS rank
                FROM unvectorized_chunks_fts
                JOIN UnvectorizedMediaChunks u ON unvectorized_chunks_fts.rowid = u.id
                JOIN Media m ON u.media_id = m.id
                WHERE unvectorized_chunks_fts MATCH ?
                  AND m.deleted = 0 AND m.is_trash = 0 AND u.deleted = 0
            """
            params.append(fts_query)
        else:
            # Postgres tsquery path over generated tsvector column
            tsquery = FTSQueryTranslator.normalize_query(query, 'postgresql')
            sql = (
                "SELECT "
                " u.uuid AS chunk_uuid, u.id AS chunk_rowid, u.media_id, u.chunk_text,"
                " u.start_char, u.end_char, u.chunk_type, u.chunk_index,"
                " m.title, m.type AS media_type, m.url,"
                " ts_rank(u.unvectorized_chunks_fts_tsv, to_tsquery('english', ?)) AS rank"
                " FROM unvectorizedmediachunks u"
                " JOIN media m ON u.media_id = m.id"
                " WHERE m.deleted = 0 AND m.is_trash = 0 AND u.deleted = 0"
                "   AND u.unvectorized_chunks_fts_tsv @@ to_tsquery('english', ?)"
            )
            params.extend([tsquery, tsquery])
        if media_type:
            sql += " AND m.type = ?"
            params.append(media_type)

        # Optional restriction to specific media IDs
        allowed_media_ids = kwargs.get("allowed_media_ids")
        if allowed_media_ids and isinstance(allowed_media_ids, (list, tuple)):
            placeholders = ",".join(["?"] * len(allowed_media_ids))
            sql += f" AND m.id IN ({placeholders})"
            params.extend(list(allowed_media_ids))

        # Optional date filter against Media.ingestion_date
        if self.config.date_filter:
            start_date, end_date = self.config.date_filter
            sql += " AND m.ingestion_date BETWEEN ? AND ?"
            params.extend([start_date.isoformat(), end_date.isoformat()])

        # Order by relevance: SQLite bm25 prefers ASC; Postgres ts_rank prefers DESC
        if backend_type == BackendType.SQLITE:
            sql += " ORDER BY rank ASC LIMIT ?"
        else:
            sql += " ORDER BY rank DESC LIMIT ?"
        params.append(self.config.max_results)

        try:
            rows = self.media_db.execute_query(sql, tuple(params)).fetchall()  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Chunk FTS query failed: {exc}")
            return []

        docs: List[Document] = []

        # Normalize scores to [0,1] (higher is better)
        norm_scores: List[float] = []
        if rows:
            row_maps = [r if isinstance(r, dict) else dict(r) for r in rows]
            raw_vals: List[float] = []
            for rm in row_maps:
                rv = rm.get('rank')
                try:
                    raw_vals.append(float(rv) if rv is not None else 0.0)
                except (TypeError, ValueError):
                    raw_vals.append(0.0)
            if backend_type == BackendType.SQLITE:
                inv = [-v for v in raw_vals]
                norm_scores = _normalize_scores(inv, method="minmax")
            else:
                norm_scores = _normalize_scores(raw_vals, method="minmax")
        else:
            row_maps = []

        min_score = float(self.config.min_score or 0.0)
        for row, score_val in zip(row_maps, norm_scores):
            if float(score_val) < min_score:
                continue

            md: Dict[str, Any] = {}
            if self.config.include_metadata:
                md = {
                    'title': row.get('title'),
                    'media_type': row.get('media_type'),
                    'url': row.get('url'),
                    'media_id': str(row.get('media_id')) if row.get('media_id') is not None else None,
                    'chunk_type': row.get('chunk_type'),
                    'chunk_index': int(row.get('chunk_index') or 0),
                    'start_char': row.get('start_char'),
                    'end_char': row.get('end_char'),
                    'source': 'media_db',
                }

                # Optionally enrich with nearest section info from DocumentStructureIndex
                try:
                    from tldw_Server_API.app.core.config import rag_enable_structure_index  # lazy import
                    _enable_si = rag_enable_structure_index()
                except Exception:
                    _enable_si = True
                if _enable_si:
                    try:
                        mid_raw = md.get('media_id')
                        st = md.get('start_char')
                        if self.media_db and mid_raw is not None and st is not None:
                            mid = int(str(mid_raw))
                            st_i = int(st)
                            sec = self.media_db.lookup_section_for_offset(mid, st_i)  # type: ignore[attr-defined]
                            if isinstance(sec, dict):
                                md['section_title'] = sec.get('title')
                                md['section_start'] = sec.get('start_char')
                                md['section_end'] = sec.get('end_char')
                                # Paragraph bounds default to chunk bounds
                                md.setdefault('paragraph_start', md.get('start_char'))
                                md.setdefault('paragraph_end', md.get('end_char'))
                    except Exception:
                        pass

            chunk_uuid = str(row.get('chunk_uuid'))
            content_text = (row.get('chunk_text') or "")

            docs.append(
                Document(
                    id=chunk_uuid,
                    content=content_text,
                    source=DataSource.MEDIA_DB,
                    metadata=md,
                    score=float(score_val),
                    start_char=md.get('start_char'),
                    end_char=md.get('end_char'),
                    chunk_index=md.get('chunk_index'),
                )
            )

        return docs

    def _retrieve_via_backend(self, query: str, media_type: Optional[str], **kwargs) -> List[Document]:
        if self.media_db is None:
            return []
        date_range = None
        if self.config.date_filter:
            start, end = self.config.date_filter
            date_range = {'start_date': start, 'end_date': end}
        media_types = [media_type] if media_type else None
        sort_by = 'relevance' if self.config.use_fts else 'last_modified_desc'
        try:
            allowed_media_ids = kwargs.get("allowed_media_ids")
            results, _total = self.media_db.search_media_db(
                search_query=query,
                search_fields=['title', 'content'],
                media_types=media_types,
                date_range=date_range,
                media_ids_filter=list(allowed_media_ids) if allowed_media_ids else None,
                sort_by=sort_by,
                results_per_page=self.config.max_results,
                page=1,
                include_trash=False,
                include_deleted=False,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(f"MediaDatabase search failed: {exc}")
            return []
        documents: List[Document] = []
        backend_type = getattr(self.media_db, 'backend_type', None)

        # Normalize scores across results to [0,1] (higher is better)
        raw_vals: List[float] = []
        for row in results:
            rv = row.get('relevance_score')
            if rv is None:
                rv = row.get('rank')
            try:
                raw_vals.append(float(rv) if rv is not None else 0.0)
            except (TypeError, ValueError):
                raw_vals.append(0.0)
        if backend_type == BackendType.SQLITE:
            inv = [-v for v in raw_vals]
            norm_vals = _normalize_scores(inv, method="minmax") if raw_vals else []
        else:
            norm_vals = _normalize_scores(raw_vals, method="minmax") if raw_vals else []

        min_score = float(self.config.min_score or 0.0)
        for row, score_val in zip(results, norm_vals):
            if float(score_val) < min_score:
                continue
            metadata = {}
            if self.config.include_metadata:
                metadata = {
                    'title': row.get('title'),
                    'media_type': row.get('type'),
                    'url': row.get('url'),
                    'created_at': row.get('ingestion_date'),
                    'transcription_model': row.get('transcription_model'),
                    'last_modified': row.get('last_modified'),
                    'source': 'media_db',
                }
            # Use numeric media ID for Document.id to match callers/tests that
            # expect Media DB identifiers, and keep uuid in metadata if needed.
            doc_id = row.get('id')
            title_text = (row.get('title') or '').strip()
            body_text = (row.get('content') or '').strip()
            if title_text and (not body_text or title_text.lower() not in body_text.lower()):
                content_text = f"{title_text}\n{body_text}" if body_text else title_text
            else:
                content_text = body_text or title_text
            documents.append(
                Document(
                    id=str(doc_id),
                    content=content_text,
                    source=DataSource.MEDIA_DB,
                    metadata=metadata,
                    score=float(score_val),
                )
            )
        documents.sort(key=lambda doc: getattr(doc, 'score', 0.0), reverse=True)
        return documents

    async def retrieve_with_keywords(
        self,
        query: str,
        keywords: List[str]
    ) -> List[Document]:
        """Retrieve with additional keyword filtering."""
        # Get base results
        documents = await self.retrieve(query)

        # Filter by keywords
        if keywords:
            filtered_docs = []
            for doc in documents:
                content_lower = doc.content.lower()
                if any(keyword.lower() in content_lower for keyword in keywords):
                    filtered_docs.append(doc)
            documents = filtered_docs

        return documents

    async def _retrieve_fts(
        self,
        query: str,
        media_type: Optional[str] = None,
        **kwargs
    ) -> List[Document]:
        """Internal method for FTS retrieval (same as retrieve)."""
        return await self.retrieve(query, media_type, **kwargs)

    async def _retrieve_vector(
        self,
        query: str,
        media_type: Optional[str] = None,
        **kwargs
    ) -> List[Document]:
        """
        Retrieve documents using vector search.

        Args:
            query: Search query text
            media_type: Optional media type filter

        Returns:
            List of documents from vector search
        """
        if not self.vector_store:
            logger.warning("Vector store not initialized, falling back to FTS")
            return await self._retrieve_fts(query, media_type, **kwargs)

        try:
            # Allow callers to provide a precomputed query vector (e.g., HyDE)
            provided_vector = kwargs.get("query_vector")
            # Initialize vector store if needed
            if not self.vector_store._initialized:
                await self.vector_store.initialize()

            # Get embedding for query (or use provided)
            if provided_vector is not None:
                query_vector = provided_vector
            else:
                try:
                    # Import only when we actually need to generate embeddings to avoid
                    # side effects (e.g., duplicate Prometheus collectors in tests)
                    from tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create import (
                        create_embeddings_batch,
                        get_embedding_config,
                    )
                    user_app_config = get_embedding_config()
                    embeddings = await asyncio.get_event_loop().run_in_executor(
                        None,
                        create_embeddings_batch,
                        [query],  # texts
                        user_app_config,
                        None,
                    )

                    if not embeddings or not embeddings[0]:
                        logger.error("Failed to generate query embedding")
                        return []

                    query_vector = embeddings[0]
                    if hasattr(query_vector, 'tolist'):
                        query_vector = query_vector.tolist()
                except Exception as e:
                    logger.error(f"Failed to generate query embedding: {e}")
                    return []

            # Build filter for vector search
            base_filter: Dict[str, Any] = {}
            if media_type:
                base_filter["media_type"] = media_type

            # Optional rich JSONB filter to be combined with base_filter
            metadata_filter = kwargs.get("metadata_filter")
            if isinstance(metadata_filter, dict) and metadata_filter:
                if base_filter:
                    # Combine via AND to preserve both constraints
                    base_filter = {"$and": [base_filter, metadata_filter]}
                else:
                    base_filter = metadata_filter

            # Search collection selection; support multi-search via wildcard/list namespace
            index_namespace = kwargs.get("index_namespace")
            multi_namespace: Optional[List[str]] = None
            if index_namespace:
                # If a list/tuple of patterns provided, use multi_search
                if isinstance(index_namespace, (list, tuple)):
                    multi_namespace = [str(x) for x in index_namespace]
                    collection_name = None  # type: ignore[assignment]
                # If a single string contains a wildcard, treat as pattern
                elif isinstance(index_namespace, str) and ("*" in index_namespace or "?" in index_namespace):
                    multi_namespace = [index_namespace]
                    collection_name = None  # type: ignore[assignment]
                else:
                    # Use provided namespace directly (already includes user prefix if desired)
                    collection_name = str(index_namespace)
            else:
                # Default: user-specific media collection
                collection_name = f"user_{self.user_id}_media_embeddings"

            # HYDE-aware retrieval and merge
            try:
                from tldw_Server_API.app.core.config import settings as _settings  # late import
                hyde_enabled = bool(_settings.get("HYDE_ENABLED", False))
                hyde_only_if_needed = bool(_settings.get("HYDE_ONLY_IF_NEEDED", True))
                hyde_score_floor = float(_settings.get("HYDE_SCORE_FLOOR", 0.30) or 0.30)
                hyde_k_frac = float(_settings.get("HYDE_K_FRACTION", 0.5) or 0.5)
                hyde_weight = float(_settings.get("HYDE_WEIGHT_QUESTION_MATCH", 0.05) or 0.05)
            except Exception:
                hyde_enabled = False
                hyde_only_if_needed = True
                hyde_score_floor = 0.30
                hyde_k_frac = 0.5
                hyde_weight = 0.05

            k = int(self.config.max_results or 10)

            async def _search_with_filter(kind_filter: Optional[str], k_: int):
                # Merge kind filter with base_filter
                f: Optional[Dict[str, Any]]
                if kind_filter:
                    if base_filter:
                        f = {"$and": [base_filter, {"kind": kind_filter}]}
                    else:
                        f = {"kind": kind_filter}
                else:
                    f = base_filter if base_filter else None

                try:
                    # Multi-namespace search when patterns provided
                    if multi_namespace:
                        return await self.vector_store.multi_search(
                            collection_patterns=multi_namespace,
                            query_vector=query_vector,
                            k=k_,
                            filter=f,
                        )
                    # Single collection search
                    return await self.vector_store.search(
                        collection_name=collection_name,  # type: ignore[arg-type]
                        query_vector=query_vector,
                        k=k_,
                        filter=f,
                        include_metadata=True,
                    )
                except Exception as exc:
                    logger.debug(f"Vector search with filter {f} failed, reason={exc}")
                    return []

            # 1) Baseline chunk search (prefer kind='chunk', fallback to no kind filter)
            base_results = await _search_with_filter("chunk", k)
            if not base_results:
                base_results = await _search_with_filter(None, k)

            # Optional early exit
            max_base = max((r.score for r in base_results), default=0.0)
            if not hyde_enabled or (hyde_only_if_needed and len(base_results) >= k and max_base >= hyde_score_floor):
                # Convert and return baseline
                documents: List[Document] = []
                allowed_media_ids = kwargs.get("allowed_media_ids")
                allowed_set = set(int(x) for x in allowed_media_ids) if allowed_media_ids else None
                for result in base_results:
                    doc_media_id = result.metadata.get("media_id", result.id)
                    try:
                        doc_media_id_int = int(str(doc_media_id))
                    except Exception:
                        doc_media_id_int = None
                    if allowed_set is not None and (doc_media_id_int is None or doc_media_id_int not in allowed_set):
                        continue
                    documents.append(
                        Document(
                            id=result.metadata.get("media_id", result.id),
                            content=result.content,
                            metadata=result.metadata,
                            score=result.score,
                            source=DataSource.MEDIA_DB,
                        )
                    )
                logger.debug(f"Retrieved {len(documents)} documents from vector search (baseline)")
                return documents

            # 2) HYDE search on question vectors
            k_hyde = max(1, int(k * hyde_k_frac))
            hyde_results = await _search_with_filter("hyde_q", k_hyde)

            # 3) Merge - two modes: media-level (default) and optional chunk-level (by parent_chunk_id)
            try:
                dedupe_by_parent = bool(_settings.get("HYDE_DEDUPE_BY_PARENT", False))
            except Exception:
                dedupe_by_parent = False

            if not dedupe_by_parent:
                # Media-level merge (default)
                best_score: Dict[str, float] = {}
                doc_map: Dict[str, Document] = {}

                def _maybe_add_media(result_obj):
                    # Convert VectorSearchResult to Document (id=media_id preferred)
                    d_id = result_obj.metadata.get("media_id", result_obj.id)
                    d = Document(
                        id=d_id,
                        content=result_obj.content,
                        metadata=result_obj.metadata,
                        score=result_obj.score,
                        source=DataSource.MEDIA_DB,
                    )
                    if d_id not in doc_map:
                        doc_map[d_id] = d
                    prev = best_score.get(d_id, 0.0)
                    if d.score > prev:
                        best_score[d_id] = d.score
                        doc_map[d_id].score = d.score

                # Add baseline first
                for r in base_results:
                    _maybe_add_media(r)

                # Add/adjust HYDE
                for r in hyde_results:
                    adj = min(1.0, r.score + hyde_weight)
                    d_id = r.metadata.get("media_id", r.id)
                    prev = best_score.get(d_id, 0.0)
                    if adj > prev:
                        best_score[d_id] = adj
                        if d_id in doc_map:
                            doc_map[d_id].score = adj
                        else:
                            doc_map[d_id] = Document(
                                id=d_id,
                                content=r.content,
                                metadata=r.metadata,
                                score=adj,
                                source=DataSource.MEDIA_DB,
                            )

                allowed_media_ids = kwargs.get("allowed_media_ids")
                allowed_set = set(int(x) for x in allowed_media_ids) if allowed_media_ids else None
                merged = list(doc_map.values())
                if allowed_set is not None:
                    tmp = []
                    for d in merged:
                        try:
                            mid = int(str(d.metadata.get("media_id", d.id)))
                        except Exception:
                            mid = None
                        if mid is not None and mid in allowed_set:
                            tmp.append(d)
                    merged = tmp
                merged.sort(key=lambda d: d.score, reverse=True)
                documents = merged[:k]
                logger.debug(f"Retrieved {len(documents)} documents from vector search (HYDE merged, media-level)")
                return documents

            # Chunk-level merge (by parent_chunk_id)
            # Build best-per-parent maps for base and HYDE
            base_by_parent: Dict[str, Tuple[float, Any]] = {}
            for r in base_results:
                parent = str(r.metadata.get("parent_chunk_id") or r.id)
                sc = float(r.score)
                if parent not in base_by_parent or sc > base_by_parent[parent][0]:
                    base_by_parent[parent] = (sc, r)

            hyde_by_parent: Dict[str, Tuple[float, Any]] = {}
            for r in hyde_results:
                parent = str(r.metadata.get("parent_chunk_id") or r.id)
                sc = min(1.0, float(r.score) + hyde_weight)
                if parent not in hyde_by_parent or sc > hyde_by_parent[parent][0]:
                    hyde_by_parent[parent] = (sc, r)

            # Combine per parent key
            chunk_keys = set(base_by_parent.keys()) | set(hyde_by_parent.keys())
            chunk_docs: List[Document] = []
            for ck in chunk_keys:
                base_tuple = base_by_parent.get(ck)
                hyde_tuple = hyde_by_parent.get(ck)
                base_sc = base_tuple[0] if base_tuple else 0.0
                hyde_sc = hyde_tuple[0] if hyde_tuple else 0.0
                best_sc = max(base_sc, hyde_sc)
                # Prefer base result's metadata/content when present; else use HYDE
                src = base_tuple[1] if base_tuple else (hyde_tuple[1] if hyde_tuple else None)
                if not src:
                    continue
                d_id = src.metadata.get("media_id", src.id)
                d = Document(
                    id=d_id,
                    content=src.content,
                    metadata=src.metadata,
                    score=best_sc,
                    source=DataSource.MEDIA_DB,
                )
                chunk_docs.append(d)

            # Apply allowed_media_ids filter
            allowed_media_ids = kwargs.get("allowed_media_ids")
            allowed_set = set(int(x) for x in allowed_media_ids) if allowed_media_ids else None
            if allowed_set is not None:
                filtered: List[Document] = []
                for d in chunk_docs:
                    try:
                        mid = int(str(d.metadata.get("media_id", d.id)))
                    except Exception:
                        mid = None
                    if mid is not None and mid in allowed_set:
                        filtered.append(d)
                chunk_docs = filtered

            chunk_docs.sort(key=lambda d: d.score, reverse=True)
            documents = chunk_docs[:k]
            logger.debug(f"Retrieved {len(documents)} documents from vector search (HYDE merged, chunk-level)")
            return documents

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            # Fallback to FTS
            return await self._retrieve_fts(query, media_type, **kwargs)

    async def retrieve_hybrid(
        self,
        query: str,
        media_type: Optional[str] = None,
        alpha: float = 0.7,
        **kwargs
    ) -> List[Document]:
        """
        Retrieve documents using hybrid search (FTS + Vector).

        Args:
            query: Search query
            media_type: Optional media type filter
            alpha: Weight for vector search (0=FTS only, 1=Vector only)

        Returns:
            Merged and re-ranked documents
        """
        # Perform both searches in parallel
        fts_task = self._retrieve_fts(query, media_type, **kwargs)
        vector_task = self._retrieve_vector(query, media_type, **kwargs)

        fts_docs, vector_docs = await asyncio.gather(fts_task, vector_task)

        # Merge using reciprocal rank fusion
        return self._reciprocal_rank_fusion(fts_docs, vector_docs, alpha)

    def _reciprocal_rank_fusion(
        self,
        fts_docs: List[Document],
        vector_docs: List[Document],
        alpha: float = 0.7,
        k: int = 60
    ) -> List[Document]:
        """
        Merge FTS and vector results using reciprocal rank fusion.

        Args:
            fts_docs: Documents from FTS search
            vector_docs: Documents from vector search
            alpha: Weight for vector search (0=FTS only, 1=Vector only)
            k: Constant for RRF (typically 60)

        Returns:
            Merged and re-ranked documents
        """
        # Create score dictionaries
        fts_scores = {}
        vector_scores = {}
        doc_map = {}

        # Calculate RRF scores for FTS results
        for rank, doc in enumerate(fts_docs):
            doc_id = doc.id
            fts_scores[doc_id] = 1.0 / (k + rank + 1)
            doc_map[doc_id] = doc

        # Calculate RRF scores for vector results
        for rank, doc in enumerate(vector_docs):
            doc_id = doc.id
            vector_scores[doc_id] = 1.0 / (k + rank + 1)
            if doc_id not in doc_map:
                doc_map[doc_id] = doc

        # Combine scores with weighting
        final_scores = {}
        all_doc_ids = set(fts_scores.keys()) | set(vector_scores.keys())

        for doc_id in all_doc_ids:
            fts_score = fts_scores.get(doc_id, 0)
            vector_score = vector_scores.get(doc_id, 0)
            # Weighted combination
            final_scores[doc_id] = (1 - alpha) * fts_score + alpha * vector_score

        # Sort by final score
        sorted_ids = sorted(final_scores.keys(), key=lambda x: final_scores[x], reverse=True)

        # Create final document list
        merged_docs = []
        for doc_id in sorted_ids[:self.config.max_results]:
            doc = doc_map[doc_id]
            doc.score = final_scores[doc_id]
            merged_docs.append(doc)

        logger.debug(f"Hybrid search merged {len(merged_docs)} documents")
        return merged_docs

    async def get_metadata(self, doc_id: str) -> Dict[str, Any]:
        """Get full metadata for a media item."""
        aggregator = "GROUP_CONCAT(t.name)"
        media_adapter = getattr(self, 'media_db', None)
        if media_adapter is not None and getattr(media_adapter, 'backend_type', None) == BackendType.POSTGRESQL:
            aggregator = "STRING_AGG(t.name, ',')"
        sql = f"""
            SELECT
                m.*,
                {aggregator} as tags,
                COUNT(DISTINCT ma.id) as analysis_count
            FROM media m
            LEFT JOIN media_tags mt ON m.id = mt.media_id
            LEFT JOIN tags t ON mt.tag_id = t.id
            LEFT JOIN media_analysis ma ON m.id = ma.media_id
            WHERE m.id = ?
            GROUP BY m.id
        """

        results = self._execute_query(sql, (doc_id,))

        if results:
            row = results[0]
            return {
                "id": row["id"],
                "title": row["title"],
                "media_type": row["media_type"],
                "url": row["url"],
                "tags": row["tags"].split(",") if row["tags"] else [],
                "analysis_count": row["analysis_count"],
                "created_at": row["created_at"]
            }

        return {}

    def _build_fts_query(self, query: str) -> str:
        """Build FTS5 query with proper escaping and hyphen/unicode handling.

        - If multiple tokens or hyphens present, use a quoted phrase to preserve order.
        - Otherwise, apply prefix match (token*).
        - Escape embedded quotes for FTS5.
        """
        text = (query or "").strip()
        if not text:
            return "*"
        # Normalize quotes
        safe = text.replace('"', '""')
        # Heuristic: phrase if contains whitespace, hyphens, or parentheses/quotes
        if any(ch in safe for ch in [" ", "-", "(", ")", "'", "\u2013", "\u2014"]):
            return f'"{safe}"'
        # Single token: prefix
        return f"{safe}*"


class NotesDBRetriever(BaseRetriever):
    """Retriever for notes database."""

    def __init__(
        self,
        db_path: Optional[str],
        config: Optional[RetrievalConfig] = None,
        *,
        chacha_db: Optional['CharactersRAGDB'] = None
    ) -> None:
        super().__init__(db_path, config, db_adapter=chacha_db)
        self.chacha_db = chacha_db

    async def retrieve(
        self,
        query: str,
        notebook_id: Optional[int] = None,
        **kwargs
    ) -> List[Document]:
        """Retrieve from notes database."""
        if self.chacha_db is not None and not self.config.tags_filter:
            docs = self._retrieve_via_chacha(query, notebook_id)
            # Optional restriction to specific note IDs
            allowed_note_ids = kwargs.get("allowed_note_ids")
            if allowed_note_ids and isinstance(allowed_note_ids, (list, tuple)):
                allowed_set = set(str(x) for x in allowed_note_ids)
                docs = [d for d in docs if str(d.id).replace("note_", "") in allowed_set]
            return docs

        documents = []

        # Build SQL query compatible with ChaChaNotes schema (no notebooks/tags tables)
        sql = """
            SELECT
                n.id,
                n.title,
                n.content,
                n.created_at,
                n.last_modified AS updated_at
            FROM notes n
            WHERE n.deleted = 0 AND (n.title LIKE ? OR n.content LIKE ?)
        """
        params = [f"%{query}%", f"%{query}%"]

        # Optional restriction to specific note IDs (e.g., from access control)
        allowed_note_ids = kwargs.get("allowed_note_ids")
        if allowed_note_ids and isinstance(allowed_note_ids, (list, tuple)):
            placeholders = ",".join(["?"] * len(allowed_note_ids))
            sql += f" AND n.id IN ({placeholders})"
            params.extend(list(allowed_note_ids))

        # Order and limit
        sql += " ORDER BY n.last_modified DESC LIMIT ?"
        params.append(self.config.max_results)

        # Execute query
        results = self._execute_query(sql, tuple(params))

        # Convert to documents
        for row in results:
            # Calculate simple relevance score
            title_match = query.lower() in row["title"].lower()
            content_match = query.lower() in row["content"].lower()
            score = (1.0 if title_match else 0.0) + (0.5 if content_match else 0.0)

            doc = Document(
                id=f"note_{row['id']}",
                content=f"# {row['title']}\n\n{row['content']}",
                source=DataSource.NOTES,  # Add required source parameter
                metadata={
                    "title": row["title"],
                    "notebook": None,
                    "notebook_id": None,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "source": "notes_db"
                },
                score=score
            )
            documents.append(doc)

        # Sort by score
        documents.sort(key=lambda x: x.score, reverse=True)

        logger.debug(f"Retrieved {len(documents)} documents from Notes_DB")

        return documents

    def _retrieve_via_chacha(self, query: str, notebook_id: Optional[int]) -> List[Document]:
        if self.chacha_db is None:
            return []
        try:
            results = self.chacha_db.search_notes(query, limit=int(self.config.max_results))
        except Exception as exc:  # noqa: BLE001
            logger.error(f"ChaCha notes search failed: {exc}")
            return []
        documents: List[Document] = []
        # Normalize backend-provided ranks (if present) to [0,1]
        ranks = []
        for r in results:
            rv = r.get('rank')
            if rv is None:
                rv = r.get('bm25_score')
            try:
                ranks.append(float(rv) if rv is not None else None)
            except Exception:
                ranks.append(None)
        norm_map = {}
        if any(v is not None for v in ranks):
            vals = [v for v in ranks if v is not None]
            if getattr(self.chacha_db, 'backend_type', None) == BackendType.POSTGRESQL:
                scaled = _normalize_scores(vals, method="minmax")
            else:
                scaled = _normalize_scores([-v for v in vals], method="minmax")
            it = iter(scaled)
            for idx, v in enumerate(ranks):
                if v is not None:
                    norm_map[idx] = float(next(it))
        min_score = float(self.config.min_score or 0.0)
        for idx, row in enumerate(results):
            if notebook_id and row.get('notebook_id') != notebook_id:
                continue
            score_val = norm_map.get(idx, 0.75)
            if score_val < min_score:
                continue
            metadata = {}
            if self.config.include_metadata:
                metadata = {
                    'title': row.get('title'),
                    'notebook': row.get('notebook_name'),
                    'notebook_id': row.get('notebook_id'),
                    'created_at': row.get('created_at'),
                    'updated_at': row.get('updated_at'),
                    'source': 'notes_db',
                }
            documents.append(
                Document(
                    id=f"note_{row.get('id')}",
                    content=f"# {row.get('title')}\n\n{row.get('content', '')}",
                    source=DataSource.NOTES,
                    metadata=metadata,
                    score=float(score_val),
                )
            )
        documents.sort(key=lambda x: getattr(x, 'score', 0.0), reverse=True)
        return documents

    async def get_metadata(self, doc_id: str) -> Dict[str, Any]:
        """Get metadata for a note."""
        # Extract numeric ID
        note_id = doc_id.replace("note_", "")

        aggregator = "GROUP_CONCAT(t.name)"
        if self.chacha_db is not None and getattr(self.chacha_db, 'backend_type', None) == BackendType.POSTGRESQL:
            aggregator = "STRING_AGG(t.name, ',')"
        sql = f"""
            SELECT
                n.*,
                nb.name as notebook_name,
                {aggregator} as tags
            FROM notes n
            LEFT JOIN notebooks nb ON n.notebook_id = nb.id
            LEFT JOIN note_tags nt ON n.id = nt.note_id
            LEFT JOIN tags t ON nt.tag_id = t.id
            WHERE n.id = ?
            GROUP BY n.id
        """

        results = self._execute_query(sql, (note_id,))

        if results:
            row = results[0]
            return {
                "id": row["id"],
                "title": row["title"],
                "notebook": row["notebook_name"],
                "tags": row["tags"].split(",") if row["tags"] else [],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }

        return {}


class PromptsDBRetriever(BaseRetriever):
    """Retriever for prompts database."""

    def __init__(
        self,
        db_path: Optional[str],
        config: Optional[RetrievalConfig] = None,
        *,
        chacha_db: Optional['CharactersRAGDB'] = None
    ) -> None:
        super().__init__(db_path, config, db_adapter=chacha_db)
        self.chacha_db = chacha_db

    async def retrieve(
        self,
        query: str,
        category: Optional[str] = None,
        **kwargs
    ) -> List[Document]:
        """
        Retrieve from prompts database.

        Args:
            query: Search query
            category: Optional category filter

        Returns:
            List of retrieved documents
        """
        documents = []

        # Build SQL query
        sql = """
            SELECT
                p.id,
                p.name,
                p.prompt,
                p.category,
                p.rating,
                p.times_used,
                p.created_at
            FROM prompts p
            WHERE (p.name LIKE ? OR p.prompt LIKE ?)
        """

        params = [f"%{query}%", f"%{query}%"]

        # Add category filter
        if category:
            sql += " AND p.category = ?"
            params.append(category)

        # Order by relevance and usage
        sql += " ORDER BY p.rating DESC, p.times_used DESC LIMIT ?"
        params.append(self.config.max_results)

        # Execute query
        results = self._execute_query(sql, tuple(params))

        # Convert to documents
        for row in results:
            # Calculate relevance score
            name_match = query.lower() in row["name"].lower()
            prompt_match = query.lower() in row["prompt"].lower()
            base_score = (1.0 if name_match else 0.0) + (0.5 if prompt_match else 0.0)

            # Boost by rating and usage
            rating_boost = (row["rating"] or 0) / 5.0 * 0.3
            usage_boost = min(row["times_used"] / 100.0, 1.0) * 0.2

            score = base_score + rating_boost + usage_boost

            doc = Document(
                id=f"prompt_{row['id']}",
                content=f"**{row['name']}**\n\n{row['prompt']}",
                source=DataSource.PROMPTS,  # Add required source parameter
                metadata={
                    "name": row["name"],
                    "category": row["category"],
                    "rating": row["rating"],
                    "times_used": row["times_used"],
                    "created_at": row["created_at"],
                    "source": "prompts_db"
                },
                score=score
            )
            documents.append(doc)

        # Sort by score
        documents.sort(key=lambda x: x.score, reverse=True)

        logger.debug(f"Retrieved {len(documents)} documents from Prompts_DB")

        return documents

    async def get_metadata(self, doc_id: str) -> Dict[str, Any]:
        """Get metadata for a prompt."""
        prompt_id = doc_id.replace("prompt_", "")

        sql = "SELECT * FROM prompts WHERE id = ?"
        results = self._execute_query(sql, (prompt_id,))

        if results:
            row = results[0]
            return dict(row)

        return {}


class CharacterCardsRetriever(BaseRetriever):
    """Retriever for character cards and chats."""

    def __init__(
        self,
        db_path: Optional[str],
        config: Optional[RetrievalConfig] = None,
        *,
        chacha_db: Optional['CharactersRAGDB'] = None
    ) -> None:
        super().__init__(db_path, config, db_adapter=chacha_db)
        self.chacha_db = chacha_db

    async def retrieve(
        self,
        query: str,
        include_chats: bool = True,
        **kwargs
    ) -> List[Document]:
        """
        Retrieve from character cards and chats.

        Args:
            query: Search query
            include_chats: Whether to include chat messages

        Returns:
            List of retrieved documents
        """
        documents: List[Document] = []

        # Prefer backend-aware path via ChaCha DB (leverages Postgres FTS when available)
        if self.chacha_db is not None:
            try:
                limit_cards = max(1, self.config.max_results // 2)
                card_rows = self.chacha_db.search_character_cards(query, limit=limit_cards)
                # Normalize ranks if provided by backend (Postgres ts_rank or SQLite-derived)
                raw_ranks = []
                for r in card_rows:
                    rv = r.get("rank")
                    try:
                        raw_ranks.append(float(rv) if rv is not None else None)
                    except Exception:
                        raw_ranks.append(None)
                norm_map = {}
                if any(v is not None for v in raw_ranks):
                    vals = [v for v in raw_ranks if v is not None]
                    if getattr(self.chacha_db, 'backend_type', None) == BackendType.POSTGRESQL:
                        scaled = _normalize_scores(vals, method="minmax")
                    else:
                        scaled = _normalize_scores([-v for v in vals], method="minmax")
                    it = iter(scaled)
                    for idx, v in enumerate(raw_ranks):
                        if v is not None:
                            norm_map[idx] = float(next(it))
                min_score = float(self.config.min_score or 0.0)
                for idx, row in enumerate(card_rows):
                    name = row.get("name") or "(Unnamed)"
                    description = row.get("description") or ""
                    personality = row.get("personality") or ""
                    scenario = row.get("scenario") or ""
                    first_message = row.get("first_message") or ""
                    score_val = norm_map.get(idx, 0.75)
                    if score_val < min_score:
                        continue

                    content = (
                        f"# {name}\n\n"
                        f"**Description:** {description}\n\n"
                        f"**Personality:** {personality}\n\n"
                        f"**Scenario:** {scenario}\n\n"
                        f"**First Message:** {first_message}"
                    )
                    doc = Document(
                        id=f"character_{row['id']}",
                        content=content,
                        source=DataSource.CHARACTER_CARDS,
                        metadata={
                            "name": name,
                            "creator": row.get("creator"),
                            "version": row.get("version"),
                            "type": "character_card",
                            "source": "characters",
                        },
                        score=float(score_val),
                    )
                    documents.append(doc)

                if include_chats:
                    limit_msgs = max(1, self.config.max_results // 2)
                    msg_rows = self.chacha_db.search_messages_by_content(query, limit=limit_msgs)
                    for row in msg_rows:
                        character_name = None
                        character_id = None
                        conv_id = row.get("conversation_id")
                        if conv_id:
                            conv = self.chacha_db.get_conversation_by_id(conv_id)
                            if conv and conv.get("character_id") is not None:
                                character_id = conv.get("character_id")
                                card = self.chacha_db.get_character_card_by_id(int(character_id))
                                if card:
                                    character_name = card.get("name")

                        content = f"{row.get('sender')}: {row.get('content', '')}"
                        metadata = {
                            "sender": row.get("sender"),
                            "timestamp": row.get("timestamp"),
                            "character_id": character_id,
                            "character_name": character_name,
                            "type": "chat_message",
                            "source": "characters",
                        }
                        doc = Document(
                            id=f"chat_{row['id']}",
                            content=content,
                            source=DataSource.CHARACTER_CARDS,
                            metadata=metadata,
                            score=0.5,
                        )
                        documents.append(doc)

                documents.sort(key=lambda x: x.score, reverse=True)
                logger.debug(f"Retrieved {len(documents)} Character/Chat documents via ChaCha backend")
                return documents
            except Exception as e:
                if getattr(self.chacha_db, "backend_type", None) == BackendType.POSTGRESQL:
                    logger.warning(
                        "ChaCha backend search failed under PostgreSQL backend; skipping legacy fallback: %s",
                        e,
                    )
                    raise
                logger.debug(f"ChaCha backend search failed; falling back to legacy SQL: {e}")

        # Legacy SQLite-style path
        # Search character cards
        card_sql = """
            SELECT
                cc.id,
                cc.name,
                cc.description,
                cc.personality,
                cc.first_message,
                cc.system_prompt,
                cc.scenario,
                cc.creator,
                cc.version
            FROM character_cards cc
            WHERE cc.deleted = 0 AND (
                cc.name LIKE ?
                OR cc.description LIKE ?
                OR cc.personality LIKE ?
                OR cc.scenario LIKE ?
                OR cc.system_prompt LIKE ?
            )
            LIMIT ?
        """
        params = [f"%{query}%"] * 5 + [self.config.max_results // 2]
        card_results = self._execute_query(card_sql, params)
        for row in card_results:
            content = f"""# {row['name']}\n\n**Description:** {row['description']}\n\n**Personality:** {row['personality']}\n\n**Scenario:** {row['scenario']}\n\n**First Message:** {row['first_message']}"""
            matches = sum([
                query.lower() in (row[field] or "").lower()
                for field in ["name", "description", "personality", "scenario", "system_prompt"]
            ])
            score = matches / 5.0 if matches else 0.0
            doc = Document(
                id=f"character_{row['id']}",
                content=content,
                source=DataSource.CHARACTER_CARDS,
                metadata={
                    "name": row["name"],
                    "creator": row["creator"],
                    "version": row["version"],
                    "type": "character_card",
                    "source": "characters",
                },
                score=score,
            )
            documents.append(doc)

        if include_chats:
            chat_sql = """
                SELECT
                    m.id,
                    m.content,
                    m.sender,
                    m.timestamp,
                    conv.character_id,
                    cc.name as character_name
                FROM messages m
                JOIN conversations conv ON m.conversation_id = conv.id
                LEFT JOIN character_cards cc ON conv.character_id = cc.id
                WHERE m.deleted = 0 AND m.content LIKE ?
                ORDER BY m.timestamp DESC
                LIMIT ?
            """
            chat_params = [f"%{query}%", self.config.max_results // 2]
            chat_results = self._execute_query(chat_sql, chat_params)
            for row in chat_results:
                content = f"[{row['sender']}]: {row['content']}"
                doc = Document(
                    id=f"chat_{row['id']}",
                    content=content,
                    source=DataSource.CHAT_HISTORY,
                    metadata={
                        "sender": row["sender"],
                        "timestamp": row["timestamp"],
                        "character": row["character_name"],
                        "type": "chat_message",
                        "source": "characters",
                    },
                    score=0.5,
                )
                documents.append(doc)

        documents.sort(key=lambda x: x.score, reverse=True)
        logger.debug(f"Retrieved {len(documents)} documents from Character Cards")
        return documents

    async def get_metadata(self, doc_id: str) -> Dict[str, Any]:
        """Get metadata for a character card or chat."""
        if doc_id.startswith("character_"):
            card_id = doc_id.replace("character_", "")
            sql = "SELECT * FROM character_cards WHERE id = ?"
            results = self._execute_query(sql, (card_id,))
        elif doc_id.startswith("chat_"):
            chat_id = doc_id.replace("chat_", "")
            sql = """
                SELECT cm.*, cs.character_id, cc.name as character_name
                FROM chat_messages cm
                JOIN chat_sessions cs ON cm.session_id = cs.id
                LEFT JOIN character_cards cc ON cs.character_id = cc.id
                WHERE cm.id = ?
            """
            results = self._execute_query(sql, (chat_id,))
        else:
            return {}

        if results:
            return dict(results[0])

        return {}


class MultiDatabaseRetriever:
    """Orchestrates retrieval across multiple databases."""

    def __init__(
        self,
        db_paths: Dict[str, str],
        user_id: str = "0",
        *,
        media_db: Optional[Any] = None,
        chacha_db: Optional[Any] = None
    ):
        """
        Initialize multi-database retriever.

        Args:
            db_paths: Mapping of database names to paths
            user_id: User ID for vector store access
        """
        self.retrievers: Dict[DataSource, BaseRetriever] = {}

        # Initialize retrievers for available databases
        if "media_db" in db_paths:
            self.retrievers[DataSource.MEDIA_DB] = MediaDBRetriever(
                db_paths["media_db"], user_id=user_id, media_db=media_db
            )

        if "notes_db" in db_paths:
            self.retrievers[DataSource.NOTES] = NotesDBRetriever(
                db_paths["notes_db"],
                chacha_db=chacha_db,
            )

        if "prompts_db" in db_paths:
            self.retrievers[DataSource.PROMPTS] = PromptsDBRetriever(
                db_paths["prompts_db"],
                chacha_db=chacha_db,
            )

        if "character_cards_db" in db_paths:
            self.retrievers[DataSource.CHARACTER_CARDS] = CharacterCardsRetriever(
                db_paths["character_cards_db"],
                chacha_db=chacha_db,
            )
        # Optional: Claims retriever if provided
        if "claims_db" in db_paths:
            try:
                self.retrievers[DataSource.CLAIMS] = ClaimsRetriever(db_paths["claims_db"])
            except Exception as e:
                logger.debug(f"ClaimsRetriever init skipped: {e}")

    # Resource management
    def close(self) -> None:
        try:
            for retr in list(self.retrievers.values()):
                close_fn = getattr(retr, "close", None)
                if callable(close_fn):
                    try:
                        close_fn()
                    except Exception:
                        pass
        finally:
            self.retrievers.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self.close()
        except Exception:
            pass
        # Do not suppress exceptions
        return False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    async def retrieve(
        self,
        query: str,
        *,
        sources: Optional[List[DataSource]] = None,
        config: Optional[RetrievalConfig] = None,
        index_namespace: Optional[str] = None,
        # Optional per-source restrictions
        allowed_media_ids: Optional[List[int]] = None,
        allowed_note_ids: Optional[List[str]] = None,
    ) -> List[Document]:
        """
        Retrieve documents from one or more configured data sources.

        Args:
            query: The search query
            sources: Optional explicit list of `DataSource` to query. Defaults to all configured.
            config: Optional `RetrievalConfig` to apply to each retriever
            index_namespace: Optional namespace for vector stores

        Returns:
            A list of `Document` objects sorted by score (desc), capped by config.max_results if provided.
        """
        # Normalize the sources list
        ds_list: List[DataSource]
        if sources is None:
            ds_list = list(self.retrievers.keys())
        else:
            # Allow callers to pass strings; normalize to DataSource
            ds_list = []
            for s in sources:
                if isinstance(s, DataSource):
                    ds_list.append(s)
                else:
                    try:
                        ds_list.append(DataSource(str(s)))
                    except Exception:
                        continue

        documents: List[Document] = []
        tasks: List[Any] = []

        # Prepare async tasks for each source
        for src in ds_list:
            retr = self.retrievers.get(src)
            if retr is None:
                continue
            # Apply per-call config if provided
            if config is not None:
                retr.config = config

            # Prefer hybrid/vector when requested and available for Media DB
            if (
                isinstance(retr, MediaDBRetriever)
                and config is not None
                and getattr(config, "use_vector", False)
                and getattr(config, "use_fts", False)
                and hasattr(retr, "retrieve_hybrid")
            ):
                tasks.append(retr.retrieve_hybrid(
                    query=query,
                    index_namespace=index_namespace,
                    allowed_media_ids=allowed_media_ids,
                ))
            elif (
                isinstance(retr, MediaDBRetriever)
                and config is not None
                and getattr(config, "use_vector", False)
                and hasattr(retr, "_retrieve_vector")
            ):
                tasks.append(retr._retrieve_vector(
                    query,
                    index_namespace=index_namespace,
                    allowed_media_ids=allowed_media_ids,
                ))
            elif (
                isinstance(retr, MediaDBRetriever)
                and config is not None
                and getattr(config, "use_fts", True)
                and hasattr(retr, "_retrieve_fts")
            ):
                tasks.append(retr._retrieve_fts(query, allowed_media_ids=allowed_media_ids))
            else:
                # Generic retrieve; pass through allowed IDs where applicable
                if isinstance(retr, NotesDBRetriever):
                    tasks.append(retr.retrieve(query, allowed_note_ids=allowed_note_ids))
                elif isinstance(retr, MediaDBRetriever):
                    tasks.append(retr.retrieve(query, allowed_media_ids=allowed_media_ids))
                else:
                    tasks.append(retr.retrieve(query))

        # Execute all retrievals concurrently
        if tasks:
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                logger.error(f"Multi-database retrieval failed: {e}")
                results = []
        else:
            results = []

        # Flatten and filter out failures
        for res in results:
            if isinstance(res, Exception):
                # Skip failed sources (partial success expected)
                continue
            if isinstance(res, list):
                documents.extend(res)

        # Sort globally by score desc and cap by max_results
        documents.sort(key=lambda d: getattr(d, "score", 0.0), reverse=True)
        if config is not None and getattr(config, "max_results", None):
            documents = documents[: int(config.max_results)]

        return documents

    async def retrieve_with_fusion(
        self,
        query: str,
        *,
        sources: Optional[List[DataSource]] = None,
        fusion_method: str = "rrf",
    ) -> List[Document]:
        """Retrieve from multiple sources and fuse results."""
        # Collect per-source results
        source_results: Dict[DataSource, List[Document]] = {}
        ds_list = list(self.retrievers.keys()) if sources is None else sources
        for src in ds_list:
            retr = self.retrievers.get(src)
            if retr is None:
                continue
            try:
                docs = await retr.retrieve(query)
            except Exception:
                docs = []
            source_results[src] = docs

        # Apply fusion
        if fusion_method == "rrf":
            return self._reciprocal_rank_fusion(source_results)
        if fusion_method == "weighted":
            return self._weighted_fusion(source_results)
        if fusion_method == "max":
            return self._max_fusion(source_results)

        # Default: simple concatenation
        all_docs: List[Document] = []
        for docs in source_results.values():
            all_docs.extend(docs)
        return sorted(all_docs, key=lambda x: getattr(x, "score", 0.0), reverse=True)

    def _reciprocal_rank_fusion(
        self,
        source_results: Dict[DataSource, List[Document]],
        k: int = 60,
    ) -> List[Document]:
        doc_scores: Dict[str, Dict[str, Any]] = {}
        for _source, docs in source_results.items():
            for rank, doc in enumerate(docs, 1):
                if doc.id not in doc_scores:
                    doc_scores[doc.id] = {"doc": doc, "score": 0.0}
                doc_scores[doc.id]["score"] += 1.0 / (k + rank)

        fused_docs: List[Document] = [
            Document(
                id=item["doc"].id,
                content=item["doc"].content,
                source=item["doc"].source,
                metadata=item["doc"].metadata,
                score=float(item["score"]),
            )
            for item in sorted(doc_scores.values(), key=lambda x: x["score"], reverse=True)
        ]
        return fused_docs

    def _weighted_fusion(
        self,
        source_results: Dict[DataSource, List[Document]],
        weights: Optional[Dict[DataSource, float]] = None,
    ) -> List[Document]:
        weights = weights or {
            DataSource.MEDIA_DB: 1.0,
            DataSource.NOTES: 0.8,
            DataSource.PROMPTS: 0.6,
            DataSource.CHARACTER_CARDS: 0.5,
        }
        doc_scores: Dict[str, Dict[str, Any]] = {}
        for source, docs in source_results.items():
            w = weights.get(source, 1.0)
            for doc in docs:
                if doc.id not in doc_scores:
                    doc_scores[doc.id] = {"doc": doc, "score": 0.0}
                doc_scores[doc.id]["score"] += float(getattr(doc, "score", 0.0)) * w
        fused_docs: List[Document] = [
            Document(
                id=item["doc"].id,
                content=item["doc"].content,
                source=item["doc"].source,
                metadata=item["doc"].metadata,
                score=float(item["score"]),
            )
            for item in sorted(doc_scores.values(), key=lambda x: x["score"], reverse=True)
        ]
        return fused_docs

    def _max_fusion(
        self,
        source_results: Dict[DataSource, List[Document]],
    ) -> List[Document]:
        doc_map: Dict[str, Document] = {}
        for _source, docs in source_results.items():
            for doc in docs:
                existing = doc_map.get(doc.id)
                if existing is None or float(getattr(doc, "score", 0.0)) > float(
                    getattr(existing, "score", 0.0)
                ):
                    doc_map[doc.id] = doc
        return sorted(list(doc_map.values()), key=lambda d: getattr(d, "score", 0.0), reverse=True)

class ClaimsRetriever(BaseRetriever):
    """Retriever for Claims table (ingestion-time factual statements)."""

    def __init__(
        self,
        db_path: Optional[str],
        config: Optional[RetrievalConfig] = None,
        *,
        media_db: Optional['MediaDatabase'] = None
    ) -> None:
        super().__init__(db_path, config, db_adapter=media_db)
        attached = None
        own = False
        if media_db is None:
            attached = self._maybe_attach_media_db(db_path)
            own = attached is not None
        self.media_db = media_db or attached
        self._own_media_db = own

    def _maybe_attach_media_db(self, db_path: Optional[str]):
        if not db_path:
            return None
        try:
            from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase  # type: ignore
            return MediaDatabase(db_path=db_path, client_id="rag_service")
        except Exception:
            return None

    def close(self):
        try:
            if self._own_media_db and self.media_db is not None:
                close_fn = getattr(self.media_db, 'close_connection', None)
                if callable(close_fn):
                    close_fn()
        except Exception:
            pass

    async def retrieve(self, query: str, **kwargs) -> List[Document]:
        if self.media_db is not None:
            return self._retrieve_via_media_backend(query)

        documents: List[Document] = []
        try:
            # Try FTS on claims_fts first
            sql = (
                "SELECT c.id, c.media_id, c.chunk_index, c.claim_text "
                "FROM claims_fts JOIN Claims c ON claims_fts.rowid = c.id "
                "WHERE claims_fts MATCH ? AND c.deleted = 0 LIMIT ?"
            )
            params = (query, int(self.config.max_results))
            rows = self._execute_query(sql, params)
            for r in rows:
                doc_id = f"claim_{r['id']}"
                content = r["claim_text"]
                documents.append(
                    Document(
                        id=doc_id,
                        content=content,
                        metadata={
                            "media_id": r["media_id"],
                            "chunk_index": r["chunk_index"],
                            "source": "claim",
                        },
                        source=DataSource.CLAIMS,
                        score=0.6,
                    )
                )
            if not documents:
                # Fallback to LIKE if FTS returns no rows
                sql = (
                    "SELECT id, media_id, chunk_index, claim_text FROM Claims "
                    "WHERE deleted = 0 AND claim_text LIKE ? LIMIT ?"
                )
                params = (f"%{query}%", int(self.config.max_results))
                rows = self._execute_query(sql, params)
                for r in rows:
                    doc_id = f"claim_{r['id']}"
                    content = r["claim_text"]
                    documents.append(
                        Document(
                            id=doc_id,
                            content=content,
                            metadata={
                                "media_id": r["media_id"],
                                "chunk_index": r["chunk_index"],
                                "source": "claim",
                            },
                            source=DataSource.CLAIMS,
                            score=0.4,
                        )
                    )
        except Exception as e:
            logger.debug(f"Claims FTS failed, fallback to LIKE: {e}")
            sql = (
                "SELECT id, media_id, chunk_index, claim_text FROM Claims "
                "WHERE deleted = 0 AND claim_text LIKE ? LIMIT ?"
            )
            params = (f"%{query}%", int(self.config.max_results))
            rows = self._execute_query(sql, params)
            for r in rows:
                doc_id = f"claim_{r['id']}"
                content = r["claim_text"]
                documents.append(
                    Document(
                        id=doc_id,
                        content=content,
                        metadata={
                            "media_id": r["media_id"],
                            "chunk_index": r["chunk_index"],
                            "source": "claim",
                        },
                        source=DataSource.CLAIMS,
                        score=0.4,
                    )
                )
        return documents

    def _retrieve_via_media_backend(self, query: str) -> List[Document]:
        if self.media_db is None:
            return []
        try:
            results = self.media_db.search_claims(query, limit=int(self.config.max_results))
        except Exception as exc:  # noqa: BLE001
            logger.error(f"MediaDatabase claims search failed: {exc}")
            return []
        documents: List[Document] = []
        min_score = float(self.config.min_score or 0.0)
        backend_type = getattr(self.media_db, 'backend_type', None)
        for row in results:
            score = row.get('relevance_score') if isinstance(row, dict) else None
            try:
                score_val = float(score) if score is not None else 0.0
            except (TypeError, ValueError):
                score_val = 0.0
            if backend_type == BackendType.SQLITE:
                # SQLite bm25 returns lower (often negative) values for better matches.
                score_val = -score_val
            if score_val < min_score:
                continue
            metadata = {
                "media_id": row.get("media_id"),
                "chunk_index": row.get("chunk_index"),
                "source": "claim",
            }
            documents.append(
                Document(
                    id=f"claim_{row.get('id')}",
                    content=row.get('claim_text') or '',
                    metadata=metadata,
                    source=DataSource.CLAIMS,
                    score=score_val if score_val else 0.4,
                )
            )
        return documents

    async def get_metadata(self, doc_id: str) -> Dict[str, Any]:
        try:
            cid = doc_id.replace("claim_", "")
            sql = "SELECT * FROM Claims WHERE id = ?"
            rows = self._execute_query(sql, (cid,))
            return dict(rows[0]) if rows else {}
        except Exception:
            return {}

    # (no second retrieve method inside ClaimsRetriever)

# ---------------------------------------------------------------------------
# Backward compatibility aliases for test suites expecting older names
try:
    # Some tests import MediaDatabaseRetriever; map to MediaDBRetriever for compatibility
    MediaDatabaseRetriever = MediaDBRetriever  # type: ignore[name-defined]
except Exception:
    pass

    async def retrieve_with_fusion(
        self,
        query: str,
        sources: Optional[List[DataSource]] = None,
        fusion_method: str = "rrf"
    ) -> List[Document]:
        """
        Retrieve with result fusion across databases.

        Args:
            query: Search query
            sources: List of sources to search
            fusion_method: Fusion method (rrf, weighted, max)

        Returns:
            Fused list of documents
        """
        # Get results from each source
        source_results = {}
        sources = sources or list(self.retrievers.keys())

        for source in sources:
            if source in self.retrievers:
                docs = await self.retrievers[source].retrieve(query)
                source_results[source] = docs

        # Apply fusion
        if fusion_method == "rrf":
            return self._reciprocal_rank_fusion(source_results)
        elif fusion_method == "weighted":
            return self._weighted_fusion(source_results)
        elif fusion_method == "max":
            return self._max_fusion(source_results)
        else:
            # Simple concatenation
            all_docs = []
            for docs in source_results.values():
                all_docs.extend(docs)
            return sorted(all_docs, key=lambda x: x.score, reverse=True)

    def _reciprocal_rank_fusion(
        self,
        source_results: Dict[DataSource, List[Document]],
        k: int = 60
    ) -> List[Document]:
        """Apply Reciprocal Rank Fusion."""
        doc_scores = {}

        for source, docs in source_results.items():
            for rank, doc in enumerate(docs, 1):
                if doc.id not in doc_scores:
                    doc_scores[doc.id] = {"doc": doc, "score": 0}

                # RRF formula
                doc_scores[doc.id]["score"] += 1.0 / (k + rank)

        # Sort by fused score
        fused_docs = [
            Document(
                id=item["doc"].id,
                content=item["doc"].content,
                source=item["doc"].source,  # Preserve original source
                metadata=item["doc"].metadata,
                score=item["score"]
            )
            for item in sorted(
                doc_scores.values(),
                key=lambda x: x["score"],
                reverse=True
            )
        ]

        return fused_docs

    def _weighted_fusion(
        self,
        source_results: Dict[DataSource, List[Document]],
        weights: Optional[Dict[DataSource, float]] = None
    ) -> List[Document]:
        """Apply weighted fusion based on source importance."""
        # Default weights
        if not weights:
            weights = {
                DataSource.MEDIA_DB: 1.0,
                DataSource.NOTES: 0.8,
                DataSource.PROMPTS: 0.6,
                DataSource.CHARACTER_CARDS: 0.5
            }

        doc_scores = {}

        for source, docs in source_results.items():
            weight = weights.get(source, 1.0)

            for doc in docs:
                if doc.id not in doc_scores:
                    doc_scores[doc.id] = {"doc": doc, "score": 0}

                doc_scores[doc.id]["score"] += doc.score * weight

        # Create fused documents
        fused_docs = [
            Document(
                id=item["doc"].id,
                content=item["doc"].content,
                source=item["doc"].source,  # Preserve original source
                metadata=item["doc"].metadata,
                score=item["score"]
            )
            for item in sorted(
                doc_scores.values(),
                key=lambda x: x["score"],
                reverse=True
            )
        ]

        return fused_docs

    def _max_fusion(
        self,
        source_results: Dict[DataSource, List[Document]]
    ) -> List[Document]:
        """Take maximum score for each document across sources."""
        doc_scores = {}

        for source, docs in source_results.items():
            for doc in docs:
                if doc.id not in doc_scores:
                    doc_scores[doc.id] = doc
                elif doc.score > doc_scores[doc.id].score:
                    doc_scores[doc.id] = doc

        return sorted(doc_scores.values(), key=lambda x: x.score, reverse=True)


# Pipeline integration function
async def retrieve_from_databases(context: Any, **kwargs) -> Any:
    """Retrieve documents from configured databases for pipeline."""
    config = context.config.get("database_retrieval", {})

    # Get database paths from config
    db_paths = config.get("db_paths", {})
    if not db_paths:
        logger.warning("No database paths configured")
        return context

    # Create multi-database retriever
    retriever = MultiDatabaseRetriever(db_paths)

    # Configure retrieval
    retrieval_config = RetrievalConfig(
        max_results=config.get("max_results", 20),
        min_score=config.get("min_score", 0.0),
        use_fts=config.get("use_fts", True),
        include_metadata=config.get("include_metadata", True)
    )

    # Get sources to search
    sources = config.get("sources")
    if sources:
        sources = [DataSource[s.upper()] for s in sources]

    # Retrieve with fusion if enabled
    if config.get("use_fusion", True):
        documents = await retriever.retrieve_with_fusion(
            query=context.query,
            sources=sources,
            fusion_method=config.get("fusion_method", "rrf")
        )
    else:
        documents = await retriever.retrieve(
            query=context.query,
            sources=sources,
            config=retrieval_config
        )

    # Update context
    context.documents = documents
    context.metadata["database_retrieval"] = {
        "sources_searched": [s.value for s in (sources or retriever.retrievers.keys())],
        "documents_retrieved": len(documents),
        "fusion_used": config.get("use_fusion", True)
    }

    logger.info(f"Retrieved {len(documents)} documents from databases")

    return context
