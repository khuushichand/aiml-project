import json
import os
import tempfile
import time
from contextlib import contextmanager

from tldw_Server_API.app.core.Claims_Extraction import claims_notifications
from tldw_Server_API.app.core.Claims_Extraction.claims_notifications import dispatch_claim_review_notifications
from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase


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


def test_dispatch_claim_review_notifications_uses_managed_media_database(monkeypatch):
    class _FakeDb:
        def __init__(self) -> None:
            self.closed = False
            self.marked_ids: list[int] = []

        def get_claims_monitoring_settings(self, user_id):
            assert user_id == "1"
            return {
                "enabled": True,
                "slack_webhook_url": None,
                "webhook_url": None,
                "email_recipients": json.dumps(["review@example.com"]),
            }

        def get_claim_notifications_by_ids(self, notification_ids):
            assert notification_ids == [7]
            return [
                {
                    "id": 7,
                    "kind": "review_update",
                    "payload_json": json.dumps({"claim_text": "A.", "new_status": "approved"}),
                    "created_at": "2026-03-16T00:00:00Z",
                }
            ]

        def mark_claim_notifications_delivered(self, notification_ids):
            self.marked_ids.extend(notification_ids)

        def close_connection(self) -> None:
            self.closed = True

    class _ImmediateThread:
        def __init__(self, *, target, daemon):
            self._target = target
            self.daemon = daemon

        def start(self) -> None:
            self._target()

    fake_db = _FakeDb()
    managed_calls: list[dict[str, object]] = []

    @contextmanager
    def _fake_managed_media_database(client_id, *, initialize=True, **kwargs):
        managed_calls.append(
            {
                "client_id": client_id,
                "initialize": initialize,
                "kwargs": kwargs,
            }
        )
        try:
            yield fake_db
        finally:
            fake_db.close_connection()

    monkeypatch.setattr(claims_notifications, "managed_media_database", _fake_managed_media_database, raising=False)
    monkeypatch.setattr(
        claims_notifications,
        "create_media_database",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("legacy raw factory should not be used")),
        raising=False,
    )
    monkeypatch.setattr(claims_notifications.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(claims_notifications, "_deliver_review_email_sync", lambda **kwargs: True, raising=False)

    dispatch_claim_review_notifications(
        db_path="/tmp/claims-review.db",
        owner_user_id="1",
        notification_ids=[7],
    )

    assert fake_db.closed is True
    assert fake_db.marked_ids == [7]
    assert managed_calls == [
        {
            "client_id": claims_notifications.settings.get("SERVER_CLIENT_ID", "SERVER_API_V1"),
            "initialize": True,
            "kwargs": {
                "db_path": "/tmp/claims-review.db",
                "suppress_init_exceptions": claims_notifications._CLAIMS_NOTIFICATION_NONCRITICAL_EXCEPTIONS,
                "suppress_close_exceptions": claims_notifications._CLAIMS_NOTIFICATION_NONCRITICAL_EXCEPTIONS,
            },
        }
    ]
