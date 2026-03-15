"""
Resource Governor endpoint coverage audit.

Reports which endpoints are protected by the Resource Governor middleware
and which are unprotected. Useful for identifying coverage gaps.
"""
from __future__ import annotations

from typing import Any

from loguru import logger

# Default prefixes excluded from governor enforcement (health, docs, etc.)
DEFAULT_EXCLUDED_PREFIXES = [
    "/docs",
    "/openapi.json",
    "/healthz",
    "/readyz",
    "/health",
]


def audit_governor_coverage(
    app: Any,
    *,
    excluded_prefixes: list[str] | None = None,
) -> dict[str, Any]:
    """Audit which routes are governor-protected.

    The governor middleware applies to all routes, but some may be excluded
    by policy configuration. This function reports the coverage state.

    Args:
        app: The FastAPI application instance.
        excluded_prefixes: Route prefixes to consider unprotected.
            Defaults to health/docs routes.

    Returns:
        Dict with total_routes, protected/unprotected counts and lists,
        coverage percentage, and excluded prefixes.
    """
    prefixes = excluded_prefixes if excluded_prefixes is not None else list(DEFAULT_EXCLUDED_PREFIXES)

    routes: list[dict[str, str]] = []
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            for method in route.methods:
                routes.append({"method": method, "path": route.path})

    protected: list[dict[str, str]] = []
    unprotected: list[dict[str, str]] = []

    for r in routes:
        if any(r["path"].startswith(p) for p in prefixes):
            unprotected.append(r)
        else:
            protected.append(r)

    total = len(routes)
    coverage = (len(protected) / total * 100) if total > 0 else 0.0

    logger.debug(
        "Governor coverage audit: {}/{} routes protected ({:.1f}%)",
        len(protected),
        total,
        coverage,
    )

    return {
        "total_routes": total,
        "protected_count": len(protected),
        "unprotected_count": len(unprotected),
        "coverage_pct": round(coverage, 1),
        "excluded_prefixes": prefixes,
        "protected_routes": protected[:50],
        "unprotected_routes": unprotected[:50],
    }
