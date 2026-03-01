"""Sandbox core module.

Provides interfaces and policy scaffolding for sandboxed code execution
across multiple runtimes.
"""

from .runtime_capabilities import RuntimeCapabilities, RuntimePreflightResult

__all__ = [
    "RuntimeCapabilities",
    "RuntimePreflightResult",
]
