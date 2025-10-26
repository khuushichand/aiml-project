import pytest


def _sample_api_key():
    # 34+ chars to satisfy pattern, prefixed by sk_
    return "sk_abcdefghijklmnopqrstuvwxyzABCDEF1234567890"


def _sample_iban():
    # Valid IBAN-like string matching pattern (example GB format)
    return "GB82WEST12345698765432"


class TestPIIPatternGroups:
    def test_api_key_detection_returns_full_match(self):
        from tldw_Server_API.app.core.Audit.unified_audit_service import PIIDetector

        key = _sample_api_key()
        text = f"my key: {key} in payload"
        det = PIIDetector()
        found = det.detect(text)
        assert "api_key" in found
        # ensure the full token is captured, not just the prefix
        assert key in found["api_key"][0]

        red = det.redact(text)
        assert key not in red
        assert "[API_KEY_REDACTED]" in red

    def test_iban_detection_returns_full_match(self):
        from tldw_Server_API.app.core.Audit.unified_audit_service import PIIDetector

        iban = _sample_iban()
        text = f"iban={iban}"
        det = PIIDetector()
        found = det.detect(text)
        assert "iban" in found
        # ensure the entire IBAN is captured
        assert iban in found["iban"][0]

        red = det.redact(text)
        assert iban not in red
        assert "[IBAN_REDACTED]" in red

    def test_email_regex_tightened(self):
        from tldw_Server_API.app.core.Audit.unified_audit_service import PIIDetector

        det = PIIDetector()
        valid = "user.name+tag@example-DOMAIN.com"
        invalid = "user@example.c|m"  # '|' should not be accepted in TLD

        found_valid = det.detect(valid)
        found_invalid = det.detect(invalid)

        assert "email" in found_valid
        assert "email" not in found_invalid


class TestRiskTuning:
    def test_action_bonus_for_sla_breached(self):
        from tldw_Server_API.app.core.Audit.unified_audit_service import RiskScorer, AuditEvent, AuditEventType

        event = AuditEvent(
            event_type=AuditEventType.SECURITY_VIOLATION,
            action="sla_breached",
            result="failure",
        )
        score = RiskScorer().calculate_risk_score(event)
        # Base: 50 (security violation) + 20 (failure) + 10 (action bonus)
        assert score >= 80

    def test_action_bonus_overrides_from_settings(self, monkeypatch):
        # Ensure settings-driven overrides are applied by RiskScorer
        from tldw_Server_API.app.core.config import settings
        from tldw_Server_API.app.core.Audit.unified_audit_service import RiskScorer, AuditEvent, AuditEventType

        # Override action bonus for a custom action
        settings["AUDIT_ACTION_RISK_BONUS"] = {"custom_action": 37}

        # Midday weekday to avoid after-hours/weekend additions
        from datetime import datetime, timezone
        event = AuditEvent(
            event_type=AuditEventType.DATA_READ,
            action="custom_action",
            timestamp=datetime(2024, 1, 3, 12, 0, 0, tzinfo=timezone.utc),
        )
        scorer = RiskScorer()
        score = scorer.calculate_risk_score(event)
        assert score >= 37
