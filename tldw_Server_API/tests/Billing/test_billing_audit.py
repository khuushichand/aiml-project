"""Tests for billing event audit trail."""
from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Billing.billing_audit import BillingAuditLogger


@pytest.fixture()
def audit_logger(tmp_path):
    db_path = str(tmp_path / "billing_audit_test.db")
    return BillingAuditLogger(db_path)


class TestLogEvent:
    def test_returns_row_id(self, audit_logger: BillingAuditLogger):
        row_id = audit_logger.log_event("subscription.created", user_id=1)
        assert isinstance(row_id, int)
        assert row_id >= 1

    def test_increments_row_id(self, audit_logger: BillingAuditLogger):
        id1 = audit_logger.log_event("subscription.created", user_id=1)
        id2 = audit_logger.log_event("invoice.paid", user_id=1)
        assert id2 > id1

    def test_with_all_fields(self, audit_logger: BillingAuditLogger):
        row_id = audit_logger.log_event(
            "invoice.paid",
            user_id=42,
            amount_cents=9900,
            currency="eur",
            description="Monthly plan",
            stripe_event_id="evt_abc123",
            metadata={"plan": "pro"},
        )
        events = audit_logger.query_events(user_id=42)
        assert len(events) == 1
        event = events[0]
        assert event["event_type"] == "invoice.paid"
        assert event["amount_cents"] == 9900
        assert event["currency"] == "eur"
        assert event["stripe_event_id"] == "evt_abc123"
        assert '"plan"' in event["metadata"]


class TestQueryEvents:
    def test_empty_table(self, audit_logger: BillingAuditLogger):
        assert audit_logger.query_events() == []

    def test_filter_by_user_id(self, audit_logger: BillingAuditLogger):
        audit_logger.log_event("sub.created", user_id=1)
        audit_logger.log_event("sub.created", user_id=2)
        events = audit_logger.query_events(user_id=1)
        assert len(events) == 1
        assert events[0]["user_id"] == 1

    def test_filter_by_event_type(self, audit_logger: BillingAuditLogger):
        audit_logger.log_event("sub.created", user_id=1)
        audit_logger.log_event("invoice.paid", user_id=1)
        events = audit_logger.query_events(event_type="invoice.paid")
        assert len(events) == 1
        assert events[0]["event_type"] == "invoice.paid"

    def test_pagination(self, audit_logger: BillingAuditLogger):
        for i in range(5):
            audit_logger.log_event(f"event_{i}", user_id=1)
        page1 = audit_logger.query_events(limit=2, offset=0)
        page2 = audit_logger.query_events(limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        # No overlap
        ids1 = {e["id"] for e in page1}
        ids2 = {e["id"] for e in page2}
        assert ids1.isdisjoint(ids2)

    def test_newest_first_ordering(self, audit_logger: BillingAuditLogger):
        audit_logger.log_event("first", user_id=1)
        audit_logger.log_event("second", user_id=1)
        events = audit_logger.query_events()
        assert events[0]["event_type"] == "second"
        assert events[1]["event_type"] == "first"


class TestSchemaIdempotent:
    def test_create_logger_twice_same_db(self, tmp_path):
        db_path = str(tmp_path / "billing.db")
        logger1 = BillingAuditLogger(db_path)
        logger1.log_event("test", user_id=1)
        logger2 = BillingAuditLogger(db_path)
        assert len(logger2.query_events()) == 1
