from __future__ import annotations

from typing import Any, List, Optional

from fastapi import BackgroundTasks, UploadFile

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


async def add_media_persist(
    background_tasks: BackgroundTasks,
    form_data: Any,
    files: Optional[List[UploadFile]],
    db: MediaDatabase,
    current_user: Any,
    usage_log: Any,
    response: Any = None,
) -> Any:
    """
    Temporary persistence helper for the `/media/add` endpoint.

    This currently delegates to the legacy `_legacy_media.add_media`
    implementation to preserve behavior while providing a single
    indirection point that can be refactored in future work to:

    - Take already-processed item dictionaries and user/DB context.
    - Perform DB writes (`add_media_with_keywords`, version creation,
      keyword/index maintenance, claims storage).
    - Return updated result dictionaries (`db_id`, `db_message`,
      `claims_details`, etc.).
    """
    # Imported lazily to avoid circular imports at module import time.
    from tldw_Server_API.app.api.v1.endpoints import (  # type: ignore
        _legacy_media as legacy_media,
    )

    return await legacy_media.add_media(
        background_tasks=background_tasks,
        form_data=form_data,
        files=files,
        db=db,
        current_user=current_user,
        usage_log=usage_log,
        response=response,
    )


__all__ = ["add_media_persist"]

