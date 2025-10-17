"""
Top-level pytest configuration.

Registers suite-wide plugins to comply with pytest>=8 requirements that
pytest_plugins be declared only in a top-level conftest.
"""

# Ensure pgvector helper fixtures are available when installed; the helper
# itself conditionally skips if psycopg/pgvector are not available.
pytest_plugins = ("tldw_Server_API.tests.helpers.pgvector",)

# Expose commonly used fixtures across sibling test packages
try:
    # Bring selected fixtures into top-level namespace so pytest can see them globally
    from tldw_Server_API.tests.AuthNZ.conftest import real_audit_service  # noqa: F401
except Exception:
    # If AuthNZ tests are not collected, ignore
    pass
