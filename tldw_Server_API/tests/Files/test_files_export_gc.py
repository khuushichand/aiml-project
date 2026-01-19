from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.services.file_artifacts_export_gc_service import _purge_expired_exports_for_user


pytestmark = pytest.mark.unit


@pytest.fixture()
def user_db_base(monkeypatch, tmp_path: Path):
    base_dir = tmp_path / "user_dbs_files_gc"
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    try:
        yield base_dir
    finally:
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


@pytest.mark.asyncio
async def test_purge_expired_exports_removes_file_and_clears_state(user_db_base):
    user_id = 777
    cdb = CollectionsDatabase.for_user(user_id=user_id)
    outputs_dir = DatabasePaths.get_user_temp_outputs_dir(user_id)
    export_name = "file_1.csv"
    export_path = outputs_dir / export_name
    export_path.write_text("data", encoding="utf-8")

    structured = {"columns": ["Name"], "rows": [["Ada"]]}
    validation = {"ok": True, "warnings": []}
    past = (datetime.now(timezone.utc) - timedelta(seconds=5)).replace(microsecond=0).isoformat()
    row = cdb.create_file_artifact(
        file_type="data_table",
        title="Roster",
        structured_json=json.dumps(structured),
        validation_json=json.dumps(validation),
        export_status="ready",
        export_format="csv",
        export_storage_path=export_name,
        export_bytes=4,
        export_content_type="text/csv",
        export_expires_at=past,
    )
    assert export_path.exists()

    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    cleared, files_deleted = await _purge_expired_exports_for_user(user_id, now_iso)
    assert cleared == 1
    assert files_deleted == 1
    assert not export_path.exists()

    refreshed = cdb.get_file_artifact(row.id)
    assert refreshed.export_status == "none"
    assert refreshed.export_storage_path is None
    assert refreshed.export_expires_at is None
