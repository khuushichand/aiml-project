from __future__ import annotations

import datetime

import pytest

from tldw_Server_API.app.api.v1.endpoints import chat as chat_endpoints
from tldw_Server_API.app.api.v1.schemas.chat_dictionary_schemas import (
    DictionaryEntryCreate,
    DictionaryEntryUpdate,
)
from tldw_Server_API.app.core.Character_Chat.chat_dictionary import ChatDictionaryService
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


@pytest.fixture()
def chacha_db(tmp_path):
    db_path = tmp_path / "ChaChaNotes.db"
    db = CharactersRAGDB(db_path=str(db_path), client_id="test-client")
    try:
        yield db
    finally:
        db.close_connection()


@pytest.mark.asyncio
async def test_add_dictionary_entry_returns_persisted_fields(chacha_db: CharactersRAGDB):
    service = ChatDictionaryService(chacha_db)
    dictionary_id = service.create_dictionary("Test Dictionary", "Description")

    entry_create = DictionaryEntryCreate(pattern="hello", replacement="world")
    response = await chat_endpoints.add_dictionary_entry(dictionary_id, entry_create, db=chacha_db)

    assert response.dictionary_id == dictionary_id
    assert response.pattern == "hello"
    assert response.replacement == "world"
    assert isinstance(response.created_at, datetime.datetime)
    assert isinstance(response.updated_at, datetime.datetime)

    stored_entries = service.get_entries(dictionary_id=dictionary_id, active_only=False)
    assert len(stored_entries) == 1
    stored_entry = stored_entries[0]
    assert stored_entry["id"] == response.id
    assert stored_entry["pattern"] == "hello"
    assert stored_entry["replacement"] == "world"


@pytest.mark.asyncio
async def test_get_chat_dictionary_includes_entry_metadata(chacha_db: CharactersRAGDB):
    service = ChatDictionaryService(chacha_db)
    dictionary_id = service.create_dictionary("Metadata Dictionary", "desc")
    service.add_entry(
        dictionary_id,
        pattern="foo",
        replacement="bar",
        probability=0.5,
        group="group-a",
    )

    response = await chat_endpoints.get_chat_dictionary(dictionary_id, db=chacha_db)

    assert response.id == dictionary_id
    assert response.entry_count == 1
    assert len(response.entries) == 1
    entry = response.entries[0]
    assert entry.pattern == "foo"
    assert entry.replacement == "bar"
    assert isinstance(entry.created_at, datetime.datetime)
    assert isinstance(entry.updated_at, datetime.datetime)


@pytest.mark.asyncio
async def test_update_dictionary_entry_returns_latest_state(chacha_db: CharactersRAGDB):
    service = ChatDictionaryService(chacha_db)
    dictionary_id = service.create_dictionary("Update Dictionary", None)
    entry_id = service.add_entry(dictionary_id, pattern="key", replacement="value")

    response = await chat_endpoints.update_dictionary_entry(
        entry_id,
        DictionaryEntryUpdate(group="updated-group", enabled=False, case_sensitive=False),
        db=chacha_db,
    )

    assert response.id == entry_id
    assert response.dictionary_id == dictionary_id
    assert response.group == "updated-group"
    assert response.enabled is False
    assert response.case_sensitive is False
    assert isinstance(response.updated_at, datetime.datetime)


@pytest.mark.asyncio
async def test_list_chat_dictionaries_counts_inactive_entries(chacha_db: CharactersRAGDB):
    service = ChatDictionaryService(chacha_db)
    dictionary_id = service.create_dictionary("Inactive Dictionary", None)
    service.add_entry(dictionary_id, pattern="alpha", replacement="beta")
    service.update_dictionary(dictionary_id, is_active=False)

    response = await chat_endpoints.list_chat_dictionaries(include_inactive=True, db=chacha_db)

    # list_chat_dictionaries returns ChatDictionaryResponse models
    dictionaries = {d.id: d for d in response.dictionaries}
    assert dictionary_id in dictionaries
    dict_payload = dictionaries[dictionary_id]
    assert dict_payload.is_active is False
    assert dict_payload.entry_count == 1
