from __future__ import annotations

import pytest

from tldw_Server_API.app.core.DB_Management.Meetings_DB import MeetingsDatabase
from tldw_Server_API.app.core.Meetings.template_service import MeetingTemplateService


pytestmark = pytest.mark.unit


@pytest.fixture()
def template_service(tmp_path):
    db = MeetingsDatabase(db_path=tmp_path / "Media_DB_v2.db", client_id="tester", user_id="1")
    service = MeetingTemplateService(db=db)
    try:
        yield service
    finally:
        db.close_connection()


def test_list_templates_includes_builtin_and_personal(template_service):
    created = template_service.create_template(
        name="Team Weekly",
        scope="personal",
        schema_json={"sections": ["summary", "actions"]},
    )
    rows = template_service.list_templates()
    ids = {row["id"] for row in rows}
    assert created["id"] in ids
    assert any(row["scope"] == "builtin" for row in rows)


def test_list_templates_respects_scope_and_enabled_filters(template_service):
    enabled = template_service.create_template(
        name="Enabled Template",
        scope="personal",
        schema_json={"sections": ["summary"]},
        enabled=True,
    )
    disabled = template_service.create_template(
        name="Disabled Template",
        scope="personal",
        schema_json={"sections": ["summary"]},
        enabled=False,
    )

    enabled_rows = template_service.list_templates(scope="personal", include_disabled=False)
    enabled_ids = {row["id"] for row in enabled_rows}
    assert enabled["id"] in enabled_ids
    assert disabled["id"] not in enabled_ids

    all_rows = template_service.list_templates(scope="personal", include_disabled=True)
    all_ids = {row["id"] for row in all_rows}
    assert enabled["id"] in all_ids
    assert disabled["id"] in all_ids
