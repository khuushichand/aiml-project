"""
Prompts Module for Unified MCP

Search/get prompts via PromptsDatabase (per-user prompts DB path).
"""

from typing import Dict, Any, List, Optional
from loguru import logger

from ..base import BaseModule, ModuleConfig, create_tool_definition
from ....DB_Management.Prompts_DB import PromptsDatabase
from ....DB_Management.db_path_utils import DatabasePaths


class PromptsModule(BaseModule):
    async def on_initialize(self) -> None:
        logger.info(f"Initializing Prompts module: {self.name}")

    async def on_shutdown(self) -> None:
        logger.info(f"Shutting down Prompts module: {self.name}")

    async def check_health(self) -> Dict[str, bool]:
        checks = {"initialized": True, "driver_available": False, "disk_space": False}
        try:
            _ = PromptsDatabase  # noqa: F401
            checks["driver_available"] = True
        except Exception:
            checks["driver_available"] = False
        try:
            import os
            base = os.path.dirname("./Databases/test.db") or "."
            stat = os.statvfs(base)
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
            checks["disk_space"] = free_gb > 1
        except Exception:
            checks["disk_space"] = False
        # Optional ephemeral DB write test (heavy) for deeper validation
        try:
            import os
            if str(os.getenv("MCP_HEALTHCHECK_DB_WRITE_TEST", "")).lower() in {"1", "true", "yes"}:
                from tempfile import NamedTemporaryFile
                with NamedTemporaryFile(prefix="mcp_prompts_health_", suffix=".db", delete=True) as tf:
                    db = PromptsDatabase(db_path=tf.name, client_id=f"mcp_prompts_{self.config.name}")
                    # Trivial read to confirm
                    _ = db.get_prompt_by_name("nonexistent")
                checks["ephemeral_db_ok"] = True
        except Exception:
            checks["ephemeral_db_ok"] = False

        return checks

    async def get_tools(self) -> List[Dict[str, Any]]:
        return [
            create_tool_definition(
                name="prompts.search",
                description="Search prompts by name/details/system_prompt/user_prompt/author/keywords.",
                parameters={
                    "properties": {
                        "query": {"type": "string", "minLength": 1, "maxLength": 1000},
                        "fields": {"type": "array", "items": {"type": "string"}},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
                        "offset": {"type": "integer", "minimum": 0, "default": 0},
                        "snippet_length": {"type": "integer", "minimum": 50, "maximum": 2000, "default": 300},
                    },
                    "required": ["query"],
                },
                metadata={"category": "search", "readOnlyHint": True},
            ),
            create_tool_definition(
                name="prompts.get",
                description="Get a prompt by id or name.",
                parameters={
                    "properties": {
                        "prompt_id_or_name": {"type": "string"}
                    },
                    "required": ["prompt_id_or_name"],
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
        if tool_name == "prompts.search":
            return await self._search(args, context)
        if tool_name == "prompts.get":
            return await self._get(args, context)
        raise ValueError(f"Unknown tool: {tool_name}")

    def _open_db(self, context: Any) -> PromptsDatabase:
        if context is None or not getattr(context, "db_paths", None):
            raise ValueError("Missing user context for Prompts access")
        ppath = context.db_paths.get("prompts")
        if not ppath:
            raise ValueError("Prompts DB path not available in context")
        return PromptsDatabase(db_path=ppath, client_id=f"mcp_prompts_{self.config.name}")

    async def _search(self, args: Dict[str, Any], context: Any | None) -> Dict[str, Any]:
        query: str = args.get("query")
        fields: List[str] = args.get("fields") or []
        limit: int = int(args.get("limit", 10))
        offset: int = int(args.get("offset", 0))
        snippet_len: int = int(args.get("snippet_length", 300))
        db = self._open_db(context)
        page = (offset // max(1, limit)) + 1 if limit > 0 else 1
        rows, total = db.search_prompts(search_query=query, search_fields=fields or None, page=page, results_per_page=limit, include_deleted=False)
        out = []
        for r in rows:
            desc = r.get("details") or r.get("system_prompt") or ""
            out.append({
                "id": r.get("id"),
                "source": "prompts",
                "title": r.get("name"),
                "snippet": " ".join(desc.split())[:snippet_len],
                "uri": f"prompts://{r.get('id')}",
                "score": 1.0,
                "score_type": "fts",
                "created_at": r.get("created_at"),
                "last_modified": r.get("last_modified"),
                "version": r.get("version"),
                "tags": r.get("keywords") or None,
                "loc": None,
            })
        return {"results": out, "has_more": (offset + len(rows)) < total, "next_offset": (offset + len(rows)) if (offset + len(rows)) < total else None, "total_estimated": total}

    async def _get(self, args: Dict[str, Any], context: Any | None) -> Dict[str, Any]:
        ident: str = args.get("prompt_id_or_name")
        db = self._open_db(context)
        row = None
        try:
            pid = int(ident)
            row = db.get_prompt_by_id(pid)
        except Exception:
            row = db.get_prompt_by_name(ident)
        if not row:
            raise ValueError(f"Prompt not found: {ident}")
        desc = row.get("details") or ""
        meta = {
            "id": row.get("id"),
            "source": "prompts",
            "title": row.get("name"),
            "snippet": " ".join(desc.split())[:300],
            "uri": f"prompts://{row.get('id')}",
            "score": 1.0,
            "score_type": "fts",
            "created_at": row.get("created_at"),
            "last_modified": row.get("last_modified"),
            "version": row.get("version"),
            "tags": None,
            "loc": None,
        }
        content = {
            k: row.get(k)
            for k in ("name", "author", "details", "system_prompt", "user_prompt")
        }
        return {"meta": meta, "content": content, "attachments": None}

    def validate_tool_arguments(self, tool_name: str, arguments: Dict[str, Any]):
        if tool_name == "prompts.search":
            q = arguments.get("query")
            if not isinstance(q, str) or not (1 <= len(q) <= 1000):
                raise ValueError("query must be 1..1000 chars")
            fields = arguments.get("fields")
            if fields is not None and (not isinstance(fields, list) or any(not isinstance(f, str) for f in fields)):
                raise ValueError("fields must be list[str] if provided")
            limit = int(arguments.get("limit", 10))
            offset = int(arguments.get("offset", 0))
            snip = int(arguments.get("snippet_length", 300))
            if limit < 1 or limit > 100:
                raise ValueError("limit must be 1..100")
            if offset < 0:
                raise ValueError("offset must be >= 0")
            if snip < 50 or snip > 2000:
                raise ValueError("snippet_length must be 50..2000")
        elif tool_name == "prompts.get":
            pid = arguments.get("prompt_id_or_name")
            if not isinstance(pid, str) or not pid:
                raise ValueError("prompt_id_or_name must be a non-empty string")
