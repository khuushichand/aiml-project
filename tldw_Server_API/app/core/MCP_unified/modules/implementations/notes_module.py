"""
Notes Module for Unified MCP

FTS-only search and retrieval for user Notes stored in ChaChaNotes DB.
Returns normalized result schema with 0–1 scores and 300-char snippets by default.
"""

from typing import Dict, Any, List, Optional, Tuple
from loguru import logger
from datetime import datetime

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
            base = os.path.dirname("./Databases/test.db") or "."
            stat = os.statvfs(base)
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
            checks["disk_space"] = free_gb > 1
        except Exception:
            checks["disk_space"] = False
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

        db = self._open_db(context)
        # CharactersRAGDB.search_notes only supports limit; emulate offset by over-fetching then slicing
        raw = db.search_notes(query, limit=limit + offset)
        rows = raw[offset: offset + limit]
        # Normalize scores (no explicit rank available → positional fallback)
        scores = _normalize_scores(rows, score_key=None)

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

        return {
            "results": results,
            "has_more": len(raw) > (offset + len(rows)),
            "next_offset": (offset + len(rows)) if len(raw) > (offset + len(rows)) else None,
            "total_estimated": len(raw),
        }

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

        db = self._open_db(context)
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
