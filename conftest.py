"""
Top-level pytest configuration.

Registers shared test plugins globally to comply with pytest>=8, which
disallows defining `pytest_plugins` in non-top-level conftest files.

See: https://docs.pytest.org/en/stable/deprecations.html#pytest-plugins-in-non-top-level-conftest-files
"""

# Register shared fixtures/plugins for the entire test suite
pytest_plugins = (
    # Ensure pytest-benchmark's 'benchmark' fixture is available when plugin autoload is disabled
    # or when running in constrained CI environments.
    "pytest_benchmark.plugin",
    # Chat + auth fixtures used widely across tests
    "tldw_Server_API.tests._plugins.chat_fixtures",
    "tldw_Server_API.tests._plugins.authnz_fixtures",
    # Isolated Chat fixtures (unit_test_client, isolated_db, etc.)
    "tldw_Server_API.tests.Chat.integration.conftest_isolated",
    # Unified Postgres fixtures (temp DBs, reachability, DatabaseConfig)
    "tldw_Server_API.tests._plugins.postgres",
    # Optional pgvector fixtures (will be skipped if not available)
    "tldw_Server_API.tests.helpers.pgvector",
)
