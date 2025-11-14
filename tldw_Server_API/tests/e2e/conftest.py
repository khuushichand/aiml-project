"""
Pytest configuration for e2e tests.

Defines custom markers and test configuration for end-to-end testing
that simulates real user interactions with the application.
"""

import pytest
import os
from typing import Dict, Any, Optional

# Register test plugins for this suite, keeping this file focused on
# markers, CLI options, and lightweight env overrides.
pytest_plugins = [
    "tldw_Server_API.tests._plugins.e2e_fixtures",
    "tldw_Server_API.tests._plugins.e2e_state_fixtures",
    "tldw_Server_API.tests._plugins.chat_fixtures",
    "tldw_Server_API.tests._plugins.media_fixtures",
]

# Disable rate limiting for all e2e tests
@pytest.fixture(autouse=True, scope="session")
def disable_rate_limiting():
    """Disable rate limiting for all tests in e2e suite"""
    os.environ["TESTING"] = "true"  # For embeddings endpoint
    os.environ["TEST_MODE"] = "true"  # For regular limiter
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


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on environment and configuration."""

    # Check environment to determine which tests to skip
    auth_mode = os.getenv("E2E_AUTH_MODE", "auto")  # auto, single_user, multi_user
    skip_slow = config.getoption("--skip-slow", default=False)
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
        if skip_slow and "slow" in item.keywords:
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

