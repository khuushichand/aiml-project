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
def test_world_books_lifecycle_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]

    character_resp = page.request.post(
        "/api/v1/characters/",
        headers=headers,
        json={
            "name": f"E2E WorldBook Character {suffix}",
            "description": f"World book character {suffix}.",
            "tags": [f"worldbook-{suffix}"],
        },
    )
    _require_ok(character_resp, "create character")
    character_id = character_resp.json()["id"]

    world_book_resp = page.request.post(
        "/api/v1/characters/world-books",
        headers=headers,
        json={
            "name": f"E2E World Book {suffix}",
            "description": "E2E world book description.",
            "scan_depth": 2,
            "token_budget": 250,
            "recursive_scanning": False,
            "enabled": True,
        },
    )
    _require_ok(world_book_resp, "create world book")
    world_book = world_book_resp.json()
    world_book_id = world_book["id"]
    world_book_version = world_book["version"]

    update_world_book_resp = page.request.put(
        f"/api/v1/characters/world-books/{world_book_id}",
        headers=headers,
        params={"expected_version": world_book_version},
        json={"description": f"E2E world book description updated {suffix}."},
    )
    _require_ok(update_world_book_resp, "update world book with expected version")
    updated_world_book = update_world_book_resp.json()
    assert updated_world_book.get("version") == world_book_version + 1

    stale_world_book_update_resp = page.request.put(
        f"/api/v1/characters/world-books/{world_book_id}",
        headers=headers,
        params={"expected_version": world_book_version},
        json={"description": "stale update should fail"},
    )
    assert stale_world_book_update_resp.status == 409

    list_resp = page.request.get(
        "/api/v1/characters/world-books",
        headers=headers,
        params={"include_disabled": "true"},
    )
    _require_ok(list_resp, "list world books")
    list_payload = list_resp.json()
    assert any(item.get("id") == world_book_id for item in list_payload.get("world_books", []))

    keyword_one = f"alpha-{suffix}"
    entry_one_resp = page.request.post(
        f"/api/v1/characters/world-books/{world_book_id}/entries",
        headers=headers,
        json={
            "keywords": [keyword_one],
            "content": f"Entry one content {suffix}.",
            "priority": 1,
            "enabled": True,
        },
    )
    _require_ok(entry_one_resp, "create world book entry one")
    entry_one = entry_one_resp.json()
    entry_one_id = entry_one["id"]

    keyword_two = f"beta-{suffix}"
    entry_two_resp = page.request.post(
        f"/api/v1/characters/world-books/{world_book_id}/entries",
        headers=headers,
        json={
            "keywords": [keyword_two],
            "content": f"Entry two content {suffix}.",
            "priority": 0,
            "enabled": True,
        },
    )
    _require_ok(entry_two_resp, "create world book entry two")
    entry_two_id = entry_two_resp.json()["id"]

    entries_resp = page.request.get(
        f"/api/v1/characters/world-books/{world_book_id}/entries",
        headers=headers,
    )
    _require_ok(entries_resp, "list world book entries")
    entries_payload = entries_resp.json()
    entry_ids = {item.get("id") for item in entries_payload.get("entries", [])}
    assert entry_one_id in entry_ids
    assert entry_two_id in entry_ids

    updated_content = f"Entry one updated {suffix}."
    update_entry_resp = page.request.put(
        f"/api/v1/characters/world-books/entries/{entry_one_id}",
        headers=headers,
        json={"content": updated_content, "priority": 2},
    )
    _require_ok(update_entry_resp, "update world book entry")
    assert update_entry_resp.json()["content"] == updated_content

    bulk_resp = page.request.post(
        "/api/v1/characters/world-books/entries/bulk",
        headers=headers,
        json={
            "entry_ids": [entry_two_id],
            "operation": "set_priority",
            "priority": 3,
        },
    )
    _require_ok(bulk_resp, "bulk update entries")
    bulk_payload = bulk_resp.json()
    assert bulk_payload.get("success") is True
    assert bulk_payload.get("affected_count") == 1

    attach_resp = page.request.post(
        f"/api/v1/characters/{character_id}/world-books",
        headers=headers,
        json={"world_book_id": world_book_id, "enabled": True, "priority": 1},
    )
    _require_ok(attach_resp, "attach world book to character")
    assert attach_resp.json().get("world_book_id") == world_book_id

    char_books_resp = page.request.get(
        f"/api/v1/characters/{character_id}/world-books",
        headers=headers,
        params={"enabled_only": "true"},
    )
    _require_ok(char_books_resp, "list character world books")
    assert any(item.get("world_book_id") == world_book_id for item in char_books_resp.json())

    process_resp = page.request.post(
        "/api/v1/characters/world-books/process",
        headers=headers,
        json={
            "text": f"Context mentions {keyword_one}.",
            "character_id": character_id,
        },
    )
    _require_ok(process_resp, "process context")
    process_payload = process_resp.json()
    assert process_payload.get("entries_matched", 0) >= 1
    assert updated_content in process_payload.get("injected_content", "")

    export_resp = page.request.get(
        f"/api/v1/characters/world-books/{world_book_id}/export",
        headers=headers,
    )
    _require_ok(export_resp, "export world book")
    export_payload = export_resp.json()
    assert export_payload.get("world_book", {}).get("name") == world_book["name"]
    assert len(export_payload.get("entries", [])) >= 2

    stats_resp = page.request.get(
        f"/api/v1/characters/world-books/{world_book_id}/statistics",
        headers=headers,
    )
    _require_ok(stats_resp, "world book statistics")
    stats_payload = stats_resp.json()
    assert stats_payload.get("total_entries", 0) >= 2

    detach_resp = page.request.delete(
        f"/api/v1/characters/{character_id}/world-books/{world_book_id}",
        headers=headers,
    )
    _require_ok(detach_resp, "detach world book")

    delete_entry_one_resp = page.request.delete(
        f"/api/v1/characters/world-books/entries/{entry_one_id}",
        headers=headers,
    )
    _require_ok(delete_entry_one_resp, "delete entry one")

    delete_entry_two_resp = page.request.delete(
        f"/api/v1/characters/world-books/entries/{entry_two_id}",
        headers=headers,
    )
    _require_ok(delete_entry_two_resp, "delete entry two")

    delete_world_book_resp = page.request.delete(
        f"/api/v1/characters/world-books/{world_book_id}",
        headers=headers,
        params={"hard_delete": "true"},
    )
    _require_ok(delete_world_book_resp, "delete world book")

    character_fresh_resp = page.request.get(f"/api/v1/characters/{character_id}", headers=headers)
    _require_ok(character_fresh_resp, "get character for delete")
    character_version = character_fresh_resp.json()["version"]

    delete_char_resp = page.request.delete(
        f"/api/v1/characters/{character_id}",
        headers=headers,
        params={"expected_version": character_version},
    )
    _require_ok(delete_char_resp, "delete character")
