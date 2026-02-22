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
