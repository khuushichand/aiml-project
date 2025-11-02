import pytest


@pytest.mark.asyncio
async def test_high_risk_operations_override(monkeypatch):
    from tldw_Server_API.app.core.config import settings
    from tldw_Server_API.app.core.Audit.unified_audit_service import RiskScorer, AuditEvent, AuditEventType

    # Override high-risk ops to include a custom verb
    settings["AUDIT_HIGH_RISK_OPERATIONS"] = ["purge", "wipe"]

    event = AuditEvent(
        event_type=AuditEventType.DATA_UPDATE,
        action="PurGe_old_records",  # mixed case and contains substring
    )
    scorer = RiskScorer()
    score = scorer.calculate_risk_score(event)
    # High-risk op should contribute +30
    assert score >= 30


@pytest.mark.asyncio
async def test_suspicious_thresholds_override(monkeypatch):
    from datetime import datetime, timezone
    from tldw_Server_API.app.core.config import settings
    from tldw_Server_API.app.core.Audit.unified_audit_service import RiskScorer, AuditEvent, AuditEventType

    # Configure small thresholds and ensure after_hours is enabled
    settings["AUDIT_SUSPICIOUS_THRESHOLDS"] = {
        "data_export": 10,
        "failed_auth": 2,
        "after_hours": True,
    }

    # Midday Wednesday to avoid time-based or weekend bias
    ts = datetime(2024, 1, 3, 12, 0, 0, tzinfo=timezone.utc)

    # Data export threshold
    event = AuditEvent(
        event_type=AuditEventType.DATA_READ,
        timestamp=ts,
        result_count=11,
    )
    scorer = RiskScorer()
    score = scorer.calculate_risk_score(event)
    assert score >= 15  # export threshold contributes +15

    # Failed auth threshold (use 3 > 2)
    event2 = AuditEvent(
        event_type=AuditEventType.AUTH_LOGIN_FAILURE,
        timestamp=ts,
        result="failure",
        metadata={"consecutive_failures": 3},
    )
    score2 = scorer.calculate_risk_score(event2)
    # 30 (type) + 20 (failure) + 20 (consecutive_failures) = 70
    assert score2 >= 70
