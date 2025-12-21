"""Pytest plugin: e2e fixtures

Provides the end-to-end test fixtures via pytest's plugin system to avoid
re-exporting from conftest files. Heavy work happens only inside fixtures.
"""

from __future__ import annotations

# Import fixtures and helpers from the canonical e2e fixtures module.
# Avoid doing any work at import-time beyond these imports.
from tldw_Server_API.tests.e2e.fixtures import (  # noqa: F401
    APIClient,
    api_client,
    authenticated_client,
    test_user_credentials,
    data_tracker,
    create_test_file,
    create_test_pdf,
    create_test_audio,
    cleanup_test_file,
    AssertionHelpers,
)

# Make the exported fixture surface explicit
__all__ = [
    # primary fixtures
    "api_client",
    "authenticated_client",
    "test_user_credentials",
    "data_tracker",
    # commonly used helpers
    "APIClient",
    "create_test_file",
    "create_test_pdf",
    "create_test_audio",
    "cleanup_test_file",
    "AssertionHelpers",
]
