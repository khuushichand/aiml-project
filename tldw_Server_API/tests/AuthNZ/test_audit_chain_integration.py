"""
Tests for audit hash chain integration with UnifiedAuditService.

Verifies that:
- Events flushed to DB include computed chain_hash values
- Chain hashes form a valid verifiable chain
- The chain continues across multiple flush batches
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

import aiosqlite
import pytest

from tldw_Server_API.app.core.AuthNZ.audit_integrity import verify_audit_chain
from tldw_Server_API.app.core.Audit.unified_audit_service import (
    AuditContext,
    AuditEvent,
    AuditEventType,
    UnifiedAuditService,
)

_T = TypeVar("_T")


@pytest.fixture
def audit_db_path(tmp_path):
    """Return path for a temporary audit database."""
    return str(tmp_path / "audit_chain_test.db")


@pytest.fixture
def event_loop():
    """Provide a fresh event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def _run(coro: Awaitable[_T], loop: asyncio.AbstractEventLoop) -> _T:
    """Helper to run a coroutine synchronously."""
    return loop.run_until_complete(coro)


class TestAuditChainIntegration:
    """Verify chain_hash is populated when events are flushed."""

    def test_chain_hash_populated_after_flush(self, audit_db_path, event_loop, monkeypatch):
        monkeypatch.setenv("TEST_MODE", "true")

        async def _test():
            service = UnifiedAuditService(
                db_path=audit_db_path,
                enable_pii_detection=False,
                enable_risk_scoring=False,
                buffer_size=100,
            )
            await service.initialize(start_background_tasks=False)

            # Log two events
            await service.log_event(
                AuditEventType.AUTH_LOGIN_SUCCESS,
                context=AuditContext(user_id="1"),
                action="login",
            )
            await service.log_event(
                AuditEventType.DATA_EXPORT,
                context=AuditContext(user_id="1"),
                action="export",
            )

            # Force flush
            await service.flush()

            # Read events from DB and check chain_hash
            async with aiosqlite.connect(audit_db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM audit_events ORDER BY timestamp ASC"
                ) as cur:
                    rows = [dict(r) for r in await cur.fetchall()]

            assert len(rows) == 2
            for row in rows:
                assert row.get("chain_hash"), f"chain_hash missing on event {row['event_id']}"
                assert len(row["chain_hash"]) == 64  # SHA-256 hex

            await service.stop()

        _run(_test(), event_loop)

    def test_chain_is_verifiable(self, audit_db_path, event_loop, monkeypatch):
        monkeypatch.setenv("TEST_MODE", "true")

        async def _test():
            service = UnifiedAuditService(
                db_path=audit_db_path,
                enable_pii_detection=False,
                enable_risk_scoring=False,
                buffer_size=100,
            )
            await service.initialize(start_background_tasks=False)

            # Log several events
            for i in range(5):
                await service.log_event(
                    AuditEventType.AUTH_LOGIN_SUCCESS,
                    context=AuditContext(user_id=str(i)),
                    action=f"action_{i}",
                )

            await service.flush()

            # Read events and verify chain
            async with aiosqlite.connect(audit_db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM audit_events ORDER BY timestamp ASC"
                ) as cur:
                    rows = [dict(r) for r in await cur.fetchall()]

            # Build verification events from stored data
            verify_events = [
                {
                    "action": row.get("action", ""),
                    "user_id": row.get("context_user_id"),
                    "timestamp": row.get("timestamp", ""),
                    "detail": row.get("event_type", ""),
                    "chain_hash": row.get("chain_hash", ""),
                }
                for row in rows
            ]

            result = verify_audit_chain(verify_events)
            assert result["valid"] is True
            assert result["checked"] == 5

            await service.stop()

        _run(_test(), event_loop)

    def test_chain_continues_across_flushes(self, audit_db_path, event_loop, monkeypatch):
        monkeypatch.setenv("TEST_MODE", "true")

        async def _test():
            service = UnifiedAuditService(
                db_path=audit_db_path,
                enable_pii_detection=False,
                enable_risk_scoring=False,
                buffer_size=100,
            )
            await service.initialize(start_background_tasks=False)

            # First batch
            await service.log_event(
                AuditEventType.AUTH_LOGIN_SUCCESS,
                context=AuditContext(user_id="1"),
                action="login",
            )
            await service.flush()

            # Second batch
            await service.log_event(
                AuditEventType.DATA_EXPORT,
                context=AuditContext(user_id="1"),
                action="export",
            )
            await service.flush()

            # Read all events
            async with aiosqlite.connect(audit_db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM audit_events ORDER BY timestamp ASC"
                ) as cur:
                    rows = [dict(r) for r in await cur.fetchall()]

            assert len(rows) == 2
            # Second event's chain_hash should differ from first (it chains)
            assert rows[0]["chain_hash"] != rows[1]["chain_hash"]
            # Both should be valid SHA-256
            assert len(rows[0]["chain_hash"]) == 64
            assert len(rows[1]["chain_hash"]) == 64

            await service.stop()

        _run(_test(), event_loop)

    def test_chain_survives_service_restart(self, audit_db_path, event_loop, monkeypatch):
        monkeypatch.setenv("TEST_MODE", "true")

        async def _test():
            service = UnifiedAuditService(
                db_path=audit_db_path,
                enable_pii_detection=False,
                enable_risk_scoring=False,
                buffer_size=100,
            )
            await service.initialize(start_background_tasks=False)
            await service.log_event(
                AuditEventType.AUTH_LOGIN_SUCCESS,
                context=AuditContext(user_id="1"),
                action="login",
            )
            await service.flush()
            await service.stop()

            restarted = UnifiedAuditService(
                db_path=audit_db_path,
                enable_pii_detection=False,
                enable_risk_scoring=False,
                buffer_size=100,
            )
            await restarted.initialize(start_background_tasks=False)
            await restarted.log_event(
                AuditEventType.DATA_EXPORT,
                context=AuditContext(user_id="1"),
                action="export",
            )
            await restarted.flush()

            async with aiosqlite.connect(audit_db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT action, context_user_id, timestamp, event_type, chain_hash "
                    "FROM audit_events ORDER BY timestamp ASC, event_id ASC"
                ) as cur:
                    rows = [dict(r) for r in await cur.fetchall()]

            verify_events = [
                {
                    "action": row.get("action", ""),
                    "user_id": row.get("context_user_id"),
                    "timestamp": row.get("timestamp", ""),
                    "detail": row.get("event_type", ""),
                    "chain_hash": row.get("chain_hash", ""),
                }
                for row in rows
            ]

            result = verify_audit_chain(verify_events)
            assert result["valid"] is True
            assert result["checked"] == 2

            await restarted.stop()

        _run(_test(), event_loop)
