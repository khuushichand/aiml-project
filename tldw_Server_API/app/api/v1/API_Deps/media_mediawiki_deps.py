from __future__ import annotations

from typing import Any

from fastapi import Form, status
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.media_request_models import (
    MediaWikiDumpOptionsForm,
    media_wiki_global_config,
)
from tldw_Server_API.app.core.exceptions import APIValidationError

try:
    HTTP_422_UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_CONTENT
except AttributeError:  # Starlette < 0.27
    HTTP_422_UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_ENTITY


SENSITIVE_FORM_FIELDS = {"api_key_vector_db"}


def _sanitize_validation_errors(exc: ValidationError) -> list[dict[str, Any]]:
    serializable_errors: list[dict[str, Any]] = []
    for error in exc.errors():
        err = error.copy()
        loc = list(err.get("loc") or [])
        if loc and loc[0] != "body":
            loc = ["body", *loc]
        elif not loc:
            loc = ["body"]
        err["loc"] = loc
        err.pop("input", None)
        ctx = err.get("ctx")
        if isinstance(ctx, dict):
            err["ctx"] = {
                k: (str(v) if isinstance(v, Exception) else v) for k, v in ctx.items()
            }
        if any(part in SENSITIVE_FORM_FIELDS for part in loc):
            err.pop("ctx", None)
            err["msg"] = "Invalid value."
        serializable_errors.append(err)
    return serializable_errors


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
) -> MediaWikiDumpOptionsForm:
    """
    Shared dependency for MediaWiki dump processing/ingest endpoints.

    Parses simple form fields into a MediaWikiDumpOptionsForm used by the
    underlying MediaWiki ingestion pipeline.
    """
    normalized_namespaces = namespaces_str.strip() if namespaces_str is not None else None
    if normalized_namespaces == "":
        normalized_namespaces = None
    try:
        return MediaWikiDumpOptionsForm(
            wiki_name=wiki_name,
            namespaces_str=normalized_namespaces,
            skip_redirects=skip_redirects,
            chunk_max_size=chunk_max_size,
            api_name_vector_db=api_name_vector_db,
            api_key_vector_db=api_key_vector_db,
        )
    except ValidationError as exc:
        raise APIValidationError(
            detail=_sanitize_validation_errors(exc),
            status_code=HTTP_422_UNPROCESSABLE,
        ) from exc


__all__ = ["get_mediawiki_form_data"]
