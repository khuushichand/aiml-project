"""Workflow constants.

DEPRECATED: This module is deprecated. Use the adapter registry instead.

The parallelizable step types are now derived from the adapter registry's
parallelizable flag. Use get_parallelizable() from the adapters module:

    from tldw_Server_API.app.core.Workflows.adapters import get_parallelizable
    parallelizable_types = get_parallelizable()
"""

from __future__ import annotations

import warnings

# Re-export get_parallelizable for backward compatibility
from tldw_Server_API.app.core.Workflows.adapters._registry import get_parallelizable


def _get_map_substep_types() -> set[str]:
    """Get parallelizable step types from registry (deprecated)."""
    warnings.warn(
        "MAP_SUBSTEP_TYPES is deprecated. Use get_parallelizable() from "
        "tldw_Server_API.app.core.Workflows.adapters instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return get_parallelizable()


# For backward compatibility only - prefer using get_parallelizable()
# This is a property-like object that calls the registry when accessed
class _DeprecatedSet:
    """Deprecated set that delegates to get_parallelizable()."""

    def __contains__(self, item: str) -> bool:
        return item in get_parallelizable()

    def __iter__(self):
        return iter(get_parallelizable())

    def __len__(self) -> int:
        return len(get_parallelizable())


# Deprecated: use get_parallelizable() instead
MAP_SUBSTEP_TYPES: set[str] = _DeprecatedSet()  # type: ignore[assignment]
