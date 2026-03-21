from __future__ import annotations

import pytest

from tldw_Server_API.app.services.integrations_control_plane_service import (
    IntegrationsControlPlaneService,
)


class _FakeUserSecretsRepo:
    async def list_secrets_for_user(self, user_id: int, *, include_revoked: bool = False) -> list[dict]:
        assert user_id == 7  # nosec B101 - pytest assertion
        assert include_revoked is False  # nosec B101 - pytest assertion
        return [
            {
                "provider": "slack",
                "metadata": {"installation_count": 2},
                "created_at": "2026-03-20T18:00:00+00:00",
                "updated_at": "2026-03-20T19:00:00+00:00",
            }
        ]


class _FakeOrgSecretsRepo:
    async def fetch_secret(
        self,
        scope_type: str,
        scope_id: int,
        provider: str,
        *,
        include_revoked: bool = False,
    ) -> dict | None:
        assert include_revoked is False  # nosec B101 - pytest assertion
        if (scope_type, scope_id, provider) == ("org", 1, "telegram"):
            return {
                "provider": "telegram",
                "metadata": {"bot_username": "tldwbot", "enabled": True},
                "created_at": "2026-03-20T17:30:00+00:00",
                "updated_at": "2026-03-20T19:30:00+00:00",
            }
        return None


class _FakeWorkspaceInstallationsRepo:
    async def list_installations(
        self,
        *,
        org_id: int,
        provider: str | None = None,
        include_disabled: bool = True,
    ) -> list[dict]:
        assert org_id == 1  # nosec B101 - pytest assertion
        assert include_disabled is True  # nosec B101 - pytest assertion
        rows = {
            "slack": [
                {
                    "id": 11,
                    "provider": "slack",
                    "external_id": "T123",
                    "display_name": "Workspace Slack",
                    "disabled": False,
                    "created_at": "2026-03-20T18:30:00+00:00",
                    "updated_at": "2026-03-20T19:30:00+00:00",
                }
            ],
            "discord": [
                {
                    "id": 21,
                    "provider": "discord",
                    "external_id": "G123",
                    "display_name": "Alerts Guild",
                    "disabled": True,
                    "created_at": "2026-03-20T18:45:00+00:00",
                    "updated_at": "2026-03-20T19:45:00+00:00",
                }
            ],
        }
        return rows.get(provider or "", [])


@pytest.mark.asyncio
async def test_workspace_integrations_service_normalizes_slack_discord_and_telegram():
    service = IntegrationsControlPlaneService(
        user_provider_secrets_repo=_FakeUserSecretsRepo(),
        org_provider_secrets_repo=_FakeOrgSecretsRepo(),
        workspace_installations_repo=_FakeWorkspaceInstallationsRepo(),
    )

    payload = await service.build_workspace_overview(org_id=1, scope_type="org", scope_id=1)
    by_provider = {item.provider: item for item in payload.items}

    assert [item.provider for item in payload.items] == ["slack", "discord", "telegram"]  # nosec B101
    assert set(by_provider) == {"slack", "discord", "telegram"}  # nosec B101
    assert all(item.scope == "workspace" for item in payload.items)  # nosec B101
    assert by_provider["slack"].status == "connected"  # nosec B101
    assert by_provider["slack"].enabled is True  # nosec B101
    assert by_provider["slack"].metadata["installation_count"] == 1  # nosec B101
    assert by_provider["discord"].status == "disabled"  # nosec B101
    assert by_provider["discord"].enabled is False  # nosec B101
    assert by_provider["telegram"].status == "connected"  # nosec B101
    assert by_provider["telegram"].display_name == "@tldwbot"  # nosec B101


@pytest.mark.asyncio
async def test_personal_integrations_service_only_exposes_slack_and_discord():
    service = IntegrationsControlPlaneService(
        user_provider_secrets_repo=_FakeUserSecretsRepo(),
        org_provider_secrets_repo=_FakeOrgSecretsRepo(),
        workspace_installations_repo=_FakeWorkspaceInstallationsRepo(),
    )

    payload = await service.build_personal_overview(user_id=7)
    by_provider = {item.provider: item for item in payload.items}

    assert [item.provider for item in payload.items] == ["slack", "discord"]  # nosec B101
    assert set(by_provider) == {"slack", "discord"}  # nosec B101
    assert all(item.scope == "personal" for item in payload.items)  # nosec B101
    assert by_provider["slack"].status == "connected"  # nosec B101
    assert by_provider["slack"].enabled is True  # nosec B101
    assert by_provider["slack"].metadata["installation_count"] == 2  # nosec B101
    assert by_provider["discord"].status == "disconnected"  # nosec B101
    assert by_provider["discord"].enabled is False  # nosec B101
