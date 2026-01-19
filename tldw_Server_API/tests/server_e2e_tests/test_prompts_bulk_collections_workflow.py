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
def test_prompts_import_bulk_collections_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]

    import_resp = page.request.post(
        "/api/v1/prompts/import",
        headers=headers,
        json={
            "prompts": [
                {
                    "name": f"Import Prompt A {suffix}",
                    "content": f"Imported content A {suffix}",
                    "author": "e2e",
                    "keywords": ["import", f"imp-{suffix}"],
                },
                {
                    "name": f"Import Prompt B {suffix}",
                    "details": f"Imported details B {suffix}",
                    "system_prompt": "System prompt",
                    "user_prompt": "User prompt",
                    "keywords": [f"imp-{suffix}"],
                },
            ],
            "skip_duplicates": False,
        },
    )
    _require_ok(import_resp, "import prompts")
    import_payload = import_resp.json()
    prompt_ids = import_payload.get("prompt_ids", [])
    assert len(prompt_ids) == 2

    bulk_kw_resp = page.request.post(
        "/api/v1/prompts/bulk/keywords",
        headers=headers,
        json={
            "prompt_ids": prompt_ids,
            "add_keywords": [f"bulk-{suffix}", "shared"],
            "remove_keywords": ["import"],
        },
    )
    _require_ok(bulk_kw_resp, "bulk update keywords")
    bulk_kw_payload = bulk_kw_resp.json()
    assert bulk_kw_payload.get("updated") == len(prompt_ids)

    search_resp = page.request.post(
        "/api/v1/prompts/search",
        headers=headers,
        params={
            "search_query": f"bulk-{suffix}",
            "search_fields": ["keywords"],
            "results_per_page": "20",
        },
    )
    _require_ok(search_resp, "search prompts by keyword")
    search_items = search_resp.json().get("items", [])
    found_ids = {item.get("id") for item in search_items}
    assert set(prompt_ids).issubset(found_ids)

    collection_resp = page.request.post(
        "/api/v1/prompts/collections/create",
        headers=headers,
        json={
            "name": f"E2E Collection {suffix}",
            "description": "Collection for prompt workflow",
            "prompt_ids": prompt_ids,
        },
    )
    _require_ok(collection_resp, "create collection")
    collection_id = collection_resp.json().get("collection_id")
    assert collection_id

    get_collection = page.request.get(
        f"/api/v1/prompts/collections/{collection_id}",
        headers=headers,
    )
    _require_ok(get_collection, "get collection")
    collection_payload = get_collection.json()
    assert collection_payload.get("collection_id") == collection_id
    assert collection_payload.get("prompt_ids") == prompt_ids

    delete_resp = page.request.post(
        "/api/v1/prompts/bulk/delete",
        headers=headers,
        json={"prompt_ids": prompt_ids},
    )
    _require_ok(delete_resp, "bulk delete prompts")
    delete_payload = delete_resp.json()
    assert delete_payload.get("deleted") == len(prompt_ids)

    post_delete_search = page.request.post(
        "/api/v1/prompts/search",
        headers=headers,
        params={
            "search_query": f"Import Prompt A {suffix}",
            "results_per_page": "20",
        },
    )
    _require_ok(post_delete_search, "search after delete")
    remaining = {item.get("id") for item in post_delete_search.json().get("items", [])}
    assert not (set(prompt_ids) & remaining)
