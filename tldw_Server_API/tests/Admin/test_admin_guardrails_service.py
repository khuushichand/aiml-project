from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.services import admin_guardrails_service


class _PasswordService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def verify_password(self, password: str, password_hash: str) -> tuple[bool, bool]:
        self.calls.append((password, password_hash))
        return True, False


class _JWTService:
    def __init__(self, payload: dict | None = None, *, error: Exception | None = None) -> None:
        self.payload = payload or {}
        self.error = error
        self.calls: list[tuple[str, str | None]] = []

    async def verify_token_async(self, token: str, token_type: str | None = None) -> dict:
        self.calls.append((token, token_type))
        if self.error is not None:
            raise self.error
        return dict(self.payload)


class _Blacklist:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def revoke_token(self, **kwargs) -> bool:  # noqa: ANN003
        self.calls.append(dict(kwargs))
        return True


def _single_user_principal() -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=1,
        subject="single_user",
        roles=["admin"],
        is_admin=True,
    )


def _multi_user_admin_principal(user_id: int = 7) -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=user_id,
        subject=f"user:{user_id}",
        roles=["admin"],
        is_admin=True,
        email="alice@example.com",
    )


@pytest.mark.asyncio
async def test_verify_privileged_action_allows_non_enterprise_single_user_without_password(monkeypatch) -> None:
    password_service = _PasswordService()

    async def _unexpected_fetch(*_args, **_kwargs):
        raise AssertionError("single-user fallback should not load password hashes")

    monkeypatch.delenv("ADMIN_UI_ENTERPRISE_MODE", raising=False)
    monkeypatch.setattr(admin_guardrails_service, "fetch_active_user_by_id", _unexpected_fetch)

    reason = await admin_guardrails_service.verify_privileged_action(
        _single_user_principal(),
        db=object(),
        password_service=password_service,
        reason="Customer requested restore",
        admin_password=None,
    )

    assert reason == "Customer requested restore"
    assert password_service.calls == []


@pytest.mark.asyncio
async def test_verify_privileged_action_rejects_single_user_without_password_in_enterprise_mode(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_UI_ENTERPRISE_MODE", "true")

    async def _fake_fetch(*_args, **_kwargs):
        return {
            "id": 1,
            "email": "single-user@example.com",
            "password_hash": "hashed-password",
        }

    monkeypatch.setattr(admin_guardrails_service, "fetch_active_user_by_id", _fake_fetch)

    with pytest.raises(HTTPException) as excinfo:
        await admin_guardrails_service.verify_privileged_action(
            _single_user_principal(),
            db=object(),
            password_service=_PasswordService(),
            reason="Customer requested restore",
            admin_password=None,
        )

    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "Reason and current password or admin reauthentication token are required for this action"


@pytest.mark.asyncio
async def test_verify_privileged_action_requires_password_for_multi_user_admin(monkeypatch) -> None:
    monkeypatch.delenv("ADMIN_UI_ENTERPRISE_MODE", raising=False)

    async def _fake_fetch(*_args, **_kwargs):
        return {
            "id": 7,
            "password_hash": "hashed-password",
        }

    password_service = _PasswordService()
    monkeypatch.setattr(admin_guardrails_service, "fetch_active_user_by_id", _fake_fetch)

    reason = await admin_guardrails_service.verify_privileged_action(
        AuthPrincipal(
            kind="user",
            user_id=7,
            subject="user:7",
            roles=["admin"],
            is_admin=True,
        ),
        db=object(),
        password_service=password_service,
        reason="Customer requested restore",
        admin_password="AdminPass123!",
    )

    assert reason == "Customer requested restore"
    assert password_service.calls == [("AdminPass123!", "hashed-password")]


@pytest.mark.asyncio
async def test_verify_privileged_action_allows_magic_link_step_up_for_federated_admin(monkeypatch) -> None:
    async def _fake_fetch(*_args, **_kwargs):
        return {
            "id": 7,
            "email": "alice@example.com",
            "password_hash": "",
        }

    jwt_service = _JWTService(
        {
            "user_id": 7,
            "email": "alice@example.com",
            "purpose": "admin_reauth",
            "jti": "magic-link-jti-1",
            "exp": datetime(2030, 1, 1, tzinfo=timezone.utc).timestamp(),
        }
    )
    blacklist = _Blacklist()
    password_service = _PasswordService()
    monkeypatch.setattr(admin_guardrails_service, "fetch_active_user_by_id", _fake_fetch)
    monkeypatch.setattr(admin_guardrails_service, "get_jwt_service", lambda: jwt_service)
    monkeypatch.setattr(admin_guardrails_service, "get_token_blacklist", lambda: blacklist)

    reason = await admin_guardrails_service.verify_privileged_action(
        _multi_user_admin_principal(),
        db=object(),
        password_service=password_service,
        reason="Customer requested restore",
        admin_password=None,
        admin_reauth_token="magic-token-123",
    )

    assert reason == "Customer requested restore"
    assert password_service.calls == []
    assert jwt_service.calls == [("magic-token-123", "admin_reauth")]
    assert blacklist.calls and blacklist.calls[0]["jti"] == "magic-link-jti-1"
    assert blacklist.calls[0]["token_type"] == "admin_reauth"


@pytest.mark.asyncio
async def test_verify_privileged_action_rejects_magic_link_step_up_for_other_admin(monkeypatch) -> None:
    async def _fake_fetch(*_args, **_kwargs):
        return {
            "id": 7,
            "email": "alice@example.com",
            "password_hash": "",
        }

    jwt_service = _JWTService(
        {
            "user_id": 8,
            "email": "mallory@example.com",
            "purpose": "admin_reauth",
            "jti": "magic-link-jti-2",
            "exp": datetime(2030, 1, 1, tzinfo=timezone.utc).timestamp(),
        }
    )
    monkeypatch.setattr(admin_guardrails_service, "fetch_active_user_by_id", _fake_fetch)
    monkeypatch.setattr(admin_guardrails_service, "get_jwt_service", lambda: jwt_service)
    monkeypatch.setattr(admin_guardrails_service, "get_token_blacklist", lambda: _Blacklist())

    with pytest.raises(HTTPException) as excinfo:
        await admin_guardrails_service.verify_privileged_action(
            _multi_user_admin_principal(),
            db=object(),
            password_service=_PasswordService(),
            reason="Customer requested restore",
            admin_password=None,
            admin_reauth_token="magic-token-456",
        )

    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "Admin reauthentication failed"


@pytest.mark.asyncio
async def test_verify_privileged_action_rejects_magic_link_without_admin_reauth_purpose(monkeypatch) -> None:
    async def _fake_fetch(*_args, **_kwargs):
        return {
            "id": 7,
            "email": "alice@example.com",
            "password_hash": "",
        }

    jwt_service = _JWTService(
        {
            "user_id": 7,
            "email": "alice@example.com",
            "jti": "magic-link-jti-3",
            "exp": datetime(2030, 1, 1, tzinfo=timezone.utc).timestamp(),
        }
    )
    monkeypatch.setattr(admin_guardrails_service, "fetch_active_user_by_id", _fake_fetch)
    monkeypatch.setattr(admin_guardrails_service, "get_jwt_service", lambda: jwt_service)
    monkeypatch.setattr(admin_guardrails_service, "get_token_blacklist", lambda: _Blacklist())

    with pytest.raises(HTTPException) as excinfo:
        await admin_guardrails_service.verify_privileged_action(
            _multi_user_admin_principal(),
            db=object(),
            password_service=_PasswordService(),
            reason="Customer requested restore",
            admin_password=None,
            admin_reauth_token="magic-token-789",
        )

    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "Admin reauthentication failed"
