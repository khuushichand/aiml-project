from collections.abc import Iterator
from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.tests.Characters.test_character_functionality_db import sample_card_data


pytestmark = pytest.mark.unit


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "conversation_character_scope.sqlite"


@pytest.fixture
def db_instance(db_path: Path) -> Iterator[CharactersRAGDB]:
    db = CharactersRAGDB(db_path, "character-scope-test-client")
    yield db
    db.close_connection()


def _create_conversation(
    db: CharactersRAGDB,
    conversation_id: str,
    *,
    title: str,
    character_id: int | None,
) -> str:
    payload = {
        "id": conversation_id,
        "root_id": conversation_id,
        "character_id": character_id,
        "title": title,
        "client_id": db.client_id,
    }
    if character_id is None:
        payload["assistant_kind"] = "persona"
        payload["assistant_id"] = f"persona-{conversation_id}"
        payload["persona_memory_mode"] = "read_only"
    return db.add_conversation(payload)


def test_get_and_count_conversations_for_user_filter_character_scope(
    db_instance: CharactersRAGDB,
) -> None:
    character_id = db_instance.add_character_card(sample_card_data(name="Scope Source"))

    character_conv = _create_conversation(
        db_instance,
        "conv-character",
        title="Character chat",
        character_id=character_id,
    )
    plain_conv = _create_conversation(
        db_instance,
        "conv-plain",
        title="Plain chat",
        character_id=None,
    )

    character_rows = db_instance.get_conversations_for_user(
        db_instance.client_id,
        character_scope="character",
    )
    non_character_rows = db_instance.get_conversations_for_user(
        db_instance.client_id,
        character_scope="non_character",
    )

    assert [row["id"] for row in character_rows] == [character_conv]
    assert [row["id"] for row in non_character_rows] == [plain_conv]
    assert (
        db_instance.count_conversations_for_user(
            db_instance.client_id,
            character_scope="character",
        )
        == 1
    )
    assert (
        db_instance.count_conversations_for_user(
            db_instance.client_id,
            character_scope="non_character",
        )
        == 1
    )


def test_search_conversations_filters_character_scope(
    db_instance: CharactersRAGDB,
) -> None:
    character_id = db_instance.add_character_card(sample_card_data(name="Search Scope Source"))

    _create_conversation(
        db_instance,
        "quota-character",
        title="Quota review",
        character_id=character_id,
    )
    _create_conversation(
        db_instance,
        "quota-plain",
        title="Quota review",
        character_id=None,
    )

    character_rows = db_instance.search_conversations(
        "Quota",
        client_id=db_instance.client_id,
        character_scope="character",
    )
    non_character_rows = db_instance.search_conversations(
        "Quota",
        client_id=db_instance.client_id,
        character_scope="non_character",
    )

    assert [row["id"] for row in character_rows] == ["quota-character"]
    assert [row["id"] for row in non_character_rows] == ["quota-plain"]
