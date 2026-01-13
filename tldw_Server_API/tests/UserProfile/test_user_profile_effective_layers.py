from __future__ import annotations

import asyncio
import uuid

from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.orgs_teams import (
    add_org_member,
    add_team_member,
    create_organization,
    create_team,
)
from tldw_Server_API.app.core.UserProfiles.overrides_repo import (
    OrgProfileOverridesRepo,
    TeamProfileOverridesRepo,
)
from tldw_Server_API.app.core.UserProfiles.service import UserProfileService


def _run_async(coro):
    return asyncio.run(coro)


def _get_user_id(client: TestClient, auth_headers) -> int:
    resp = client.get("/api/v1/users/me/profile", headers=auth_headers)
    assert resp.status_code == 200
    return int(resp.json()["user"]["id"])


def test_select_lowest_id_overrides() -> None:
    rows = [
        {"org_id": 3, "key": "preferences.ui.theme", "value": "org-three"},
        {"org_id": 1, "key": "preferences.ui.theme", "value": "org-one"},
        {"org_id": 2, "key": "preferences.ui.density", "value": "org-two"},
        {"org_id": 1, "key": "preferences.ui.density", "value": "org-one-density"},
        {"org_id": 4, "key": "preferences.ui.theme", "value": None},
    ]

    selected = UserProfileService._select_lowest_id_overrides(rows, id_field="org_id")
    assert selected["preferences.ui.theme"]["value"] == "org-one"
    assert selected["preferences.ui.theme"]["id"] == 1
    assert selected["preferences.ui.density"]["value"] == "org-one-density"
    assert selected["preferences.ui.density"]["id"] == 1


def test_effective_config_layering(auth_headers) -> None:
    with TestClient(app) as client:
        user_id = _get_user_id(client, auth_headers)
        suffix = uuid.uuid4().hex[:8]

        async def _setup_overrides():
            org = await create_organization(name=f"Config Org {suffix}", owner_user_id=None)
            await add_org_member(org_id=int(org["id"]), user_id=user_id, role="member")
            team = await create_team(org_id=int(org["id"]), name=f"Config Team {suffix}")
            await add_team_member(team_id=int(team["id"]), user_id=user_id, role="member")

            pool = await get_db_pool()
            org_repo = OrgProfileOverridesRepo(pool)
            team_repo = TeamProfileOverridesRepo(pool)
            await org_repo.ensure_tables()
            await team_repo.ensure_tables()

            await org_repo.upsert_override(
                org_id=int(org["id"]),
                key="preferences.ui.theme",
                value="org-theme",
                updated_by=user_id,
            )
            await team_repo.upsert_override(
                team_id=int(team["id"]),
                key="preferences.ui.theme",
                value="team-theme",
                updated_by=user_id,
            )
            return int(org["id"]), int(team["id"])

        org_id, team_id = _run_async(_setup_overrides())

        resp = client.patch(
            "/api/v1/users/me/profile",
            headers=auth_headers,
            json={
                "updates": [{"key": "preferences.ui.theme", "value": "user-theme"}],
            },
        )
        assert resp.status_code == 200

        resp = client.get(
            "/api/v1/users/me/profile",
            headers=auth_headers,
            params={"sections": "effective_config", "include_sources": True},
        )
        assert resp.status_code == 200
        effective = resp.json().get("effective_config", {})
        assert effective["preferences.ui.theme"]["value"] == "user-theme"
        assert effective["preferences.ui.theme"]["source"] == "user"

        resp = client.patch(
            "/api/v1/users/me/profile",
            headers=auth_headers,
            json={
                "updates": [{"key": "preferences.ui.theme", "value": None}],
            },
        )
        assert resp.status_code == 200

        resp = client.get(
            "/api/v1/users/me/profile",
            headers=auth_headers,
            params={"sections": "effective_config", "include_sources": True},
        )
        assert resp.status_code == 200
        effective = resp.json().get("effective_config", {})
        assert effective["preferences.ui.theme"]["value"] == "team-theme"
        assert effective["preferences.ui.theme"]["source"] == "team"

        async def _remove_team_override():
            pool = await get_db_pool()
            team_repo = TeamProfileOverridesRepo(pool)
            await team_repo.ensure_tables()
            await team_repo.delete_override(team_id=team_id, key="preferences.ui.theme")

        _run_async(_remove_team_override())

        resp = client.get(
            "/api/v1/users/me/profile",
            headers=auth_headers,
            params={"sections": "effective_config", "include_sources": True},
        )
        assert resp.status_code == 200
        effective = resp.json().get("effective_config", {})
        assert effective["preferences.ui.theme"]["value"] == "org-theme"
        assert effective["preferences.ui.theme"]["source"] == "org"

        async def _add_second_org_override():
            org = await create_organization(name=f"Config Org 2 {suffix}", owner_user_id=None)
            await add_org_member(org_id=int(org["id"]), user_id=user_id, role="member")
            pool = await get_db_pool()
            org_repo = OrgProfileOverridesRepo(pool)
            await org_repo.ensure_tables()
            await org_repo.upsert_override(
                org_id=int(org["id"]),
                key="preferences.ui.theme",
                value="org-theme-2",
                updated_by=user_id,
            )

        _run_async(_add_second_org_override())

        resp = client.get(
            "/api/v1/users/me/profile",
            headers=auth_headers,
            params={"sections": "effective_config", "include_sources": True},
        )
        assert resp.status_code == 200
        effective = resp.json().get("effective_config", {})
        assert effective["preferences.ui.theme"]["value"] == "org-theme"
        assert effective["preferences.ui.theme"]["source"] == "org"
