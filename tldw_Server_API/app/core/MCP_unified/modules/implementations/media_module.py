"""
Media Module for Unified MCP

Production-ready media management module with full MCP compliance.
"""

import os
import asyncio
import uuid
import socket
import ipaddress
import hashlib
import json
from collections import OrderedDict
from urllib.parse import urlsplit
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
from loguru import logger

from ..base import BaseModule, ModuleConfig, create_tool_definition, create_resource_definition
from ....DB_Management.Media_DB_v2 import MediaDatabase
from ....DB_Management.db_path_utils import DatabasePaths


class MediaModule(BaseModule):
    """
    Enhanced Media Module with production features.

    Provides tools for:
    - Media search (full-text and semantic)
    - Media ingestion (URLs, files)
    - Transcript retrieval
    - Media metadata management
    - Summary generation
    """

    async def on_initialize(self) -> None:
        """Initialize media module with connection pooling"""
        try:
            # Get database path from config
            default_db_path = str(DatabasePaths.get_media_db_path(DatabasePaths.get_single_user_id()))
            db_path = self.config.settings.get("db_path") or default_db_path

            # Ensure database directory exists
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

            # Initialize database with async support
            self.db = MediaDatabase(
                db_path=db_path,
                client_id=f"mcp_media_{self.config.name}"
            )

            # Initialize connection pool if supported
            if hasattr(self.db, 'initialize_pool'):
                await self.db.initialize_pool(
                    pool_size=self.config.settings.get("pool_size", 10)
                )

            # Cache for frequently accessed data
            self._media_cache = {}
            self._cache_ttl = self.config.settings.get("cache_ttl", 300)  # 5 minutes
            self._semantic_retrievers: Dict[Tuple[Optional[str], Optional[str]], Any] = {}

            logger.info(f"Media module initialized with database: {db_path}")

        except Exception as e:
            logger.error(f"Failed to initialize media module: {e}")
            raise

    async def on_shutdown(self) -> None:
        """Graceful shutdown with connection cleanup"""
        try:
            # Clear cache
            self._media_cache.clear()
            try:
                if hasattr(self, "_semantic_retrievers"):
                    for retriever in self._semantic_retrievers.values():
                        close_fn = getattr(retriever, "close", None)
                        if callable(close_fn):
                            try:
                                close_fn()
                            except Exception:
                                pass
                    self._semantic_retrievers.clear()
            except Exception:
                pass

            # Close database connections
            if hasattr(self.db, 'close_pool'):
                await self.db.close_pool()

            logger.info("Media module shutdown complete")

        except Exception as e:
            logger.error(f"Error during media module shutdown: {e}")

    async def check_health(self) -> Dict[str, bool]:
        """Comprehensive health checks"""
        checks = {
            "database_connection": False,
            "database_writable": False,
            "disk_space": False,
            "service_available": True
        }

        try:
            # Check database connection (backend-agnostic)
            try:
                cur = self.db.execute_query("SELECT 1")
                _ = cur.fetchone()
                checks["database_connection"] = True
            except Exception as _db_e:
                logger.debug(f"Media DB connection check failed: {_db_e}")
                checks["database_connection"] = False

            # Check if database is writable (use a test table or transaction)
            # This is a simplified check - implement proper health check table
            try:
                # Use a short-lived transaction to avoid leaving artifacts
                with self.db.transaction():
                    self.db.execute_query("CREATE TABLE IF NOT EXISTS _mcp_healthcheck (k TEXT PRIMARY KEY, v TEXT)")
                    self.db.execute_query("INSERT OR REPLACE INTO _mcp_healthcheck(k, v) VALUES (?, ?)", ("ping", datetime.utcnow().isoformat()))
                    # Best-effort cleanup to keep DB tidy (ignore errors for non-SQLite backends)
                    try:
                        self.db.execute_query("DELETE FROM _mcp_healthcheck WHERE k = ?", ("ping",))
                    except Exception:
                        pass
                checks["database_writable"] = True
            except Exception as _w_e:
                logger.debug(f"Media DB writable check failed: {_w_e}")
                checks["database_writable"] = False

            # Check disk space
            default_db_path = str(DatabasePaths.get_media_db_path(DatabasePaths.get_single_user_id()))
            db_path = self.config.settings.get("db_path", default_db_path)
            stat = os.statvfs(os.path.dirname(db_path))
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
            checks["disk_space"] = free_gb > 1  # At least 1GB free

        except Exception as e:
            logger.error(f"Health check failed: {e}")

        return checks

    async def get_tools(self) -> List[Dict[str, Any]]:
        """Get available media tools"""
        tools = [
            # Context-search tools (FTS-only v1)
            create_tool_definition(
                name="media.search",
                description="Search media by title/content with optional filters (FTS-only).",
                parameters={
                    "properties": {
                        "query": {"type": "string", "minLength": 1, "maxLength": 1000},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
                        "offset": {"type": "integer", "minimum": 0, "default": 0},
                        "snippet_length": {"type": "integer", "minimum": 50, "maximum": 2000, "default": 300},
                        "media_types": {"type": "array", "items": {"type": "string"}},
                        "date_from": {"type": "string", "description": "ISO 8601 start date"},
                        "date_to": {"type": "string", "description": "ISO 8601 end date"},
                        "order_by": {"type": "string", "enum": ["relevance", "recent"], "default": "relevance"}
                    },
                    "required": ["query"],
                },
                metadata={"category": "search", "readOnlyHint": True},
            ),
            create_tool_definition(
                name="media.get",
                description="Retrieve media content or snippet by id.",
                parameters={
                    "properties": {
                        "media_id": {"type": "integer"},
                        "retrieval": {
                            "type": "object",
                            "properties": {
                                "mode": {"type": "string", "enum": ["snippet", "full"], "default": "snippet"},
                                "snippet_length": {"type": "integer", "minimum": 50, "maximum": 2000, "default": 300},
                            }
                        }
                    },
                    "required": ["media_id"],
                },
                metadata={"category": "retrieval", "readOnlyHint": True},
            ),
            create_tool_definition(
                name="search_media",
                description="Search for media content using keywords or semantic search",
                parameters={
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                            "minLength": 1,
                            "maxLength": 1000
                        },
                        "search_type": {
                            "type": "string",
                            "enum": ["keyword", "semantic", "hybrid"],
                            "default": "keyword",
                            "description": "Type of search to perform"
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 10,
                            "description": "Maximum number of results"
                        },
                        "offset": {
                            "type": "integer",
                            "minimum": 0,
                            "default": 0,
                            "description": "Pagination offset"
                        }
                    },
                    "required": ["query"]
                },
                metadata={"category": "search", "auth_required": False}
            ),

            create_tool_definition(
                name="get_transcript",
                description="Get the transcript for a specific media item",
                parameters={
                    "properties": {
                        "media_id": {
                            "type": "integer",
                            "description": "ID of the media item"
                        },
                        "include_timestamps": {
                            "type": "boolean",
                            "default": False,
                            "description": "Include timestamps in transcript"
                        },
                        "format": {
                            "type": "string",
                            "enum": ["text", "srt", "vtt", "json"],
                            "default": "text",
                            "description": "Output format"
                        }
                    },
                    "required": ["media_id"]
                },
                metadata={"category": "retrieval", "auth_required": True}
            ),

            create_tool_definition(
                name="get_media_metadata",
                description="Get metadata for a specific media item",
                parameters={
                    "properties": {
                        "media_id": {
                            "type": "integer",
                            "description": "ID of the media item"
                        },
                        "include_stats": {
                            "type": "boolean",
                            "default": False,
                            "description": "Include usage statistics"
                        }
                    },
                    "required": ["media_id"]
                },
                metadata={"category": "metadata", "auth_required": False}
            ),

            create_tool_definition(
                name="ingest_media",
                description="Ingest a new media item from URL or file",
                parameters={
                    "properties": {
                        "url": {
                            "type": "string",
                            "format": "uri",
                            "description": "URL of the media to ingest"
                        },
                        "title": {
                            "type": "string",
                            "description": "Optional title for the media"
                        },
                        "process_type": {
                            "type": "string",
                            "enum": ["transcribe", "summarize", "both", "none"],
                            "default": "transcribe",
                            "description": "Type of processing to perform"
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Tags for categorization"
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "normal", "high"],
                            "default": "normal",
                            "description": "Processing priority"
                        }
                    },
                    "required": ["url"]
                },
                metadata={"category": "ingestion", "auth_required": True, "admin_only": False}
            ),

            create_tool_definition(
                name="update_media",
                description="Update media metadata or content",
                parameters={
                    "properties": {
                        "media_id": {
                            "type": "integer",
                            "description": "ID of the media item"
                        },
                        "updates": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "tags": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                }
                            }
                        }
                    },
                    "required": ["media_id", "updates"]
                },
                metadata={"category": "management", "auth_required": True}
            ),

            create_tool_definition(
                name="delete_media",
                description="Delete a media item (soft delete)",
                parameters={
                    "properties": {
                        "media_id": {
                            "type": "integer",
                            "description": "ID of the media item"
                        },
                        "permanent": {
                            "type": "boolean",
                            "default": False,
                            "description": "Permanently delete (admin only)"
                        }
                    },
                    "required": ["media_id"]
                },
                metadata={"category": "management", "auth_required": True}
            )
        ]
        return tools

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], context: Any | None = None) -> Any:
        """Execute media tool with validation and error handling"""
        # Validate and sanitize inputs
        arguments = self.sanitize_input(arguments)
        # High-risk operations: validate against stricter schema
        try:
            self.validate_tool_arguments(tool_name, arguments)
        except Exception as ve:
            raise ValueError(f"Invalid arguments for {tool_name}: {ve}")

        # Log tool execution
        logger.info(f"Executing media tool: {tool_name}", extra={"audit": True})

        try:
            if tool_name == "media.search":
                return await self._media_search_normalized(context=context, **arguments)
            elif tool_name == "media.get":
                return await self._media_get_normalized(context=context, **arguments)
            elif tool_name == "search_media":
                return await self._search_media(context=context, **arguments)

            elif tool_name == "get_transcript":
                return await self._get_transcript(context=context, **arguments)

            elif tool_name == "get_media_metadata":
                return await self._get_media_metadata(context=context, **arguments)

            elif tool_name == "ingest_media":
                return await self._ingest_media(**arguments)

            elif tool_name == "update_media":
                return await self._update_media(context=context, **arguments)

            elif tool_name == "delete_media":
                return await self._delete_media(context=context, **arguments)

            else:
                raise ValueError(f"Unknown tool: {tool_name}")

        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name} - {e}")
            raise

    def _open_media_db(self, context: Any | None) -> MediaDatabase:
        """Open per-user media DB when context provides one; fallback to module DB."""
        try:
            if context and getattr(context, "db_paths", None):
                user_media_path = context.db_paths.get("media")
                if user_media_path and str(user_media_path) != str(getattr(self.db, "db_path_str", "")):
                    return MediaDatabase(db_path=user_media_path, client_id=f"mcp_media_{self.config.name}")
        except Exception:
            pass
        return self.db

    def _normalize_scores(self, rows: List[Dict[str, Any]]) -> List[float]:
        if not rows:
            return []
        # If relevance_score present (bm25-like), lower is better
        if all((r.get("relevance_score") is not None) for r in rows):
            vals = [float(r.get("relevance_score") or 0.0) for r in rows]
            mn, mx = min(vals), max(vals)
            if mx - mn < 1e-9:
                return [1.0 for _ in vals]
            return [(mx - v) / (mx - mn + 1e-9) for v in vals]
        # Fallback positional decay
        n = len(rows)
        if n == 1:
            return [1.0]
        return [1.0 - (i / max(1, n - 1)) for i in range(n)]

    def _make_snippet(self, text: Optional[str], query: Optional[str], length: int = 300) -> str:
        if not text:
            return ""
        length = max(50, min(length, 2000))
        t = " ".join(text.split())
        if not query:
            return t[:length]
        try:
            idx = t.lower().find(query.lower())
            if idx == -1:
                return t[:length]
            half = max(0, length // 2)
            start = max(0, idx - half)
            end = min(len(t), start + length)
            return t[start:end]
        except Exception:
            return t[:length]

    async def _media_search_normalized(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        snippet_length: int = 300,
        media_types: Optional[List[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        order_by: str = "relevance",
        context: Any | None = None,
    ) -> Dict[str, Any]:
        # Session defaults
        try:
            if context and getattr(context, "metadata", None):
                sc = context.metadata.get("safe_config")
                if isinstance(sc, dict):
                    snippet_length = int(sc.get("snippet_length", snippet_length))
        except Exception:
            pass

        # Build date_range
        date_range = None
        try:
            if date_from or date_to:
                from datetime import datetime as _dt
                date_range = {}
                if date_from:
                    date_range["start_date"] = _dt.fromisoformat(date_from)
                if date_to:
                    date_range["end_date"] = _dt.fromisoformat(date_to)
        except Exception:
            date_range = None

        # Map order
        sort_by = "relevance" if order_by == "relevance" else "last_modified_desc"
        page = (offset // max(1, limit)) + 1 if limit > 0 else 1
        dbi = self._open_media_db(context)
        results, total = dbi.search_media_db(
            search_query=query,
            search_fields=["title", "content"],
            media_types=media_types or None,
            date_range=date_range,
            sort_by=sort_by,
            page=page,
            results_per_page=limit,
            include_trash=False,
            include_deleted=False,
        )
        scores = self._normalize_scores(results)
        out = []
        for i, r in enumerate(results):
            mid = r.get("id")
            content = r.get("content") or ""
            # Compute an approximate offset of query within content as a location hint
            approx_offset = None
            try:
                idx = content.lower().find(query.lower()) if query else -1
                if idx >= 0:
                    approx_offset = idx
            except Exception:
                approx_offset = None
            # Try to map to prechunked chunk_index when available
            loc_hint = None
            try:
                if approx_offset is not None and isinstance(mid, (int, str)):
                    mid_int = int(mid)
                    if self._open_media_db(context).has_unvectorized_chunks(mid_int):
                        cidx = self._open_media_db(context).get_unvectorized_anchor_index_for_offset(mid_int, int(approx_offset))
                        if cidx is not None:
                            loc_hint = {"chunk_index": cidx}
            except Exception:
                loc_hint = None
            out.append({
                "id": mid,
                "source": "media",
                "title": r.get("title"),
                "snippet": self._make_snippet(content, query, snippet_length),
                "uri": f"media://{mid}",
                "score": float(scores[i] if i < len(scores) else 0.0),
                "score_type": "fts",
                "created_at": r.get("ingestion_date"),
                "last_modified": r.get("last_modified"),
                "version": r.get("version"),
                "tags": None,
                "media_type": r.get("type"),
                "url": r.get("url"),
                "loc": (loc_hint if loc_hint is not None else ({"approx_offset": approx_offset} if approx_offset is not None else None)),
            })
        return {
            "results": out,
            "has_more": (offset + len(results)) < total,
            "next_offset": (offset + len(results)) if (offset + len(results)) < total else None,
            "total_estimated": total,
        }

    async def _media_get_normalized(self, media_id: int, retrieval: Optional[Dict[str, Any]] = None, context: Any | None = None) -> Dict[str, Any]:
        retrieval = retrieval or {}
        mode = retrieval.get("mode", "snippet")
        snippet_length = int(retrieval.get("snippet_length", 300))
        max_tokens = retrieval.get("max_tokens")
        cpt = int(retrieval.get("chars_per_token", 4))
        chunk_size_tokens = int(retrieval.get("chunk_size_tokens", 1000 if max_tokens else 500))
        sibling_window = int(retrieval.get("sibling_window", 1))
        loc = retrieval.get("loc") or {}
        # Session defaults
        try:
            if context and getattr(context, "metadata", None):
                sc = context.metadata.get("safe_config")
                if isinstance(sc, dict):
                    snippet_length = int(sc.get("snippet_length", snippet_length))
                    if isinstance(sc.get("chars_per_token"), int):
                        cpt = int(sc.get("chars_per_token"))
        except Exception:
            pass

        dbi = self._open_media_db(context)
        # Use active media row for metadata + content
        meta = dbi.get_media_by_id(media_id, include_deleted=False, include_trash=False)
        if not meta:
            raise ValueError(f"Media not found: {media_id}")
        # Ownership check
        self._assert_media_access(media_id, context)
        content = meta.get("content") or ""
        item = {
            "id": meta.get("id"),
            "source": "media",
            "title": meta.get("title"),
            "snippet": self._make_snippet(content, None, snippet_length),
            "uri": f"media://{meta.get('id')}",
            "score": 1.0,
            "score_type": "fts",
            "created_at": meta.get("ingestion_date"),
            "last_modified": meta.get("last_modified"),
            "version": meta.get("version"),
            "tags": None,
            "media_type": meta.get("type"),
            "url": meta.get("url"),
            "loc": None,
        }
        if mode == "full":
            body = content
            return {"meta": item, "content": body, "attachments": None}

        # Helper for on-the-fly chunking
        def _chunkify(text: str, size_chars: int) -> List[str]:
            if size_chars <= 0:
                size_chars = 1000 * cpt
            chunks = []
            i = 0
            n = len(text)
            while i < n:
                chunks.append(text[i:i+size_chars])
                i += size_chars
            return chunks

        def _estimate_tokens(chars: int) -> int:
            return max(1, (chars + cpt - 1) // cpt)

        # If chunking modes requested:
        if mode in {"chunk", "chunk_with_siblings", "auto"}:
            if mode == "auto" and max_tokens:
                mode = "chunk_with_siblings"
            elif mode == "auto":
                mode = "snippet"

            # Prefer prechunked retrieval when available
            prefer_prechunked = bool(retrieval.get("prefer_prechunked", True))
            anchor_index: Optional[int] = None
            anchor_uuid: Optional[str] = None

            # Extract loc hints
            approx_offset = None
            try:
                if isinstance(loc, dict) and isinstance(loc.get("approx_offset"), int):
                    approx_offset = int(loc.get("approx_offset"))
            except Exception:
                approx_offset = None
            if isinstance(loc, dict) and isinstance(loc.get("chunk_index"), int):
                anchor_index = int(loc.get("chunk_index"))
            if isinstance(loc, dict) and isinstance(loc.get("chunk_uuid"), str):
                anchor_uuid = str(loc.get("chunk_uuid"))

            if prefer_prechunked and dbi.has_unvectorized_chunks(media_id):
                # Resolve anchor by uuid or offset
                if anchor_index is None and anchor_uuid:
                    anchor_index = dbi.get_unvectorized_chunk_index_by_uuid(media_id, anchor_uuid)
                if anchor_index is None and isinstance(approx_offset, int):
                    anchor_index = dbi.get_unvectorized_anchor_index_for_offset(media_id, approx_offset)
                if anchor_index is None:
                    anchor_index = 0

                anchor_list = dbi.get_unvectorized_chunks_in_range(media_id, anchor_index, anchor_index)
                if anchor_list:
                    anchor_chunk = anchor_list[0]
                    anchor_uuid = anchor_chunk.get("uuid") or anchor_uuid

                    if mode == "chunk":
                        body = anchor_chunk.get("chunk_text") or ""
                        item["loc"] = {"chunk_index": anchor_index, "chunk_uuid": anchor_uuid}
                        return {"meta": item, "content": body, "attachments": None}

                    # chunk_with_siblings budgeted expansion
                    budget_tokens = int(max_tokens) if max_tokens else None
                    selected_indexes: List[int] = [anchor_index]
                    selected_texts: Dict[int, str] = {anchor_index: anchor_chunk.get("chunk_text") or ""}
                    if budget_tokens is None:
                        for d in range(1, max(1, sibling_window) + 1):
                            li = anchor_index - d
                            ri = anchor_index + d
                            if li >= 0:
                                left_chunks = dbi.get_unvectorized_chunks_in_range(media_id, li, li)
                                if left_chunks:
                                    selected_indexes.insert(0, li)
                                    selected_texts[li] = left_chunks[0].get("chunk_text") or ""
                            right_chunks = dbi.get_unvectorized_chunks_in_range(media_id, ri, ri)
                            if right_chunks:
                                selected_indexes.append(ri)
                                selected_texts[ri] = right_chunks[0].get("chunk_text") or ""
                    else:
                        current_tokens = _estimate_tokens(len(selected_texts[anchor_index]))
                        left = anchor_index - 1
                        right = anchor_index + 1
                        while True:
                            progressed = False
                            if left >= 0:
                                lc = dbi.get_unvectorized_chunks_in_range(media_id, left, left)
                                if lc:
                                    t_add = _estimate_tokens(len(lc[0].get("chunk_text") or ""))
                                    if current_tokens + t_add <= budget_tokens:
                                        selected_indexes.insert(0, left)
                                        selected_texts[left] = lc[0].get("chunk_text") or ""
                                        current_tokens += t_add
                                        left -= 1
                                        progressed = True
                            rc = dbi.get_unvectorized_chunks_in_range(media_id, right, right)
                            if rc:
                                t_add = _estimate_tokens(len(rc[0].get("chunk_text") or ""))
                                if current_tokens + t_add <= budget_tokens:
                                    selected_indexes.append(right)
                                    selected_texts[right] = rc[0].get("chunk_text") or ""
                                    current_tokens += t_add
                                    right += 1
                                    progressed = True
                            if not progressed:
                                break

                    body = "\n\n".join([selected_texts[i] for i in selected_indexes])
                    item["loc"] = {"chunk_index": anchor_index, "chunk_uuid": anchor_uuid}
                    return {"meta": item, "content": body, "attachments": None}

            # Fallback: on-the-fly chunking from full content
            size_chars = max(1, chunk_size_tokens * cpt)
            chunks = _chunkify(content, size_chars)
            if not chunks:
                body = self._make_snippet(content, None, snippet_length)
                return {"meta": item, "content": body, "attachments": None}

            if approx_offset is None:
                anchor_index = 0
            else:
                anchor_index = max(0, min(len(chunks) - 1, approx_offset // size_chars))

            if mode == "chunk":
                body = chunks[anchor_index]
                item["loc"] = {"chunk_index": anchor_index, "approx_offset": anchor_index * size_chars}
                return {"meta": item, "content": body, "attachments": None}

            budget_tokens = int(max_tokens) if max_tokens else None
            sel = [anchor_index]
            if budget_tokens is None:
                for d in range(1, max(1, sibling_window) + 1):
                    if anchor_index - d >= 0:
                        sel.insert(0, anchor_index - d)
                    if anchor_index + d < len(chunks):
                        sel.append(anchor_index + d)
            else:
                current_tokens = _estimate_tokens(len(chunks[anchor_index]))
                left = anchor_index - 1
                right = anchor_index + 1
                while True:
                    progressed = False
                    if left >= 0:
                        t_add = _estimate_tokens(len(chunks[left]))
                        if current_tokens + t_add <= budget_tokens:
                            sel.insert(0, left)
                            current_tokens += t_add
                            left -= 1
                            progressed = True
                    if right < len(chunks):
                        t_add = _estimate_tokens(len(chunks[right]))
                        if current_tokens + t_add <= budget_tokens:
                            sel.append(right)
                            current_tokens += t_add
                            right += 1
                            progressed = True
                    if not progressed:
                        break

            selected_chunks = [chunks[i] for i in sel]
            body = "\n\n".join(selected_chunks)
            item["loc"] = {"chunk_index": anchor_index, "approx_offset": anchor_index * size_chars}
            return {"meta": item, "content": body, "attachments": None}

        # Default snippet mode
        body = self._make_snippet(content, None, snippet_length)
        return {"meta": item, "content": body, "attachments": None}

    async def _search_media(
        self,
        query: str,
        search_type: str = "keyword",
        limit: int = 10,
        offset: int = 0,
        context: Any | None = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Search media with caching and unified keyword/semantic support."""
        if not query or len(query) > 1000:
            raise ValueError("Invalid search query")

        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))

        dbi = self._open_media_db(context)

        search_fields = kwargs.get("search_fields")
        media_types = kwargs.get("media_types")
        date_range = kwargs.get("date_range")
        must_have_keywords = kwargs.get("must_have_keywords")
        must_not_have_keywords = kwargs.get("must_not_have_keywords")
        sort_by_value = kwargs.get("sort_by")
        order_by_param = kwargs.get("order_by")
        if sort_by_value is None and isinstance(order_by_param, str):
            order_key = order_by_param.strip().lower()
            if order_key == "relevance":
                sort_by_value = "relevance"
            elif order_key in {"recent", "last_modified_desc"}:
                sort_by_value = "last_modified_desc"
            elif order_key == "last_modified_asc":
                sort_by_value = "last_modified_asc"
            elif order_key in {"date_desc", "ingestion_desc"}:
                sort_by_value = "date_desc"
            elif order_key in {"date_asc", "ingestion_asc"}:
                sort_by_value = "date_asc"
            elif order_key in {"title_asc", "title_desc"}:
                sort_by_value = order_key

        media_ids_filter = kwargs.get("media_ids_filter")
        include_trash = bool(kwargs.get("include_trash", False))
        include_deleted = bool(kwargs.get("include_deleted", False))
        metadata_filter = kwargs.get("metadata_filter")
        index_namespace = kwargs.get("index_namespace")
        query_vector = kwargs.get("query_vector")

        cache_payload = {
            "db_path": getattr(dbi, "db_path_str", None),
            "query": query,
            "search_type": search_type,
            "limit": limit,
            "offset": offset,
            "search_fields": search_fields,
            "media_types": media_types,
            "date_range": date_range,
            "must_have_keywords": must_have_keywords,
            "must_not_have_keywords": must_not_have_keywords,
            "sort_by": sort_by_value,
            "order_by": order_by_param,
            "media_ids_filter": media_ids_filter,
            "include_trash": include_trash,
            "include_deleted": include_deleted,
            "metadata_filter": metadata_filter,
            "index_namespace": index_namespace,
            "user_id": getattr(context, "user_id", None),
        }
        if query_vector is not None:
            cache_payload["query_vector"] = query_vector

        cache_key = self._make_cache_key("search_media", cache_payload)
        cached = self._media_cache.get(cache_key)
        if cached and (datetime.utcnow() - cached["time"]).seconds < self._cache_ttl:
            logger.debug(f"Cache hit for search: {cache_key}")
            return cached["data"]

        try:
            if search_type == "keyword":
                rows, total = self._keyword_search(
                    dbi=dbi,
                    query=query,
                    limit=limit,
                    offset=offset,
                    search_fields=search_fields,
                    media_types=media_types,
                    date_range=date_range,
                    must_have_keywords=must_have_keywords,
                    must_not_have_keywords=must_not_have_keywords,
                    sort_by_value=sort_by_value,
                    media_ids_filter=media_ids_filter,
                    include_trash=include_trash,
                    include_deleted=include_deleted,
                )
            elif search_type == "semantic":
                rows, total = await self._semantic_search(
                    query=query,
                    limit=limit,
                    offset=offset,
                    dbi=dbi,
                    media_types=media_types,
                    metadata_filter=metadata_filter,
                    index_namespace=index_namespace,
                    media_ids_filter=media_ids_filter,
                    context=context,
                    query_vector=query_vector,
                )
            elif search_type == "hybrid":
                rows, total = await self._hybrid_search(
                    query=query,
                    limit=limit,
                    offset=offset,
                    dbi=dbi,
                    media_types=media_types,
                    date_range=date_range,
                    must_have_keywords=must_have_keywords,
                    must_not_have_keywords=must_not_have_keywords,
                    sort_by_value=sort_by_value,
                    media_ids_filter=media_ids_filter,
                    include_trash=include_trash,
                    include_deleted=include_deleted,
                    search_fields=search_fields,
                    metadata_filter=metadata_filter,
                    index_namespace=index_namespace,
                    context=context,
                    query_vector=query_vector,
                )
            else:
                raise ValueError(f"Unknown search type: {search_type}")

            formatted_results = {
                "query": query,
                "type": search_type,
                "count": len(rows),
                "results": rows,
                "offset": offset,
                "limit": limit,
                "total": total,
            }

            self._media_cache[cache_key] = {
                "time": datetime.utcnow(),
                "data": formatted_results,
            }
            await self._clean_cache()
            return formatted_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def _serialize_for_cache(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(k): self._serialize_for_cache(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
        if isinstance(value, (list, tuple, set)):
            return [self._serialize_for_cache(v) for v in value]
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, (bytes, bytearray)):
            return value.hex()
        return value

    def _make_cache_key(self, namespace: str, payload: Dict[str, Any]) -> str:
        try:
            normalised = self._serialize_for_cache(payload)
            raw = json.dumps(normalised, sort_keys=True, separators=(",", ":"))
        except Exception:
            raw = repr(payload)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"{namespace}:{digest}"

    def _keyword_search(
        self,
        dbi: MediaDatabase,
        query: str,
        limit: int,
        offset: int,
        *,
        search_fields: Optional[List[str]],
        media_types: Optional[List[str]],
        date_range: Optional[Dict[str, Any]],
        must_have_keywords: Optional[List[str]],
        must_not_have_keywords: Optional[List[str]],
        sort_by_value: Optional[str],
        media_ids_filter: Optional[List[Any]],
        include_trash: bool,
        include_deleted: bool,
    ) -> Tuple[List[Dict[str, Any]], int]:
        page = (offset // max(1, limit)) + 1
        rows, total = dbi.search_media_db(
            search_query=query,
            search_fields=search_fields,
            media_types=media_types,
            date_range=date_range,
            must_have_keywords=must_have_keywords,
            must_not_have_keywords=must_not_have_keywords,
            sort_by=sort_by_value or "last_modified_desc",
            media_ids_filter=media_ids_filter,
            page=page,
            results_per_page=limit,
            include_trash=include_trash,
            include_deleted=include_deleted,
        )
        return rows, total

    def _keyword_search_head(
        self,
        dbi: MediaDatabase,
        query: str,
        size: int,
        *,
        search_fields: Optional[List[str]],
        media_types: Optional[List[str]],
        date_range: Optional[Dict[str, Any]],
        must_have_keywords: Optional[List[str]],
        must_not_have_keywords: Optional[List[str]],
        sort_by_value: Optional[str],
        media_ids_filter: Optional[List[Any]],
        include_trash: bool,
        include_deleted: bool,
    ) -> Tuple[List[Dict[str, Any]], int]:
        fetch_ceiling = int(self.config.settings.get("hybrid_fetch_ceiling", 200))
        fetch_size = max(1, min(int(size), fetch_ceiling))
        rows, total = dbi.search_media_db(
            search_query=query,
            search_fields=search_fields,
            media_types=media_types,
            date_range=date_range,
            must_have_keywords=must_have_keywords,
            must_not_have_keywords=must_not_have_keywords,
            sort_by=sort_by_value or "last_modified_desc",
            media_ids_filter=media_ids_filter,
            page=1,
            results_per_page=fetch_size,
            include_trash=include_trash,
            include_deleted=include_deleted,
        )
        return rows[:fetch_size], total

    def _get_semantic_retriever(self, dbi: MediaDatabase, context: Any | None):
        db_path = getattr(dbi, "db_path_str", None)
        user_key = str(getattr(context, "user_id", None) or "0")
        retriever_key = (db_path, user_key)
        retriever = self._semantic_retrievers.get(retriever_key)
        if retriever is False:
            return None
        if retriever is None:
            try:
                from tldw_Server_API.app.core.RAG.rag_service.database_retrievers import (  # lazy import
                    MediaDBRetriever,
                    RetrievalConfig,
                )
                config = RetrievalConfig(max_results=20, use_fts=True, use_vector=True)
                retriever = MediaDBRetriever(
                    db_path=db_path,
                    config=config,
                    user_id=user_key,
                    media_db=dbi,
                )
                self._semantic_retrievers[retriever_key] = retriever
            except Exception as exc:
                logger.debug(f"Semantic retriever unavailable: {exc}")
                self._semantic_retrievers[retriever_key] = False  # sentinel to avoid retries
                return None
        return retriever

    async def _semantic_search(
        self,
        *,
        query: str,
        limit: int,
        offset: int,
        dbi: MediaDatabase,
        media_types: Optional[List[str]],
        metadata_filter: Optional[Dict[str, Any]],
        index_namespace: Any,
        media_ids_filter: Optional[List[Any]],
        context: Any | None,
        query_vector: Any,
    ) -> Tuple[List[Dict[str, Any]], int]:
        retriever = self._get_semantic_retriever(dbi, context)
        if retriever is None:
            return [], 0
        max_results = max(1, limit + offset)
        try:
            retriever.config.max_results = max_results
        except Exception:
            pass

        media_type_arg: Optional[str] = None
        if isinstance(media_types, list) and len(media_types) == 1:
            media_type_arg = media_types[0]

        try:
            docs = await retriever._retrieve_vector(  # type: ignore[attr-defined]
                query,
                media_type=media_type_arg,
                metadata_filter=metadata_filter,
                index_namespace=index_namespace,
                allowed_media_ids=media_ids_filter,
                query_vector=query_vector,
            )
        except Exception as exc:
            logger.debug(f"Semantic retrieval failed, falling back to empty set: {exc}")
            docs = []

        allowed_types = {t.lower() for t in media_types} if media_types else None
        rows: List[Dict[str, Any]] = []
        for doc in docs or []:
            meta = getattr(doc, "metadata", {}) or {}
            media_type_val = (
                meta.get("media_type")
                or meta.get("type")
                or meta.get("mediaType")
                or meta.get("kind")
            )
            if allowed_types:
                if not media_type_val:
                    continue
                if str(media_type_val).lower() not in allowed_types:
                    continue
            doc_id = getattr(doc, "id", None)
            try:
                media_id = int(doc_id) if doc_id is not None else None
            except (TypeError, ValueError):
                media_id = doc_id
            record = {
                "id": media_id,
                "title": meta.get("title"),
                "content": getattr(doc, "content", None),
                "type": media_type_val or meta.get("type"),
                "media_type": media_type_val or meta.get("type"),
                "url": meta.get("url"),
                "ingestion_date": meta.get("created_at") or meta.get("ingestion_date"),
                "last_modified": meta.get("last_modified"),
                "semantic_score": float(getattr(doc, "score", 0.0) or 0.0),
                "score_type": "semantic",
            }
            rows.append(record)

        total = len(rows)
        return rows[offset: offset + limit], total

    async def _hybrid_search(
        self,
        *,
        query: str,
        limit: int,
        offset: int,
        dbi: MediaDatabase,
        media_types: Optional[List[str]],
        date_range: Optional[Dict[str, Any]],
        must_have_keywords: Optional[List[str]],
        must_not_have_keywords: Optional[List[str]],
        sort_by_value: Optional[str],
        media_ids_filter: Optional[List[Any]],
        include_trash: bool,
        include_deleted: bool,
        search_fields: Optional[List[str]],
        metadata_filter: Optional[Dict[str, Any]],
        index_namespace: Any,
        context: Any | None,
        query_vector: Any,
    ) -> Tuple[List[Dict[str, Any]], int]:
        fetch_size = limit + offset
        keyword_rows_all, keyword_total = self._keyword_search_head(
            dbi=dbi,
            query=query,
            size=fetch_size,
            search_fields=search_fields,
            media_types=media_types,
            date_range=date_range,
            must_have_keywords=must_have_keywords,
            must_not_have_keywords=must_not_have_keywords,
            sort_by_value=sort_by_value,
            media_ids_filter=media_ids_filter,
            include_trash=include_trash,
            include_deleted=include_deleted,
        )

        semantic_rows_all, semantic_total = await self._semantic_search(
            query=query,
            limit=max(1, fetch_size),
            offset=0,
            dbi=dbi,
            media_types=media_types,
            metadata_filter=metadata_filter,
            index_namespace=index_namespace,
            media_ids_filter=media_ids_filter,
            context=context,
            query_vector=query_vector,
        )

        combined: "OrderedDict[Any, Dict[str, Any]]" = OrderedDict()
        for row in keyword_rows_all:
            key = row.get("id")
            if key is None:
                continue
            merged = dict(row)
            merged.setdefault("score_type", "fts")
            combined[key] = merged

        for row in semantic_rows_all:
            key = row.get("id")
            if key is None:
                continue
            merged = dict(row)
            existing = combined.get(key)
            if existing:
                if "semantic_score" in merged:
                    existing["semantic_score"] = merged["semantic_score"]
                existing["score_type"] = "hybrid"
            else:
                combined[key] = merged

        combined_rows = list(combined.values())
        total_estimate = max(keyword_total, semantic_total, len(combined_rows))
        paged = combined_rows[offset: offset + limit]
        for row in paged:
            row.setdefault("score_type", "hybrid")
        return paged, total_estimate

    async def _get_transcript(
        self,
        media_id: int,
        include_timestamps: bool = False,
        format: str = "text",
        context: Any | None = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Get media transcript with formatting options"""
        try:
            # Ownership check first
            self._assert_media_access(media_id, context)
            # Get transcript from database
            transcript_data = self.db.get_transcript(media_id)

            if not transcript_data:
                raise ValueError(f"No transcript found for media ID: {media_id}")

            # Format based on requested type
            if format == "text":
                if include_timestamps:
                    # Include timestamps in text format
                    formatted = self._format_transcript_with_timestamps(transcript_data)
                else:
                    formatted = transcript_data.get("text", "")

            elif format == "srt":
                formatted = self._convert_to_srt(transcript_data)

            elif format == "vtt":
                formatted = self._convert_to_vtt(transcript_data)

            elif format == "json":
                formatted = transcript_data

            else:
                formatted = transcript_data.get("text", "")

            return {
                "media_id": media_id,
                "format": format,
                "include_timestamps": include_timestamps,
                "transcript": formatted
            }

        except Exception as e:
            logger.error(f"Failed to get transcript: {e}")
            raise

    async def _get_media_metadata(
        self,
        media_id: int,
        include_stats: bool = False,
        context: Any | None = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Get comprehensive media metadata"""
        try:
            # Ownership check
            self._assert_media_access(media_id, context)
            # Get basic metadata
            metadata = self.db.get_media_metadata(media_id)

            if not metadata:
                raise ValueError(f"Media not found: {media_id}")

            # Add statistics if requested
            if include_stats:
                stats = await self._get_media_stats(media_id)
                metadata["statistics"] = stats

            return metadata

        except Exception as e:
            logger.error(f"Failed to get metadata: {e}")
            raise

    async def _ingest_media(
        self,
        url: str,
        title: Optional[str] = None,
        process_type: str = "transcribe",
        tags: Optional[List[str]] = None,
        priority: str = "normal",
        **kwargs
    ) -> Dict[str, Any]:
        """Ingest new media with processing options"""
        try:
            # Validate URL
            if not self._validate_url(url):
                raise ValueError("Invalid or unsupported URL")

            # Create ingestion job
            job_id = await self._create_ingestion_job(
                url=url,
                title=title or url,
                process_type=process_type,
                tags=tags or [],
                priority=priority
            )

            # Start processing based on priority
            if priority == "high":
                # Process immediately
                await self._process_media_job(job_id)
            else:
                # Queue for background processing
                await self._queue_media_job(job_id)

            return {
                "job_id": job_id,
                "status": "processing" if priority == "high" else "queued",
                "url": url,
                "title": title,
                "process_type": process_type
            }

        except Exception as e:
            logger.error(f"Failed to ingest media: {e}")
            raise

    async def _update_media(
        self,
        media_id: int,
        updates: Dict[str, Any],
        context: Any | None = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Update media with validation"""
        try:
            # Ownership check
            self._assert_media_access(media_id, context)
            # Validate media exists
            existing = self.db.get_media_metadata(media_id)
            if not existing:
                raise ValueError(f"Media not found: {media_id}")

            # Apply updates
            updated_fields = []

            if "title" in updates:
                self.db.update_media_title(media_id, updates["title"])
                updated_fields.append("title")

            if "description" in updates:
                self.db.update_media_description(media_id, updates["description"])
                updated_fields.append("description")

            if "tags" in updates:
                self.db.update_media_tags(media_id, updates["tags"])
                updated_fields.append("tags")

            # Clear cache for this media
            self._clear_media_cache(media_id)

            return {
                "media_id": media_id,
                "updated_fields": updated_fields,
                "success": True
            }

        except Exception as e:
            logger.error(f"Failed to update media: {e}")
            raise

    async def _delete_media(
        self,
        media_id: int,
        permanent: bool = False,
        context: Any | None = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Delete media with soft/hard delete options"""
        try:
            # Ownership check
            self._assert_media_access(media_id, context)
            # Validate media exists
            existing = self.db.get_media_metadata(media_id)
            if not existing:
                raise ValueError(f"Media not found: {media_id}")

            if permanent:
                # Hard delete (requires admin)
                # Check would be done at protocol level
                self.db.delete_media_permanent(media_id)
                action = "permanently_deleted"
            else:
                # Soft delete
                self.db.delete_media_soft(media_id)
                action = "soft_deleted"

            # Clear cache
            self._clear_media_cache(media_id)

            return {
                "media_id": media_id,
                "action": action,
                "success": True
            }

        except Exception as e:
            logger.error(f"Failed to delete media: {e}")
            raise

    async def get_resources(self) -> List[Dict[str, Any]]:
        """Get available media resources"""
        return [
            create_resource_definition(
                uri="media://recent",
                name="Recent Media",
                description="Recently added media items",
                mime_type="application/json"
            ),
            create_resource_definition(
                uri="media://popular",
                name="Popular Media",
                description="Most accessed media items",
                mime_type="application/json"
            ),
            create_resource_definition(
                uri="media://types",
                name="Media Types",
                description="Distinct media types present in the database",
                mime_type="application/json"
            ),
        ]

    async def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read media resource"""
        def _rows_to_items(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            items = []
            for row in rows:
                items.append({
                    "id": row.get("id"),
                    "title": row.get("title"),
                    "type": row.get("type"),
                    "media_type": row.get("type"),
                    "ingestion_date": row.get("ingestion_date"),
                    "last_modified": row.get("last_modified"),
                    "url": row.get("url"),
                })
            return items

        if uri == "media://recent":
            rows, _ = self.db.search_media_db(
                search_query=None,
                search_fields=None,
                media_types=None,
                date_range=None,
                must_have_keywords=None,
                must_not_have_keywords=None,
                sort_by="last_modified_desc",
                media_ids_filter=None,
                page=1,
                results_per_page=20,
                include_trash=False,
                include_deleted=False,
            )
            return {
                "uri": uri,
                "type": "media_list",
                "items": _rows_to_items(rows),
            }

        elif uri == "media://popular":
            rows, _ = self.db.search_media_db(
                search_query=None,
                search_fields=None,
                media_types=None,
                date_range=None,
                must_have_keywords=None,
                must_not_have_keywords=None,
                sort_by="date_desc",
                media_ids_filter=None,
                page=1,
                results_per_page=20,
                include_trash=False,
                include_deleted=False,
            )
            return {
                "uri": uri,
                "type": "media_list",
                "items": _rows_to_items(rows),
            }
        elif uri == "media://types":
            types = self.db.get_distinct_media_types()
            return {"uri": uri, "type": "media_types", "items": types}

        else:
            raise ValueError(f"Unknown resource URI: {uri}")

    # Helper methods

    async def _clean_cache(self):
        """Clean expired cache entries"""
        current_time = datetime.utcnow()
        expired_keys = []

        for key, value in self._media_cache.items():
            if (current_time - value["time"]).seconds > self._cache_ttl:
                expired_keys.append(key)

        for key in expired_keys:
            del self._media_cache[key]

    def _clear_media_cache(self, media_id: int):
        """Clear cached search results (all entries)."""
        self._media_cache.clear()

    def _validate_url(self, url: str) -> bool:
        """Validate URL for ingestion with SSRF safeguards.

        Rules:
        - Only http/https schemes
        - Optional allowed_domains allowlist
        - Enforce port allowlist (default 80/443)
        - Reject hosts resolving to private/loopback/link-local/reserved/multicast
        - Reject .local TLDs and empty hosts
        """
        try:
            parts = urlsplit(url)
            if parts.scheme not in {"http", "https"}:
                return False
            host = parts.hostname or ""
            if not host:
                return False
            # Disallow .local
            if host.endswith(".local"):
                return False

            # Allowlist check if configured
            allowed_domains = self.config.settings.get("allowed_domains", []) or []
            if allowed_domains:
                host_l = host.lower()
                ok = False
                for d in allowed_domains:
                    d = str(d).lower().lstrip(".")
                    if host_l == d or host_l.endswith("." + d):
                        ok = True
                        break
                if not ok:
                    return False

            # Blocklist check (substring match)
            blocked_domains = self.config.settings.get("blocked_domains", []) or []
            for d in blocked_domains:
                try:
                    if d and d.lower() in host.lower():
                        return False
                except Exception:
                    pass

            # Port allowlist (default http/https)
            port = parts.port
            allowed_ports = set(self.config.settings.get("allowed_ports", [80, 443]))
            if port is not None and port not in allowed_ports:
                return False

            # Resolve and reject private/bad ranges
            try:
                addrinfos = socket.getaddrinfo(host, port or (80 if parts.scheme == "http" else 443))
            except Exception:
                return False
            if not addrinfos:
                return False
            for ai in addrinfos:
                try:
                    ip_str = ai[4][0]
                    ip = ipaddress.ip_address(ip_str)
                    if (
                        ip.is_private
                        or ip.is_loopback
                        or ip.is_link_local
                        or ip.is_reserved
                        or ip.is_multicast
                    ):
                        return False
                except Exception:
                    return False
            return True
        except Exception:
            return False

    def _is_admin(self, context: Any | None) -> bool:
        try:
            roles = (getattr(context, "metadata", {}) or {}).get("roles")
            return isinstance(roles, list) and any(str(r).lower() == "admin" for r in roles)
        except Exception:
            return False

    def _assert_media_access(self, media_id: int, context: Any | None) -> None:
        """Enforce that non-admin users can only access their own media when ownership is present."""
        try:
            if context is None or getattr(context, "user_id", None) is None:
                return
            if self._is_admin(context):
                return
            row = self.db.get_media_by_id(media_id, include_deleted=False, include_trash=False)
            if not row:
                return
            owner = row.get("user_id")
            if owner is not None and str(owner) != str(context.user_id):
                raise PermissionError("Access denied for this media item")
        except PermissionError:
            raise
        except Exception:
            # Fail-open if ownership field not present or any non-critical error occurs
            return

    def validate_tool_arguments(self, tool_name: str, arguments: Dict[str, Any]):
        """Stricter validation for high-risk tools."""
        if tool_name == "ingest_media":
            url = arguments.get("url")
            if not isinstance(url, str) or not self._validate_url(url) or len(url) > 2048:
                raise ValueError("url must be a valid http(s) URL <= 2048 chars")
            title = arguments.get("title")
            if title is not None and (not isinstance(title, str) or len(title) > 512):
                raise ValueError("title must be a string <= 512 chars")
            tags = arguments.get("tags")
            if tags is not None:
                if not isinstance(tags, list) or any(not isinstance(t, str) or len(t) > 64 for t in tags):
                    raise ValueError("tags must be list[str] with each tag <= 64 chars")
            process_type = arguments.get("process_type", "transcribe")
            if process_type not in {"transcribe", "summarize", "both", "none"}:
                raise ValueError("process_type invalid")
            priority = arguments.get("priority", "normal")
            if priority not in {"low", "normal", "high"}:
                raise ValueError("priority invalid")

        elif tool_name == "update_media":
            mid = arguments.get("media_id")
            if not isinstance(mid, int) or mid <= 0:
                raise ValueError("media_id must be a positive integer")
            updates = arguments.get("updates")
            if not isinstance(updates, dict) or not updates:
                raise ValueError("updates must be a non-empty object")
            for k, v in updates.items():
                if k == "title":
                    if not isinstance(v, str) or len(v) > 512:
                        raise ValueError("title must be a string <= 512 chars")
                elif k == "description":
                    if not isinstance(v, str) or len(v) > 4096:
                        raise ValueError("description must be a string <= 4096 chars")
                elif k == "tags":
                    if not isinstance(v, list) or any(not isinstance(t, str) or len(t) > 64 for t in v):
                        raise ValueError("tags must be list[str] with each tag <= 64 chars")
                else:
                    raise ValueError(f"unsupported update field: {k}")

        elif tool_name == "delete_media":
            mid = arguments.get("media_id")
            if not isinstance(mid, int) or mid <= 0:
                raise ValueError("media_id must be a positive integer")
            if "permanent" in arguments and not isinstance(arguments.get("permanent"), bool):
                raise ValueError("permanent must be a boolean")

    async def _create_ingestion_job(self, **kwargs) -> str:
        """Create media ingestion job"""
        # Generate job ID
        job_id = str(uuid.uuid4())

        # Store job details (in production, use job queue)
        # For now, return job ID
        return job_id

    async def _process_media_job(self, job_id: str):
        """Process media ingestion job"""
        # Placeholder for actual processing
        await asyncio.sleep(0.1)

    async def _queue_media_job(self, job_id: str):
        """Queue media job for background processing"""
        # Placeholder for job queue integration
        pass

    async def _get_media_stats(self, media_id: int) -> Dict[str, Any]:
        """Get media statistics"""
        return {
            "views": 0,
            "likes": 0,
            "transcriptions": 0,
            "last_accessed": None
        }

    def _format_transcript_with_timestamps(self, transcript_data: Dict) -> str:
        """Format transcript with timestamps"""
        # Placeholder implementation
        return transcript_data.get("text", "")

    def _convert_to_srt(self, transcript_data: Dict) -> str:
        """Convert transcript to SRT format"""
        # Placeholder implementation
        return ""

    def _convert_to_vtt(self, transcript_data: Dict) -> str:
        """Convert transcript to WebVTT format"""
        # Placeholder implementation
        return "WEBVTT\n\n"
