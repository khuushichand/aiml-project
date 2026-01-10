import asyncio
import json
import os
import tempfile

from tldw_Server_API.app.core.Claims_Extraction.claims_service import (
    send_claims_alert_email_digest_for_scheduler,
)
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.config import settings


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


def _seed_digest_db() -> MediaDatabase:


     tmpdir = tempfile.mkdtemp(prefix="claims_alert_digest_")
    db_path = os.path.join(tmpdir, "media.db")
    db = MediaDatabase(db_path=db_path, client_id="1")
    db.initialize_db()
    return db


def test_claims_alert_email_digest_marks_delivered(monkeypatch):


     monkeypatch.setitem(settings, "CLAIMS_ALERT_EMAIL_DIGEST_ENABLED", True)
    monkeypatch.setitem(settings, "CLAIMS_ALERT_EMAIL_DIGEST_INTERVAL_SEC", 0)
    monkeypatch.setitem(settings, "CLAIMS_ALERT_EMAIL_DIGEST_MAX_EVENTS", 50)

    db = _seed_digest_db()
    try:
        db.upsert_claims_monitoring_settings(
            user_id="1",
            threshold_ratio=0.2,
            baseline_ratio=0.1,
            slack_webhook_url=None,
            webhook_url=None,
            email_recipients=json.dumps(["alerts@example.com"]),
            enabled=True,
        )
        alert = db.create_claims_monitoring_alert(
            user_id="1",
            name="Unsupported ratio alert",
            alert_type="threshold_breach",
            threshold_ratio=0.3,
            channels_json=json.dumps({"email": True}),
            email_recipients=json.dumps(["alerts@example.com"]),
            enabled=True,
        )
        payload = {
            "alert_id": alert.get("id"),
            "alert_name": alert.get("name"),
            "window_ratio": 0.5,
            "baseline_ratio": 0.2,
            "threshold": 0.3,
            "drift": 0.3,
        }
        db.insert_claims_monitoring_event(
            user_id="1",
            event_type="unsupported_ratio",
            severity="warning",
            payload_json=json.dumps(payload),
        )

        email_service = _FakeEmailService()
        result = asyncio.run(
            send_claims_alert_email_digest_for_scheduler(
                target_user_id="1",
                db=db,
                email_service=email_service,
            )
        )
        assert result.get("events") == 1
        assert email_service.sent
        undelivered = db.list_undelivered_claims_monitoring_events(user_id="1", event_type="unsupported_ratio")
        assert undelivered == []
    finally:
        db.close_connection()
