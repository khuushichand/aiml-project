"""
Chats Module for Unified MCP

Search conversations (titles) and messages (content) and retrieve conversation content.
FTS-only search backed by ChaChaNotes DB.
"""

from typing import Dict, Any, List, Optional
from loguru import logger

from ..base import BaseModule, ModuleConfig, create_tool_definition
from ....DB_Management.ChaChaNotes_DB import CharactersRAGDB


class ChatsModule(BaseModule):
    async def on_initialize(self) -> None:
        logger.info(f"Initializing Chats module: {self.name}")

    async def on_shutdown(self) -> None:
        logger.info(f"Shutting down Chats module: {self.name}")

    async def check_health(self) -> Dict[str, bool]:
        checks = {"initialized": True, "driver_available": False, "disk_space": False}
        try:
            _ = CharactersRAGDB  # noqa: F401
            checks["driver_available"] = True
        except Exception:
            checks["driver_available"] = False
        try:
            import os
            from pathlib import Path
            try:
                from tldw_Server_API.app.core.Utils.Utils import get_project_root
                base = Path(get_project_root())
            except Exception:
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
                with NamedTemporaryFile(prefix="mcp_chats_health_", suffix=".db", delete=True) as tf:
                    db = CharactersRAGDB(db_path=tf.name, client_id=f"mcp_chats_{self.config.name}")
                    # Trivial call to ensure DB usable
                    _ = db.search_messages_by_content("ping", conversation_id=None, limit=1)
                checks["ephemeral_db_ok"] = True
        except Exception:
            checks["ephemeral_db_ok"] = False

        return checks

    async def get_tools(self) -> List[Dict[str, Any]]:
        return [
            create_tool_definition(
                name="chats.search",
                description="Search conversations (titles) and messages (content).",
                parameters={
                    "properties": {
                        "query": {"type": "string", "minLength": 1, "maxLength": 1000},
                        "by": {"type": "string", "enum": ["both", "title", "message"], "default": "both"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
                        "offset": {"type": "integer", "minimum": 0, "default": 0},
                        "snippet_length": {"type": "integer", "minimum": 50, "maximum": 2000, "default": 300},
                        "character_id": {"type": "integer"},
                        "sender": {"type": "string"},
                    },
                    "required": ["query"],
                },
                metadata={"category": "search", "readOnlyHint": True},
            ),
            create_tool_definition(
                name="chats.get",
                description="Retrieve conversation messages; supports snippet/full or window around a message.",
                parameters={
                    "properties": {
                        "conversation_id": {"type": "string"},
                        "retrieval": {
                            "type": "object",
                            "properties": {
                                "mode": {"type": "string", "enum": ["snippet", "full", "chunk_with_siblings"], "default": "snippet"},
                                "snippet_length": {"type": "integer", "minimum": 50, "maximum": 2000, "default": 300},
                                "max_tokens": {"type": "integer"},
                                "chars_per_token": {"type": "integer"},
                                "loc": {"type": "object", "properties": {"message_id": {"type": "string"}}},
                            }
                        }
                    },
                    "required": ["conversation_id"],
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
        if tool_name == "chats.search":
            return await self._search(args, context)
        if tool_name == "chats.get":
            return await self._get(args, context)
        raise ValueError(f"Unknown tool: {tool_name}")

    def _open_db(self, context: Any) -> CharactersRAGDB:
        if context is None or not getattr(context, "db_paths", None):
            raise ValueError("Missing user context for Chats access")
        chacha_path = context.db_paths.get("chacha")
        if not chacha_path:
            raise ValueError("ChaChaNotes DB path not available in context")
        return CharactersRAGDB(db_path=chacha_path, client_id=f"mcp_chats_{self.config.name}")

    async def _search(self, args: Dict[str, Any], context: Any | None) -> Dict[str, Any]:
        query: str = args.get("query")
        by: str = args.get("by", "both")
        limit: int = int(args.get("limit", 10))
        offset: int = int(args.get("offset", 0))
        snippet_len: int = int(args.get("snippet_length", 300))
        character_id = args.get("character_id")
        sender = args.get("sender")

        db = self._open_db(context)
        results: List[Dict[str, Any]] = []
        # Conversations by title
        if by in {"both", "title"}:
            convs = db.search_conversations_by_title(
                query,
                character_id=character_id,
                limit=limit + offset,
                client_id=None,  # MCP operates with a synthetic client_id; fetch full tenant scope explicitly.
            )
            for r in convs[offset: offset + limit]:
                results.append({
                    "id": r.get("id"),
                    "source": "chats",
                    "title": r.get("title"),
                    "snippet": r.get("title"),
                    "uri": f"chats://{r.get('id')}",
                    "score": 1.0,
                    "score_type": "fts",
                    "created_at": r.get("created_at"),
                    "last_modified": r.get("last_modified"),
                    "version": r.get("version"),
                    "tags": None,
                    "conversation_id": r.get("id"),
                    "loc": {"conversation_id": r.get("id")},
                })

        # Messages by content
        if by in {"both", "message"}:
            msgs = db.search_messages_by_content(query, conversation_id=None, limit=limit + offset)
            idx = 0
            for r in msgs:
                if sender and (str(r.get("sender") or "").lower() != str(sender).lower()):
                    continue
                if idx < offset:
                    idx += 1
                    continue
                if len(results) >= limit + offset:
                    break
                content = r.get("content") or ""
                results.append({
                    "id": r.get("id"),
                    "source": "chats",
                    "title": None,
                    "snippet": " ".join(content.split())[:snippet_len],
                    "uri": f"chats://{r.get('conversation_id')}#{r.get('id')}",
                    "score": 1.0,
                    "score_type": "fts",
                    "created_at": r.get("timestamp"),
                    "last_modified": r.get("last_modified"),
                    "version": r.get("version"),
                    "tags": None,
                    "conversation_id": r.get("conversation_id"),
                    "message_id": r.get("id"),
                    "sender": r.get("sender"),
                    "loc": {"conversation_id": r.get("conversation_id"), "message_id": r.get("id")},
                })
                idx += 1

        # Normalize length, compute has_more/next_offset best-effort
        results = results[:limit]
        return {
            "results": results,
            "has_more": False,
            "next_offset": None,
            "total_estimated": len(results) + offset,
        }

    def validate_tool_arguments(self, tool_name: str, arguments: Dict[str, Any]):
        if tool_name == "chats.search":
            q = arguments.get("query")
            if not isinstance(q, str) or not (1 <= len(q) <= 1000):
                raise ValueError("query must be 1..1000 chars")
            by = arguments.get("by", "both")
            if by not in {"both", "title", "message"}:
                raise ValueError("by must be both|title|message")
            limit = int(arguments.get("limit", 10))
            offset = int(arguments.get("offset", 0))
            snip = int(arguments.get("snippet_length", 300))
            if limit < 1 or limit > 100:
                raise ValueError("limit must be 1..100")
            if offset < 0:
                raise ValueError("offset must be >= 0")
            if snip < 50 or snip > 2000:
                raise ValueError("snippet_length must be 50..2000")
            if arguments.get("character_id") is not None and not isinstance(arguments.get("character_id"), int):
                raise ValueError("character_id must be int when provided")
            if arguments.get("sender") is not None and not isinstance(arguments.get("sender"), str):
                raise ValueError("sender must be string when provided")
        elif tool_name == "chats.get":
            cid = arguments.get("conversation_id")
            if not isinstance(cid, str) or not cid:
                raise ValueError("conversation_id must be a non-empty string")
            retrieval = arguments.get("retrieval") or {}
            if not isinstance(retrieval, dict):
                raise ValueError("retrieval must be an object")
            snip = int(retrieval.get("snippet_length", 300))
            if snip < 50 or snip > 2000:
                raise ValueError("retrieval.snippet_length must be 50..2000")
            loc = retrieval.get("loc")
            if loc is not None:
                if not isinstance(loc, dict):
                    raise ValueError("retrieval.loc must be an object")
                if loc.get("message_id") is not None and not isinstance(loc.get("message_id"), str):
                    raise ValueError("retrieval.loc.message_id must be a string if provided")

    async def _get(self, args: Dict[str, Any], context: Any | None) -> Dict[str, Any]:
        conversation_id: str = args.get("conversation_id")
        retrieval = args.get("retrieval") or {}
        mode = retrieval.get("mode", "snippet")
        snippet_len = int(retrieval.get("snippet_length", 300))
        max_tokens = retrieval.get("max_tokens")
        cpt = int(retrieval.get("chars_per_token", 4))
        loc = retrieval.get("loc") or {}

        db = self._open_db(context)
        conv = db.get_conversation_by_id(conversation_id)
        if not conv:
            raise ValueError(f"Conversation not found: {conversation_id}")
        messages = db.get_messages_for_conversation(conversation_id, limit=1000, offset=0, order_by_timestamp="ASC")

        meta = {
            "id": conversation_id,
            "source": "chats",
            "title": conv.get("title"),
            "snippet": conv.get("title") or "",
            "uri": f"chats://{conversation_id}",
            "score": 1.0,
            "score_type": "fts",
            "created_at": conv.get("created_at"),
            "last_modified": conv.get("last_modified"),
            "version": conv.get("version"),
            "tags": None,
            "conversation_id": conversation_id,
            "loc": None,
        }

        def _estimate_tokens(s: str) -> int:
            return max(1, (len(s) + cpt - 1) // cpt)

        if mode == "full":
            body = "\n".join([f"{m.get('sender')}: {m.get('content','')}" for m in messages])
            return {"meta": meta, "content": body, "attachments": messages}

        if mode == "chunk_with_siblings" and messages:
            anchor_id = None
            try:
                if isinstance(loc, dict) and loc.get("message_id"):
                    anchor_id = str(loc.get("message_id"))
            except Exception:
                anchor_id = None
            anchor_index = 0
            if anchor_id:
                for i, m in enumerate(messages):
                    if str(m.get("id")) == anchor_id:
                        anchor_index = i
                        break
            # Greedy expand around anchor under token budget
            selected = [anchor_index]
            budget = int(max_tokens) if isinstance(max_tokens, (int, float)) else None
            if budget is None:
                # default window of 5 messages each side
                w = 5
                left = max(0, anchor_index - w)
                right = min(len(messages), anchor_index + w + 1)
                span = messages[left:right]
            else:
                current = _estimate_tokens(messages[anchor_index].get("content") or "")
                left = anchor_index - 1
                right = anchor_index + 1
                while True:
                    progressed = False
                    if left >= 0:
                        t_add = _estimate_tokens(messages[left].get("content") or "")
                        if current + t_add <= budget:
                            selected.insert(0, left)
                            current += t_add
                            left -= 1
                            progressed = True
                    if right < len(messages):
                        t_add = _estimate_tokens(messages[right].get("content") or "")
                        if current + t_add <= budget:
                            selected.append(right)
                            current += t_add
                            right += 1
                            progressed = True
                    if not progressed:
                        break
                span = [messages[i] for i in selected]
            body = "\n".join([f"{m.get('sender')}: {m.get('content','')}" for m in span])
            meta["loc"] = {"conversation_id": conversation_id, "message_index": anchor_index, "message_id": messages[anchor_index].get("id")}
            return {"meta": meta, "content": body, "attachments": span}

        # snippet default: title or first message excerpt
        if messages:
            first = messages[0]
            meta["snippet"] = (first.get("content") or "")[:snippet_len]
        return {"meta": meta, "content": meta["snippet"], "attachments": None}
