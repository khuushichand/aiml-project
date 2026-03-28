from datetime import datetime

import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas import admin_schemas
from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    AdminWebhookCreateRequest,
    AdminWebhookResponse,
    AdminWebhookUpdateRequest,
)
from tldw_Server_API.app.core.Security.egress import URLPolicyResult


pytestmark = pytest.mark.unit


def test_admin_webhook_create_request_rejects_embedded_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        admin_schemas,
        "evaluate_url_policy",
        lambda _url: URLPolicyResult(True),
    )

    with pytest.raises(ValidationError, match="embedded credentials"):
        AdminWebhookCreateRequest(
            url="https://user:pass@example.com/hook",
            event_types=["*"],
        )


def test_admin_webhook_update_request_rejects_unsafe_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        admin_schemas,
        "evaluate_url_policy",
        lambda _url: URLPolicyResult(False, "URL resolves to a private or reserved address"),
    )

    with pytest.raises(ValidationError, match="not allowed"):
        AdminWebhookUpdateRequest(url="http://169.254.169.254/latest/meta-data")


def test_admin_webhook_response_coerces_timestamp_fields_to_datetime() -> None:
    payload = AdminWebhookResponse(
        id=1,
        url="https://example.com/hook",
        event_types=["*"],
        description="Example",
        active=True,
        retry_count=3,
        timeout_seconds=10,
        created_by=7,
        created_at="2026-03-01T12:00:00Z",
        updated_at="2026-03-01T12:05:00Z",
    )

    assert isinstance(payload.created_at, datetime)
    assert isinstance(payload.updated_at, datetime)
