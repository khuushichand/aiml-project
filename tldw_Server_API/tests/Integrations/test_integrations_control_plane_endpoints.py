from __future__ import annotations

import pytest
from fastapi import Request

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.api.v1.endpoints.integrations_control_plane import (
    get_integrations_control_plane_service,
)
from tldw_Server_API.app.api.v1.endpoints.discord_support import _reset_discord_state_for_tests
from tldw_Server_API.app.api.v1.endpoints.slack_support import _reset_slack_state_for_tests
from tldw_Server_API.app.api.v1.endpoints.telegram_support import _reset_telegram_link_state_for_tests
from tldw_Server_API.app.api.v1.schemas.integrations_control_plane_schemas import (
    IntegrationConnection,
    IntegrationOverviewResponse,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.repos import get_workspace_provider_installations_repo
from tldw_Server_API.app.core.AuthNZ.repos.telegram_runtime_repo import get_telegram_runtime_repo


class _FakeIntegrationsControlPlaneService:
    async def build_personal_overview(self, *, user_id: int) -> IntegrationOverviewResponse:
        assert user_id == 303  # nosec B101 - pytest assertion
        return IntegrationOverviewResponse(
            scope="personal",
            items=[
                IntegrationConnection(
                    id="personal:slack",
                    provider="slack",
                    scope="personal",
                    display_name="Slack",
                    status="connected",
                    enabled=True,
                    actions=["disconnect"],
                ),
                IntegrationConnection(
                    id="personal:discord",
                    provider="discord",
                    scope="personal",
                    display_name="Discord",
                    status="disconnected",
                    enabled=False,
                    actions=["connect"],
                ),
            ],
        )

    async def build_workspace_overview(
        self,
        *,
        org_id: int,
        scope_type: str = "org",
        scope_id: int | None = None,
    ) -> IntegrationOverviewResponse:
        assert org_id == 11  # nosec B101 - pytest assertion
        assert scope_type == "team"  # nosec B101 - pytest assertion
        assert scope_id == 22  # nosec B101 - pytest assertion
        return IntegrationOverviewResponse(
            scope="workspace",
            items=[
                IntegrationConnection(
                    id="workspace:slack",
                    provider="slack",
                    scope="workspace",
                    display_name="Slack",
                    status="connected",
                    enabled=True,
                    actions=["manage"],
                ),
                IntegrationConnection(
                    id="workspace:discord",
                    provider="discord",
                    scope="workspace",
                    display_name="Discord",
                    status="disabled",
                    enabled=False,
                    actions=["manage"],
                ),
                IntegrationConnection(
                    id="workspace:telegram",
                    provider="telegram",
                    scope="workspace",
                    display_name="@tldwbot",
                    status="connected",
                    enabled=True,
                    actions=["configure_bot", "generate_pairing_code", "manage_linked_actors"],
                ),
            ],
        )


def _make_principal(
    *,
    active_org_id: int | None = None,
    active_team_id: int | None = None,
    org_ids: list[int] | None = None,
    team_ids: list[int] | None = None,
) -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=303,
        api_key_id=None,
        subject="integrations-control-plane-test",
        token_type="access",  # nosec B106 - auth principal test fixture token type
        jti=None,
        roles=["admin"],
        permissions=["system.configure"],
        is_admin=True,
        org_ids=org_ids or [],
        team_ids=team_ids or [],
        active_org_id=active_org_id,
        active_team_id=active_team_id,
    )


def _override_principal(client, principal: AuthPrincipal) -> None:
    async def _fake_get_auth_principal(request: Request) -> AuthPrincipal:
        request.state.auth = AuthContext(principal=principal, ip=None, user_agent=None, request_id=None)
        request.state.active_org_id = principal.active_org_id
        request.state.active_team_id = principal.active_team_id
        request.state.org_ids = list(principal.org_ids)
        request.state.team_ids = list(principal.team_ids)
        return principal

    client.app.dependency_overrides[get_auth_principal] = _fake_get_auth_principal


@pytest.fixture()
def client(client_user_only):
    _reset_slack_state_for_tests()
    _reset_discord_state_for_tests()
    _reset_telegram_link_state_for_tests()
    return client_user_only


@pytest.fixture()
def principal_override(client):
    def _install(principal: AuthPrincipal) -> None:
        _override_principal(client, principal)

    yield _install
    client.app.dependency_overrides.pop(get_auth_principal, None)
    client.app.dependency_overrides.pop(get_integrations_control_plane_service, None)
    _reset_slack_state_for_tests()
    _reset_discord_state_for_tests()
    _reset_telegram_link_state_for_tests()


@pytest.fixture()
def service_override(client):
    client.app.dependency_overrides[get_integrations_control_plane_service] = lambda: _FakeIntegrationsControlPlaneService()
    yield
    client.app.dependency_overrides.pop(get_integrations_control_plane_service, None)


def test_get_personal_integrations_returns_normalized_payload(client, auth_headers, principal_override, service_override):
    principal_override(_make_principal(active_org_id=11, active_team_id=22, org_ids=[11], team_ids=[22]))

    response = client.get("/api/v1/integrations/personal", headers=auth_headers)

    assert response.status_code == 200, response.text  # nosec B101 - pytest assertion
    body = response.json()
    assert body["scope"] == "personal"  # nosec B101 - pytest assertion
    assert [item["provider"] for item in body["items"]] == ["slack", "discord"]  # nosec B101 - pytest assertion


def test_get_workspace_integrations_returns_normalized_payload(client, auth_headers, principal_override, service_override):
    principal_override(_make_principal(active_org_id=11, active_team_id=22, org_ids=[11], team_ids=[22]))

    response = client.get("/api/v1/integrations/workspace", headers=auth_headers)

    assert response.status_code == 200, response.text  # nosec B101 - pytest assertion
    body = response.json()
    assert body["scope"] == "workspace"  # nosec B101 - pytest assertion
    assert [item["provider"] for item in body["items"]] == ["slack", "discord", "telegram"]  # nosec B101


@pytest.mark.asyncio
async def test_workspace_slack_policy_routes_apply_to_registry_installations(client, auth_headers, principal_override):
    principal_override(_make_principal(active_org_id=11, active_team_id=22, org_ids=[11], team_ids=[22]))

    workspace_repo = await get_workspace_provider_installations_repo()
    await workspace_repo.upsert_installation(
        org_id=11,
        provider="slack",
        external_id="T-11",
        display_name="Slack Org 11",
        installed_by_user_id=303,
        disabled=False,
    )

    get_response = client.get("/api/v1/integrations/workspace/slack/policy", headers=auth_headers)

    assert get_response.status_code == 200, get_response.text  # nosec B101 - pytest assertion
    assert get_response.json()["installation_ids"] == ["T-11"]  # nosec B101 - pytest assertion

    put_response = client.put(
        "/api/v1/integrations/workspace/slack/policy",
        headers=auth_headers,
        json={
            "allowed_commands": ["help", "status"],
            "default_response_mode": "thread",
            "status_scope": "workspace_and_user",
        },
    )

    assert put_response.status_code == 200, put_response.text  # nosec B101 - pytest assertion
    body = put_response.json()
    assert body["provider"] == "slack"  # nosec B101 - pytest assertion
    assert body["policy"]["allowed_commands"] == ["help", "status"]  # nosec B101 - pytest assertion
    assert body["policy"]["default_response_mode"] == "thread"  # nosec B101 - pytest assertion


@pytest.mark.asyncio
async def test_workspace_discord_policy_routes_apply_to_registry_installations(client, auth_headers, principal_override):
    principal_override(_make_principal(active_org_id=11, active_team_id=22, org_ids=[11], team_ids=[22]))

    workspace_repo = await get_workspace_provider_installations_repo()
    await workspace_repo.upsert_installation(
        org_id=11,
        provider="discord",
        external_id="G-11",
        display_name="Discord Org 11",
        installed_by_user_id=303,
        disabled=False,
    )

    put_response = client.put(
        "/api/v1/integrations/workspace/discord/policy",
        headers=auth_headers,
        json={
            "allowed_commands": ["help"],
            "default_response_mode": "channel",
            "status_scope": "guild_and_user",
        },
    )

    assert put_response.status_code == 200, put_response.text  # nosec B101 - pytest assertion
    body = put_response.json()
    assert body["provider"] == "discord"  # nosec B101 - pytest assertion
    assert body["installation_ids"] == ["G-11"]  # nosec B101 - pytest assertion
    assert body["policy"]["allowed_commands"] == ["help"]  # nosec B101 - pytest assertion
    assert body["policy"]["default_response_mode"] == "channel"  # nosec B101 - pytest assertion


@pytest.mark.asyncio
async def test_workspace_telegram_linked_actor_routes_proxy_admin_management(client, auth_headers, principal_override):
    principal_override(_make_principal(active_org_id=11, active_team_id=22, org_ids=[11], team_ids=[22]))

    runtime_repo = await get_telegram_runtime_repo()
    seeded = await runtime_repo.upsert_actor_link(
        scope_type="team",
        scope_id=22,
        telegram_user_id=123456,
        auth_user_id=77,
        telegram_username="linked",
    )

    list_response = client.get("/api/v1/integrations/workspace/telegram/linked-actors", headers=auth_headers)
    assert list_response.status_code == 200, list_response.text  # nosec B101 - pytest assertion
    assert list_response.json()["items"][0]["id"] == seeded["id"]  # nosec B101 - pytest assertion

    delete_response = client.delete(
        f"/api/v1/integrations/workspace/telegram/linked-actors/{seeded['id']}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 200, delete_response.text  # nosec B101 - pytest assertion
    assert delete_response.json()["deleted"] is True  # nosec B101 - pytest assertion
