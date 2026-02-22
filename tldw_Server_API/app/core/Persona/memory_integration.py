"""
Persona memory integration helpers.

This module wires persona session activity to the per-user personalization DB
when personalization is enabled and the user has opted in.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.DB_Management.Personalization_DB import (
    PersonalizationDB,
    SemanticMemory,
    UsageEvent,
)
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.feature_flags import is_personalization_enabled


@dataclass
class RetrievedMemory:
    content: str
    memory_id: str | None = None


def _normalize_personalization_user_id(user_id: str) -> str:
    raw = str(user_id or "").strip()
    if not raw:
        raise ValueError("user_id is required")
    if raw.isdigit():
        return str(int(raw))
    digest = hashlib.sha1(raw.encode("utf-8"), usedforsecurity=False).digest()
    return str(int.from_bytes(digest[:4], byteorder="big", signed=False))


def _get_db_for_user(user_id: str) -> tuple[PersonalizationDB, str]:
    normalized_user_id = _normalize_personalization_user_id(user_id)
    db_path = DatabasePaths.get_personalization_db_path(int(normalized_user_id))
    return PersonalizationDB(str(db_path)), normalized_user_id


def _is_profile_opted_in(db: PersonalizationDB, normalized_user_id: str) -> bool:
    profile = db.get_or_create_profile(normalized_user_id)
    return bool(profile.get("enabled", 0))


def retrieve_top_memories(
    *,
    user_id: str | None,
    query_text: str,
    top_k: int = 3,
) -> list[RetrievedMemory]:
    if not user_id or not is_personalization_enabled():
        return []
    try:
        db, normalized_user_id = _get_db_for_user(user_id)
        if not _is_profile_opted_in(db, normalized_user_id):
            return []
        safe_top_k = max(1, min(int(top_k), 10))
        query = str(query_text or "").strip() or None
        items, _ = db.list_semantic_memories(
            user_id=normalized_user_id,
            q=query,
            limit=safe_top_k,
            offset=0,
        )
        if not items and query:
            items, _ = db.list_semantic_memories(
                user_id=normalized_user_id,
                q=None,
                limit=safe_top_k,
                offset=0,
            )
        out: list[RetrievedMemory] = []
        for item in items:
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            memory_id = item.get("id")
            out.append(
                RetrievedMemory(
                    content=content,
                    memory_id=(str(memory_id) if memory_id is not None else None),
                )
            )
        return out
    except Exception as exc:
        logger.debug(f"persona memory retrieval skipped: {exc}")
        return []


def persist_persona_turn(
    *,
    user_id: str | None,
    session_id: str,
    persona_id: str,
    role: str,
    content: str,
    turn_type: str,
    metadata: dict[str, Any] | None = None,
    store_as_memory: bool = False,
) -> bool:
    if not user_id or not is_personalization_enabled():
        return False
    try:
        db, normalized_user_id = _get_db_for_user(user_id)
        if not _is_profile_opted_in(db, normalized_user_id):
            return False
        clean_metadata = dict(metadata or {})
        clean_metadata["persona_id"] = str(persona_id or "")
        clean_metadata["turn_type"] = str(turn_type or "text")
        clean_metadata["content_length"] = len(str(content or ""))
        _ = db.insert_usage_event(
            UsageEvent(
                user_id=normalized_user_id,
                type="persona.turn",
                resource_id=str(session_id or ""),
                tags=["persona", str(role or "unknown")],
                metadata=clean_metadata,
            )
        )
        if store_as_memory:
            memory_text = str(content or "").strip()
            if memory_text:
                if len(memory_text) > 1024:
                    memory_text = memory_text[:1024]
                _ = db.add_semantic_memory(
                    SemanticMemory(
                        user_id=normalized_user_id,
                        content=memory_text,
                        tags=["persona", str(role or "unknown"), str(persona_id or "")],
                        pinned=False,
                    )
                )
        return True
    except Exception as exc:
        logger.debug(f"persona turn persistence skipped: {exc}")
        return False


def persist_tool_outcome(
    *,
    user_id: str | None,
    session_id: str,
    persona_id: str,
    tool_name: str,
    step_idx: int,
    outcome: dict[str, Any],
    store_as_memory: bool = True,
) -> bool:
    try:
        serialized = json.dumps(outcome, ensure_ascii=True, sort_keys=True)
    except Exception:
        serialized = str(outcome)
    tool_summary = f"Tool={tool_name} step={step_idx} outcome={serialized}"
    return persist_persona_turn(
        user_id=user_id,
        session_id=session_id,
        persona_id=persona_id,
        role="tool",
        content=tool_summary,
        turn_type="tool_result",
        metadata={"tool_name": str(tool_name or ""), "step_idx": int(step_idx)},
        store_as_memory=bool(store_as_memory),
    )
