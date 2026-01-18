import os

import pytest


def _api_key() -> str:
    return os.environ.get("SINGLE_USER_API_KEY", "sk-test-1234567890-VALID")


def _auth_headers() -> dict:
    return {"X-API-KEY": _api_key()}


def _require_ok(resp, label: str) -> None:
    if not resp.ok:
        raise AssertionError(f"{label} failed: status={resp.status} body={resp.text()}")


@pytest.mark.e2e
def test_file_artifacts_purge_workflow(page, server_url):
    headers = _auth_headers()

    create_resp = page.request.post(
        "/api/v1/files/create",
        headers=headers,
        json={
            "file_type": "data_table",
            "title": "E2E Purge Table",
            "payload": {
                "columns": ["id", "name"],
                "rows": [
                    [101, "Purge"],
                    [102, "Cleanup"],
                ],
            },
            "export": {
                "format": "csv",
                "mode": "url",
                "async_mode": "sync",
            },
            "options": {"persist": True},
        },
    )
    _require_ok(create_resp, "create file artifact")
    artifact = create_resp.json()["artifact"]
    file_id = artifact["file_id"]

    delete_resp = page.request.delete(
        f"/api/v1/files/{file_id}",
        headers=headers,
    )
    _require_ok(delete_resp, "delete file artifact")

    purge_resp = page.request.post(
        "/api/v1/files/purge",
        headers=headers,
        json={
            "delete_files": True,
            "soft_deleted_grace_days": 0,
            "include_retention": True,
        },
    )
    _require_ok(purge_resp, "purge file artifacts")

    missing = page.request.get(f"/api/v1/files/{file_id}", headers=headers)
    assert missing.status == 404
