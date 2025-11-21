from __future__ import annotations

from typing import Any, AsyncGenerator, Dict

import asyncio
import json
import shutil
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from loguru import logger
from starlette.responses import StreamingResponse

from tldw_Server_API.app.api.v1.API_Deps.backpressure import (
    guard_backpressure_and_quota,
)
from tldw_Server_API.app.api.v1.API_Deps.media_mediawiki_deps import (
    get_mediawiki_form_data,
)
from tldw_Server_API.app.api.v1.schemas.media_request_models import (
    ProcessedMediaWikiPage,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.MediaWiki.Media_Wiki import (
    import_mediawiki_dump as core_import_mediawiki_dump,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.input_sourcing import (
    TempDirManager,
)
from tldw_Server_API.app.core.Utils.Utils import sanitize_filename
from pydantic import ValidationError

router = APIRouter()


async def _process_mediawiki_dump(
    *,
    form_data: Dict[str, Any],
    dump_file: UploadFile,
    store_to_db: bool,
    store_to_vector_db: bool,
    filter_item_results: bool,
) -> StreamingResponse:
    """Shared ingestion/processing helper."""
    if core_import_mediawiki_dump is None:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="MediaWiki processing module not loaded.",
        )

    if not dump_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dump file has no filename.",
        )

    prefix = "mediawiki_ingest_" if store_to_db or store_to_vector_db else "mediawiki_process_"
    with TempDirManager(prefix=prefix, cleanup=False) as temp_dir:
        temp_dir_path = Path(temp_dir)
        temp_file_path = temp_dir_path / sanitize_filename(dump_file.filename)
        try:
            async with aiofiles.open(temp_file_path, "wb") as f:
                while True:
                    chunk = await dump_file.read(8192)
                    if not chunk:
                        break
                    await f.write(chunk)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to save uploaded MediaWiki dump: {}", exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save uploaded file",
            ) from exc
        finally:
            try:
                await dump_file.close()
            except Exception:
                pass

        logger.info("MediaWiki dump saved to temporary path: {}", temp_file_path)

        async def stream_ingestion_results() -> AsyncGenerator[str, None]:
            try:
                for result_event in core_import_mediawiki_dump(
                    file_path=str(temp_file_path),
                    wiki_name=form_data["wiki_name"],
                    namespaces=form_data["namespaces"],
                    skip_redirects=form_data["skip_redirects"],
                    chunk_options_override=form_data["chunk_options_override"],
                    store_to_db=store_to_db,
                    store_to_vector_db=store_to_vector_db,
                    api_name_vector_db=form_data.get("api_name_vector_db"),
                    api_key_vector_db=form_data.get("api_key_vector_db"),
                ):
                    if filter_item_results and result_event.get("type") == "item_result":
                        page_data = result_event.get("data", {})
                        try:
                            processed_page_model = ProcessedMediaWikiPage(**page_data)
                            yield json.dumps(processed_page_model.model_dump()) + "\n"
                        except ValidationError as ve:
                            logger.error(
                                "Validation error for processed MediaWiki page "
                                "'{}': {}",
                                page_data.get("title", "Unknown"),
                                ve.errors(),
                            )
                            error_output = {
                                "type": "validation_error",
                                "title": page_data.get("title", "Unknown"),
                                "page_id": page_data.get("page_id"),
                                "detail": ve.errors(),
                            }
                            yield json.dumps(error_output) + "\n"
                    else:
                        yield json.dumps(result_event) + "\n"

                    await asyncio.sleep(0.01)
            finally:
                try:
                    shutil.rmtree(temp_dir_path, ignore_errors=True)
                    logger.info("Cleaned up temporary directory: {}", temp_dir_path)
                except Exception:  # noqa: BLE001
                    logger.warning("Failed to cleanup temporary directory: {}", temp_dir_path)

        return StreamingResponse(
            stream_ingestion_results(),
            media_type="application/x-ndjson",
        )


@router.post(
    "/mediawiki/ingest-dump",
    summary="Ingest and process a MediaWiki XML dump, storing results to database and vector store.",
    tags=["MediaWiki Processing"],
    dependencies=[Depends(guard_backpressure_and_quota)],
)
async def ingest_mediawiki_dump_endpoint(
    form_data: Dict[str, Any] = Depends(get_mediawiki_form_data),
    dump_file: UploadFile = File(
        ...,
        description="MediaWiki XML dump file (.xml, .xml.bz2, .xml.gz).",
    ),
) -> StreamingResponse:
    """
    MediaWiki ingest endpoint (streaming).

    Streams ingestion events while processing a MediaWiki XML dump and
    persisting results to the primary database and vector store.
    """
    return await _process_mediawiki_dump(
        form_data=form_data,
        dump_file=dump_file,
        store_to_db=True,
        store_to_vector_db=True,
        filter_item_results=False,
    )


@router.post(
    "/mediawiki/process-dump",
    summary="Process a MediaWiki XML dump and return structured content without database storage.",
    tags=["MediaWiki Processing"],
)
async def process_mediawiki_dump_ephemeral_endpoint(
    form_data: Dict[str, Any] = Depends(get_mediawiki_form_data),
    dump_file: UploadFile = File(
        ...,
        description="MediaWiki XML dump file (.xml, .xml.bz2, .xml.gz).",
    ),
) -> StreamingResponse:
    """
    MediaWiki processing endpoint (ephemeral, streaming).

    Streams processed items from a MediaWiki XML dump without saving to the
    main database or vector store. Each line in the response is a JSON object.
    """
    return await _process_mediawiki_dump(
        form_data=form_data,
        dump_file=dump_file,
        store_to_db=False,
        store_to_vector_db=False,
        filter_item_results=True,
    )


__all__ = ["router"]
