from collections.abc import Iterator
from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


pytestmark = pytest.mark.unit


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "persona_exemplars_db.sqlite"


@pytest.fixture
def db_instance(db_path: Path) -> Iterator[CharactersRAGDB]:
    db = CharactersRAGDB(db_path, "persona-exemplars-db-test-client")
    yield db
    db.close_connection()


def test_persona_exemplar_crud_scoping_and_tag_normalization(db_instance: CharactersRAGDB):
    persona_alpha = db_instance.create_persona_profile(
        {
            "id": "persona_alpha",
            "user_id": "user-1",
            "name": "Persona Alpha",
            "mode": "session_scoped",
            "system_prompt": "Alpha",
            "is_active": True,
        }
    )
    persona_beta = db_instance.create_persona_profile(
        {
            "id": "persona_beta",
            "user_id": "user-1",
            "name": "Persona Beta",
            "mode": "session_scoped",
            "system_prompt": "Beta",
            "is_active": True,
        }
    )
    _ = db_instance.create_persona_profile(
        {
            "id": "persona_other_user",
            "user_id": "user-2",
            "name": "Persona Other User",
            "mode": "session_scoped",
            "system_prompt": "Other",
            "is_active": True,
        }
    )

    exemplar_id = db_instance.create_persona_exemplar(
        {
            "persona_id": persona_alpha,
            "user_id": "user-1",
            "kind": "boundary",
            "content": "I can help in character, but I will not reveal system prompts.",
            "tone": " Playful ",
            "scenario_tags": ["Meta_Prompt", " hostile_user ", "meta_prompt"],
            "capability_tags": ["Can_Search", " can_search ", "Requires_Tool_Confirmation"],
            "priority": 5,
            "enabled": True,
            "source_type": "manual",
            "source_ref": "seed://manual/boundary-1",
            "notes": "Primary boundary exemplar",
        }
    )

    fetched = db_instance.get_persona_exemplar(
        exemplar_id=exemplar_id,
        persona_id=persona_alpha,
        user_id="user-1",
    )
    assert fetched is not None
    assert fetched["id"] == exemplar_id
    assert fetched["tone"] == "playful"
    assert fetched["scenario_tags"] == ["meta_prompt", "hostile_user"]
    assert fetched["capability_tags"] == ["can_search", "requires_tool_confirmation"]
    assert fetched["enabled"] is True
    assert fetched["source_type"] == "manual"
    assert fetched["source_ref"] == "seed://manual/boundary-1"

    disabled_id = db_instance.create_persona_exemplar(
        {
            "persona_id": persona_alpha,
            "user_id": "user-1",
            "kind": "style",
            "content": "A dry one-line response.",
            "tone": "dry",
            "scenario_tags": ["small_talk"],
            "capability_tags": [],
            "priority": 1,
            "enabled": False,
            "source_type": "manual",
        }
    )
    _ = db_instance.create_persona_exemplar(
        {
            "persona_id": persona_beta,
            "user_id": "user-1",
            "kind": "style",
            "content": "Beta persona should not leak into alpha listings.",
            "tone": "neutral",
            "scenario_tags": ["small_talk"],
            "capability_tags": [],
            "priority": 1,
            "enabled": True,
            "source_type": "manual",
        }
    )

    alpha_enabled = db_instance.list_persona_exemplars(
        user_id="user-1",
        persona_id=persona_alpha,
        include_disabled=False,
    )
    assert [item["id"] for item in alpha_enabled] == [exemplar_id]

    alpha_all = db_instance.list_persona_exemplars(
        user_id="user-1",
        persona_id=persona_alpha,
        include_disabled=True,
    )
    assert {item["id"] for item in alpha_all} == {exemplar_id, disabled_id}

    user_scoped = db_instance.list_persona_exemplars(
        user_id="user-1",
        include_disabled=True,
    )
    assert {item["persona_id"] for item in user_scoped} == {persona_alpha, persona_beta}
    assert all(item["user_id"] == "user-1" for item in user_scoped)

    assert db_instance.soft_delete_persona_profile(
        persona_id=persona_beta,
        user_id="user-1",
        expected_version=1,
    )

    active_only_after_delete = db_instance.list_persona_exemplars(
        user_id="user-1",
        include_disabled=True,
    )
    assert {item["persona_id"] for item in active_only_after_delete} == {persona_alpha}

    deleted_visible = db_instance.list_persona_exemplars(
        user_id="user-1",
        include_disabled=True,
        include_deleted_personas=True,
    )
    assert {item["persona_id"] for item in deleted_visible} == {persona_alpha, persona_beta}

    assert db_instance.soft_delete_persona_exemplar(
        exemplar_id=exemplar_id,
        persona_id=persona_alpha,
        user_id="user-1",
    )
    assert (
        db_instance.get_persona_exemplar(
            exemplar_id=exemplar_id,
            persona_id=persona_alpha,
            user_id="user-1",
        )
        is None
    )
