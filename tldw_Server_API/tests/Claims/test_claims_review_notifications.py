import json
import os
import tempfile
import time

from tldw_Server_API.app.core.Claims_Extraction.claims_notifications import dispatch_claim_review_notifications
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


class _FakeEmailService:
    def __init__(self) -> None:
        self.sent = []

    async def send_email(self, *, to_email: str, subject: str, html_body: str, text_body: str):
        self.sent.append(
            {
                "to_email": to_email,
                "subject": subject,
                "html_body": html_body,
                "text_body": text_body,
            }
        )
        return True


def _seed_review_notification_db() -> MediaDatabase:
    tmpdir = tempfile.mkdtemp(prefix="claims_review_notify_")
    db_path = os.path.join(tmpdir, "media.db")
    db = MediaDatabase(db_path=db_path, client_id="1")
    db.initialize_db()
    media_id, _, _ = db.add_media_with_keywords(
        title="Doc",
        media_type="text",
        content="A. B.",
        keywords=None,
    )
    db.upsert_claims(
        [
            {
                "media_id": media_id,
                "chunk_index": 0,
                "span_start": None,
                "span_end": None,
                "claim_text": "A.",
                "confidence": 0.9,
                "extractor": "heuristic",
                "extractor_version": "v1",
                "chunk_hash": "abc",
            }
        ]
    )
    row = db.execute_query("SELECT id, uuid FROM Claims WHERE media_id = ?", (media_id,)).fetchone()
    claim_id = int(row["id"]) if isinstance(row, dict) else int(row[0])
    claim_uuid = row["uuid"] if isinstance(row, dict) else row[1]
    return db, claim_id, claim_uuid


def test_claims_review_notifications_deliver_email(monkeypatch):
    from tldw_Server_API.app.core.AuthNZ import email_service as email_module

    fake_service = _FakeEmailService()
    monkeypatch.setattr(email_module, "get_email_service", lambda: fake_service)

    db, claim_id, claim_uuid = _seed_review_notification_db()
    try:
        db.upsert_claims_monitoring_settings(
            user_id="1",
            threshold_ratio=0.2,
            baseline_ratio=0.1,
            slack_webhook_url=None,
            webhook_url=None,
            email_recipients=json.dumps(["review@example.com"]),
            enabled=True,
        )
        notification = db.insert_claim_notification(
            user_id="1",
            kind="review_update",
            target_user_id="1",
            target_review_group=None,
            resource_type="claim",
            resource_id=str(claim_id),
            payload_json=json.dumps(
                {
                    "claim_id": claim_id,
                    "claim_uuid": claim_uuid,
                    "claim_text": "A.",
                    "old_status": "pending",
                    "new_status": "approved",
                }
            ),
        )
        notif_id = int(notification.get("id"))
        dispatch_claim_review_notifications(
            db_path=str(db.db_path_str),
            owner_user_id="1",
            notification_ids=[notif_id],
        )
        delivered = None
        for _ in range(20):
            row = db.get_claim_notification(notif_id)
            delivered = row.get("delivered_at")
            if delivered:
                break
            time.sleep(0.05)
        assert delivered is not None
        assert fake_service.sent
    finally:
        db.close_connection()
