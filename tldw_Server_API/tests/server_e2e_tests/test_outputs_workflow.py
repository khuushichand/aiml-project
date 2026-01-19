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
def test_outputs_templates_and_artifacts_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]

    template_body = "\n".join(
        [
            "# Output {{ date }}",
            "",
            "{% for item in items %}- {{ item.title }} ({{ item.url }})",
            "{% endfor %}",
        ]
    )
    template_resp = page.request.post(
        "/api/v1/outputs/templates",
        headers=headers,
        json={
            "name": f"E2E Output Template {suffix}",
            "type": "newsletter_markdown",
            "format": "md",
            "body": template_body,
            "description": "E2E outputs template.",
            "is_default": False,
        },
    )
    _require_ok(template_resp, "create output template")
    template_payload = template_resp.json()
    template_id = template_payload["id"]

    list_resp = page.request.get(
        "/api/v1/outputs/templates",
        headers=headers,
        params={"limit": 50, "offset": 0},
    )
    _require_ok(list_resp, "list output templates")
    list_payload = list_resp.json()
    assert any(item.get("id") == template_id for item in list_payload.get("items", []))

    get_resp = page.request.get(f"/api/v1/outputs/templates/{template_id}", headers=headers)
    _require_ok(get_resp, "get output template")
    assert get_resp.json()["name"] == template_payload["name"]

    update_resp = page.request.patch(
        f"/api/v1/outputs/templates/{template_id}",
        headers=headers,
        json={"description": f"Updated template {suffix}."},
    )
    _require_ok(update_resp, "update output template")
    assert update_resp.json()["description"] == f"Updated template {suffix}."

    preview_data = {
        "date": "2025-01-01 00:00 UTC",
        "items": [
            {"title": f"Item {suffix}", "url": "https://example.com/item", "summary": "Summary"},
        ],
        "job": {"name": "Preview", "run_id": None, "selection": {"item_ids": [], "count": 1}},
    }
    preview_resp = page.request.post(
        f"/api/v1/outputs/templates/{template_id}/preview",
        headers=headers,
        json={
            "template_id": template_id,
            "data": preview_data,
        },
    )
    _require_ok(preview_resp, "preview template")
    preview_payload = preview_resp.json()
    assert f"Item {suffix}" in preview_payload.get("rendered", "")

    output_resp = page.request.post(
        "/api/v1/outputs",
        headers=headers,
        json={
            "template_id": template_id,
            "title": f"E2E Output {suffix}",
            "data": preview_data,
        },
    )
    _require_ok(output_resp, "create output")
    output_payload = output_resp.json()
    output_id = output_payload["id"]

    outputs_list_resp = page.request.get(
        "/api/v1/outputs",
        headers=headers,
        params={"page": 1, "size": 50},
    )
    _require_ok(outputs_list_resp, "list outputs")
    outputs_list = outputs_list_resp.json()
    assert any(item.get("id") == output_id for item in outputs_list.get("items", []))

    get_output_resp = page.request.get(f"/api/v1/outputs/{output_id}", headers=headers)
    _require_ok(get_output_resp, "get output")
    assert get_output_resp.json()["id"] == output_id

    head_resp = page.request.fetch(
        f"/api/v1/outputs/{output_id}/download",
        method="HEAD",
        headers=headers,
    )
    _require_ok(head_resp, "head output download")
    assert head_resp.headers.get("content-type", "").startswith("text/")

    download_resp = page.request.get(f"/api/v1/outputs/{output_id}/download", headers=headers)
    _require_ok(download_resp, "download output")
    download_text = download_resp.text()
    assert f"Item {suffix}" in download_text

    updated_title = f"E2E Output Updated {suffix}"
    update_output_resp = page.request.patch(
        f"/api/v1/outputs/{output_id}",
        headers=headers,
        json={"title": updated_title},
    )
    _require_ok(update_output_resp, "update output")
    assert update_output_resp.json()["title"] == updated_title

    delete_output_resp = page.request.delete(
        f"/api/v1/outputs/{output_id}",
        headers=headers,
        params={"hard": "true", "delete_file": "true"},
    )
    _require_ok(delete_output_resp, "delete output")
    assert delete_output_resp.json().get("success") is True

    delete_template_resp = page.request.delete(
        f"/api/v1/outputs/templates/{template_id}",
        headers=headers,
    )
    _require_ok(delete_template_resp, "delete template")
