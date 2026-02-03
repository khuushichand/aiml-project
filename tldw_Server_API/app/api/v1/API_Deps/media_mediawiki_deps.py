from __future__ import annotations

from typing import Any

from fastapi import Form, HTTPException, status

from tldw_Server_API.app.api.v1.schemas.media_request_models import (
    media_wiki_global_config,
)

try:
    HTTP_422_UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_CONTENT
except AttributeError:  # Starlette < 0.27
    HTTP_422_UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_ENTITY


def get_mediawiki_form_data(
    wiki_name: str = Form(
        ...,
        description="A unique name for this MediaWiki instance.",
    ),
    namespaces_str: str | None = Form(
        None,
        description="Comma-separated namespace IDs (e.g., '0,1'). All if None.",
    ),
    skip_redirects: bool = Form(
        True,
        description="Skip redirect pages.",
    ),
    chunk_max_size: int = Form(
        default_factory=lambda: media_wiki_global_config.get(
            "chunking",
            {},
        ).get("default_size", 1000),
        description="Max chunk size.",
    ),
    api_name_vector_db: str | None = Form(
        None,
        description="API name for vector DB/embedding service.",
    ),
    api_key_vector_db: str | None = Form(
        None,
        description="API key for vector DB/embedding service.",
    ),
) -> dict[str, Any]:
    """
    Shared dependency for MediaWiki dump processing/ingest endpoints.

    Parses simple form fields into a structured dict used by the underlying
    MediaWiki ingestion pipeline.
    """
    namespaces = None
    if namespaces_str:
        try:
            namespaces = [int(ns.strip()) for ns in namespaces_str.split(",")]
        except ValueError as ve:
            raise HTTPException(
                status_code=HTTP_422_UNPROCESSABLE,
                detail="Invalid namespace format. Must be comma-separated integers.",
            ) from ve

    chunk_options_override = {"max_size": chunk_max_size}

    return {
        "wiki_name": wiki_name,
        "namespaces": namespaces,
        "skip_redirects": skip_redirects,
        "chunk_options_override": chunk_options_override,
        "api_name_vector_db": api_name_vector_db,
        "api_key_vector_db": api_key_vector_db,
    }


__all__ = ["get_mediawiki_form_data"]
