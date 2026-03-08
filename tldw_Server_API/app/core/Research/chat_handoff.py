"""Best-effort chat completion handoff for deep research runs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    CharactersRAGDBError,
    InputError,
)
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Research.artifact_store import ResearchArtifactStore

_CHAT_UNAVAILABLE_EXCEPTIONS = (
    CharactersRAGDBError,
    InputError,
    FileNotFoundError,
    KeyError,
    LookupError,
    OSError,
    PermissionError,
    RuntimeError,
    TypeError,
    ValueError,
)


class ChatUnavailableError(RuntimeError):
    """Raised when the originating chat can no longer accept completion delivery."""


def _open_chat_db_for_user(owner_user_id: str) -> CharactersRAGDB:
    return CharactersRAGDB(str(DatabasePaths.get_chacha_db_path(int(owner_user_id))), client_id=str(owner_user_id))


def _open_notifications_db_for_user(owner_user_id: str) -> CollectionsDatabase:
    return CollectionsDatabase.for_user(user_id=int(owner_user_id))


def _build_completion_message(*, query: str, session_id: str, bundle: dict[str, Any]) -> str:
    source_count = len(bundle.get("source_inventory", [])) if isinstance(bundle.get("source_inventory"), list) else 0
    claim_count = len(bundle.get("claims", [])) if isinstance(bundle.get("claims"), list) else 0
    counter_bits: list[str] = []
    if source_count > 0:
        counter_bits.append(f"{source_count} source{'s' if source_count != 1 else ''}")
    if claim_count > 0:
        counter_bits.append(f"{claim_count} claim{'s' if claim_count != 1 else ''}")
    summary = ""
    if counter_bits:
        summary = " " + ", ".join(counter_bits) + "."
    return (
        f'Deep research finished for "{query}".{summary} '
        f"Open the full report: /research?run={session_id}"
    )


def deliver_research_chat_handoff(
    *,
    db: ResearchSessionsDB,
    artifact_store: ResearchArtifactStore,
    session_id: str,
    chat_db_factory: Callable[[str], CharactersRAGDB] | None = None,
    notifications_db_factory: Callable[[str], CollectionsDatabase] | None = None,
) -> dict[str, Any] | None:
    session = db.get_session(session_id)
    if session is None:
        raise KeyError(session_id)
    handoff = db.get_chat_handoff(session_id)
    if handoff is None:
        return None
    if handoff.handoff_status in {"chat_inserted", "notification_only", "failed"}:
        return None

    bundle = artifact_store.read_json(session_id=session_id, artifact_name="bundle.json") or {}
    message_content = _build_completion_message(
        query=session.query,
        session_id=session_id,
        bundle=bundle if isinstance(bundle, dict) else {},
    )

    chat_db = None
    try:
        chat_db = (chat_db_factory or _open_chat_db_for_user)(session.owner_user_id)
        conversation = chat_db.get_conversation_by_id(handoff.chat_id)
        if conversation is None:
            raise ChatUnavailableError("originating chat no longer exists")
        if str(conversation.get("client_id") or "").strip() != session.owner_user_id:
            raise ChatUnavailableError("originating chat is not owned by the research run owner")
        message_id = chat_db.add_message(
            {
                "conversation_id": handoff.chat_id,
                "sender": "assistant",
                "content": message_content,
                "client_id": session.owner_user_id,
            }
        )
        if not message_id:
            raise RuntimeError("failed to insert research completion chat message")
        chat_db.set_message_metadata_extra(
            message_id,
            {
                "deep_research_completion": {
                    "run_id": session.id,
                    "query": session.query,
                    "kind": "completion_handoff",
                }
            },
            merge=True,
        )
        db.mark_chat_handoff_chat_inserted(
            session_id,
            delivered_chat_message_id=message_id,
        )
        return {
            "delivery": "chat_inserted",
            "message_id": message_id,
        }
    except ChatUnavailableError as exc:
        logger.info("research chat handoff falling back to notification for session {}: {}", session_id, exc)
    except _CHAT_UNAVAILABLE_EXCEPTIONS as exc:
        logger.warning("research chat handoff unavailable for session {}: {}", session_id, exc)
    finally:
        if chat_db is not None:
            try:
                chat_db.close_connection()
            except Exception:
                logger.debug("research chat handoff: failed to close chat db for session {}", session_id)

    notifications_db = None
    try:
        notifications_db = (notifications_db_factory or _open_notifications_db_for_user)(session.owner_user_id)
        notification = notifications_db.create_user_notification(
            kind="deep_research_completed",
            title="Deep research completed",
            message=message_content,
            severity="info",
            source_domain="research",
            source_job_type="research_phase",
            link_type="deep_research_run",
            link_id=session_id,
            link_url=f"/research?run={session_id}",
            dedupe_key=f"deep_research_completed:{session_id}",
        )
        db.mark_chat_handoff_notification_only(
            session_id,
            delivered_notification_id=notification.id,
        )
        return {
            "delivery": "notification_only",
            "notification_id": notification.id,
        }
    finally:
        if notifications_db is not None:
            try:
                notifications_db.close()
            except Exception:
                logger.debug("research chat handoff: failed to close notifications db for session {}", session_id)


__all__ = ["deliver_research_chat_handoff"]
