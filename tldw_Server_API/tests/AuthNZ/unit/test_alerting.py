"""
Tests for the SecurityAlertDispatcher module.

Tests cover:
- Dispatcher initialization and configuration
- Severity threshold filtering
- Backoff/cooldown mechanisms
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from tldw_Server_API.app.core.AuthNZ.alerting import SecurityAlertDispatcher


@pytest.fixture
def mock_settings():
     """Create mock settings for alert dispatcher."""
    settings = MagicMock()
    settings.SECURITY_ALERTS_ENABLED = True
    settings.SECURITY_ALERT_MIN_SEVERITY = "medium"
    settings.SECURITY_ALERT_FILE_PATH = None  # Disable file sink
    settings.SECURITY_ALERT_WEBHOOK_URL = None  # Disable webhook sink
    settings.SECURITY_ALERT_EMAIL_TO = ""  # Disable email sink
    settings.SECURITY_ALERT_WEBHOOK_HEADERS = ""
    settings.SECURITY_ALERT_EMAIL_FROM = None
    settings.SECURITY_ALERT_SMTP_HOST = None
    settings.SECURITY_ALERT_SMTP_PORT = 587
    settings.SECURITY_ALERT_SMTP_STARTTLS = True
    settings.SECURITY_ALERT_SMTP_USERNAME = None
    settings.SECURITY_ALERT_SMTP_PASSWORD = None
    settings.SECURITY_ALERT_SMTP_TIMEOUT = 10
    settings.SECURITY_ALERT_EMAIL_SUBJECT_PREFIX = "[Alert]"
    settings.SECURITY_ALERT_FILE_MIN_SEVERITY = None
    settings.SECURITY_ALERT_WEBHOOK_MIN_SEVERITY = None
    settings.SECURITY_ALERT_EMAIL_MIN_SEVERITY = None
    settings.SECURITY_ALERT_BACKOFF_SECONDS = 0
    return settings


@pytest.fixture
def dispatcher(mock_settings):
     """Create alert dispatcher with mock settings."""
    return SecurityAlertDispatcher(settings=mock_settings)


class TestDispatcherInitialization:
    """Tests for SecurityAlertDispatcher initialization."""

    def test_dispatcher_disabled_by_default(self):

             """Dispatcher should respect SECURITY_ALERTS_ENABLED setting."""
        settings = MagicMock()
        settings.SECURITY_ALERTS_ENABLED = False
        settings.SECURITY_ALERT_MIN_SEVERITY = "high"
        settings.SECURITY_ALERT_FILE_PATH = None
        settings.SECURITY_ALERT_WEBHOOK_URL = None
        settings.SECURITY_ALERT_EMAIL_TO = ""
        settings.SECURITY_ALERT_WEBHOOK_HEADERS = ""
        settings.SECURITY_ALERT_EMAIL_FROM = None
        settings.SECURITY_ALERT_SMTP_HOST = None
        settings.SECURITY_ALERT_SMTP_PORT = 587
        settings.SECURITY_ALERT_SMTP_STARTTLS = True
        settings.SECURITY_ALERT_SMTP_USERNAME = None
        settings.SECURITY_ALERT_SMTP_PASSWORD = None
        settings.SECURITY_ALERT_SMTP_TIMEOUT = 10
        settings.SECURITY_ALERT_EMAIL_SUBJECT_PREFIX = "[Alert]"
        settings.SECURITY_ALERT_FILE_MIN_SEVERITY = None
        settings.SECURITY_ALERT_WEBHOOK_MIN_SEVERITY = None
        settings.SECURITY_ALERT_EMAIL_MIN_SEVERITY = None
        settings.SECURITY_ALERT_BACKOFF_SECONDS = 0

        dispatcher = SecurityAlertDispatcher(settings=settings)
        assert dispatcher.enabled is False

    def test_severity_threshold_configuration(self, mock_settings):

             """Severity thresholds should be configurable."""
        mock_settings.SECURITY_ALERT_MIN_SEVERITY = "critical"
        dispatcher = SecurityAlertDispatcher(settings=mock_settings)
        assert dispatcher.min_severity == "critical"

    def test_backoff_configuration(self, mock_settings):

             """Backoff seconds should be configurable."""
        mock_settings.SECURITY_ALERT_BACKOFF_SECONDS = 60
        dispatcher = SecurityAlertDispatcher(settings=mock_settings)
        assert dispatcher.backoff_seconds == 60


class TestSeverityFiltering:
    """Tests for severity-based alert filtering."""

    def test_low_severity_filtered_when_threshold_high(self, mock_settings):

             """Low severity alerts should be filtered when threshold is high."""
        mock_settings.SECURITY_ALERT_MIN_SEVERITY = "high"
        dispatcher = SecurityAlertDispatcher(settings=mock_settings)
        # The dispatcher should filter based on severity using _meets_threshold
        assert dispatcher._meets_threshold("low") is False
        assert dispatcher._meets_threshold("medium") is False
        assert dispatcher._meets_threshold("high") is True
        assert dispatcher._meets_threshold("critical") is True

    def test_all_severities_pass_when_threshold_low(self, mock_settings):

             """All severity levels should pass when threshold is low."""
        mock_settings.SECURITY_ALERT_MIN_SEVERITY = "low"
        dispatcher = SecurityAlertDispatcher(settings=mock_settings)
        assert dispatcher._meets_threshold("low") is True
        assert dispatcher._meets_threshold("medium") is True
        assert dispatcher._meets_threshold("high") is True
        assert dispatcher._meets_threshold("critical") is True


class TestBackoffMechanism:
    """Tests for backoff/cooldown mechanisms."""

    def test_backoff_prevents_dispatch(self, mock_settings):

             """Backoff should prevent dispatches when active."""
        mock_settings.SECURITY_ALERT_BACKOFF_SECONDS = 60
        dispatcher = SecurityAlertDispatcher(settings=mock_settings)

        # Set backoff for file sink
        now = datetime.now(timezone.utc)
        dispatcher._sink_backoff["file"] = now + timedelta(seconds=60)

        # Check if backoff is active
        is_backed_off = dispatcher._sink_in_backoff("file", now)
        assert is_backed_off is True

    def test_backoff_expires(self, mock_settings):

             """Backoff should expire after configured duration."""
        mock_settings.SECURITY_ALERT_BACKOFF_SECONDS = 1
        dispatcher = SecurityAlertDispatcher(settings=mock_settings)

        # Set backoff in the past
        dispatcher._sink_backoff["file"] = datetime.now(timezone.utc) - timedelta(seconds=10)

        # Backoff should have expired
        now = datetime.now(timezone.utc)
        is_backed_off = dispatcher._sink_in_backoff("file", now)
        assert is_backed_off is False

    def test_set_and_clear_backoff(self, mock_settings):

             """Backoff should be settable and clearable."""
        mock_settings.SECURITY_ALERT_BACKOFF_SECONDS = 60
        dispatcher = SecurityAlertDispatcher(settings=mock_settings)

        now = datetime.now(timezone.utc)

        # Initially no backoff
        assert "file" not in dispatcher._sink_backoff or dispatcher._sink_backoff.get("file") is None

        # Set backoff
        dispatcher._set_backoff("file", now)
        assert "file" in dispatcher._sink_backoff

        # Clear backoff
        dispatcher._clear_backoff("file")
        assert "file" not in dispatcher._sink_backoff


class TestDispatcherStatus:
    """Tests for dispatcher status reporting."""

    def test_status_reports_enabled(self, dispatcher):

             """Status should report enabled state."""
        # The dispatcher object should have enabled attribute
        assert hasattr(dispatcher, "enabled")
        assert dispatcher.enabled is True

    def test_dispatcher_has_dispatch_count(self, dispatcher):

             """Dispatcher should track dispatch count."""
        assert hasattr(dispatcher, "_dispatch_count")
        assert dispatcher._dispatch_count == 0


class TestDispatchIntegration:
    """Integration tests for alert dispatch."""

    @pytest.mark.asyncio
    async def test_dispatch_returns_false_when_disabled(self, mock_settings):
        """Dispatch should return False when alerting is disabled."""
        mock_settings.SECURITY_ALERTS_ENABLED = False
        dispatcher = SecurityAlertDispatcher(settings=mock_settings)

        result = await dispatcher.dispatch(
            subject="Test Alert",
            message="This is a test",
            severity="high"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_dispatch_returns_false_below_threshold(self, mock_settings):
        """Dispatch should return False when severity below threshold."""
        mock_settings.SECURITY_ALERT_MIN_SEVERITY = "high"
        dispatcher = SecurityAlertDispatcher(settings=mock_settings)

        result = await dispatcher.dispatch(
            subject="Test Alert",
            message="This is a test",
            severity="low"
        )
        assert result is False
