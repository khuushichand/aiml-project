"""Compatibility shim for claims rebuild service."""

from tldw_Server_API.app.core.Claims_Extraction.claims_rebuild_service import (
    ClaimsRebuildService,
    ClaimsRebuildTask,
    get_claims_rebuild_service,
)

__all__ = [
    "ClaimsRebuildService",
    "ClaimsRebuildTask",
    "get_claims_rebuild_service",
]
