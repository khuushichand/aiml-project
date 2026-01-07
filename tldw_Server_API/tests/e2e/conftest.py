"""
Pytest configuration for e2e tests.

Defines custom markers and test configuration for end-to-end testing
that simulates real user interactions with the application.
"""

import pytest
import os
from typing import Dict, Any, Optional

pytest_plugins = (
    "tldw_Server_API.tests._plugins.e2e_fixtures",
    "tldw_Server_API.tests._plugins.e2e_state_fixtures",
    "tldw_Server_API.tests._plugins.chat_fixtures",
    "tldw_Server_API.tests._plugins.media_fixtures",
)

# Disable rate limiting for all e2e tests
@pytest.fixture(autouse=True, scope="session")
def disable_rate_limiting():
    """Disable rate limiting for all tests in e2e suite"""
    os.environ["TESTING"] = "true"  # For embeddings endpoint
    os.environ["TEST_MODE"] = "true"  # For regular limiter
    os.environ.setdefault("ENABLE_REGISTRATION", "true")
    os.environ.setdefault("REQUIRE_REGISTRATION_CODE", "false")
    yield
    # Clean up after tests
    if "TESTING" in os.environ:
        del os.environ["TESTING"]
    if "TEST_MODE" in os.environ:
        del os.environ["TEST_MODE"]

# Custom markers for conditional test execution
pytest_markers = [
    "single_user: marks tests that only run in single-user mode",
    "multi_user: marks tests that only run in multi-user mode",
    "requires_llm: marks tests that require a configured LLM provider",
    "requires_transcription: marks tests that require transcription services",
    "requires_embeddings: marks tests that require embedding services",
    "slow: marks tests that take a long time to run (>30s)",
    "critical: marks tests that are critical for basic functionality",
    "benchmark: marks benchmark-related tests",
    "media_processing: marks media processing tests",
    "auth: marks authentication-related tests",
    "timeout: marks tests with explicit timeout limits (requires pytest-timeout plugin)",
]

def pytest_configure(config):
    """Register custom markers."""
    for marker in pytest_markers:
        config.addinivalue_line("markers", marker)
    # Additional marker for explicit rate-limit verification tests
    config.addinivalue_line("markers", "rate_limits: Tests that verify rate limiting behavior")


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on environment and configuration."""

    # Check environment to determine which tests to skip
    auth_mode = os.getenv("E2E_AUTH_MODE", "auto")  # auto, single_user, multi_user
    skip_slow = config.getoption("--skip-slow", default=False)
    run_slow = config.getoption("--run-slow", default=False)
    run_critical_only = config.getoption("--critical-only", default=False)

    # Get auth mode from API if auto
    if auth_mode == "auto":
        auth_mode = _detect_auth_mode()

    for item in items:
        # Skip tests based on auth mode
        if auth_mode == "single_user":
            if "multi_user" in item.keywords:
                item.add_marker(pytest.mark.skip(
                    reason="Multi-user test skipped in single-user mode"
                ))
        elif auth_mode == "multi_user":
            if "single_user" in item.keywords:
                item.add_marker(pytest.mark.skip(
                    reason="Single-user test skipped in multi-user mode"
                ))

        # Skip slow tests if requested
        if skip_slow and not run_slow and "slow" in item.keywords:
            item.add_marker(pytest.mark.skip(
                reason="Slow test skipped (use --run-slow to include)"
            ))

        # Run only critical tests if requested
        if run_critical_only and "critical" not in item.keywords:
            item.add_marker(pytest.mark.skip(
                reason="Non-critical test skipped (--critical-only mode)"
            ))


def _detect_auth_mode() -> str:
    """Detect auth mode from running API server."""
    try:
        import httpx
        base_url = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000")
        with httpx.Client(timeout=5) as client:
            response = client.get(f"{base_url}/api/v1/health")
            if response.status_code == 200:
                return response.json().get("auth_mode", "multi_user")
    except:
        pass
    return "multi_user"  # Default


def pytest_addoption(parser):
    """Add custom command-line options."""
    parser.addoption(
        "--skip-slow",
        action="store_true",
        default=False,
        help="Skip slow-running tests"
    )
    parser.addoption(
        "--critical-only",
        action="store_true",
        default=False,
        help="Run only critical tests"
    )
    parser.addoption(
        "--auth-mode",
        action="store",
        default="auto",
        choices=["auto", "single_user", "multi_user"],
        help="Force specific auth mode for testing"
    )
    # Alias to include slow tests (pairs with --skip-slow default behavior)
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="Include tests marked as slow"
    )

# Attach the shared test results dict to config so sessionfinish can print a summary
@pytest.fixture(scope="session", autouse=True)
def _attach_results_to_config(test_results, request):
    request.config._test_results = test_results  # type: ignore[attr-defined]
    yield

# For tests that validate rate limiting, temporarily disable the global TEST_MODE
# env that turns off rate limits. Controlled via @pytest.mark.rate_limits
@pytest.fixture(autouse=True)
def _rate_limit_env_toggle(request):
    if request.node.get_closest_marker("rate_limits"):
        original_test_mode = os.environ.get("TEST_MODE")
        original_testing = os.environ.get("TESTING")
        # Remove flags that disable rate limiting
        os.environ.pop("TEST_MODE", None)
        os.environ.pop("TESTING", None)
        try:
            yield
        finally:
            if original_test_mode is None:
                os.environ.pop("TEST_MODE", None)
            else:
                os.environ["TEST_MODE"] = original_test_mode
            if original_testing is None:
                os.environ.pop("TESTING", None)
            else:
                os.environ["TESTING"] = original_testing
    else:
        yield
