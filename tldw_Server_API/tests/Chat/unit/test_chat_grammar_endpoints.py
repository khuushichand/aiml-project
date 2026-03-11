from __future__ import annotations

import pytest
from fastapi import HTTPException

from tldw_Server_API.app.api.v1.endpoints import chat as chat_endpoints
from tldw_Server_API.app.api.v1.endpoints import chat_grammars as chat_grammar_endpoints
from tldw_Server_API.app.api.v1.schemas.chat_grammar_schemas import (
    ChatGrammarCreate,
    ChatGrammarUpdate,
)
from tldw_Server_API.app.core.Character_Chat.chat_grammar import ChatGrammarService
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


@pytest.fixture()
def chacha_db(tmp_path):
    db_path = tmp_path / "ChaChaNotes.db"
    db = CharactersRAGDB(db_path=str(db_path), client_id="test-client")
    try:
        yield db
    finally:
        db.close_connection()


def test_chat_grammar_router_exposes_expected_paths():
    paths = {route.path for route in chat_grammar_endpoints.router.routes}
    assert "/grammars" in paths
    assert "/grammars/{grammar_id}" in paths


def test_chat_grammar_route_handlers_have_docstrings():
    handlers = (
        chat_grammar_endpoints.create_chat_grammar,
        chat_grammar_endpoints.list_chat_grammars,
        chat_grammar_endpoints.get_chat_grammar,
        chat_grammar_endpoints.update_chat_grammar,
        chat_grammar_endpoints.delete_chat_grammar,
    )

    for handler in handlers:
        assert handler.__doc__


@pytest.mark.asyncio
async def test_create_and_list_chat_grammars(chacha_db: CharactersRAGDB):
    created = await chat_endpoints.create_chat_grammar(
        ChatGrammarCreate(name="Root", description="desc", grammar_text='root ::= "ok"'),
        db=chacha_db,
    )
    assert created.name == "Root"

    listing = await chat_endpoints.list_chat_grammars(
        include_archived=False,
        limit=100,
        offset=0,
        db=chacha_db,
    )
    assert listing.total == 1
    assert listing.items[0].id == created.id


@pytest.mark.asyncio
async def test_get_archived_grammar_requires_include_archived(chacha_db: CharactersRAGDB):
    service = ChatGrammarService(chacha_db)
    grammar_id = service.create_grammar(
        name="Archived Grammar",
        description="desc",
        grammar_text='root ::= "archived"',
    )
    service.archive_grammar(grammar_id)

    with pytest.raises(HTTPException) as excinfo:
        await chat_endpoints.get_chat_grammar(grammar_id, include_archived=False, db=chacha_db)
    assert excinfo.value.status_code == 404

    archived = await chat_endpoints.get_chat_grammar(
        grammar_id,
        include_archived=True,
        db=chacha_db,
    )
    assert archived.id == grammar_id
    assert archived.is_archived is True


@pytest.mark.asyncio
async def test_update_chat_grammar_returns_refreshed_record(chacha_db: CharactersRAGDB):
    created = await chat_endpoints.create_chat_grammar(
        ChatGrammarCreate(
            name="Versioned Grammar",
            description="v1",
            grammar_text='root ::= "v1"',
        ),
        db=chacha_db,
    )

    updated = await chat_endpoints.update_chat_grammar(
        created.id,
        ChatGrammarUpdate(description="v2", grammar_text='root ::= "v2"'),
        db=chacha_db,
    )

    assert updated.description == "v2"
    assert updated.grammar_text == 'root ::= "v2"'
    assert updated.version == created.version + 1


@pytest.mark.asyncio
async def test_delete_chat_grammar_hides_record_from_default_reads(chacha_db: CharactersRAGDB):
    created = await chat_endpoints.create_chat_grammar(
        ChatGrammarCreate(
            name="Delete Grammar",
            description="desc",
            grammar_text='root ::= "delete"',
        ),
        db=chacha_db,
    )

    response = await chat_endpoints.delete_chat_grammar(created.id, db=chacha_db)
    assert response.status_code == 204

    with pytest.raises(HTTPException) as excinfo:
        await chat_endpoints.get_chat_grammar(created.id, include_archived=False, db=chacha_db)
    assert excinfo.value.status_code == 404
