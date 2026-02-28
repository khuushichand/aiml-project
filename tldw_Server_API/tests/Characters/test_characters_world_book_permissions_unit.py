from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.tests.Characters._ml_import_stubs import stub_heavy_ml_imports

stub_heavy_ml_imports()

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.api.v1.endpoints import characters_endpoint as characters_api_module
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDBError


CHARACTERS_ENDPOINT_PREFIX = "/api/v1/characters"
UNIT_TEST_PATCH_PREFIX = "tldw_Server_API.app.api.v1.endpoints.characters_endpoint"


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(characters_api_module.router, prefix=CHARACTERS_ENDPOINT_PREFIX)
    app.dependency_overrides[get_chacha_db_for_user] = lambda: MagicMock()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@patch(f"{UNIT_TEST_PATCH_PREFIX}.WorldBookService")
@patch(f"{UNIT_TEST_PATCH_PREFIX}.get_character_details")
def test_attach_world_book_permission_denied_maps_to_403(
    mock_get_character_details: MagicMock,
    mock_world_book_service: MagicMock,
    client: TestClient,
):
    mock_get_character_details.return_value = {"id": 1, "name": "Permission Char"}
    service = mock_world_book_service.return_value
    service.get_world_book.return_value = {"id": 9, "name": "Restricted Book"}
    service.attach_to_character.side_effect = CharactersRAGDBError("permission denied")

    response = client.post(
        f"{CHARACTERS_ENDPOINT_PREFIX}/1/world-books",
        json={"world_book_id": 9, "enabled": True, "priority": 0},
    )

    assert response.status_code == 403, response.text
    assert "Insufficient permissions" in response.json()["detail"]


@patch(f"{UNIT_TEST_PATCH_PREFIX}.WorldBookService")
def test_detach_world_book_permission_denied_maps_to_403(
    mock_world_book_service: MagicMock,
    client: TestClient,
):
    service = mock_world_book_service.return_value
    service.detach_from_character.side_effect = CharactersRAGDBError("forbidden")

    response = client.delete(f"{CHARACTERS_ENDPOINT_PREFIX}/1/world-books/9")

    assert response.status_code == 403, response.text
    assert "Insufficient permissions" in response.json()["detail"]


@patch(f"{UNIT_TEST_PATCH_PREFIX}.WorldBookService")
@patch(f"{UNIT_TEST_PATCH_PREFIX}.get_character_details")
def test_list_character_world_books_permission_denied_maps_to_403(
    mock_get_character_details: MagicMock,
    mock_world_book_service: MagicMock,
    client: TestClient,
):
    mock_get_character_details.return_value = {"id": 1, "name": "Permission Char"}
    service = mock_world_book_service.return_value
    service.get_character_world_books.side_effect = CharactersRAGDBError("insufficient privilege")

    response = client.get(f"{CHARACTERS_ENDPOINT_PREFIX}/1/world-books")

    assert response.status_code == 403, response.text
    assert "Insufficient permissions" in response.json()["detail"]


@patch(f"{UNIT_TEST_PATCH_PREFIX}.WorldBookService")
def test_list_world_books_uses_bulk_entry_count_lookup(
    mock_world_book_service: MagicMock,
    client: TestClient,
):
    now = datetime.now(timezone.utc)
    service = mock_world_book_service.return_value
    service.list_world_books.return_value = [
        {
            "id": 11,
            "name": "Lore A",
            "description": "Book A",
            "scan_depth": 3,
            "token_budget": 500,
            "recursive_scanning": False,
            "enabled": True,
            "created_at": now,
            "last_modified": now,
            "version": 1,
        },
        {
            "id": 12,
            "name": "Lore B",
            "description": "Book B",
            "scan_depth": 4,
            "token_budget": 600,
            "recursive_scanning": True,
            "enabled": True,
            "created_at": now,
            "last_modified": now,
            "version": 2,
        },
    ]
    service.get_entry_counts_for_world_books.return_value = {11: 3, 12: 7}

    response = client.get(f"{CHARACTERS_ENDPOINT_PREFIX}/world-books")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 2
    by_id = {int(item["id"]): item for item in payload["world_books"]}
    assert by_id[11]["entry_count"] == 3
    assert by_id[12]["entry_count"] == 7
    service.get_entry_counts_for_world_books.assert_called_once_with([11, 12])


@patch(f"{UNIT_TEST_PATCH_PREFIX}.WorldBookService")
@patch(f"{UNIT_TEST_PATCH_PREFIX}.get_character_details")
def test_list_character_world_books_uses_bulk_entry_count_lookup(
    mock_get_character_details: MagicMock,
    mock_world_book_service: MagicMock,
    client: TestClient,
):
    now = datetime.now(timezone.utc)
    mock_get_character_details.return_value = {"id": 1, "name": "Permission Char"}
    service = mock_world_book_service.return_value
    service.get_character_world_books.return_value = [
        {
            "id": 9,
            "name": "Attached Lore",
            "description": "Attached",
            "scan_depth": 3,
            "token_budget": 400,
            "recursive_scanning": False,
            "enabled": True,
            "created_at": now,
            "last_modified": now,
            "version": 1,
            "attachment_enabled": True,
            "attachment_priority": 5,
        }
    ]
    service.get_entry_counts_for_world_books.return_value = {9: 2}

    response = client.get(f"{CHARACTERS_ENDPOINT_PREFIX}/1/world-books")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["world_book_id"] == 9
    assert payload[0]["entry_count"] == 2
    service.get_entry_counts_for_world_books.assert_called_once_with([9])


@patch(f"{UNIT_TEST_PATCH_PREFIX}.WorldBookService")
def test_add_world_book_entry_accepts_recursive_scanning_flag(
    mock_world_book_service: MagicMock,
    client: TestClient,
):
    now = datetime.now(timezone.utc)
    service = mock_world_book_service.return_value
    service.get_world_book.return_value = {
        "id": 9,
        "name": "Lore",
        "created_at": now,
        "last_modified": now,
    }
    service.add_entry.return_value = 99
    service.get_entry.return_value = {
        "id": 99,
        "world_book_id": 9,
        "keywords": ["hero"],
        "content": "Hero lore",
        "recursive_scanning": True,
        "priority": 10,
        "enabled": True,
        "case_sensitive": False,
        "regex_match": False,
        "whole_word_match": True,
        "metadata": {"recursive_scanning": True},
    }

    response = client.post(
        f"{CHARACTERS_ENDPOINT_PREFIX}/world-books/9/entries",
        json={
            "keywords": ["hero"],
            "content": "Hero lore",
            "recursive_scanning": True,
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["recursive_scanning"] is True
    add_call = service.add_entry.call_args.kwargs
    assert add_call["metadata"]["recursive_scanning"] is True
    service.get_entry.assert_called_once_with(99)
    service.get_entries.assert_not_called()


@patch(f"{UNIT_TEST_PATCH_PREFIX}.WorldBookService")
def test_list_world_book_entries_passes_server_side_filters(
    mock_world_book_service: MagicMock,
    client: TestClient,
):
    now = datetime.now(timezone.utc)
    service = mock_world_book_service.return_value
    service.get_world_book.return_value = {
        "id": 9,
        "name": "Lore",
        "created_at": now,
        "last_modified": now,
    }
    service.get_entries.return_value = [
        {
            "id": 42,
            "world_book_id": 9,
            "keywords": ["hero"],
            "content": "Hero lore",
            "group": "Characters",
            "appendable": True,
            "recursive_scanning": False,
            "priority": 10,
            "enabled": True,
            "case_sensitive": False,
            "regex_match": False,
            "whole_word_match": True,
            "metadata": {"group": "Characters", "appendable": True},
        }
    ]

    response = client.get(
        f"{CHARACTERS_ENDPOINT_PREFIX}/world-books/9/entries",
        params={
            "group": "Characters",
            "appendable": "true",
            "recursive_scanning": "false",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 1
    assert payload["entries"][0]["id"] == 42
    service.get_entries.assert_called_once_with(
        9,
        enabled_only=False,
        group="Characters",
        appendable=True,
        recursive_scanning=False,
    )


@patch(f"{UNIT_TEST_PATCH_PREFIX}.WorldBookService")
def test_add_world_book_entry_prefers_entry_timestamps_when_available(
    mock_world_book_service: MagicMock,
    client: TestClient,
):
    now = datetime(2026, 2, 1, 8, 0, tzinfo=timezone.utc)
    entry_created = datetime(2026, 2, 2, 9, 15, tzinfo=timezone.utc)
    entry_modified = datetime(2026, 2, 3, 10, 30, tzinfo=timezone.utc)
    service = mock_world_book_service.return_value
    service.get_world_book.return_value = {
        "id": 9,
        "name": "Lore",
        "created_at": now,
        "last_modified": now,
    }
    service.add_entry.return_value = 100
    service.get_entry.return_value = {
        "id": 100,
        "world_book_id": 9,
        "keywords": ["hero"],
        "content": "Hero lore",
        "priority": 10,
        "enabled": True,
        "case_sensitive": False,
        "regex_match": False,
        "whole_word_match": True,
        "metadata": {},
        "created_at": entry_created,
        "last_modified": entry_modified,
    }

    response = client.post(
        f"{CHARACTERS_ENDPOINT_PREFIX}/world-books/9/entries",
        json={
            "keywords": ["hero"],
            "content": "Hero lore",
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["created_at"].startswith("2026-02-02T09:15:00")
    assert payload["last_modified"].startswith("2026-02-03T10:30:00")


@patch(f"{UNIT_TEST_PATCH_PREFIX}.WorldBookService")
def test_update_world_book_entry_accepts_recursive_scanning_flag(
    mock_world_book_service: MagicMock,
    client: TestClient,
):
    now = datetime.now(timezone.utc)
    service = mock_world_book_service.return_value
    service.update_entry.return_value = True
    service.get_entry.side_effect = [
        {
            "id": 99,
            "world_book_id": 9,
            "keywords": ["hero"],
            "content": "Hero lore",
            "priority": 10,
            "enabled": True,
            "case_sensitive": False,
            "regex_match": False,
            "whole_word_match": True,
            "metadata": {"group": "main"},
        },
        {
            "id": 99,
            "world_book_id": 9,
            "keywords": ["hero"],
            "content": "Hero lore",
            "recursive_scanning": True,
            "priority": 10,
            "enabled": True,
            "case_sensitive": False,
            "regex_match": False,
            "whole_word_match": True,
            "metadata": {"group": "main", "recursive_scanning": True},
        },
    ]
    service.get_world_book.return_value = {
        "id": 9,
        "name": "Lore",
        "created_at": now,
        "last_modified": now,
    }

    response = client.put(
        f"{CHARACTERS_ENDPOINT_PREFIX}/world-books/entries/99",
        json={"recursive_scanning": True},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["recursive_scanning"] is True
    update_call = service.update_entry.call_args.kwargs
    assert update_call["metadata"]["recursive_scanning"] is True
    assert service.get_entry.call_count == 2
    service.get_entries.assert_not_called()
