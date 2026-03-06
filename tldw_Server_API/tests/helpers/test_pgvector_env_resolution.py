from tldw_Server_API.tests.helpers.pgvector import _resolve_pgvector_dsn


_PG_ENV_KEYS = (
    "PG_TEST_DSN",
    "PGVECTOR_DSN",
    "JOBS_DB_URL",
    "POSTGRES_TEST_DSN",
    "TEST_DATABASE_URL",
    "DATABASE_URL",
    "POSTGRES_TEST_HOST",
    "POSTGRES_TEST_PORT",
    "POSTGRES_TEST_USER",
    "POSTGRES_TEST_PASSWORD",
    "POSTGRES_TEST_DB",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "TEST_DB_HOST",
    "TEST_DB_PORT",
    "TEST_DB_USER",
    "TEST_DB_PASSWORD",
    "TEST_DB_NAME",
)


def _clear_pg_env(monkeypatch) -> None:
    for key in _PG_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_resolve_pgvector_dsn_prefers_pg_specific_env(monkeypatch):
    _clear_pg_env(monkeypatch)
    monkeypatch.setenv("PG_TEST_DSN", "postgresql://pg_test:pw@host:5432/pg_test")
    monkeypatch.setenv("PGVECTOR_DSN", "postgresql://pgvector:pw@host:5432/pgvector")
    monkeypatch.setenv("JOBS_DB_URL", "postgresql://jobs:pw@host:5432/jobs")
    monkeypatch.setenv("POSTGRES_TEST_DSN", "postgresql://pgtest:pw@host:5432/pgtest")
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://testdb:pw@host:5432/testdb")
    monkeypatch.setenv("DATABASE_URL", "postgresql://db:pw@host:5432/db")

    assert _resolve_pgvector_dsn() == "postgresql://pg_test:pw@host:5432/pg_test"  # nosec B101


def test_resolve_pgvector_dsn_uses_postgres_test_dsn(monkeypatch):
    _clear_pg_env(monkeypatch)
    dsn = "postgresql://pgtest:pw@127.0.0.1:5432/tldw_content"
    monkeypatch.setenv("POSTGRES_TEST_DSN", dsn)

    assert _resolve_pgvector_dsn() == dsn  # nosec B101


def test_resolve_pgvector_dsn_ignores_non_postgres_database_url(monkeypatch):
    _clear_pg_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./Databases/users.db")

    assert _resolve_pgvector_dsn() is None  # nosec B101


def test_resolve_pgvector_dsn_builds_from_container_style_env(monkeypatch):
    _clear_pg_env(monkeypatch)
    monkeypatch.setenv("POSTGRES_TEST_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_TEST_PORT", "55432")
    monkeypatch.setenv("POSTGRES_TEST_USER", "tldw")
    monkeypatch.setenv("POSTGRES_TEST_PASSWORD", "tldw")
    monkeypatch.setenv("POSTGRES_TEST_DB", "tldw_content")

    assert _resolve_pgvector_dsn() == "postgresql://tldw:tldw@127.0.0.1:55432/tldw_content"  # nosec B101
