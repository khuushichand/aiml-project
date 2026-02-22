"""
Tests for notification digest/batching functionality.
"""
from __future__ import annotations

from unittest.mock import patch

from tldw_Server_API.app.core.Monitoring.notification_service import NotificationService


def _make_service(**overrides) -> NotificationService:
    """Create a NotificationService with test-friendly defaults."""
    env = {
        "MONITORING_NOTIFY_ENABLED": "true",
        "MONITORING_NOTIFY_MIN_SEVERITY": "info",
        "MONITORING_NOTIFY_DIGEST_MODE": overrides.pop("digest_mode", "immediate"),
        "MONITORING_NOTIFY_WEBHOOK_URL": "",
        "MONITORING_NOTIFY_EMAIL_TO": "",
        "MONITORING_NOTIFY_SMTP_HOST": "",
    }
    with patch.dict("os.environ", env, clear=False):
        svc = NotificationService()
    # Override file path to /dev/null to avoid writing files
    svc.file_path = "/dev/null"
    return svc


class TestDigestModeImmediate:
    def test_immediate_sends_now(self):
        """In immediate mode, notify_or_batch should call notify_generic."""
        svc = _make_service(digest_mode="immediate")
        payload = {"type": "test", "severity": "info", "user_id": "u1"}
        result = svc.notify_or_batch(payload)
        assert result in ("logged", "skipped", "failed")

    def test_immediate_has_no_pending(self):
        """In immediate mode, nothing should be batched."""
        svc = _make_service(digest_mode="immediate")
        payload = {"type": "test", "severity": "info", "user_id": "u1"}
        svc.notify_or_batch(payload)
        assert svc.get_pending_digest_count() == 0


class TestDigestModeHourly:
    def test_hourly_batches_alert(self):
        """In hourly mode, notify_or_batch should accumulate alerts."""
        svc = _make_service(digest_mode="hourly")
        payload = {"type": "test", "severity": "info", "user_id": "u1", "category": "test"}
        result = svc.notify_or_batch(payload)
        assert result == "batched"
        assert svc.get_pending_digest_count() == 1
        assert svc.get_pending_digest_count("u1") == 1

    def test_hourly_batches_multiple_alerts(self):
        """Multiple alerts should accumulate."""
        svc = _make_service(digest_mode="hourly")
        for i in range(5):
            svc.notify_or_batch({"type": "test", "severity": "info", "user_id": "u1", "idx": i})
        assert svc.get_pending_digest_count("u1") == 5

    def test_flush_digest_clears_buffer(self):
        """flush_digest should clear the pending buffer."""
        svc = _make_service(digest_mode="hourly")
        for i in range(3):
            svc.notify_or_batch({"type": "test", "severity": "info", "user_id": "u1"})
        assert svc.get_pending_digest_count("u1") == 3

        count = svc.flush_digest("u1")
        assert count == 3
        assert svc.get_pending_digest_count("u1") == 0

    def test_flush_digest_all_recipients(self):
        """flush_digest(None) should flush all recipients."""
        svc = _make_service(digest_mode="hourly")
        svc.notify_or_batch({"type": "test", "severity": "info", "user_id": "u1"})
        svc.notify_or_batch({"type": "test", "severity": "info", "user_id": "u2"})
        svc.notify_or_batch({"type": "test", "severity": "info", "user_id": "u2"})

        count = svc.flush_digest()
        assert count == 3
        assert svc.get_pending_digest_count() == 0

    def test_flush_empty_returns_zero(self):
        """flush_digest with no pending alerts should return 0."""
        svc = _make_service(digest_mode="hourly")
        count = svc.flush_digest()
        assert count == 0

    def test_batched_per_recipient(self):
        """Alerts should be batched per recipient."""
        svc = _make_service(digest_mode="daily")
        svc.notify_or_batch({"type": "t", "severity": "info", "user_id": "alice"})
        svc.notify_or_batch({"type": "t", "severity": "info", "user_id": "bob"})
        svc.notify_or_batch({"type": "t", "severity": "info", "user_id": "alice"})

        assert svc.get_pending_digest_count("alice") == 2
        assert svc.get_pending_digest_count("bob") == 1

        count = svc.flush_digest("alice")
        assert count == 2
        assert svc.get_pending_digest_count("alice") == 0
        assert svc.get_pending_digest_count("bob") == 1
