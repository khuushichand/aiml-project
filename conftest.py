"""
Top-level pytest configuration for the repository.

Registers shared test plugins to satisfy pytest's top-level requirement.
"""

pytest_plugins = (
    "tldw_Server_API.tests.helpers.pgvector",
    "tldw_Server_API.tests._plugins.e2e_fixtures",
    "tldw_Server_API.tests._plugins.e2e_state_fixtures",
    "tldw_Server_API.tests._plugins.chat_fixtures",
    "tldw_Server_API.tests._plugins.media_fixtures",
    "tldw_Server_API.tests._plugins.postgres",
)
