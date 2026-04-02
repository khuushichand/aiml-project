import json

import pytest

from tldw_Server_API.app.core.Slides.slides_db import ConflictError, SlidesDatabase
from tldw_Server_API.app.core.Slides.visual_styles import list_builtin_visual_styles
from tldw_Server_API.app.core.Slides.visual_style_catalog import (
    get_builtin_visual_style_definition,
    list_builtin_visual_style_definitions,
)
from tldw_Server_API.app.core.Slides.visual_style_packs import get_visual_style_pack
from tldw_Server_API.app.core.Slides.visual_style_profiles import (
    VisualStyleProfile,
    _index_visual_style_profiles,
)


def test_slides_db_initializes_visual_styles_table(tmp_path):
    db_path = tmp_path / "Slides.db"
    db = SlidesDatabase(db_path=db_path, client_id="tester")
    try:
        conn = db.get_connection()
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        db.close_connection()

    assert "visual_styles" in tables


def test_visual_style_registry_includes_expected_builtins():
    styles = list_builtin_visual_styles()
    style_ids = [style.style_id for style in styles]

    assert len(styles) == 44
    assert len(style_ids) == len(set(style_ids))
    assert "timeline" in style_ids
    assert "exam-focused-bullet" in style_ids
    assert "notebooklm-chalkboard" in style_ids
    assert "notebooklm-blueprint" in style_ids
    assert "notebooklm-swiss-design" in style_ids
    assert "notebooklm-brutalist-design" in style_ids


def test_visual_style_registry_returns_defensive_copies():
    definition = get_builtin_visual_style_definition("notebooklm-whiteboard")
    assert definition is not None
    definition.appearance_overrides["token_overrides"]["surface"] = "#000000"
    definition.generation_rules["instructional_bias"] = "low"

    pack = get_visual_style_pack("hand_drawn_surface")
    assert pack is not None
    pack.default_token_overrides["surface"] = "#000000"

    fresh_definition = get_builtin_visual_style_definition("notebooklm-whiteboard")
    fresh_pack = get_visual_style_pack("hand_drawn_surface")
    assert fresh_definition is not None
    assert fresh_pack is not None
    assert fresh_definition.appearance_overrides["token_overrides"]["surface"] == "#fdfdfb"
    assert fresh_definition.generation_rules["instructional_bias"] == "high"
    assert fresh_pack.default_token_overrides["surface"] == "#101418"


def test_visual_style_registry_references_are_valid():
    definitions = list_builtin_visual_style_definitions()
    assert len(definitions) == 44
    for definition in definitions:
        assert get_visual_style_pack(definition.style_pack) is not None
        assert definition.prompt_profile in {
            "instructional_hand_drawn",
            "fine_art_human",
            "tactile_playful",
            "technical_precision",
            "metric_first",
            "narrative_journey",
            "corporate_strategy",
            "design_editorial",
            "playful_approachable",
            "retro_synthetic",
            "high_energy_marketing",
        }


def test_visual_style_profiles_reject_duplicate_ids():
    with pytest.raises(ValueError, match="Duplicate visual style profile IDs: duplicate"):
        _index_visual_style_profiles(
            (
                VisualStyleProfile(profile_id="duplicate", name="One", guidance=("a",)),
                VisualStyleProfile(profile_id="duplicate", name="Two", guidance=("b",)),
            )
        )


def test_slides_db_visual_style_crud(tmp_path):
    db_path = tmp_path / "Slides.db"
    db = SlidesDatabase(db_path=db_path, client_id="tester")
    try:
        created = db.create_visual_style(
            name="Exam Sprint",
            scope="user",
            style_payload=json.dumps(
                {
                    "description": "Recall-first deck",
                    "generation_rules": {"exam_focus": True, "bullet_bias": "high"},
                    "artifact_preferences": ["stat_group"],
                    "appearance_defaults": {"theme": "white"},
                }
            ),
        )

        fetched = db.get_visual_style_by_id(created.id)
        listed, total = db.list_visual_styles(limit=10, offset=0)
        updated = db.update_visual_style(
            style_id=created.id,
            name="Exam Sprint Updated",
            style_payload=json.dumps(
                {
                    "description": "Updated",
                    "generation_rules": {"exam_focus": True, "bullet_bias": "medium"},
                }
            ),
            expected_updated_at=created.updated_at,
        )
        deleted = db.delete_visual_style(created.id)
    finally:
        db.close_connection()

    assert fetched.name == "Exam Sprint"
    assert total == 1
    assert listed[0].id == created.id
    assert updated.name == "Exam Sprint Updated"
    assert deleted is True


def test_slides_db_visual_style_delete_removes_row(tmp_path):
    db_path = tmp_path / "Slides.db"
    db = SlidesDatabase(db_path=db_path, client_id="tester")
    try:
        created = db.create_visual_style(
            name="Exam Sprint",
            scope="user",
            style_payload=json.dumps({"generation_rules": {"exam_focus": True}}),
        )

        deleted = db.delete_visual_style(created.id)

        with pytest.raises(KeyError):
            db.get_visual_style_by_id(created.id)
    finally:
        db.close_connection()

    assert deleted is True


def test_slides_db_visual_style_update_uses_optimistic_locking(tmp_path):
    db_path = tmp_path / "Slides.db"
    db = SlidesDatabase(db_path=db_path, client_id="tester")
    try:
        created = db.create_visual_style(
            name="Exam Sprint",
            scope="user",
            style_payload=json.dumps({"generation_rules": {"exam_focus": True}}),
        )
        updated = db.update_visual_style(
            style_id=created.id,
            name="Exam Sprint Updated",
            style_payload=json.dumps({"generation_rules": {"exam_focus": True, "bullet_bias": "high"}}),
            expected_updated_at=created.updated_at,
        )

        with pytest.raises(ConflictError):
            db.update_visual_style(
                style_id=created.id,
                name="Exam Sprint Stale Update",
                style_payload=json.dumps({"generation_rules": {"exam_focus": False}}),
                expected_updated_at="1970-01-01T00:00:00+00:00",
            )
    finally:
        db.close_connection()

    assert updated.name == "Exam Sprint Updated"
