"""Local conftest for AuthNZ_SQLite tests.

Pull in shared AuthNZ fixtures so this subtree works even if global
plugin registration is skipped by the CI runner.
"""

try:
    from tldw_Server_API.tests._plugins.authnz_fixtures import (
        authnz_schema_ready,       # noqa: F401
        authnz_schema_ready_sync,  # noqa: F401
        real_audit_service,        # noqa: F401
    )
except Exception:
    # If shared plugin import fails, tests that need these fixtures
    # will error explicitly; do not fail collection here.
    pass
