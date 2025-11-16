from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, UploadFile

from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase

# Reuse existing form model and handler from the legacy module to preserve
# behavior while gradually extracting endpoints into per-type modules.
from tldw_Server_API.app.api.v1.endpoints import _legacy_media as legacy_media  # type: ignore

router = APIRouter()


@router.post(
    "/process-code",
    summary="Process code files (NO DB Persistence)",
    tags=["Media Processing (No DB)"],
)
async def process_code_endpoint(
    db: MediaDatabase = Depends(get_media_db_for_user),
    form_data: legacy_media.ProcessCodeForm = Depends(legacy_media.get_process_code_form),
    files: Optional[List[UploadFile]] = File(
        None,
        description="Code uploads (.py, .c, .cpp, .java, .ts, etc.)",
    ),
):
    """
    Thin wrapper that delegates to the legacy implementation.

    This keeps the HTTP contract and internal behavior identical while
    allowing router wiring to move into the modular `media` package.
    """

    return await legacy_media.process_code_endpoint(  # type: ignore[func-returns-value]
        db=db,
        form_data=form_data,
        files=files,
    )


__all__ = ["router"]

