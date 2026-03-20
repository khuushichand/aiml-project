"""Tests for GDPR consent record management."""
from __future__ import annotations

import os
import tempfile

import pytest

from tldw_Server_API.app.core.AuthNZ.consent_manager import ConsentManager


@pytest.fixture()
def consent_db(tmp_path):
    """Provide a ConsentManager backed by a temporary SQLite database."""
    db_path = str(tmp_path / "consent_test.db")
    return ConsentManager(db_path)


class TestGrantConsent:
    def test_grant_returns_record(self, consent_db: ConsentManager):
        result = consent_db.grant_consent(1, "analytics")
        assert result["user_id"] == 1
        assert result["purpose"] == "analytics"
        assert "granted_at" in result

    def test_grant_with_metadata(self, consent_db: ConsentManager):
        result = consent_db.grant_consent(
            1, "marketing", ip_address="127.0.0.1", user_agent="TestBot/1.0"
        )
        assert result["user_id"] == 1
        assert result["purpose"] == "marketing"

    def test_grant_replaces_withdrawn(self, consent_db: ConsentManager):
        consent_db.grant_consent(1, "analytics")
        consent_db.withdraw_consent(1, "analytics")
        assert not consent_db.check_consent(1, "analytics")

        consent_db.grant_consent(1, "analytics")
        assert consent_db.check_consent(1, "analytics")

    def test_grant_multiple_purposes(self, consent_db: ConsentManager):
        consent_db.grant_consent(1, "analytics")
        consent_db.grant_consent(1, "marketing")
        consents = consent_db.get_user_consents(1)
        assert len(consents) == 2


class TestWithdrawConsent:
    def test_withdraw_active_consent(self, consent_db: ConsentManager):
        consent_db.grant_consent(1, "analytics")
        result = consent_db.withdraw_consent(1, "analytics")
        assert result is not None
        assert result["user_id"] == 1
        assert result["purpose"] == "analytics"
        assert "withdrawn_at" in result

    def test_withdraw_nonexistent_returns_none(self, consent_db: ConsentManager):
        result = consent_db.withdraw_consent(1, "nonexistent")
        assert result is None

    def test_withdraw_already_withdrawn_returns_none(self, consent_db: ConsentManager):
        consent_db.grant_consent(1, "analytics")
        consent_db.withdraw_consent(1, "analytics")
        result = consent_db.withdraw_consent(1, "analytics")
        assert result is None


class TestCheckConsent:
    def test_check_active_consent(self, consent_db: ConsentManager):
        consent_db.grant_consent(1, "analytics")
        assert consent_db.check_consent(1, "analytics") is True

    def test_check_withdrawn_consent(self, consent_db: ConsentManager):
        consent_db.grant_consent(1, "analytics")
        consent_db.withdraw_consent(1, "analytics")
        assert consent_db.check_consent(1, "analytics") is False

    def test_check_no_consent(self, consent_db: ConsentManager):
        assert consent_db.check_consent(1, "analytics") is False

    def test_check_different_user(self, consent_db: ConsentManager):
        consent_db.grant_consent(1, "analytics")
        assert consent_db.check_consent(2, "analytics") is False


class TestGetUserConsents:
    def test_get_empty(self, consent_db: ConsentManager):
        result = consent_db.get_user_consents(999)
        assert result == []

    def test_get_returns_all_records(self, consent_db: ConsentManager):
        consent_db.grant_consent(1, "analytics")
        consent_db.grant_consent(1, "marketing")
        records = consent_db.get_user_consents(1)
        assert len(records) == 2
        purposes = {r["purpose"] for r in records}
        assert purposes == {"analytics", "marketing"}

    def test_get_includes_withdrawn(self, consent_db: ConsentManager):
        consent_db.grant_consent(1, "analytics")
        consent_db.withdraw_consent(1, "analytics")
        records = consent_db.get_user_consents(1)
        assert len(records) == 1
        assert records[0]["withdrawn_at"] is not None

    def test_get_does_not_return_other_users(self, consent_db: ConsentManager):
        consent_db.grant_consent(1, "analytics")
        consent_db.grant_consent(2, "analytics")
        records = consent_db.get_user_consents(1)
        assert len(records) == 1
        assert records[0]["user_id"] == 1


class TestSchemaIdempotent:
    def test_create_manager_twice_same_db(self, tmp_path):
        db_path = str(tmp_path / "consent.db")
        mgr1 = ConsentManager(db_path)
        mgr1.grant_consent(1, "analytics")
        mgr2 = ConsentManager(db_path)
        assert mgr2.check_consent(1, "analytics") is True
