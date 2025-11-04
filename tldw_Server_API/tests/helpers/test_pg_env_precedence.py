import os
from tldw_Server_API.tests.helpers.pg_env import get_pg_env


def test_get_pg_env_prefers_jobs_over_test_database_url(monkeypatch):
    monkeypatch.setenv("JOBS_DB_URL", "postgresql://jobs_user:jobs_pwd@host1:5555/jobs_db")
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://test_user:test_pwd@host2:6666/test_db")
    pg = get_pg_env()
    assert pg.dsn.startswith("postgresql://jobs_user:jobs_pwd@host1:5555/jobs_db")


def test_get_pg_env_builds_from_container_style(monkeypatch):
    for key in [
        "JOBS_DB_URL",
        "POSTGRES_TEST_DSN",
        "TEST_DATABASE_URL",
        "DATABASE_URL",
    ]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("POSTGRES_TEST_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_TEST_PORT", "55432")
    monkeypatch.setenv("POSTGRES_TEST_USER", "tldw")
    monkeypatch.setenv("POSTGRES_TEST_PASSWORD", "tldw")
    monkeypatch.setenv("POSTGRES_TEST_DB", "tldw_content")
    pg = get_pg_env()
    assert pg.dsn == "postgresql://tldw:tldw@127.0.0.1:55432/tldw_content"

