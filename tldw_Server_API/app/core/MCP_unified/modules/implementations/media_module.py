"""
Media Module for Unified MCP

Production-ready media management module with full MCP compliance.
"""

import os
import asyncio
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
from loguru import logger

from ..base import BaseModule, ModuleConfig, create_tool_definition, create_resource_definition
from ....DB_Management.Media_DB_v2 import MediaDatabase


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
            db_path = self.config.settings.get(
                "db_path",
                "./Databases/Media_DB_v2.db"
            )
            
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
            
            logger.info(f"Media module initialized with database: {db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize media module: {e}")
            raise
    
    async def on_shutdown(self) -> None:
        """Graceful shutdown with connection cleanup"""
        try:
            # Clear cache
            self._media_cache.clear()
            
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
            db_path = self.config.settings.get("db_path", "./Databases/Media_DB_v2.db")
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
                return await self._search_media(**arguments)
            
            elif tool_name == "get_transcript":
                return await self._get_transcript(**arguments)
            
            elif tool_name == "get_media_metadata":
                return await self._get_media_metadata(**arguments)
            
            elif tool_name == "ingest_media":
                return await self._ingest_media(**arguments)
            
            elif tool_name == "update_media":
                return await self._update_media(**arguments)
            
            elif tool_name == "delete_media":
                return await self._delete_media(**arguments)
            
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
        **kwargs
    ) -> Dict[str, Any]:
        """Search media with caching"""
        # Validate inputs
        if not query or len(query) > 1000:
            raise ValueError("Invalid search query")
        
        if limit > 100:
            limit = 100
        
        # Check cache
        cache_key = f"search:{query}:{search_type}:{limit}:{offset}"
        if cache_key in self._media_cache:
            cached = self._media_cache[cache_key]
            if (datetime.utcnow() - cached["time"]).seconds < self._cache_ttl:
                logger.debug(f"Cache hit for search: {cache_key}")
                return cached["data"]
        
        # Perform search
        try:
            if search_type == "keyword":
                results = self.db.search_media_db(query, limit=limit)
            elif search_type == "semantic":
                # Implement semantic search
                results = []  # Placeholder
            else:  # hybrid
                # Combine keyword and semantic
                results = self.db.search_media_db(query, limit=limit)
            
            # Format results
            formatted_results = {
                "query": query,
                "type": search_type,
                "count": len(results),
                "results": results,
                "offset": offset,
                "limit": limit
            }
            
            # Cache results
            self._media_cache[cache_key] = {
                "time": datetime.utcnow(),
                "data": formatted_results
            }
            
            # Clean old cache entries
            await self._clean_cache()
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise
    
    async def _get_transcript(
        self,
        media_id: int,
        include_timestamps: bool = False,
        format: str = "text",
        **kwargs
    ) -> Dict[str, Any]:
        """Get media transcript with formatting options"""
        try:
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
        **kwargs
    ) -> Dict[str, Any]:
        """Get comprehensive media metadata"""
        try:
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
        **kwargs
    ) -> Dict[str, Any]:
        """Update media with validation"""
        try:
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
        **kwargs
    ) -> Dict[str, Any]:
        """Delete media with soft/hard delete options"""
        try:
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
        if uri == "media://recent":
            # Get recent media
            recent = self.db.get_recent_media(limit=20)
            return {
                "uri": uri,
                "type": "media_list",
                "items": recent
            }
        
        elif uri == "media://popular":
            # Get popular media
            popular = self.db.get_popular_media(limit=20)
            return {
                "uri": uri,
                "type": "media_list",
                "items": popular
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
        """Clear cache entries for specific media"""
        keys_to_clear = [k for k in self._media_cache.keys() if str(media_id) in k]
        for key in keys_to_clear:
            del self._media_cache[key]
    
    def _validate_url(self, url: str) -> bool:
        """Validate URL for ingestion"""
        # Basic URL validation
        if not url.startswith(("http://", "https://")):
            return False
        
        # Check against blocklist
        blocked_domains = self.config.settings.get("blocked_domains", [])
        for domain in blocked_domains:
            if domain in url:
                return False
        
        return True

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
