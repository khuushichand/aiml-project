import json
import shutil
from pathlib import Path

import pytest

from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase


pytestmark = pytest.mark.unit


@pytest.fixture()
def seeded_db(tmp_path, monkeypatch):
    template_dir = tmp_path / "watchlists_templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / "seeded.md").write_text("Seeded {{ title }}", encoding="utf-8")
    (template_dir / "seeded.meta.json").write_text(json.dumps({"description": "Seeded template"}), encoding="utf-8")
    monkeypatch.setenv("WATCHLIST_TEMPLATE_DIR", str(template_dir))

    base_dir = Path.cwd() / "Databases" / "test_user_dbs_seed"
    shutil.rmtree(base_dir, ignore_errors=True)
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    try:
        yield
    finally:
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


def test_seed_watchlists_templates_into_outputs(seeded_db):
    cdb = CollectionsDatabase.for_user(user_id=901)
    items, total = cdb.list_output_templates(q=None, limit=50, offset=0)
    assert total >= 1
    seeded = next((tpl for tpl in items if tpl.name == "seeded"), None)
    assert seeded is not None
    assert seeded.format == "md"
    meta = json.loads(seeded.metadata_json or "{}")
    assert meta.get("seeded_from") == "watchlists_templates"

    # Seeding should be idempotent
    cdb_again = CollectionsDatabase.for_user(user_id=901)
    items_again, total_again = cdb_again.list_output_templates(q=None, limit=50, offset=0)
    names = [tpl.name for tpl in items_again]
    assert names.count("seeded") == 1


def test_output_templates_search_case_insensitive_sqlite(seeded_db):
    cdb = CollectionsDatabase.for_user(user_id=902)
    cdb.create_output_template(
        name="CaseTemplate",
        type_="summary",
        format_="md",
        body="Body",
        description="Mixed Case Template",
        is_default=False,
    )
    items, total = cdb.list_output_templates(q="casetemplate", limit=10, offset=0)
    assert total >= 1
    assert any(tpl.name == "CaseTemplate" for tpl in items)
