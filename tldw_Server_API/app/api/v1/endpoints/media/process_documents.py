from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, UploadFile

from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.Ingestion_Media_Processing.Upload_Sink import FileValidator
from tldw_Server_API.app.api.v1.endpoints import _legacy_media as legacy_media  # type: ignore

router = APIRouter()


@router.post(
    "/process-documents",
    summary="Extract, chunk, analyse Documents (NO DB Persistence)",
    tags=["Media Processing (No DB)"],
)
async def process_documents_endpoint(
    db: MediaDatabase = Depends(get_media_db_for_user),
    form_data: legacy_media.ProcessDocumentsForm = Depends(legacy_media.get_process_documents_form),
    files: Optional[List[UploadFile]] = File(
        None,
        description="Document file uploads (.txt, .md, .docx, .rtf, .html, .xml)",
    ),
    usage_log: legacy_media.UsageEventLogger = Depends(legacy_media.get_usage_event_logger),
):
    """
    Thin wrapper that delegates to the legacy implementation.

    This keeps HTTP semantics and batching behavior identical while allowing the
    `/process-documents` route to live under the modular `media` package.
    """

    # Preserve compatibility for tests that monkeypatch `media.file_validator_instance`
    # by ensuring the legacy module sees the current validator instance.
    try:
        from tldw_Server_API.app.api.v1.endpoints import media as media_mod

        validator: FileValidator = getattr(  # type: ignore[assignment]
            media_mod, "file_validator_instance", legacy_media.file_validator_instance
        )
        legacy_media.file_validator_instance = validator  # type: ignore[assignment]
    except Exception:  # pragma: no cover - defensive fallback
        pass

    return await legacy_media.process_documents_endpoint(  # type: ignore[func-returns-value]
        db=db,
        form_data=form_data,
        files=files,
        usage_log=usage_log,
    )


__all__ = ["router"]
