"""Tests for trial management service."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tldw_Server_API.app.services.trial_management_service import TrialManagementService


@pytest.fixture()
def svc():
    return TrialManagementService()


class TestCalculateTrialExpiry:
    def test_default_14_days(self, svc: TrialManagementService):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        expiry = svc.calculate_trial_expiry(start)
        assert expiry == datetime(2026, 1, 15, tzinfo=timezone.utc)

    def test_custom_duration(self, monkeypatch):
        monkeypatch.setenv("TRIAL_DURATION_DAYS", "30")
        svc = TrialManagementService()
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        expiry = svc.calculate_trial_expiry(start)
        assert expiry == datetime(2026, 1, 31, tzinfo=timezone.utc)

    def test_defaults_to_now(self, svc: TrialManagementService):
        before = datetime.now(timezone.utc)
        expiry = svc.calculate_trial_expiry()
        after = datetime.now(timezone.utc)
        assert before + timedelta(days=14) <= expiry <= after + timedelta(days=14)


class TestIsTrialExpired:
    def test_not_expired(self, svc: TrialManagementService):
        future = datetime.now(timezone.utc) + timedelta(days=5)
        assert svc.is_trial_expired(future) is False

    def test_expired(self, svc: TrialManagementService):
        past = datetime.now(timezone.utc) - timedelta(days=1)
        assert svc.is_trial_expired(past) is True

    def test_naive_datetime_treated_as_utc(self, svc: TrialManagementService):
        past = datetime.utcnow() - timedelta(days=1)
        assert svc.is_trial_expired(past) is True


class TestGetTrialStatus:
    def test_no_trial(self, svc: TrialManagementService):
        result = svc.get_trial_status({})
        assert result["in_trial"] is False
        assert result["reason"] == "no_trial"

    def test_active_trial(self, svc: TrialManagementService):
        future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        result = svc.get_trial_status({"trial_ends_at": future})
        assert result["in_trial"] is True
        assert result["expired"] is False
        assert result["days_remaining"] >= 6

    def test_expired_trial(self, svc: TrialManagementService):
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        result = svc.get_trial_status({"trial_ends_at": past})
        assert result["in_trial"] is False
        assert result["expired"] is True
        assert result["days_remaining"] == 0

    def test_trial_with_datetime_object(self, svc: TrialManagementService):
        future = datetime.now(timezone.utc) + timedelta(days=3)
        result = svc.get_trial_status({"trial_ends_at": future})
        assert result["in_trial"] is True
