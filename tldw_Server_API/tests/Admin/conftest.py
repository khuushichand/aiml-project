"""Local conftest for Admin tests.

Minimal import to ensure shared AuthNZ fixtures are available when
pytest does not auto-load plugins from pyproject.toml in CI.
"""

# Expose the AuthNZ schema initializers to this package's tests
from tldw_Server_API.tests._plugins.authnz_fixtures import (
    authnz_schema_ready_sync,  # noqa: F401
    authnz_schema_ready,       # noqa: F401
)
