"""Compatibility shim for ingestion-time claims helpers."""

from tldw_Server_API.app.core.Claims_Extraction.ingestion_claims import (
    extract_claims_for_chunks,
    store_claims,
)

__all__ = [
    "extract_claims_for_chunks",
    "store_claims",
]
