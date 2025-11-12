"""Local conftest for Characters tests.

Register required shared plugins for this subtree:
- Unified Postgres fixtures (pg_server, pg_temp_db, etc.) so Postgres tests
  provision a temp DB or skip gracefully when PG is unavailable.
- Chat fixtures (authenticated_client, mock_chacha_db, setup_dependencies,
  auth_headers, etc.) used by API tests in this package.

Why register plugins here when pyproject.toml already lists them?
- Developers and CI often run tests from subdirectories or individual files;
  in those cases, relying solely on the project‑level plugin list can fail to
  load the needed fixtures depending on the working directory and runner.
- Some environments set PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 or otherwise tweak
  plugin discovery, which can prevent pyproject‑declared plugins from loading.
- Keeping a minimal, explicit pytest_plugins list in this package ensures the
  Characters tests remain hermetic and consistently runnable without a root
  conftest. Do not remove unless you verify subtree and file‑scoped runs still
  discover fixtures reliably across local and CI environments.
"""

pytest_plugins = [
    "tldw_Server_API.tests._plugins.postgres",
    "tldw_Server_API.tests._plugins.chat_fixtures",
]
