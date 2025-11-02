import pytest

from tldw_Server_API.app.core.Jobs.manager import JobManager


class FakeCursor:
    def __init__(self, responses=None):
        self._responses = responses or {}
        self._last_sql = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self._last_sql = str(sql)

    def fetchone(self):
        # Return a mapping compatible with dict_row (uses .get)
        return {"c": 42}

    def fetchall(self):
        return []


class FakeConn:
    def __init__(self):
        pass

    def close(self):
        pass


@pytest.mark.unit
def test_pg_dict_row_count_alias_used(monkeypatch, tmp_path):
    # Instantiate as SQLite to skip PG migrations, then flip backend
    jm = JobManager(db_path=tmp_path / "dummy.db")
    jm.backend = "postgres"

    # Monkeypatch connection and cursor to avoid real psycopg
    monkeypatch.setattr(jm, "_connect", lambda: FakeConn())
    monkeypatch.setattr(jm, "_pg_cursor", lambda conn: FakeCursor())

    # Dry-run path only issues a single COUNT(*) AS c query and returns the count
    n = jm.retry_now_jobs(domain="x", dry_run=True)
    assert n == 42
