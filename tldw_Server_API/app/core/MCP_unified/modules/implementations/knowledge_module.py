"""
Knowledge Aggregator Module for Unified MCP

Provides knowledge.search and knowledge.get by fanning out to source modules
(notes, media, chats, characters, prompts). Stage 4 initial implementation:
- FTS-only sources
- Normalized inputs/outputs using common schema
- Per-request dedupe by URI; persists across WS sessions via context.metadata
- Retrieval modes supported minimally (snippet|full). chunk_with_siblings deferred.
"""

from typing import Dict, Any, List, Optional, Tuple
from loguru import logger
from datetime import datetime
import asyncio

from ..base import BaseModule, ModuleConfig, create_tool_definition
from ..registry import get_module_registry


def _iso_to_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


class KnowledgeModule(BaseModule):
    """Aggregator for knowledge search/get"""

    async def on_initialize(self) -> None:
        logger.info(f"Initializing Knowledge module: {self.name}")

    async def on_shutdown(self) -> None:
        logger.info(f"Shutting down Knowledge module: {self.name}")

    async def check_health(self) -> Dict[str, bool]:
        return {"initialized": True}

    async def get_tools(self) -> List[Dict[str, Any]]:
        return [
            create_tool_definition(
                name="knowledge.search",
                description="Unified search across notes, media, chats, characters, prompts (FTS-only).",
                parameters={
                    "properties": {
                        "query": {"type": "string", "minLength": 1, "maxLength": 1000},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                        "offset": {"type": "integer", "minimum": 0, "default": 0},
                        "snippet_length": {"type": "integer", "minimum": 50, "maximum": 2000, "default": 300},
                        "order_by": {"type": "string", "enum": ["relevance", "recent"], "default": "relevance"},
                        "sources": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["notes", "media", "chats", "characters", "prompts"]},
                        },
                        "filters": {"type": "object"}
                    },
                    "required": ["query"],
                },
                metadata={"category": "search", "readOnlyHint": True},
            ),
            create_tool_definition(
                name="knowledge.get",
                description="Retrieve an item by source + id with basic retrieval modes (snippet/full).",
                parameters={
                    "properties": {
                        "source": {"type": "string", "enum": ["notes", "media", "chats", "characters", "prompts"]},
                        "id": {"type": ["string", "number"]},
                        "retrieval": {
                            "type": "object",
                            "properties": {
                                "mode": {"type": "string", "enum": ["snippet", "full", "chunk", "chunk_with_siblings", "auto"], "default": "snippet"},
                                "snippet_length": {"type": "integer", "minimum": 50, "maximum": 2000, "default": 300},
                                "max_tokens": {"type": "integer"},
                                "chars_per_token": {"type": "integer"},
                            }
                        }
                    },
                    "required": ["source", "id"],
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
        if tool_name == "knowledge.search":
            return await self._search(args, context)
        if tool_name == "knowledge.get":
            return await self._get(args, context)
        raise ValueError(f"Unknown tool: {tool_name}")

    async def _call_tool(self, tool: str, arguments: Dict[str, Any], context: Any | None) -> Any:
        registry = get_module_registry()
        module = await registry.find_module_for_tool(tool)
        if not module:
            return None
        return await module.execute_with_circuit_breaker(module.execute_tool, tool, arguments, context)

    def _collect_seen(self, context: Any | None) -> set[str]:
        seen: set[str] = set()
        try:
            if context and getattr(context, "metadata", None):
                if isinstance(context.metadata.get("seen_uris"), list):
                    seen.update([str(u) for u in context.metadata.get("seen_uris")])
        except Exception:
            pass
        return seen

    def _update_seen(self, context: Any | None, new_uris: List[str]):
        try:
            if context and getattr(context, "metadata", None):
                arr = list(set([str(u) for u in (context.metadata.get("seen_uris") or [])] + new_uris))
                context.metadata["seen_uris"] = arr
        except Exception:
            pass

    def _combine_and_sort(self, buckets: List[List[Dict[str, Any]]], order_by: str) -> List[Dict[str, Any]]:
        items = [it for b in buckets for it in (b or [])]
        if order_by == "recent":
            items.sort(key=lambda x: (_iso_to_dt(x.get("last_modified")) or datetime.min), reverse=True)
        else:
            items.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
        return items

    async def _search(self, args: Dict[str, Any], context: Any | None) -> Dict[str, Any]:
        query: str = args.get("query")
        limit: int = int(args.get("limit", 20))
        offset: int = int(args.get("offset", 0))
        snippet_len: int = int(args.get("snippet_length", 300))
        order_by: str = args.get("order_by", "relevance")
        sources: List[str] = args.get("sources") or ["notes", "media"]
        filters: Dict[str, Any] = args.get("filters") or {}

        # Apply session defaults
        try:
            if context and getattr(context, "metadata", None):
                sc = context.metadata.get("safe_config") or {}
                if isinstance(sc, dict):
                    snippet_len = int(sc.get("snippet_length", snippet_len))
        except Exception:
            pass

        # Seed dedupe with session-persisted URIs if any
        seen = self._collect_seen(context)

        # Fan-out calls
        tasks = []
        if "notes" in sources:
            tasks.append(self._call_tool("notes.search", {"query": query, "limit": limit + offset, "offset": 0, "snippet_length": snippet_len}, context))
        if "media" in sources:
            f = (filters or {}).get("media") or {}
            tasks.append(self._call_tool("media.search", {
                "query": query,
                "limit": limit + offset,
                "offset": 0,
                "snippet_length": snippet_len,
                "media_types": f.get("media_types"),
                "date_from": f.get("date_from"),
                "date_to": f.get("date_to"),
                "order_by": f.get("order_by", order_by),
            }, context))
        if "chats" in sources:
            f = (filters or {}).get("chats") or {}
            tasks.append(self._call_tool("chats.search", {
                "query": query,
                "by": f.get("by", "both"),
                "limit": limit + offset,
                "offset": 0,
                "snippet_length": snippet_len,
                "character_id": f.get("character_id"),
                "sender": f.get("sender"),
            }, context))
        if "characters" in sources:
            tasks.append(self._call_tool("characters.search", {"query": query, "limit": limit + offset, "offset": 0, "snippet_length": snippet_len}, context))
        if "prompts" in sources:
            f = (filters or {}).get("prompts") or {}
            tasks.append(self._call_tool("prompts.search", {
                "query": query,
                "fields": f.get("fields"),
                "limit": limit + offset,
                "offset": 0,
                "snippet_length": snippet_len,
            }, context))

        results_raw = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []

        buckets: List[List[Dict[str, Any]]] = []
        for r in results_raw:
            try:
                if isinstance(r, dict) and isinstance(r.get("results"), list):
                    buckets.append(r.get("results"))
            except Exception:
                continue

        combined = self._combine_and_sort(buckets, order_by=order_by)

        # Dedupe by URI (skip items already seen in session/request)
        out: List[Dict[str, Any]] = []
        new_uris: List[str] = []
        for item in combined:
            uri = str(item.get("uri") or "")
            if not uri or uri in seen:
                continue
            seen.add(uri)
            new_uris.append(uri)
            out.append(item)
            if len(out) >= (offset + limit):
                break

        # Apply offset/limit across combined results
        sliced = out[offset: offset + limit]
        has_more = (len(out) > (offset + len(sliced)))
        next_offset = (offset + len(sliced)) if has_more else None

        # Persist dedupe across WS sessions via context.metadata
        self._update_seen(context, new_uris)

        return {
            "results": sliced,
            "has_more": has_more,
            "next_offset": next_offset,
            "total_estimated": len(combined),
        }

    async def _get(self, args: Dict[str, Any], context: Any | None) -> Dict[str, Any]:
        source: str = args.get("source")
        idv = args.get("id")
        retrieval: Dict[str, Any] = args.get("retrieval") or {}
        mode = retrieval.get("mode", "snippet")
        snippet_len = int(retrieval.get("snippet_length", 300))
        # If auto and a token budget is provided, prefer chunk_with_siblings
        if mode == "auto" and isinstance(retrieval.get("max_tokens"), (int, float)):
            retrieval = dict(retrieval)
            retrieval["mode"] = "chunk_with_siblings"

        # Map to source tools
        if source == "notes":
            return await self._call_tool("notes.get", {"note_id": str(idv), "retrieval": retrieval}, context)
        if source == "media":
            return await self._call_tool("media.get", {"media_id": int(idv), "retrieval": retrieval}, context)
        if source == "chats":
            return await self._call_tool("chats.get", {"conversation_id": str(idv), "retrieval": retrieval}, context)
        if source == "characters":
            return await self._call_tool("characters.get", {"character_id": int(idv)}, context)
        if source == "prompts":
            return await self._call_tool("prompts.get", {"prompt_id_or_name": str(idv)}, context)
        # Unsupported source
        raise ValueError(f"Unsupported source for get: {source}")

    def validate_tool_arguments(self, tool_name: str, arguments: Dict[str, Any]):
        if tool_name == "knowledge.search":
            q = arguments.get("query")
            if not isinstance(q, str) or not (1 <= len(q) <= 1000):
                raise ValueError("query must be 1..1000 chars")
            limit = int(arguments.get("limit", 20))
            offset = int(arguments.get("offset", 0))
            snip = int(arguments.get("snippet_length", 300))
            if limit < 1 or limit > 100:
                raise ValueError("limit must be 1..100")
            if offset < 0:
                raise ValueError("offset must be >= 0")
            if snip < 50 or snip > 2000:
                raise ValueError("snippet_length must be 50..2000")
            sources = arguments.get("sources")
            if sources is not None and (not isinstance(sources, list) or any(s not in {"notes","media","chats","characters","prompts"} for s in sources)):
                raise ValueError("sources must be subset of notes|media|chats|characters|prompts")
        elif tool_name == "knowledge.get":
            source = arguments.get("source")
            if source not in {"notes","media","chats","characters","prompts"}:
                raise ValueError("source invalid")
            if arguments.get("id") is None:
                raise ValueError("id is required")
            retrieval = arguments.get("retrieval") or {}
            if not isinstance(retrieval, dict):
                raise ValueError("retrieval must be an object")
            mode = retrieval.get("mode", "snippet")
            if mode not in {"snippet","full","chunk","chunk_with_siblings","auto"}:
                raise ValueError("retrieval.mode invalid")
