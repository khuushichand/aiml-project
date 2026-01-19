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
def test_prompts_template_and_export_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]

    template = "Hello {{name}}, welcome to {{topic}}."
    vars_resp = page.request.post(
        "/api/v1/prompts/templates/variables",
        headers=headers,
        json={"template": template},
    )
    _require_ok(vars_resp, "extract template variables")
    variables = vars_resp.json().get("variables", [])
    assert set(variables) == {"name", "topic"}

    render_resp = page.request.post(
        "/api/v1/prompts/templates/render",
        headers=headers,
        json={
            "template": template,
            "variables": {"name": "Ada", "topic": "LLMs"},
        },
    )
    _require_ok(render_resp, "render template")
    rendered = render_resp.json().get("rendered", "")
    assert "Ada" in rendered
    assert "LLMs" in rendered

    prompt_name = f"E2E Prompt {suffix}"
    keywords = [f"e2e-{suffix}", f"template-{suffix}"]
    create_payload = {
        "name": prompt_name,
        "author": "e2e",
        "details": f"Prompt details {suffix}",
        "system_prompt": "You are a helpful assistant.",
        "user_prompt": template,
        "keywords": keywords,
    }
    create_resp = page.request.post(
        "/api/v1/prompts",
        headers=headers,
        json=create_payload,
    )
    _require_ok(create_resp, "create prompt")
    created = create_resp.json()
    prompt_id = created["id"]
    assert created["name"] == prompt_name

    get_resp = page.request.get(f"/api/v1/prompts/{prompt_id}", headers=headers)
    _require_ok(get_resp, "get prompt")
    fetched = get_resp.json()
    assert fetched["id"] == prompt_id
    assert fetched["name"] == prompt_name

    updated_payload = {
        "name": prompt_name,
        "author": "e2e-updated",
        "details": f"Updated details {suffix}",
        "system_prompt": "You are a precise assistant.",
        "user_prompt": template,
        "keywords": [keywords[0], f"updated-{suffix}"],
    }
    update_resp = page.request.put(
        f"/api/v1/prompts/{prompt_id}",
        headers=headers,
        json=updated_payload,
    )
    _require_ok(update_resp, "update prompt")
    updated = update_resp.json()
    assert updated["details"] == updated_payload["details"]
    assert updated["author"] == updated_payload["author"]

    search_resp = page.request.post(
        "/api/v1/prompts/search",
        headers=headers,
        params={"search_query": prompt_name, "results_per_page": "20"},
    )
    _require_ok(search_resp, "search prompts")
    search_payload = search_resp.json()
    assert any(item.get("id") == prompt_id for item in search_payload.get("items", []))

    export_resp = page.request.get(
        "/api/v1/prompts/export",
        headers=headers,
        params={"export_format": "csv", "filter_keywords": keywords[0]},
    )
    _require_ok(export_resp, "export prompts")
    export_payload = export_resp.json()
    assert export_payload.get("message")
    assert export_payload.get("file_content_b64") or export_payload.get("file_path")

    delete_resp = page.request.delete(f"/api/v1/prompts/{prompt_id}", headers=headers)
    assert delete_resp.status == 204

    post_delete_search = page.request.post(
        "/api/v1/prompts/search",
        headers=headers,
        params={"search_query": prompt_name, "results_per_page": "20"},
    )
    _require_ok(post_delete_search, "search prompts after delete")
    remaining = post_delete_search.json().get("items", [])
    assert all(item.get("id") != prompt_id for item in remaining)
