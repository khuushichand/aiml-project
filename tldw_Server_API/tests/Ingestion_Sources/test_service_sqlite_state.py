from __future__ import annotations

import aiosqlite
import pytest


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_source_persists_state_row(tmp_path):
    from tldw_Server_API.app.core.Ingestion_Sources.service import (
        create_source,
        ensure_ingestion_sources_schema,
    )

    db_path = tmp_path / "ingestion_sources.sqlite3"
    async with aiosqlite.connect(str(db_path)) as db:
        db.row_factory = aiosqlite.Row

        await ensure_ingestion_sources_schema(db)
        row = await create_source(
            db,
            user_id=7,
            payload={
                "source_type": "local_directory",
                "sink_type": "media",
                "policy": "canonical",
                "config": {"path": "/allowed/project/docs"},
            },
        )

        assert row["user_id"] == 7
        assert row["source_type"] == "local_directory"
        assert row["sink_type"] == "media"

        state_cur = await db.execute(
            "SELECT source_id, active_job_id, last_successful_snapshot_id "
            "FROM ingestion_source_state WHERE source_id = ?",
            (row["id"],),
        )
        state_row = await state_cur.fetchone()

        assert state_row is not None
        assert state_row["source_id"] == row["id"]
        assert state_row["active_job_id"] is None
        assert state_row["last_successful_snapshot_id"] is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_ensure_sqlite_column_rejects_unsafe_identifiers(tmp_path):
    from tldw_Server_API.app.core.Ingestion_Sources.service import _ensure_sqlite_column
    from tldw_Server_API.app.core.exceptions import IngestionSourceValidationError

    db_path = tmp_path / "ingestion_sources.sqlite3"
    async with aiosqlite.connect(str(db_path)) as db:
        with pytest.raises(IngestionSourceValidationError, match="unsafe SQL identifier"):
            await _ensure_sqlite_column(
                db,
                table_name="ingestion_source_items; DROP TABLE users;--",
                column_name="present_in_source",
                column_sql="INTEGER NOT NULL DEFAULT 1",
            )
