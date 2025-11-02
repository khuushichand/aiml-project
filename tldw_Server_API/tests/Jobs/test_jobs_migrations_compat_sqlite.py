import sqlite3

from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables


def test_sqlite_schema_additional_tables_and_indexes(tmp_path):
    db_path = ensure_jobs_tables(tmp_path / "jobs_mig2.db")
    conn = sqlite3.connect(db_path)
    try:
        # Core auxiliary tables exist
        def has_table(name: str) -> bool:
            row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
            return bool(row)

        assert has_table("job_events")
        assert has_table("job_queue_controls")
        assert has_table("job_attachments")
        assert has_table("job_sla_policies")

        # Hot-path index for queued vs scheduled scans present
        idxs = [r[1] for r in conn.execute("PRAGMA index_list('jobs')").fetchall()]
        assert any("idx_jobs_status_available_at" in x for x in idxs)
        # Partial unique idempotency index present
        assert any("idx_jobs_idempotent" in x for x in idxs)
    finally:
        conn.close()
