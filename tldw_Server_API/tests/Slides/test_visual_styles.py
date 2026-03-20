import json

import pytest

from tldw_Server_API.app.core.Slides.slides_db import ConflictError, SlidesDatabase
from tldw_Server_API.app.core.Slides.visual_styles import list_builtin_visual_styles


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

    assert len(styles) >= 8
    assert len(style_ids) == len(set(style_ids))
    assert "timeline" in style_ids
    assert "exam-focused-bullet" in style_ids


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
