# provider_config.py
# Description: Provider configuration for LLM API calls
"""
This module is a deprecated compatibility stub for LLM provider dispatch.
Dispatch tables were removed in favor of the adapter registry.
"""
#
# Imports
from typing import Callable

#
# Legacy module; dispatch tables removed in favor of adapter registry.
from tldw_Server_API.app.core.LLM_Calls.deprecation import log_legacy_once

log_legacy_once(
    "provider_config",
    "provider_config is deprecated; use adapter registry and provider_metadata instead.",
)
#
####################################################################################################
#
# Provider Configuration
#

API_CALL_HANDLERS: dict[str, Callable] = {}
ASYNC_API_CALL_HANDLERS: dict[str, Callable] = {}

def get_provider_handler(provider: str) -> Callable:
    """
    Get the handler function for a specific provider.

    Args:
        provider: The provider name

    Returns:
        The handler function for the provider

    Raises:
        KeyError: If the provider is not supported
    """
    raise KeyError(
        "provider_config dispatch tables were removed; use adapter_registry instead."
    )

#
# End of provider_config.py
####################################################################################################
