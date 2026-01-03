"""Explicit feedback endpoints shared by chat and RAG."""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import check_rate_limit
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.api.v1.schemas.feedback_schemas import (
    ExplicitFeedbackRequest,
    ExplicitFeedbackResponse,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.RAG.rag_service.analytics_system import UnifiedFeedbackSystem

router = APIRouter()

# In-memory cache for idempotency; per-process scope (no cross-worker guarantees).
# Pending entries reduce duplicate submissions within a single worker.
_IDEMPOTENCY_WINDOW_SECONDS = 300
_IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS = 60
_idempotency_lock = Lock()
_idempotency_store: dict[str, "_IdempotencyRecord"] = {}
_idempotency_last_cleanup = 0.0


@dataclass
class _IdempotencyRecord:
    feedback_id: Optional[str]
    created_at: float
    issues: List[str]
    user_notes: Optional[str]
    pending: bool = False


def _normalize_text_list(values: Optional[List[str]]) -> List[str]:
    if not values:
        return []
    normalized: List[str] = []
    seen = set()
    for item in values:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _merge_issues(existing: List[str], incoming: List[str]) -> List[str]:
    merged: List[str] = []
    seen = set()
    for item in existing + incoming:
        if item in seen:
            continue
        seen.add(item)
        merged.append(item)
    return merged


def _cleanup_idempotency_store(now: float) -> None:
    global _idempotency_last_cleanup
    if (now - _idempotency_last_cleanup) < _IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS:
        return
    expired = [
        key for key, record in _idempotency_store.items()
        if (now - record.created_at) > _IDEMPOTENCY_WINDOW_SECONDS
    ]
    for key in expired:
        _idempotency_store.pop(key, None)
    _idempotency_last_cleanup = now


def _get_idempotency_record(key: str) -> Optional[_IdempotencyRecord]:
    now = time.monotonic()
    with _idempotency_lock:
        _cleanup_idempotency_store(now)
        record = _idempotency_store.get(key)
        if not record:
            return None
        if (now - record.created_at) > _IDEMPOTENCY_WINDOW_SECONDS:
            _idempotency_store.pop(key, None)
            return None
        return record


def _reserve_idempotency_record(
    key: str,
    issues: List[str],
    user_notes: Optional[str],
) -> tuple[bool, _IdempotencyRecord]:
    now = time.monotonic()
    with _idempotency_lock:
        _cleanup_idempotency_store(now)
        record = _idempotency_store.get(key)
        if record:
            if (now - record.created_at) > _IDEMPOTENCY_WINDOW_SECONDS:
                _idempotency_store.pop(key, None)
            else:
                return False, record
        record = _IdempotencyRecord(
            feedback_id=None,
            created_at=now,
            issues=issues,
            user_notes=user_notes,
            pending=True,
        )
        _idempotency_store[key] = record
        return True, record


def _finalize_idempotency_record(
    key: str,
    feedback_id: Optional[str],
    issues: List[str],
    user_notes: Optional[str],
) -> None:
    with _idempotency_lock:
        record = _idempotency_store.get(key)
        if not record:
            return
        record.feedback_id = feedback_id
        record.issues = issues
        record.user_notes = user_notes
        record.pending = False


def _clear_idempotency_record(key: str) -> None:
    with _idempotency_lock:
        _idempotency_store.pop(key, None)


def _update_idempotency_record(key: str, issues: List[str], user_notes: Optional[str]) -> None:
    with _idempotency_lock:
        record = _idempotency_store.get(key)
        if not record:
            return
        record.issues = issues
        record.user_notes = user_notes


def _build_dedupe_key(
    *,
    user_key: str,
    request: ExplicitFeedbackRequest,
    conversation_id: Optional[str],
    query: str,
    document_ids: List[str],
    chunk_ids: List[str],
) -> str:
    if request.idempotency_key:
        return f"idem:{user_key}:{request.idempotency_key}"
    if request.message_id:
        return (
            f"chat:{user_key}:{conversation_id or ''}:{request.message_id}:"
            f"{request.feedback_type}:{request.helpful}:{request.relevance_score}"
        )
    doc_key = ",".join(sorted(document_ids)) if document_ids else ""
    chunk_key = ",".join(sorted(chunk_ids)) if chunk_ids else ""
    corpus = request.corpus or ""
    return (
        f"rag:{user_key}:{query}:{request.feedback_type}:"
        f"{request.helpful}:{request.relevance_score}:{doc_key}:{chunk_key}:{corpus}"
    )


def _ensure_conversation_owner(conversation: dict, current_user: User) -> None:
    conv_client_id = conversation.get("client_id")
    user_id = current_user.id
    if conv_client_id is None or user_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden for this conversation")
    try:
        if int(conv_client_id) != int(user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden for this conversation")
    except (TypeError, ValueError):
        if str(conv_client_id) != str(user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden for this conversation") from None


@router.post(
    "/explicit",
    response_model=ExplicitFeedbackResponse,
    summary="Submit explicit feedback (chat + RAG)",
    dependencies=[Depends(check_rate_limit)],
)
async def submit_explicit_feedback(
    payload: ExplicitFeedbackRequest,
    current_user: User = Depends(get_request_user),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
) -> ExplicitFeedbackResponse:
    resolved_conversation_id = payload.conversation_id
    message = None

    if payload.message_id:
        message = db.get_message_by_id(payload.message_id)
        if not message or message.get("deleted"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        if not resolved_conversation_id:
            resolved_conversation_id = message.get("conversation_id")
        if resolved_conversation_id != message.get("conversation_id"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message is not in conversation",
            )

    if resolved_conversation_id:
        conversation = db.get_conversation_by_id(resolved_conversation_id)
        if not conversation or conversation.get("deleted"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        _ensure_conversation_owner(conversation, current_user)

    resolved_query = payload.query
    if (resolved_query is None or str(resolved_query).strip() == "") and message is not None:
        resolved_query = message.get("content") or ""
    if resolved_query is None:
        resolved_query = ""
    resolved_query = str(resolved_query)

    issues = _normalize_text_list(payload.issues)
    document_ids = _normalize_text_list(payload.document_ids)
    chunk_ids = _normalize_text_list(payload.chunk_ids)
    user_key = str(current_user.id)

    dedupe_key = _build_dedupe_key(
        user_key=user_key,
        request=payload,
        conversation_id=resolved_conversation_id,
        query=resolved_query,
        document_ids=document_ids,
        chunk_ids=chunk_ids,
    )

    reserved, existing = _reserve_idempotency_record(dedupe_key, issues, payload.user_notes)
    if not reserved:
        if issues or payload.user_notes is not None:
            merged_issues = _merge_issues(existing.issues, issues)
            updated_notes = existing.user_notes if payload.user_notes is None else payload.user_notes
            if existing.feedback_id and not existing.pending:
                collector = UnifiedFeedbackSystem(chacha_db=db)
                if collector.user_feedback:
                    await collector.user_feedback.merge_feedback_update(
                        existing.feedback_id,
                        issues=merged_issues or None,
                        user_notes=updated_notes,
                    )
            _update_idempotency_record(dedupe_key, merged_issues, updated_notes)
        return ExplicitFeedbackResponse(ok=True, feedback_id=existing.feedback_id)

    collector = UnifiedFeedbackSystem(chacha_db=db)
    try:
        result = await collector.submit_feedback(
            conversation_id=resolved_conversation_id or "",
            query=resolved_query,
            document_ids=document_ids,
            chunk_ids=chunk_ids,
            relevance_score=payload.relevance_score,
            helpful=payload.helpful,
            issues=issues or None,
            user_notes=payload.user_notes,
            _user_id=current_user.username if current_user else None,
            message_id=payload.message_id,
        )
    except Exception:  # clear pending idempotency slot on any failure
        _clear_idempotency_record(dedupe_key)
        raise

    if result.get("errors"):
        logger.warning("Explicit feedback errors: {}", result.get("errors"))

    feedback_id = result.get("feedback_id")
    if resolved_conversation_id and not feedback_id:
        _clear_idempotency_record(dedupe_key)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not record feedback")

    finalized = _get_idempotency_record(dedupe_key)
    final_issues = finalized.issues if finalized else issues
    final_notes = finalized.user_notes if finalized else payload.user_notes
    _finalize_idempotency_record(dedupe_key, feedback_id, final_issues, final_notes)
    if (
        feedback_id
        and collector.user_feedback
        and (final_issues != issues or final_notes != payload.user_notes)
    ):
        await collector.user_feedback.merge_feedback_update(
            feedback_id,
            issues=final_issues or None,
            user_notes=final_notes,
        )

    return ExplicitFeedbackResponse(ok=True, feedback_id=feedback_id)
