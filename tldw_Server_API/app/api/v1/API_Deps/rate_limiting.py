# rate_limiting.py
# Centralized rate limiting configuration that respects TEST_MODE and
# defers to ResourceGovernor ingress middleware when present.

import os
from slowapi import Limiter
from slowapi.util import get_remote_address as _original_get_remote_address


def get_test_aware_remote_address(request):
    """
    Custom key function for rate limiting that:
    - Bypasses limits entirely in TEST_MODE.
    - Defers to ResourceGovernor ingress middleware (RGSimpleMiddleware)
      when it is attached to the app, treating SlowAPI as a configuration
      carrier only.
    """
    # ONLY check for server-side test mode envs — NEVER trust client headers
    raw = (os.getenv("TEST_MODE", "") or os.getenv("TLDW_TEST_MODE", "")).strip().lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return None  # Bypass rate limiting in test mode

    # When RGSimpleMiddleware is installed on the app, let it be the primary
    # ingress limiter and effectively disable SlowAPI counting by returning
    # None as the key. This keeps the decorators as config carriers only.
    try:
        app = getattr(request, "app", None)
        if app is not None:
            try:
                from tldw_Server_API.app.core.Resource_Governance.middleware_simple import (  # type: ignore
                    RGSimpleMiddleware as _RGMw,
                )

                for m in getattr(app, "user_middleware", []):
                    if getattr(m, "cls", None) is _RGMw:
                        return None
            except Exception:
                # If RG middleware introspection fails, fall back to legacy behavior.
                pass
    except Exception:
        # Defensive: key function must never raise; fall back to legacy behavior.
        pass

    return _original_get_remote_address(request)


def create_limiter():
    """
    Create a Limiter instance that respects TEST_MODE and RG middleware.
    """
    return Limiter(key_func=get_test_aware_remote_address)


# Global limiter instance that can be imported by endpoints
limiter = create_limiter()
