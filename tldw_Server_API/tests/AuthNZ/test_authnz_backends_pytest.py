import os
import pytest


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
@pytest.mark.skipif(not _has_postgres_dependencies() or not os.getenv("TEST_DATABASE_URL"), reason="Postgres not configured")
def test_authnz_backend_smoke_postgres():
    from tldw_Server_API.tests.test_authnz_backends import AuthNZBackendTests
    tester = AuthNZBackendTests("postgresql", verbose=False)
    tester.setup()
    try:
        assert tester.run_all_tests() is True
    finally:
        tester.teardown()

