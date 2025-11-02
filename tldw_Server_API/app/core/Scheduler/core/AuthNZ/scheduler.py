"""
Shim module for tests: expose AuthNZScheduler from the real AuthNZ package
under the path expected by test imports.
"""

from tldw_Server_API.app.core.AuthNZ.scheduler import AuthNZScheduler  # noqa: F401
