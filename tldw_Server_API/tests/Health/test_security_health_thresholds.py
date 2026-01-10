import os
from fastapi.testclient import TestClient


def _monkeypatch_audit_summary(monkeypatch, high_risk: int, failures: int):
    from tldw_Server_API.app.api.v1.endpoints import health as health_mod

    class _DummyAudit:
        async def initialize(self):
            return None

        async def get_security_summary(self, hours=24):
            return {
                "high_risk_events": high_risk,
                "failure_events": failures,
                "unique_security_users": 1,
                "top_failing_ips": ["1.2.3.4"],
                "total_events": high_risk + failures,
            }

    monkeypatch.setattr(health_mod, "UnifiedAuditService", lambda: _DummyAudit())


def _get_client(monkeypatch, env: dict):
    # Ensure test-friendly startup
    for k, v in {"TEST_MODE": "true"}.items():
        monkeypatch.setenv(k, v)
    for k, v in env.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, str(v))

    from tldw_Server_API.app.main import app
    return TestClient(app)


def test_security_critical_when_high_risk_meets_threshold(monkeypatch):
    # Configure thresholds
    client = _get_client(monkeypatch, {
        "AUDIT_SEC_CRITICAL_HIGH_RISK_MIN": 3,
        "AUDIT_SEC_ELEVATED_FAILURE_MIN": 10,
    })
    _monkeypatch_audit_summary(monkeypatch, high_risk=3, failures=0)

    r = client.get("/api/v1/health/security")
    assert r.status_code == 200 or r.status_code == 503 or r.status_code == 206
    data = r.json()
    assert data["risk_level"] == "critical"
    assert data["status"] == "at_risk"


def test_security_elevated_when_failures_meet_threshold(monkeypatch):
    client = _get_client(monkeypatch, {
        "AUDIT_SEC_CRITICAL_HIGH_RISK_MIN": 5,
        "AUDIT_SEC_ELEVATED_FAILURE_MIN": 7,
    })
    _monkeypatch_audit_summary(monkeypatch, high_risk=0, failures=7)

    r = client.get("/api/v1/health/security")
    data = r.json()
    assert data["risk_level"] == "high"
    assert data["status"] == "elevated"


def test_security_low_when_some_failures_below_threshold(monkeypatch):
    client = _get_client(monkeypatch, {
        "AUDIT_SEC_CRITICAL_HIGH_RISK_MIN": 2,
        "AUDIT_SEC_ELEVATED_FAILURE_MIN": 10,
    })
    _monkeypatch_audit_summary(monkeypatch, high_risk=0, failures=1)

    r = client.get("/api/v1/health/security")
    data = r.json()
    assert data["risk_level"] == "low"
    assert data["status"] == "secure"
