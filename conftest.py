"""
Top-level pytest configuration.

Register shared test plugins here (pytest >= 8 requires plugins referenced from
conftest to be declared only at the top-level). These are safe non-conftest
plugin modules, so they won’t be auto-discovered twice.
"""

# Shared Chat fixtures used across multiple test packages
pytest_plugins = (
    "tldw_Server_API.tests._plugins.chat_fixtures",
    "tldw_Server_API.tests._plugins.authnz_fixtures",
)
