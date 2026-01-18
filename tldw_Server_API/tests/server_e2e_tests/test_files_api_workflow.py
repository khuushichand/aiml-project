import base64
import json
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
def test_file_artifacts_export_workflow(page, server_url):
    headers = _auth_headers()

    inline_resp = page.request.post(
        "/api/v1/files/create",
        headers=headers,
        json={
            "file_type": "data_table",
            "title": "E2E Data Table Inline",
            "payload": {
                "columns": ["id", "name"],
                "rows": [
                    [1, "Alpha"],
                    [2, "Beta"],
                ],
            },
            "export": {
                "format": "csv",
                "mode": "inline",
                "async_mode": "sync",
            },
            "options": {"persist": True},
        },
    )
    _require_ok(inline_resp, "create inline artifact")
    inline_artifact = inline_resp.json()["artifact"]
    inline_export = inline_artifact["export"]
    assert inline_export["content_b64"]
    csv_text = base64.b64decode(inline_export["content_b64"]).decode("utf-8")
    assert "id,name" in csv_text
    assert "1,Alpha" in csv_text
    assert "2,Beta" in csv_text

    inline_id = inline_artifact["file_id"]
    get_inline = page.request.get(f"/api/v1/files/{inline_id}", headers=headers)
    _require_ok(get_inline, "get inline artifact")
    inline_payload = get_inline.json()["artifact"]["structured"]
    assert inline_payload["columns"] == ["id", "name"]
    assert inline_payload["rows"][0] == [1, "Alpha"]

    url_resp = page.request.post(
        "/api/v1/files/create",
        headers=headers,
        json={
            "file_type": "data_table",
            "title": "E2E Data Table URL",
            "payload": {
                "columns": ["id", "name"],
                "rows": [
                    [10, "Gamma"],
                    [11, "Delta"],
                ],
            },
            "export": {
                "format": "json",
                "mode": "url",
                "async_mode": "sync",
            },
            "options": {"persist": True},
        },
    )
    _require_ok(url_resp, "create url artifact")
    url_artifact = url_resp.json()["artifact"]
    export_url = url_artifact["export"]["url"]
    assert export_url

    download_resp = page.request.get(export_url, headers=headers)
    _require_ok(download_resp, "download export")
    downloaded = json.loads(download_resp.body().decode("utf-8"))
    assert downloaded == [
        {"id": 10, "name": "Gamma"},
        {"id": 11, "name": "Delta"},
    ]

    consumed_resp = page.request.get(export_url, headers=headers)
    assert consumed_resp.status in (404, 409)

    delete_inline = page.request.delete(f"/api/v1/files/{inline_id}", headers=headers)
    _require_ok(delete_inline, "delete inline artifact")
    delete_url = page.request.delete(f"/api/v1/files/{url_artifact['file_id']}", headers=headers)
    _require_ok(delete_url, "delete url artifact")
