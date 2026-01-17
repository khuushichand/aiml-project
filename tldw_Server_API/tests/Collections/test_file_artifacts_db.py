import json
import shutil
from pathlib import Path

import pytest

from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase


pytestmark = pytest.mark.unit


@pytest.fixture()
def collections_db(monkeypatch):
    base_dir = Path.cwd() / "Databases" / "test_user_dbs_file_artifacts"
    shutil.rmtree(base_dir, ignore_errors=True)
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    try:
        yield CollectionsDatabase.for_user(user_id=777)
    finally:
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


def test_create_and_update_file_artifact(collections_db: CollectionsDatabase):
    structured = {"columns": ["Name"], "rows": [["Ada"]]}
    validation = {"ok": True, "warnings": []}
    row = collections_db.create_file_artifact(
        file_type="markdown_table",
        title="Roster",
        structured_json=json.dumps(structured),
        validation_json=json.dumps(validation),
    )
    assert row.id is not None
    assert row.file_type == "markdown_table"
    assert row.title == "Roster"

    updated = collections_db.update_file_artifact_export(
        row.id,
        export_status="ready",
        export_format="md",
        export_storage_path="file_777.md",
        export_bytes=42,
        export_content_type="text/markdown",
        export_job_id=None,
    )
    assert updated.export_status == "ready"
    assert updated.export_format == "md"
    assert updated.export_storage_path == "file_777.md"
