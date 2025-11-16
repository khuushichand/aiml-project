from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, File, UploadFile

from tldw_Server_API.app.api.v1.endpoints import _legacy_media as legacy_media  # type: ignore

router = APIRouter()


@router.post(
    "/mediawiki/process-dump",
    summary="Process a MediaWiki XML dump and return structured content without database storage.",
    tags=["MediaWiki Processing"],
)
async def process_mediawiki_dump_ephemeral_endpoint(
    form_data: Dict[str, Any] = Depends(legacy_media.get_mediawiki_form_data),  # type: ignore[attr-defined]
    dump_file: UploadFile = File(
        ...,
        description="MediaWiki XML dump file (.xml, .xml.bz2, .xml.gz).",
    ),
):
    """
    Thin wrapper that delegates to the legacy implementation.

    This keeps the streaming NDJSON behavior, response shape, and status codes
    identical while allowing the `/mediawiki/process-dump` route to live under
    the modular `media` package.
    """

    return await legacy_media.process_mediawiki_dump_ephemeral_endpoint(  # type: ignore[func-returns-value]
        form_data=form_data,
        dump_file=dump_file,
    )


__all__ = ["router"]

