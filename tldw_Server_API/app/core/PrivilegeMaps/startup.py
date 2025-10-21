from __future__ import annotations

import os
from typing import Dict, List

from fastapi import FastAPI
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.privilege_catalog import PrivilegeCatalog, load_catalog
from tldw_Server_API.app.core.PrivilegeMaps.introspection import RouteMetadata, collect_privilege_route_registry


def validate_privilege_metadata_on_startup(app: FastAPI) -> Dict[str, List[RouteMetadata]]:
    """
    Ensure the privilege catalog can be loaded and that FastAPI routes reference valid scope identifiers.

    Returns:
        The collected route registry keyed by privilege scope ID.

    Raises:
        FileNotFoundError: If the catalog file is missing.
        ValidationError: If the catalog contents are invalid.
        ValueError: If any route references an unknown privilege scope.
    """
    if os.getenv("PRIVILEGE_METADATA_VALIDATE_ON_STARTUP", "1").lower() in {"0", "false", "no", "off"}:
        logger.info("Skipping privilege metadata validation due to environment override")
        return {}

    catalog: PrivilegeCatalog = load_catalog()
    registry = collect_privilege_route_registry(app, catalog, strict=True)
    total_routes = sum(len(entries) for entries in registry.values())
    logger.info(
        "Privilege catalog validated (version={}, scopes={}, mapped_routes={})",
        catalog.version,
        len(catalog.scopes),
        total_routes,
    )
    return registry
