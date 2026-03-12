from collections.abc import Iterator
from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.VoiceAssistant.db_helpers import (
    get_user_voice_commands,
    get_voice_command,
    save_voice_command,
)
from tldw_Server_API.app.core.VoiceAssistant.schemas import ActionType, VoiceCommand


pytestmark = pytest.mark.unit


@pytest.fixture
def db_instance(tmp_path: Path) -> Iterator[CharactersRAGDB]:
    db = CharactersRAGDB(tmp_path / "persona_voice_command_persistence.sqlite", "persona-voice-command-tests")
    yield db
    db.close_connection()


def test_voice_command_roundtrip_preserves_persona_and_connection(db_instance: CharactersRAGDB):
    command = VoiceCommand(
        id="cmd-builder-search",
        user_id=1,
        persona_id="builder_bot",
        connection_id="conn-search",
        name="Search notes",
        phrases=["search notes for {topic}"],
        action_type=ActionType.MCP_TOOL,
        action_config={"tool_name": "notes.search"},
        priority=10,
        enabled=True,
        requires_confirmation=False,
        description="Find notes by topic",
    )

    save_voice_command(db_instance, command)

    persisted = get_voice_command(
        db_instance,
        "cmd-builder-search",
        user_id=1,
        persona_id="builder_bot",
    )
    assert persisted is not None
    assert persisted.persona_id == "builder_bot"
    assert persisted.connection_id == "conn-search"


def test_get_voice_command_persona_filter_blocks_other_persona(db_instance: CharactersRAGDB):
    save_voice_command(
        db_instance,
        VoiceCommand(
            id="cmd-persona-a",
            user_id=1,
            persona_id="persona-a",
            name="Persona A command",
            phrases=["alpha"],
            action_type=ActionType.LLM_CHAT,
            action_config={},
        ),
    )

    persisted = get_voice_command(
        db_instance,
        "cmd-persona-a",
        user_id=1,
        persona_id="persona-b",
    )

    assert persisted is None


def test_get_user_voice_commands_filters_by_persona_without_legacy_leakage(
    db_instance: CharactersRAGDB,
):
    save_voice_command(
        db_instance,
        VoiceCommand(
            id="cmd-a",
            user_id=1,
            persona_id="persona-a",
            name="Persona A command",
            phrases=["open alpha"],
            action_type=ActionType.LLM_CHAT,
            action_config={},
            priority=20,
        ),
    )
    save_voice_command(
        db_instance,
        VoiceCommand(
            id="cmd-b",
            user_id=1,
            persona_id="persona-b",
            name="Persona B command",
            phrases=["open beta"],
            action_type=ActionType.LLM_CHAT,
            action_config={},
            priority=10,
        ),
    )
    save_voice_command(
        db_instance,
        VoiceCommand(
            id="cmd-legacy",
            user_id=1,
            name="Legacy command",
            phrases=["open legacy"],
            action_type=ActionType.LLM_CHAT,
            action_config={},
            priority=30,
        ),
    )

    filtered = get_user_voice_commands(
        db_instance,
        user_id=1,
        include_system=False,
        enabled_only=False,
        persona_id="persona-a",
    )

    assert [command.id for command in filtered] == ["cmd-a"]
