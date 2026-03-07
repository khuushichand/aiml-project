from __future__ import annotations

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


def _single_user_principal() -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=1,
        subject="single_user",
        roles=["admin"],
        is_admin=True,
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

    with pytest.raises(HTTPException) as excinfo:
        await admin_guardrails_service.verify_privileged_action(
            _single_user_principal(),
            db=object(),
            password_service=_PasswordService(),
            reason="Customer requested restore",
            admin_password=None,
        )

    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "Reason and current password are required for this action"


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
