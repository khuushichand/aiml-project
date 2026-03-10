"""
Unit tests for ChatGrammarService.

Tests the llama.cpp grammar-library persistence service against the real
per-user ChaChaNotes database.
"""

import pytest

from tldw_Server_API.app.core.Character_Chat.chat_grammar import ChatGrammarService
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import ConflictError


class TestChatGrammarService:
    """Test grammar-library CRUD operations."""

    @pytest.mark.unit
    def test_chat_grammar_service_creates_and_reads_grammar(self, character_db):
        service = ChatGrammarService(character_db)

        grammar_id = service.create_grammar(
            name="JSON Root",
            description="Simple test grammar",
            grammar_text='root ::= "ok"',
        )

        grammar = service.get_grammar(grammar_id)

        assert grammar is not None
        assert grammar["id"] == grammar_id
        assert grammar["name"] == "JSON Root"
        assert grammar["validation_status"] == "unchecked"

    @pytest.mark.unit
    def test_chat_grammar_service_archives_without_deleting_text(self, character_db):
        service = ChatGrammarService(character_db)

        grammar_id = service.create_grammar(
            name="Archive Me",
            description="",
            grammar_text='root ::= "x"',
        )

        service.archive_grammar(grammar_id)

        grammar = service.get_grammar(grammar_id, include_archived=True)

        assert grammar is not None
        assert grammar["is_archived"] is True
        assert grammar["grammar_text"] == 'root ::= "x"'

    @pytest.mark.unit
    def test_chat_grammar_service_lists_active_grammars_by_default(self, character_db):
        service = ChatGrammarService(character_db)

        active_id = service.create_grammar(
            name="Active Grammar",
            description="",
            grammar_text='root ::= "active"',
        )
        archived_id = service.create_grammar(
            name="Archived Grammar",
            description="",
            grammar_text='root ::= "archived"',
        )
        service.archive_grammar(archived_id)

        grammars = service.list_grammars()

        assert [grammar["id"] for grammar in grammars] == [active_id]

    @pytest.mark.unit
    def test_chat_grammar_service_updates_grammar_and_bumps_version(self, character_db):
        service = ChatGrammarService(character_db)

        grammar_id = service.create_grammar(
            name="Versioned Grammar",
            description="v1",
            grammar_text='root ::= "v1"',
        )
        created = service.get_grammar(grammar_id)

        updated = service.update_grammar(
            grammar_id,
            {
                "description": "v2",
                "grammar_text": 'root ::= "v2"',
            },
            expected_version=created["version"],
        )

        assert updated["description"] == "v2"
        assert updated["grammar_text"] == 'root ::= "v2"'
        assert updated["version"] == created["version"] + 1

    @pytest.mark.unit
    def test_chat_grammar_service_rejects_stale_update_version(self, character_db):
        service = ChatGrammarService(character_db)

        grammar_id = service.create_grammar(
            name="Conflicted Grammar",
            description="v1",
            grammar_text='root ::= "v1"',
        )
        created = service.get_grammar(grammar_id)

        service.update_grammar(
            grammar_id,
            {"description": "v2"},
            expected_version=created["version"],
        )

        with pytest.raises(ConflictError, match="Version mismatch"):
            service.update_grammar(
                grammar_id,
                {"description": "v3"},
                expected_version=created["version"],
            )

    @pytest.mark.unit
    def test_chat_grammar_service_rejects_duplicate_names(self, character_db):
        service = ChatGrammarService(character_db)

        service.create_grammar(
            name="Duplicate Grammar",
            description="first",
            grammar_text='root ::= "first"',
        )

        with pytest.raises(ConflictError, match="already exists"):
            service.create_grammar(
                name="Duplicate Grammar",
                description="second",
                grammar_text='root ::= "second"',
            )

    @pytest.mark.unit
    def test_chat_grammar_service_soft_deletes_grammar(self, character_db):
        service = ChatGrammarService(character_db)

        grammar_id = service.create_grammar(
            name="Delete Me",
            description="",
            grammar_text='root ::= "gone"',
        )

        service.delete_grammar(grammar_id)

        assert service.get_grammar(grammar_id) is None
        deleted = service.get_grammar(grammar_id, include_deleted=True, include_archived=True)
        assert deleted is not None
        assert deleted["deleted"] is True
