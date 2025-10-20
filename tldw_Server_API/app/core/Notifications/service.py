from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.email_service import get_email_service
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.Chat.document_generator import DocumentGeneratorService, DocumentType


@dataclass
class NotificationResult:
    channel: str
    status: str
    details: Dict[str, Any] = field(default_factory=dict)


class NotificationsService:
    """
    Unified notifications helper to send watchlist outputs via email or persist them to Chatbook.
    """

    def __init__(self, *, user_id: int, user_email: Optional[str] = None) -> None:
        self.user_id = int(user_id)
        self.user_email = user_email
        self._email_service = get_email_service()
        self._doc_service: Optional[DocumentGeneratorService] = None

    def _ensure_doc_service(self) -> DocumentGeneratorService:
        if self._doc_service is None:
            db_path = DatabasePaths.get_chacha_db_path(self.user_id)
            db = CharactersRAGDB(db_path=str(db_path), client_id=str(self.user_id))
            self._doc_service = DocumentGeneratorService(db, user_id=str(self.user_id))
        return self._doc_service

    async def deliver_email(
        self,
        *,
        subject: str,
        html_body: str,
        text_body: Optional[str],
        recipients: Optional[List[str]],
        attachments: Optional[List[Dict[str, Any]]] = None,
        fallback_to_user_email: bool = True,
    ) -> NotificationResult:
        recips = [r.strip() for r in (recipients or []) if r and r.strip()]
        if not recips and fallback_to_user_email and self.user_email:
            recips = [self.user_email]
        if not recips:
            return NotificationResult(
                channel="email",
                status="skipped",
                details={"reason": "no_recipients"},
            )

        deliveries: List[Dict[str, Any]] = []
        for addr in recips:
            try:
                ok = await self._email_service.send_email(
                    to_email=addr,
                    subject=subject,
                    html_body=html_body,
                    text_body=text_body,
                    attachments=attachments,
                )
                deliveries.append({"recipient": addr, "status": "sent" if ok else "failed"})
            except Exception as exc:
                logger.error(f"Email delivery to {addr} failed: {exc}")
                deliveries.append({"recipient": addr, "status": "error", "error": str(exc)})

        if all(entry["status"] == "sent" for entry in deliveries):
            status = "sent"
        elif any(entry["status"] == "sent" for entry in deliveries):
            status = "partial"
        else:
            status = "failed"
        return NotificationResult(
            channel="email",
            status=status,
            details={"deliveries": deliveries, "subject": subject},
        )

    def deliver_chatbook(
        self,
        *,
        title: str,
        content: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        document_type: DocumentType = DocumentType.BRIEFING,
        provider: str = "watchlists",
        model: str = "watchlists",
        conversation_id: Optional[int] = None,
    ) -> NotificationResult:
        try:
            svc = self._ensure_doc_service()
            extra_meta = dict(metadata or {})
            if description:
                extra_meta["description"] = description
            doc_id = svc.create_manual_document(
                title=title,
                content=content,
                document_type=document_type,
                metadata=extra_meta,
                provider=provider,
                model=model,
                conversation_id=conversation_id,
            )
            return NotificationResult(
                channel="chatbook",
                status="stored",
                details={"document_id": doc_id, "provider": provider, "model": model},
            )
        except Exception as exc:
            logger.error(f"Chatbook delivery failed: {exc}")
            return NotificationResult(
                channel="chatbook",
                status="failed",
                details={"error": str(exc)},
            )
