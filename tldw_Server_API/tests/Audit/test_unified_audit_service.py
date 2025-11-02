"""
Test suite for the unified audit service.

This replaces the old test_audit_improvements.py file and focuses only on
testing the new unified audit service without references to deprecated modules.
"""

import asyncio
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import aiosqlite

from tldw_Server_API.app.core.Audit.unified_audit_service import (
    UnifiedAuditService,
    AuditEvent,
    AuditContext,
    AuditEventType,
    AuditEventCategory,
    AuditSeverity,
    PIIDetector,
    RiskScorer,
    audit_operation,
    get_unified_audit_service,
    shutdown_audit_service
)


# ============================================================================
# Test Fixtures
# ============================================================================

import pytest_asyncio

@pytest_asyncio.fixture
async def temp_db_path():
    """Create temporary database path"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest_asyncio.fixture
async def audit_service(temp_db_path):
    """Create audit service instance"""
    service = UnifiedAuditService(
        db_path=temp_db_path,
        retention_days=7,
        enable_pii_detection=True,
        enable_risk_scoring=True,
        buffer_size=10,
        flush_interval=1.0
    )
    await service.initialize()
    yield service
    await service.stop()


# ============================================================================
# Test PII Detection
# ============================================================================

class TestPIIDetection:
    """Test PII detection functionality"""

    def test_detect_various_pii(self):
        """Test detection of various PII types"""
        detector = PIIDetector()

        test_text = """
        SSN: 123-45-6789
        Credit Card: 4111-1111-1111-1111
        Email: john.doe@example.com
        Phone: (555) 123-4567
        IP: 192.168.1.1
        API Key: sk_abcdefghijklmnopqrstuvwxyzABCDEF1234567890
        """

        found_pii = detector.detect(test_text)

        assert "ssn" in found_pii
        assert "credit_card" in found_pii
        assert "email" in found_pii
        assert "phone" in found_pii
        assert "ip_address" in found_pii
        assert "api_key" in found_pii

    def test_redact_pii(self):
        """Test PII redaction"""
        detector = PIIDetector()

        text = "My SSN is 123-45-6789 and email is test@example.com"
        redacted = detector.redact(text)

        assert "123-45-6789" not in redacted
        assert "[SSN_REDACTED]" in redacted
        assert "test@example.com" not in redacted
        assert "[EMAIL_REDACTED]" in redacted

    def test_jwt_token_detection(self):
        """Test JWT token detection"""
        detector = PIIDetector()

        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        text = f"Token: {jwt}"

        found_pii = detector.detect(text)
        assert "jwt_token" in found_pii

        redacted = detector.redact(text)
        assert jwt not in redacted
        assert "[JWT_TOKEN_REDACTED]" in redacted

    @pytest.mark.asyncio
    async def test_recursive_redaction_in_structures(self, audit_service):
        """PII is redacted recursively in dicts/lists without breaking structure."""
        context = AuditContext(user_id="nested_user")
        api_key = "sk_abcdefghijklmnopqrstuvwxyzABCDEF1234567890"
        card = "4111-1111-1111-1111"
        phone = "(555) 321-9876"
        metadata = {
            "profile": {"email": "user@example.com", "phones": [phone]},
            "secrets": [api_key],
            "note": f"test card {card}"
        }
        await audit_service.log_event(
            event_type=AuditEventType.DATA_WRITE,
            context=context,
            metadata=metadata,
        )
        await audit_service.flush()
        events = await audit_service.query_events(user_id="nested_user")
        assert events, "No audit events returned"
        event = events[0]
        red_meta = json.loads(event["metadata"]) if isinstance(event["metadata"], str) else event["metadata"]
        # Ensure structure preserved and values redacted
        assert "profile" in red_meta and isinstance(red_meta["profile"], dict)
        assert red_meta["profile"]["email"] == "[EMAIL_REDACTED]"
        assert "[PHONE_REDACTED]" in red_meta["profile"]["phones"][0]
        # API key and card redacted somewhere in metadata
        stringified = json.dumps(red_meta)
        assert api_key not in stringified
        assert card not in stringified


# ============================================================================
# Test Risk Scoring
# ============================================================================

class TestRiskScoring:
    """Test risk scoring functionality"""

    def test_high_risk_events(self):
        """Test scoring of high-risk events"""
        scorer = RiskScorer()

        event = AuditEvent(
            event_type=AuditEventType.SECURITY_VIOLATION,
            action="unauthorized_access",
            result="failure"
        )

        score = scorer.calculate_risk_score(event)
        assert score >= 70  # High risk

    def test_after_hours_activity(self):
        """Test after-hours risk scoring"""
        scorer = RiskScorer()

        # Create event at 3 AM
        event = AuditEvent(
            event_type=AuditEventType.DATA_READ,
            timestamp=datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc)
        )

        score = scorer.calculate_risk_score(event)
        assert score > 0  # Should have some risk due to time

    def test_high_risk_operations(self):
        """Test detection of high-risk operations"""
        scorer = RiskScorer()

        event = AuditEvent(
            event_type=AuditEventType.DATA_DELETE,
            action="delete_user_data"
        )

        score = scorer.calculate_risk_score(event)
        assert score >= 30  # Should be elevated risk

    def test_weekend_activity(self):
        """Test weekend risk scoring"""
        scorer = RiskScorer()

        # Create event on Saturday
        saturday = datetime(2024, 1, 6, 12, 0, 0, tzinfo=timezone.utc)  # Jan 6, 2024 is Saturday
        event = AuditEvent(
            event_type=AuditEventType.CONFIG_CHANGED,
            timestamp=saturday
        )

        score = scorer.calculate_risk_score(event)
        assert score >= 35  # CONFIG_CHANGED (30) + weekend (5)

    def test_consecutive_failures(self):
        """Test risk scoring with consecutive failures"""
        scorer = RiskScorer()

        event = AuditEvent(
            event_type=AuditEventType.AUTH_LOGIN_FAILURE,
            result="failure",
            metadata={"consecutive_failures": 5}
        )

        score = scorer.calculate_risk_score(event)
        assert score >= 70  # AUTH_LOGIN_FAILURE (30) + failure (20) + consecutive_failures (20)

    def test_consecutive_failures_with_string_metadata(self):
        """Risk scoring should tolerate string JSON metadata."""
        scorer = RiskScorer()
        metadata = json.dumps({"consecutive_failures": 4})
        event = AuditEvent(
            event_type=AuditEventType.AUTH_LOGIN_FAILURE,
            result="failure",
            metadata=metadata,
        )

        score = scorer.calculate_risk_score(event)
        assert score >= 70


# ============================================================================
# Test Unified Audit Service
# ============================================================================

class TestUnifiedAuditService:
    """Test unified audit service functionality"""

    @pytest.mark.asyncio
    async def test_service_initialization(self, audit_service):
        """Test service initializes correctly"""
        assert audit_service.db_path.exists()

        # Check database schema
        async with aiosqlite.connect(audit_service.db_path) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = await cursor.fetchall()
            table_names = [row[0] for row in tables]

            assert "audit_events" in table_names
            assert "audit_daily_stats" in table_names

    @pytest.mark.asyncio
    async def test_log_event(self, audit_service):
        """Test logging an event"""
        context = AuditContext(
            user_id="test_user",
            ip_address="192.168.1.1"
        )

        event_id = await audit_service.log_event(
            event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
            context=context,
            metadata={"browser": "Chrome"}
        )

        assert event_id is not None
        assert audit_service.stats["events_logged"] == 1

    @pytest.mark.asyncio
    async def test_event_buffering_and_flush(self, audit_service):
        """Test event buffering and flushing"""
        # Log multiple events
        for i in range(5):
            await audit_service.log_event(
                event_type=AuditEventType.DATA_READ,
                context=AuditContext(user_id=f"user_{i}")
            )

        assert len(audit_service.event_buffer) == 5

        # Force flush
        await audit_service.flush()

        assert len(audit_service.event_buffer) == 0
        assert audit_service.stats["events_flushed"] == 5

    @pytest.mark.asyncio
    async def test_auto_flush_on_buffer_full(self, audit_service):
        """Test automatic flush when buffer is full"""
        # Buffer size is 10 in fixture
        for i in range(12):
            await audit_service.log_event(
                event_type=AuditEventType.DATA_READ,
                context=AuditContext(user_id=f"user_{i}")
            )

        # Wait for async flush
        await asyncio.sleep(0.5)

        # Buffer should have been flushed at 10 events
        assert len(audit_service.event_buffer) < 10

    @pytest.mark.asyncio
    async def test_log_event_allows_string_metadata(self, audit_service):
        """Logging with string metadata should not crash risk scoring."""
        context = AuditContext(user_id="string_meta_user")
        await audit_service.log_event(
            event_type=AuditEventType.AUTH_LOGIN_FAILURE,
            context=context,
            metadata="plain string metadata",
            result="failure",
        )
        await audit_service.flush()
        events = await audit_service.query_events(user_id="string_meta_user")
        assert events

    @pytest.mark.asyncio
    async def test_pii_detection_in_metadata(self, audit_service):
        """Test PII detection in event metadata"""
        context = AuditContext(user_id="test_user")

        await audit_service.log_event(
            event_type=AuditEventType.DATA_WRITE,
            context=context,
            metadata={
                "email": "user@example.com",
                "ssn": "123-45-6789"
            }
        )

        # Flush to database
        await audit_service.flush()

        # Query event
        events = await audit_service.query_events(user_id="test_user")
        assert len(events) > 0

        event = events[0]
        assert event["pii_detected"] == 1

        # Check metadata was redacted
        metadata = json.loads(event["metadata"])
        assert "user@example.com" not in str(metadata)
        assert "123-45-6789" not in str(metadata)

    @pytest.mark.asyncio
    async def test_pii_detection_in_non_metadata_fields(self, audit_service):
        """PII in action/resource_id/user_agent gets redacted and sets flag."""
        context = AuditContext(user_id="pii_user", user_agent="sk_abcdefghijklmnopqrstuvwxyzABCDEF1234567890")
        action = "delete account for john.doe@example.com"
        resource_id = "order-4111-1111-1111-1111"
        await audit_service.log_event(
            event_type=AuditEventType.DATA_DELETE,
            context=context,
            action=action,
            resource_id=resource_id,
            error_message="User reported api_key=sk_abcdefghijklmnopqrstuvwxyzABCDEF1234567890",
        )
        await audit_service.flush()
        events = await audit_service.query_events(user_id="pii_user")
        assert events
        e = events[0]
        # pii_detected flag set
        assert e.get("pii_detected") == 1
        # Redactions occurred
        assert "[EMAIL_REDACTED]" in (e.get("action") or "")
        assert "[CREDIT_CARD_REDACTED]" in (e.get("resource_id") or "")
        # user_agent redacted
        assert "[API_KEY_REDACTED]" in (e.get("context_user_agent") or "")
        # error_message redacted
        assert "[API_KEY_REDACTED]" in (e.get("error_message") or "")

    @pytest.mark.asyncio
    async def test_risk_scoring(self, audit_service):
        """Test risk scoring for events"""
        # High risk event
        await audit_service.log_event(
            event_type=AuditEventType.SECURITY_VIOLATION,
            context=AuditContext(user_id="attacker"),
            result="failure"
        )

        # Check high-risk counter
        assert audit_service.stats["high_risk_events"] > 0

    @pytest.mark.asyncio
    async def test_query_events_with_filters(self, audit_service):
        """Test querying events with various filters"""
        # Log diverse events
        context1 = AuditContext(user_id="user1", request_id="req1")
        context2 = AuditContext(user_id="user2", request_id="req2")

        await audit_service.log_event(
            event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
            context=context1
        )

        await audit_service.log_event(
            event_type=AuditEventType.DATA_READ,
            context=context2
        )

        await audit_service.flush()

        # Query by user
        events = await audit_service.query_events(user_id="user1")
        assert len(events) == 1
        assert events[0]["context_user_id"] == "user1"

        # Query by event type
        events = await audit_service.query_events(
            event_types=[AuditEventType.DATA_READ]
        )
        assert len(events) == 1
        assert events[0]["event_type"] == AuditEventType.DATA_READ.value

    @pytest.mark.asyncio
    async def test_export_events_json_and_csv(self, audit_service):
        """Test exporting events to JSON and CSV formats"""
        # Log a few events
        for i in range(3):
            await audit_service.log_event(
                event_type=AuditEventType.DATA_READ,
                context=AuditContext(user_id="export_user"),
                resource_type="doc",
                resource_id=f"d{i}",
                metadata={"idx": i},
            )
        await audit_service.flush()

        # Export JSON content (no file)
        json_content = await audit_service.export_events(
            user_id="export_user",
            format="json",
        )
        data = json.loads(json_content)
        assert isinstance(data, list) and len(data) >= 3
        assert any(e.get("resource_type") == "doc" for e in data)

        # Export CSV content (no file)
        csv_content = await audit_service.export_events(
            user_id="export_user",
            format="csv",
        )
        # Expect header + at least 3 rows
        lines = [ln for ln in csv_content.splitlines() if ln.strip()]
        assert len(lines) >= 4  # header + 3 rows
        header = lines[0].split(",")
        assert "event_type" in header and "event_id" in header

    @pytest.mark.asyncio
    async def test_daily_statistics_aggregation(self, audit_service):
        """Test daily statistics are properly aggregated"""
        # Log events with metrics
        for i in range(5):
            await audit_service.log_event(
                event_type=AuditEventType.EVAL_COMPLETED,
                context=AuditContext(user_id="user1"),
                tokens_used=100,
                estimated_cost=0.01,
                duration_ms=500.0
            )

        await audit_service.flush()

        # Check daily stats
        async with aiosqlite.connect(audit_service.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM audit_daily_stats WHERE category = ?",
                (AuditEventCategory.EVALUATION.value,)
            )
            row = await cursor.fetchone()

            assert row is not None
            # Verify aggregations
            assert row[2] == 5  # total_events
            assert row[5] == 0.05  # total_cost (5 * 0.01)
            assert row[6] == 500  # total_tokens (5 * 100)

    @pytest.mark.asyncio
    async def test_cleanup_old_logs(self, audit_service):
        """Test cleanup of old audit logs"""
        # Log old event (manually set timestamp)
        old_event = AuditEvent(
            event_type=AuditEventType.DATA_READ,
            timestamp=datetime.now(timezone.utc) - timedelta(days=10)
        )

        async with audit_service.buffer_lock:
            audit_service.event_buffer.append(old_event)

        await audit_service.flush()

        # Run cleanup
        await audit_service.cleanup_old_logs()

        # Old event should be deleted
        events = await audit_service.query_events()
        for event in events:
            timestamp = datetime.fromisoformat(event["timestamp"])
            age = datetime.now(timezone.utc) - timestamp
            assert age.days < audit_service.retention_days

    @pytest.mark.asyncio
    async def test_audit_context_manager(self, audit_service):
        """Test audit operation context manager"""
        context = AuditContext(user_id="test_user")

        # Successful operation
        async with audit_operation(
            audit_service,
            AuditEventType.DATA_READ,
            context,
            resource_type="document",
            resource_id="doc123"
        ):
            # Simulate work
            await asyncio.sleep(0.1)

        await audit_service.flush()

        events = await audit_service.query_events(user_id="test_user")
        assert len(events) == 1
        assert events[0]["result"] == "success"
        assert events[0]["duration_ms"] > 0

    @pytest.mark.asyncio
    async def test_audit_context_manager_with_error(self, audit_service):
        """Test audit context manager handles errors"""
        context = AuditContext(user_id="test_user")

        # Operation that fails
        with pytest.raises(ValueError):
            async with audit_operation(
                audit_service,
                AuditEventType.DATA_WRITE,
                context,
                resource_type="document"
            ):
                raise ValueError("Test error")

        await audit_service.flush()

        events = await audit_service.query_events(user_id="test_user")
        assert len(events) == 1
        assert events[0]["result"] == "failure"
        assert "Test error" in events[0]["error_message"]

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Global audit service deprecated; use dependency injection")
    async def test_global_service_singleton(self):
        """Test global service singleton pattern"""
        service1 = await get_unified_audit_service()
        service2 = await get_unified_audit_service()

        assert service1 is service2

        await shutdown_audit_service()

    @pytest.mark.asyncio
    async def test_correlation_tracking(self, audit_service):
        """Test correlation ID tracking across events"""
        correlation_id = "corr-123"

        # Log related events
        context = AuditContext(
            user_id="user1",
            correlation_id=correlation_id
        )

        await audit_service.log_event(
            event_type=AuditEventType.API_REQUEST,
            context=context
        )

        await audit_service.log_event(
            event_type=AuditEventType.DATA_READ,
            context=context
        )

        await audit_service.log_event(
            event_type=AuditEventType.API_RESPONSE,
            context=context
        )

        await audit_service.flush()

        # Query by correlation ID
        events = await audit_service.query_events(correlation_id=correlation_id)
        assert len(events) == 3

        # All should have same correlation ID
        for event in events:
            assert event["context_correlation_id"] == correlation_id

    @pytest.mark.asyncio
    async def test_session_tracking(self, audit_service):
        """Test session ID tracking"""
        session_id = "sess-456"

        context = AuditContext(
            user_id="user1",
            session_id=session_id
        )

        # Log session events
        await audit_service.log_event(
            event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
            context=context
        )

        await audit_service.log_event(
            event_type=AuditEventType.DATA_READ,
            context=context
        )

        await audit_service.log_event(
            event_type=AuditEventType.AUTH_LOGOUT,
            context=context
        )

        await audit_service.flush()

        # Query events
        events = await audit_service.query_events(user_id="user1")

        # All should have same session ID
        for event in events:
            assert event["context_session_id"] == session_id

    @pytest.mark.asyncio
    async def test_auto_category_determination(self, audit_service):
        """Test automatic category determination from event type"""
        test_cases = [
            (AuditEventType.AUTH_LOGIN_SUCCESS, AuditEventCategory.AUTHENTICATION),
            (AuditEventType.USER_CREATED, AuditEventCategory.AUTHORIZATION),
            (AuditEventType.DATA_READ, AuditEventCategory.DATA_ACCESS),
            (AuditEventType.RAG_SEARCH, AuditEventCategory.RAG),
            (AuditEventType.EVAL_STARTED, AuditEventCategory.EVALUATION),
            (AuditEventType.API_REQUEST, AuditEventCategory.API_CALL),
            (AuditEventType.SECURITY_VIOLATION, AuditEventCategory.SECURITY),
            (AuditEventType.SYSTEM_START, AuditEventCategory.SYSTEM),
        ]

        for event_type, expected_category in test_cases:
            await audit_service.log_event(event_type=event_type)

        await audit_service.flush()

        events = await audit_service.query_events()

        for event, (event_type, expected_category) in zip(reversed(events), test_cases):
            assert event["category"] == expected_category.value

    @pytest.mark.asyncio
    async def test_auto_severity_determination(self, audit_service):
        """Test automatic severity determination"""
        test_cases = [
            (AuditEventType.SECURITY_VIOLATION, "success", AuditSeverity.CRITICAL),
            (AuditEventType.AUTH_LOGIN_FAILURE, "failure", AuditSeverity.WARNING),
            (AuditEventType.SYSTEM_START, "success", AuditSeverity.DEBUG),
            (AuditEventType.DATA_READ, "error", AuditSeverity.ERROR),
        ]

        for event_type, result, expected_severity in test_cases:
            await audit_service.log_event(
                event_type=event_type,
                result=result
            )

        await audit_service.flush()

        events = await audit_service.query_events()

        for event, (_, _, expected_severity) in zip(reversed(events), test_cases):
            assert event["severity"] == expected_severity.value


# ============================================================================
# Test Performance
# ============================================================================

class TestPerformance:
    """Test performance characteristics"""

    @pytest.mark.asyncio
    async def test_batch_insert_performance(self, audit_service):
        """Test batch insert is performant"""
        import time

        # Log many events
        start = time.perf_counter()

        for i in range(1000):
            await audit_service.log_event(
                event_type=AuditEventType.DATA_READ,
                context=AuditContext(user_id=f"user_{i % 10}")
            )

        await audit_service.flush()

        elapsed = time.perf_counter() - start

        # Should handle 1000 events in under 5 seconds
        assert elapsed < 5.0

        # Verify all events were stored
        assert audit_service.stats["events_flushed"] >= 1000

    @pytest.mark.asyncio
    async def test_concurrent_writes(self, audit_service):
        """Test concurrent write handling"""
        async def write_events(user_id: str, count: int):
            for i in range(count):
                await audit_service.log_event(
                    event_type=AuditEventType.DATA_WRITE,
                    context=AuditContext(user_id=user_id),
                    metadata={"index": i}
                )

        # Launch concurrent writers
        tasks = [
            write_events(f"user_{i}", 100)
            for i in range(10)
        ]

        await asyncio.gather(*tasks)
        await audit_service.flush()

        # Should have logged all events
        assert audit_service.stats["events_logged"] == 1000

    @pytest.mark.asyncio
    async def test_query_performance(self, audit_service):
        """Test query performance with indexes"""
        # Log many events
        for i in range(500):
            await audit_service.log_event(
                event_type=AuditEventType.DATA_READ,
                context=AuditContext(
                    user_id=f"user_{i % 50}",
                    request_id=f"req_{i}"
                )
            )

        await audit_service.flush()

        # Test indexed queries
        import time

        # Query by user_id (indexed)
        start = time.perf_counter()
        events = await audit_service.query_events(user_id="user_10")
        user_query_time = time.perf_counter() - start

        # Query by request_id (indexed)
        start = time.perf_counter()
        events = await audit_service.query_events(request_id="req_100")
        request_query_time = time.perf_counter() - start

        # Both should be fast due to indexes; allow margin for CI load
        assert user_query_time < 0.3
        assert request_query_time < 0.3


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Test integration scenarios"""

    @pytest.mark.asyncio
    async def test_full_audit_workflow(self, audit_service):
        """Test complete audit workflow"""
        # Simulate user session
        session_id = "session-123"
        user_id = "user-456"

        # 1. User login
        await audit_service.log_event(
            event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
            context=AuditContext(
                user_id=user_id,
                session_id=session_id,
                ip_address="192.168.1.100"
            )
        )

        # 2. User performs operations
        for i in range(5):
            await audit_service.log_event(
                event_type=AuditEventType.DATA_READ,
                context=AuditContext(
                    user_id=user_id,
                    session_id=session_id
                ),
                resource_type="document",
                resource_id=f"doc_{i}"
            )

        # 3. User modifies data
        await audit_service.log_event(
            event_type=AuditEventType.DATA_UPDATE,
            context=AuditContext(
                user_id=user_id,
                session_id=session_id
            ),
            resource_type="profile",
            resource_id=user_id,
            metadata={"fields_updated": ["email", "name"]}
        )

        # 4. User logout
        await audit_service.log_event(
            event_type=AuditEventType.AUTH_LOGOUT,
            context=AuditContext(
                user_id=user_id,
                session_id=session_id
            )
        )

        await audit_service.flush()

        # Verify complete session trail
        events = await audit_service.query_events(user_id=user_id)
        assert len(events) == 8

        # Check session consistency
        for event in events:
            assert event["context_session_id"] == session_id

        # Verify event sequence
        event_types = [e["event_type"] for e in reversed(events)]
        assert event_types[0] == AuditEventType.AUTH_LOGIN_SUCCESS.value
        assert event_types[-1] == AuditEventType.AUTH_LOGOUT.value

    @pytest.mark.asyncio
    async def test_rag_workflow_audit(self, audit_service):
        """Test RAG operation audit trail"""
        request_id = "req-789"
        correlation_id = "corr-abc"

        context = AuditContext(
            user_id="researcher",
            request_id=request_id,
            correlation_id=correlation_id
        )

        # 1. Search request
        await audit_service.log_event(
            event_type=AuditEventType.RAG_SEARCH,
            context=context,
            metadata={"query": "quantum computing basics"}
        )

        # 2. Document retrieval
        await audit_service.log_event(
            event_type=AuditEventType.RAG_RETRIEVAL,
            context=context,
            result_count=10,
            duration_ms=150
        )

        # 3. Embedding generation
        await audit_service.log_event(
            event_type=AuditEventType.RAG_EMBEDDING,
            context=context,
            tokens_used=500,
            estimated_cost=0.001
        )

        # 4. Response generation
        await audit_service.log_event(
            event_type=AuditEventType.RAG_GENERATION,
            context=context,
            tokens_used=1500,
            estimated_cost=0.03,
            duration_ms=2000
        )

        await audit_service.flush()

        # Query all related events
        events = await audit_service.query_events(correlation_id=correlation_id)
        assert len(events) == 4

        # Calculate total cost and tokens
        total_cost = sum(e["estimated_cost"] or 0 for e in events)
        total_tokens = sum(e["tokens_used"] or 0 for e in events)

        assert total_cost == pytest.approx(0.031, rel=1e-3)
        assert total_tokens == 2000

    @pytest.mark.asyncio
    async def test_security_incident_tracking(self, audit_service):
        """Test tracking of security incidents"""
        attacker_ip = "10.0.0.1"

        # Simulate attack pattern
        for i in range(10):
            context = AuditContext(
                ip_address=attacker_ip,
                user_id=f"attempt_{i}" if i < 5 else None
            )

            await audit_service.log_event(
                event_type=AuditEventType.AUTH_LOGIN_FAILURE,
                context=context,
                result="failure",
                metadata={"consecutive_failures": i + 1}
            )

        # Security violation detected
        await audit_service.log_event(
            event_type=AuditEventType.SECURITY_VIOLATION,
            context=AuditContext(ip_address=attacker_ip),
            metadata={"reason": "brute_force_detected"}
        )

        await audit_service.flush()

        # Query high-risk events
        events = await audit_service.query_events(min_risk_score=70)

        # Should have multiple high-risk events
        assert len(events) > 0

        # All should be from same IP
        for event in events:
            if event["context_ip_address"]:
                assert event["context_ip_address"] == attacker_ip


# ============================================================================
# Streaming Export Tests (CSV and JSON with file_path)
# ============================================================================

class TestStreamingExport:
    """Tests for streaming export paths when writing to files."""

    @pytest.mark.asyncio
    async def test_export_events_csv_streaming_to_file(self, audit_service, tmp_path):
        user = "csv_stream_user"
        # Log a few events for a specific user
        for i in range(3):
            await audit_service.log_event(
                event_type=AuditEventType.DATA_READ,
                context=AuditContext(user_id=user),
                resource_type="doc",
                resource_id=f"d{i}",
                metadata={"idx": i},
            )
        await audit_service.flush()

        # Export to CSV using streaming file path
        csv_path = tmp_path / "audit_stream.csv"
        count = await audit_service.export_events(
            user_id=user,
            format="csv",
            file_path=str(csv_path),
        )
        # Verify count and file content
        assert count >= 3
        content = csv_path.read_text(encoding="utf-8").splitlines()
        assert content[0].startswith("event_id,")
        # header + at least 3 rows
        assert len(content) >= 4

    @pytest.mark.asyncio
    async def test_export_events_json_streaming_to_file(self, audit_service, tmp_path):
        user = "json_stream_user"
        # Log a few events for a specific user
        for i in range(4):
            await audit_service.log_event(
                event_type=AuditEventType.DATA_WRITE,
                context=AuditContext(user_id=user),
                resource_type="note",
                resource_id=f"n{i}",
                metadata={"idx": i},
            )
        await audit_service.flush()

        # Export to JSON using streaming file path
        json_path = tmp_path / "audit_stream.json"
        count = await audit_service.export_events(
            user_id=user,
            format="json",
            file_path=str(json_path),
        )
        assert count >= 4
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) >= 4
        assert any(e.get("resource_type") == "note" for e in data)

    @pytest.mark.asyncio
    async def test_export_events_csv_streaming_large_file(self, audit_service, tmp_path):
        user = "csv_stream_many"
        total = 123
        # Generate more rows than a small chunk size to exercise chunked writes
        for i in range(total):
            await audit_service.log_event(
                event_type=AuditEventType.DATA_READ,
                context=AuditContext(user_id=user),
                resource_type="doc",
                resource_id=f"d{i}",
                metadata={"idx": i},
            )
        await audit_service.flush()

        csv_path = tmp_path / "audit_stream_large.csv"
        import time
        start = time.perf_counter()
        count = await audit_service.export_events(
            user_id=user,
            format="csv",
            file_path=str(csv_path),
            chunk_size=10,  # small chunk to force multiple iterations
        )
        elapsed = time.perf_counter() - start
        assert count == total
        lines = csv_path.read_text(encoding="utf-8").splitlines()
        # header + total rows
        assert lines[0].startswith("event_id,")
        assert len(lines) == total + 1
        # Performance bound (generous to avoid flakiness)
        assert elapsed < 1.5

    @pytest.mark.asyncio
    async def test_export_events_json_streaming_generator_large(self, audit_service):
        user = "json_stream_gen"
        total = 200
        for i in range(total):
            await audit_service.log_event(
                event_type=AuditEventType.DATA_WRITE,
                context=AuditContext(user_id=user),
                resource_type="note",
                resource_id=f"n{i}",
                metadata={"idx": i},
            )
        await audit_service.flush()

        gen = await audit_service.export_events(
            user_id=user,
            format="json",
            stream=True,
            chunk_size=25,
        )

        import time, json as _json
        start = time.perf_counter()
        chunks = []
        async for c in gen:
            chunks.append(c)
        elapsed = time.perf_counter() - start
        content = "".join(chunks)
        data = _json.loads(content)
        assert isinstance(data, list)
        assert len(data) == total
        # Performance bound (generous to avoid flakiness)
        assert elapsed < 1.5

    @pytest.mark.asyncio
    async def test_export_events_json_streaming_large_file(self, audit_service, tmp_path):
        user = "json_stream_file"
        total = 120
        for i in range(total):
            await audit_service.log_event(
                event_type=AuditEventType.DATA_READ,
                context=AuditContext(user_id=user),
                resource_type="doc",
                resource_id=f"dx{i}",
                metadata={"i": i},
            )
        await audit_service.flush()

        json_path = tmp_path / "audit_large.json"
        # Use small chunk_size to exercise multi-chunk writes
        count = await audit_service.export_events(
            user_id=user,
            format="json",
            file_path=str(json_path),
            chunk_size=15,
        )
        assert count == total
        import json as _json
        data = _json.loads(json_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == total

    @pytest.mark.asyncio
    async def test_export_events_jsonl_streaming_to_file(self, audit_service, tmp_path):
        user = "jsonl_stream_file"
        total = 25
        for i in range(total):
            await audit_service.log_event(
                event_type=AuditEventType.DATA_READ,
                context=AuditContext(user_id=user),
                resource_type="doc",
                resource_id=f"j{i}",
                metadata={"i": i},
            )
        await audit_service.flush()

        jsonl_path = tmp_path / "audit_stream.ndjson"
        count = await audit_service.export_events(
            user_id=user,
            format="jsonl",
            file_path=str(jsonl_path),
            chunk_size=7,
        )
        assert count == total
        lines = [ln for ln in jsonl_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == total
        import json as _json
        objs = [_json.loads(ln) for ln in lines]
        assert any(o.get("resource_id") == "j0" for o in objs)

    @pytest.mark.asyncio
    async def test_export_events_jsonl_streaming_max_rows(self, audit_service):
        user = "jsonl_max_rows"
        total = 60
        for i in range(total):
            await audit_service.log_event(
                event_type=AuditEventType.DATA_WRITE,
                context=AuditContext(user_id=user),
                resource_type="item",
                resource_id=f"x{i}",
                metadata={"i": i},
            )
        await audit_service.flush()

        max_rows = 25
        gen = await audit_service.export_events(
            user_id=user,
            format="jsonl",
            stream=True,
            chunk_size=9,
            max_rows=max_rows,
        )
        chunks = []
        async for c in gen:
            chunks.append(c)
        content = "".join(chunks)
        lines = [ln for ln in content.splitlines() if ln.strip()]
        assert len(lines) == max_rows
        # Ensure each line is valid JSON
        import json as _json
        for ln in lines:
            _json.loads(ln)

    async def test_audit_operation_with_start_and_completed_types(self, audit_service):
        ctx = AuditContext(user_id="ctx_op_user")
        # Use distinct start and complete event types
        async with audit_operation(
            audit_service,
            AuditEventType.DATA_READ,
            ctx,
            start_event_type=AuditEventType.API_REQUEST,
            completed_event_type=AuditEventType.API_RESPONSE,
            resource_type="document",
            resource_id="docABC",
        ):
            await asyncio.sleep(0.05)
        await audit_service.flush()
        events = await audit_service.query_events(user_id="ctx_op_user")
        assert len(events) == 2
        types = {e["event_type"] for e in events}
        assert AuditEventType.API_REQUEST.value in types
        assert AuditEventType.API_RESPONSE.value in types
        # Verify result fields
        started = next(e for e in events if e["event_type"] == AuditEventType.API_REQUEST.value)
        completed = next(e for e in events if e["event_type"] == AuditEventType.API_RESPONSE.value)
        assert started["result"] == "started"
        assert completed["result"] == "success"
        assert (completed.get("duration_ms") or 0) > 0
