import pytest


pytestmark = pytest.mark.integration

@pytest.mark.integration
def test_authnz_sqlite_backend_smoke():
    """Smoke-run the AuthNZ backend tests against SQLite under pytest.

    This wraps the existing test runner class so pytest can collect it,
    without relying on the CLI entry in test_authnz_backends.py.
    """
    # Import locally to avoid side effects at collection time
    from tldw_Server_API.tests.test_authnz_backends import AuthNZBackendTests

    tester = AuthNZBackendTests("sqlite", verbose=False)
    tester.setup()
    try:
        passed = tester.run_all_tests()
        assert passed is True
    finally:
        tester.teardown()
