import os
from uuid import uuid4

import pytest


def _api_key() -> str:
    return os.environ.get("SINGLE_USER_API_KEY", "sk-test-1234567890-VALID")


def _auth_headers() -> dict:
    return {"X-API-KEY": _api_key()}


def _require_ok(resp, label: str) -> None:
    if not resp.ok:
        raise AssertionError(f"{label} failed: status={resp.status} body={resp.text()}")


@pytest.mark.e2e
def test_prompts_versioning_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]
    original_details = f"Version one details {suffix}"

    create_resp = page.request.post(
        "/api/v1/prompts",
        headers=headers,
        json={
            "name": f"Versioned Prompt {suffix}",
            "author": "e2e",
            "details": original_details,
            "system_prompt": "System prompt v1",
            "user_prompt": "User prompt v1",
            "keywords": [f"version-{suffix}"],
        },
    )
    _require_ok(create_resp, "create prompt")
    prompt = create_resp.json()
    prompt_id = prompt["id"]

    update_resp = page.request.put(
        f"/api/v1/prompts/{prompt_id}",
        headers=headers,
        json={
            "name": f"Versioned Prompt {suffix}",
            "author": "e2e",
            "details": f"Version two details {suffix}",
            "system_prompt": "System prompt v2",
            "user_prompt": "User prompt v2",
            "keywords": [f"version-{suffix}", "updated"],
        },
    )
    _require_ok(update_resp, "update prompt")
    updated = update_resp.json()
    assert updated["details"] != original_details

    versions_resp = page.request.get(
        f"/api/v1/prompts/{prompt_id}/versions",
        headers=headers,
    )
    _require_ok(versions_resp, "list versions")
    versions = versions_resp.json()
    assert len(versions) >= 2

    versions_sorted = sorted(versions, key=lambda v: v.get("version", 0))
    oldest_version = versions_sorted[0]["version"]
    oldest_details = versions_sorted[0].get("details")

    restore_resp = page.request.post(
        f"/api/v1/prompts/{prompt_id}/versions/{oldest_version}/restore",
        headers=headers,
    )
    _require_ok(restore_resp, "restore version")
    restored = restore_resp.json()

    if oldest_details:
        assert restored["details"] == oldest_details
    else:
        assert restored["details"] == original_details

    delete_resp = page.request.delete(
        f"/api/v1/prompts/{prompt_id}",
        headers=headers,
    )
    assert delete_resp.status == 204
