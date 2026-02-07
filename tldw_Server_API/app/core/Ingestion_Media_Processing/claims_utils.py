"""Compatibility shim for claims utilities moved to core.Claims_Extraction."""

from tldw_Server_API.app.core.Claims_Extraction.claims_utils import (
    claims_extraction_enabled,
    extract_claims_if_requested,
    persist_claims_if_applicable,
    prepare_claims_chunks,
    resolve_claims_parameters,
)

__all__ = [
    "claims_extraction_enabled",
    "resolve_claims_parameters",
    "prepare_claims_chunks",
    "extract_claims_if_requested",
    "persist_claims_if_applicable",
]
