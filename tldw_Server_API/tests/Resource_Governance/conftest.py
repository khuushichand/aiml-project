"""
Make AuthNZ Postgres test fixtures (e.g., test_db_pool) available here by
importing the AuthNZ test plugin module.
"""

pytest_plugins = (
    "tldw_Server_API.tests.AuthNZ.conftest",
)

