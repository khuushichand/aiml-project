from __future__ import annotations

import pytest

from tldw_Server_API.app.api.v1.schemas.api_key_schemas import APIKeyUpdateRequest
from tldw_Server_API.app.services import admin_api_keys_service as svc


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_user_api_key_passes_backend_mode_to_admin_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def _fake_enforce_admin_user_scope(*args, **kwargs) -> None:  # noqa: ANN002
        return None

    async def _fake_update_api_key_metadata(
        db,
        *,
        user_id: int,
        key_id: int,
        rate_limit: int | None = None,
        allowed_ips: list[str] | None = None,
        is_postgres: bool,
    ) -> dict:
        captured["is_postgres"] = is_postgres
        captured["user_id"] = user_id
        captured["key_id"] = key_id
        captured["rate_limit"] = rate_limit
        captured["allowed_ips"] = allowed_ips
        return {
            "id": key_id,
            "scope": "read",
            "key_prefix": "sk-test",
        }

    async def _fake_is_pg() -> bool:
        return True

    monkeypatch.setattr(svc.admin_scope_service, "enforce_admin_user_scope", _fake_enforce_admin_user_scope)
    monkeypatch.setattr(svc, "update_api_key_metadata", _fake_update_api_key_metadata)

    result = await svc.update_user_api_key(
        principal=object(),
        user_id=12,
        key_id=34,
        request=APIKeyUpdateRequest(rate_limit=55, allowed_ips=["10.1.1.1"]),
        db=object(),
        is_pg_fn=_fake_is_pg,
    )

    assert result.id == 34
    assert result.scope == "read"
    assert captured == {
        "is_postgres": True,
        "user_id": 12,
        "key_id": 34,
        "rate_limit": 55,
        "allowed_ips": ["10.1.1.1"],
    }
