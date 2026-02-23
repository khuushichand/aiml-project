from __future__ import annotations

import pytest


pytestmark = pytest.mark.unit


def test_create_and_list_personal_templates(meetings_api_client):
    create_resp = meetings_api_client.post(
        "/api/v1/meetings/templates",
        json={
            "name": "Weekly Template",
            "scope": "personal",
            "schema_json": {"sections": ["summary", "actions"]},
            "enabled": True,
            "is_default": False,
        },
    )
    assert create_resp.status_code == 201
    created_id = create_resp.json()["id"]

    list_resp = meetings_api_client.get("/api/v1/meetings/templates", params={"scope": "personal"})
    assert list_resp.status_code == 200
    ids = {row["id"] for row in list_resp.json()}
    assert created_id in ids


def test_builtin_templates_are_listed(meetings_api_client):
    resp = meetings_api_client.get("/api/v1/meetings/templates", params={"scope": "builtin"})
    assert resp.status_code == 200
    rows = resp.json()
    assert rows
    assert all(row["scope"] == "builtin" for row in rows)


def test_create_builtin_template_is_forbidden(meetings_api_client):
    create_resp = meetings_api_client.post(
        "/api/v1/meetings/templates",
        json={
            "name": "Should Fail",
            "scope": "builtin",
            "schema_json": {"sections": ["summary"]},
            "enabled": True,
            "is_default": False,
        },
    )
    assert create_resp.status_code == 403
