"""
Top-level pytest configuration.

Registers shared test plugins globally to comply with pytest>=8, which
disallows defining `pytest_plugins` in non-top-level conftest files.

See: https://docs.pytest.org/en/stable/deprecations.html#pytest-plugins-in-non-top-level-conftest-files
"""

# Register shared fixtures/plugins for the entire test suite
# Note: Avoid double-registering third-party plugins that are already
# auto-discovered via entry points (e.g., pytest-benchmark). Only add them
# explicitly when plugin autoloading is disabled.
import os

_plugins = [
    # Chat + auth fixtures used widely across tests
    "tldw_Server_API.tests._plugins.chat_fixtures",
    "tldw_Server_API.tests._plugins.authnz_fixtures",
    # Isolated Chat fixtures (unit_test_client, isolated_db, etc.)
    "tldw_Server_API.tests.Chat.integration.conftest_isolated",
    # Unified Postgres fixtures (temp DBs, reachability, DatabaseConfig)
    "tldw_Server_API.tests._plugins.postgres",
    # Optional pgvector fixtures (will be skipped if not available)
    "tldw_Server_API.tests.helpers.pgvector",
]

# Include pytest-benchmark only when autoload is disabled, to avoid duplicate
# registration errors when the plugin is already auto-loaded as 'benchmark'.
if os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "").strip().lower() in {"1", "true", "yes"}:
    try:
        import importlib

        importlib.import_module("pytest_benchmark.plugin")
    except Exception:
        # Plugin not installed or failed to import; continue without it.
        pass
    else:
        _plugins.insert(0, "pytest_benchmark.plugin")

pytest_plugins = tuple(_plugins)
