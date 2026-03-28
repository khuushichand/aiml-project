"""Unit tests for admin_webhooks_service — HMAC signing, CRUD, delivery."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tldw_Server_API.app.services.admin_webhooks_service import (
    AdminWebhooksService,
    WebhookRecord,
    generate_signature,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# HMAC signing
# ---------------------------------------------------------------------------


def test_generate_signature_deterministic():
    sig1 = generate_signature("secret", "12345", '{"hello": "world"}')
    sig2 = generate_signature("secret", "12345", '{"hello": "world"}')
    assert sig1 == sig2
    assert sig1.startswith("v1=")


def test_generate_signature_changes_with_secret():
    sig1 = generate_signature("secret-a", "12345", "body")
    sig2 = generate_signature("secret-b", "12345", "body")
    assert sig1 != sig2


def test_generate_signature_changes_with_timestamp():
    sig1 = generate_signature("secret", "12345", "body")
    sig2 = generate_signature("secret", "99999", "body")
    assert sig1 != sig2


# ---------------------------------------------------------------------------
# Row parsing
# ---------------------------------------------------------------------------


def test_row_to_record_from_dict():
    row = {
        "id": 1,
        "url": "https://example.com/hook",
        "secret": "s3cret",
        "event_types": '["incident.created", "alert.fired"]',
        "description": "Test hook",
        "active": 1,
        "retry_count": 3,
        "timeout_seconds": 10,
        "created_by": 42,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    record = AdminWebhooksService._row_to_record(row)
    assert record.id == 1
    assert record.url == "https://example.com/hook"
    assert record.event_types == ["incident.created", "alert.fired"]
    assert record.active is True
    assert record.created_by == 42


def test_row_to_record_handles_invalid_json():
    row = {
        "id": 2,
        "url": "https://example.com/hook",
        "secret": "s3cret",
        "event_types": "NOT-JSON",
        "description": "",
        "active": 0,
        "retry_count": 1,
        "timeout_seconds": 5,
        "created_by": None,
        "created_at": None,
        "updated_at": None,
    }
    record = AdminWebhooksService._row_to_record(row)
    assert record.event_types == []
    assert record.active is False


# ---------------------------------------------------------------------------
# CRUD (with mocked pool)
# ---------------------------------------------------------------------------


def _make_pool_mock() -> MagicMock:
    """Return a mock DatabasePool with async helpers."""
    pool = MagicMock()
    pool.fetchone = AsyncMock()
    pool.fetchall = AsyncMock()
    pool.execute = AsyncMock()
    return pool


@pytest.fixture()
def svc() -> AdminWebhooksService:
    return AdminWebhooksService(db_pool=_make_pool_mock())


@pytest.mark.asyncio
async def test_create_webhook_generates_secret(svc: AdminWebhooksService):
    svc.db_pool.fetchone.return_value = {
        "id": 10,
        "url": "https://example.com/hook",
        "secret": "generated",
        "event_types": '["*"]',
        "description": "",
        "active": 1,
        "retry_count": 3,
        "timeout_seconds": 10,
        "created_by": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    record = await svc.create_webhook(url="https://example.com/hook", event_types=["*"])
    assert record.id == 10
    assert record.url == "https://example.com/hook"
    svc.db_pool.fetchone.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_webhooks(svc: AdminWebhooksService):
    svc.db_pool.fetchone.return_value = {"cnt": 2}
    svc.db_pool.fetchall.return_value = [
        {
            "id": 1, "url": "https://a.com", "secret": "s1",
            "event_types": '["*"]', "description": "", "active": 1,
            "retry_count": 3, "timeout_seconds": 10,
            "created_by": None, "created_at": None, "updated_at": None,
        },
        {
            "id": 2, "url": "https://b.com", "secret": "s2",
            "event_types": '["incident.created"]', "description": "hook 2",
            "active": 0, "retry_count": 1, "timeout_seconds": 5,
            "created_by": 1, "created_at": None, "updated_at": None,
        },
    ]
    items, total = await svc.list_webhooks(limit=10, offset=0)
    assert total == 2
    assert len(items) == 2
    assert items[1].active is False


@pytest.mark.asyncio
async def test_update_webhook_skips_none_fields(svc: AdminWebhooksService):
    svc.db_pool.fetchone.return_value = {
        "id": 1, "url": "https://updated.com", "secret": "s",
        "event_types": '["*"]', "description": "updated", "active": 1,
        "retry_count": 3, "timeout_seconds": 10,
        "created_by": None, "created_at": None, "updated_at": None,
    }
    record = await svc.update_webhook(1, url="https://updated.com", description=None)
    # description=None should leave the existing value untouched.
    call_args = svc.db_pool.execute.call_args
    params = call_args[0][1]
    assert params[2] is None


@pytest.mark.asyncio
async def test_delete_webhook(svc: AdminWebhooksService):
    result = await svc.delete_webhook(42)
    assert result is True
    svc.db_pool.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_success(svc: AdminWebhooksService):
    wh = WebhookRecord(
        id=1, url="https://example.com/hook", secret="test-secret",
        event_types=["*"], description="", active=True,
        retry_count=0, timeout_seconds=5,
        created_by=None, created_at=None, updated_at=None,
    )

    # Mock the delivery log insert
    svc.db_pool.fetchone.return_value = {
        "id": 100, "webhook_id": 1, "event_type": "test.event",
        "status_code": 200, "latency_ms": 50, "retry_attempt": 0,
        "error_message": None, "delivered_at": "2026-01-01T00:00:00Z",
        "created_at": "2026-01-01T00:00:00Z",
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "OK"

    with patch("tldw_Server_API.app.services.admin_webhooks_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        entry = await svc.deliver(wh, "test.event", {"key": "value"})
        assert entry.status_code == 200
        mock_client_cls.assert_called_once_with(timeout=5, follow_redirects=False)
        mock_client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_event_filters_by_event_type(svc: AdminWebhooksService):
    svc.db_pool.fetchone.side_effect = [
        {"cnt": 2},  # list_webhooks count
        # deliver log entry for matching webhook
        {
            "id": 1, "webhook_id": 1, "event_type": "incident.created",
            "status_code": 200, "latency_ms": 10, "retry_attempt": 0,
            "error_message": None, "delivered_at": "2026-01-01T00:00:00Z",
            "created_at": "2026-01-01T00:00:00Z",
        },
    ]
    svc.db_pool.fetchall.return_value = [
        {
            "id": 1, "url": "https://a.com", "secret": "s1",
            "event_types": '["incident.created"]', "description": "",
            "active": 1, "retry_count": 0, "timeout_seconds": 5,
            "created_by": None, "created_at": None, "updated_at": None,
        },
        {
            "id": 2, "url": "https://b.com", "secret": "s2",
            "event_types": '["alert.fired"]', "description": "",
            "active": 1, "retry_count": 0, "timeout_seconds": 5,
            "created_by": None, "created_at": None, "updated_at": None,
        },
    ]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "OK"

    with patch("tldw_Server_API.app.services.admin_webhooks_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        delivered = await svc.dispatch_event("incident.created", {"id": 1})
        # Only webhook 1 matches "incident.created", webhook 2 only wants "alert.fired"
        assert delivered == 1
