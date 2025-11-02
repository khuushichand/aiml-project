"""
Notes Module for Unified MCP

FTS-only search and retrieval for user Notes stored in ChaChaNotes DB.
Returns normalized result schema with 0-1 scores and 300-char snippets by default.
"""

import asyncio
from typing import Dict, Any, List, Optional
from loguru import logger

from ..base import BaseModule, ModuleConfig, create_tool_definition
from ....DB_Management.ChaChaNotes_DB import CharactersRAGDB


def _normalize_scores(results: List[Dict[str, Any]], score_key: Optional[str] = None) -> List[float]:
    if not results:
        return []
    # Prefer a numeric score if present (e.g., bm25 or ts_rank), otherwise use position-based decay
    if score_key and all(isinstance(r.get(score_key), (int, float)) for r in results):
        vals = [float(r.get(score_key)) for r in results]
        mn, mx = min(vals), max(vals)
        if mx - mn < 1e-9:
            return [1.0 for _ in vals]
        # If this looks like bm25 (lower is better), invert scale
        # Heuristic: if the average is > 1.0, treat as bm25-like
        avg = sum(vals) / len(vals)
        if avg > 1.0:
            return [(mx - v) / (mx - mn + 1e-9) for v in vals]
        # Otherwise assume higher is better
        return [(v - mn) / (mx - mn + 1e-9) for v in vals]
    # Positional fallback
    n = len(results)
    if n == 1:
        return [1.0]
    # simple linear decay from 1.0 → ~0.0
    return [1.0 - (i / max(1, n - 1)) for i in range(n)]


def _make_snippet(text: Optional[str], query: Optional[str], length: int = 300) -> str:
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


class NotesModule(BaseModule):
    """FTS search/get over user notes"""

    async def on_initialize(self) -> None:
        logger.info(f"Initializing Notes module: {self.name}")

    async def on_shutdown(self) -> None:
        logger.info(f"Shutting down Notes module: {self.name}")

    async def check_health(self) -> Dict[str, bool]:
        checks = {"initialized": True, "driver_available": False, "disk_space": False}
        try:
            # Verify DB driver class is importable
            _ = CharactersRAGDB  # noqa: F401
            checks["driver_available"] = True
        except Exception:
            checks["driver_available"] = False
        # Check Databases directory has free space
        try:
            import os
            from pathlib import Path
            try:
                from tldw_Server_API.app.core.Utils.Utils import get_project_root
                base = Path(get_project_root())
            except Exception:
                # Anchor to package root if project root resolution fails
                base = Path(__file__).resolve().parents[5]
            stat = os.statvfs(str(base))
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
            checks["disk_space"] = free_gb > 1
        except Exception:
            checks["disk_space"] = False
        # Optional ephemeral DB write test (heavy) for deeper validation
        try:
            import os
            if str(os.getenv("MCP_HEALTHCHECK_DB_WRITE_TEST", "")).lower() in {"1", "true", "yes"}:
                from tempfile import NamedTemporaryFile
                with NamedTemporaryFile(prefix="mcp_notes_health_", suffix=".db", delete=True) as tf:
                    db = CharactersRAGDB(db_path=tf.name, client_id=f"mcp_notes_{self.config.name}")
                    # A trivial read to confirm
                    _ = db.get_note_by_id("nonexistent")
                checks["ephemeral_db_ok"] = True
        except Exception:
            checks["ephemeral_db_ok"] = False

        return checks

    async def get_tools(self) -> List[Dict[str, Any]]:
        return [
            create_tool_definition(
                name="notes.search",
                description="Search notes by title/content (FTS-only).",
                parameters={
                    "properties": {
                        "query": {"type": "string", "minLength": 1, "maxLength": 1000},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
                        "offset": {"type": "integer", "minimum": 0, "default": 0},
                        "snippet_length": {"type": "integer", "minimum": 50, "maximum": 2000, "default": 300},
                    },
                    "required": ["query"],
                },
                metadata={"category": "search", "readOnlyHint": True},
            ),
            create_tool_definition(
                name="notes.get",
                description="Retrieve a note by id (snippet or full).",
                parameters={
                    "properties": {
                        "note_id": {"type": "string"},
                        "retrieval": {
                            "type": "object",
                            "properties": {
                                "mode": {"type": "string", "enum": ["snippet", "full"], "default": "snippet"},
                                "snippet_length": {"type": "integer", "minimum": 50, "maximum": 2000, "default": 300},
                            }
                        }
                    },
                    "required": ["note_id"],
                },
                metadata={"category": "retrieval", "readOnlyHint": True},
            ),
        ]

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], context: Any | None = None) -> Any:
        args = self.sanitize_input(arguments)
        try:
            self.validate_tool_arguments(tool_name, args)
        except Exception as ve:
            raise ValueError(f"Invalid arguments for {tool_name}: {ve}")
        if tool_name == "notes.search":
            return await self._search_notes(args, context)
        if tool_name == "notes.get":
            return await self._get_note(args, context)
        raise ValueError(f"Unknown tool: {tool_name}")

    def _open_db(self, context: Any) -> CharactersRAGDB:
        if context is None or not getattr(context, "db_paths", None):
            raise ValueError("Missing user context for Notes access")
        chacha_path = context.db_paths.get("chacha")
        if not chacha_path:
            raise ValueError("ChaChaNotes DB path not available in context")
        return CharactersRAGDB(db_path=chacha_path, client_id=f"mcp_notes_{self.config.name}")

    async def _search_notes(self, args: Dict[str, Any], context: Any | None) -> Dict[str, Any]:
        query: str = args.get("query")
        limit: int = int(args.get("limit", 10))
        offset: int = int(args.get("offset", 0))
        snippet_len: int = int(args.get("snippet_length", 300))
        # Apply session defaults if present
        try:
            if context and isinstance(getattr(context, "metadata", {}), dict):
                sc = context.metadata.get("safe_config") or {}
                if isinstance(sc, dict):
                    snippet_len = int(sc.get("snippet_length", snippet_len))
        except Exception:
            pass
        snippet_len = max(50, min(2000, snippet_len))

        return await asyncio.to_thread(
            self._search_notes_sync,
            context,
            query,
            limit,
            offset,
            snippet_len,
        )

    def validate_tool_arguments(self, tool_name: str, arguments: Dict[str, Any]):
        if tool_name == "notes.search":
            q = arguments.get("query")
            if not isinstance(q, str) or not (1 <= len(q) <= 1000):
                raise ValueError("query must be 1..1000 chars")
            limit = int(arguments.get("limit", 10))
            offset = int(arguments.get("offset", 0))
            snip = int(arguments.get("snippet_length", 300))
            if limit < 1 or limit > 100:
                raise ValueError("limit must be 1..100")
            if offset < 0:
                raise ValueError("offset must be >= 0")
            if snip < 50 or snip > 2000:
                raise ValueError("snippet_length must be 50..2000")
        elif tool_name == "notes.get":
            note_id = arguments.get("note_id")
            if not isinstance(note_id, str) or not note_id:
                raise ValueError("note_id must be a non-empty string")
            retrieval = arguments.get("retrieval") or {}
            if not isinstance(retrieval, dict):
                raise ValueError("retrieval must be an object")
            mode = retrieval.get("mode", "snippet")
            if mode not in {"snippet", "full"}:
                raise ValueError("retrieval.mode must be 'snippet' or 'full'")
            snip = int(retrieval.get("snippet_length", 300))
            if snip < 50 or snip > 2000:
                raise ValueError("retrieval.snippet_length must be 50..2000")

    async def _get_note(self, args: Dict[str, Any], context: Any | None) -> Dict[str, Any]:
        note_id: str = args.get("note_id")
        retrieval = args.get("retrieval") or {}
        mode = (retrieval or {}).get("mode", "snippet")
        snippet_len = int((retrieval or {}).get("snippet_length", 300))
        # Apply session defaults if present
        try:
            if context and isinstance(getattr(context, "metadata", {}), dict):
                sc = context.metadata.get("safe_config") or {}
                if isinstance(sc, dict):
                    snippet_len = int(sc.get("snippet_length", snippet_len))
        except Exception:
            pass
        snippet_len = max(50, min(2000, snippet_len))

        return await asyncio.to_thread(
            self._get_note_sync,
            context,
            note_id,
            mode,
            snippet_len,
        )

    def _search_notes_sync(
        self,
        context: Any | None,
        query: str,
        limit: int,
        offset: int,
        snippet_len: int,
    ) -> Dict[str, Any]:
        db = self._open_db(context)
        try:
            fetch_limit = limit + 1  # fetch one extra row to detect additional pages
            raw = db.search_notes(query, limit=fetch_limit, offset=offset)
            rows = raw[:limit]
            # Detect score key if backend provided it
            score_key = None
            if rows:
                first = rows[0]
                if isinstance(first.get("rank"), (int, float)):
                    score_key = "rank"
                elif isinstance(first.get("bm25_score"), (int, float)):
                    score_key = "bm25_score"
            scores = _normalize_scores(rows, score_key=score_key)

            has_more = len(raw) > limit
            next_offset = (offset + len(rows)) if has_more else None

            results = []
            for i, r in enumerate(rows):
                note_id = r.get("id")
                title = r.get("title")
                content = r.get("content") or ""
                created_at = r.get("created_at")
                last_modified = r.get("last_modified") or r.get("updated_at")
                # Approximate offset of query within content
                approx_offset = None
                try:
                    idx = content.lower().find(query.lower()) if query else -1
                    if idx >= 0:
                        approx_offset = idx
                except Exception:
                    approx_offset = None
                results.append({
                    "id": note_id,
                    "source": "notes",
                    "title": title,
                    "snippet": _make_snippet(content, query, snippet_len),
                    "uri": f"notes://{note_id}",
                    "score": float(scores[i] if i < len(scores) else 0.0),
                    "score_type": "fts",
                    "created_at": created_at,
                    "last_modified": last_modified,
                    "version": r.get("version"),
                    "tags": None,
                    "loc": ({"approx_offset": approx_offset} if approx_offset is not None else None),
                })

            try:
                total_estimated = db.count_notes_matching(query)
            except Exception:
                total_estimated = offset + len(rows) + (1 if has_more else 0)

            return {
                "results": results,
                "has_more": has_more,
                "next_offset": next_offset,
                "total_estimated": total_estimated,
            }
        finally:
            try:
                db.close_all_connections()
            except Exception as exc:
                logger.debug("Failed to close ChaChaNotes DB connections after search: {}", exc)

    def _get_note_sync(
        self,
        context: Any | None,
        note_id: str,
        mode: str,
        snippet_len: int,
    ) -> Dict[str, Any]:
        db = self._open_db(context)
        try:
            row = db.get_note_by_id(note_id)
            if not row:
                raise ValueError(f"Note not found: {note_id}")
            content = row.get("content") or ""
            meta = {
                "id": row.get("id"),
                "source": "notes",
                "title": row.get("title"),
                "snippet": _make_snippet(content, None, snippet_len),
                "uri": f"notes://{row.get('id')}",
                "score": 1.0,
                "score_type": "fts",
                "created_at": row.get("created_at"),
                "last_modified": row.get("last_modified") or row.get("updated_at"),
                "version": row.get("version"),
                "tags": None,
                "loc": None,
            }

            if mode == "full":
                body = content
            else:
                body = _make_snippet(content, None, snippet_len)

            return {
                "meta": meta,
                "content": body,
                "attachments": None,
            }
        finally:
            try:
                db.close_all_connections()
            except Exception as exc:
                logger.debug("Failed to close ChaChaNotes DB connections after note fetch: {}", exc)
