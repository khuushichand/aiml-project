import os
import pytest


pytestmark = pytest.mark.integration

def _has_postgres_dependencies() -> bool:
    try:
        import asyncpg  # noqa: F401
        return True
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.parametrize("backend", ["sqlite"])  # Always run sqlite
def test_authnz_backend_smoke(backend):
    from tldw_Server_API.tests.test_authnz_backends import AuthNZBackendTests
    tester = AuthNZBackendTests(backend, verbose=False)
    tester.setup()
    try:
        assert tester.run_all_tests() is True
    finally:
        tester.teardown()


@pytest.mark.integration
@pytest.mark.postgres
@pytest.mark.skipif(
    not _has_postgres_dependencies(),
    reason="Postgres dependencies missing (install asyncpg)",
)
@pytest.mark.usefixtures("setup_test_database", "clean_database")
async def test_authnz_backend_smoke_postgres(monkeypatch):
    from tldw_Server_API.tests.test_authnz_backends import AuthNZBackendTests

    # Reuse the Postgres database prepared by the AuthNZ fixtures
    dsn = (os.getenv("DATABASE_URL") or os.getenv("TEST_DATABASE_URL") or "").strip()
    assert dsn, "AuthNZ Postgres fixture did not provide a database URL"
    monkeypatch.setenv("TEST_DATABASE_URL", dsn)

    tester = AuthNZBackendTests("postgresql", verbose=False)
    tester.setup()
    try:
        assert tester.run_all_tests() is True
    finally:
        tester.teardown()
