# Media_Update_lib.py
# Description: File contains functions relating to updating media items in the database.
#
from typing import Any, Optional

# Local Imports
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import (
    MediaDatabase,
)
from tldw_Server_API.app.core.DB_Management.media_db.legacy_state import (
    check_media_exists as _check_media_exists,
)
from tldw_Server_API.app.core.DB_Management.media_db.legacy_wrappers import (
    get_document_version as _get_document_version,
)

#
########################################################################################################################
#
# Functions:

def process_media_update(
    db: MediaDatabase,
    *,
    media_id: int,
    content: Optional[str] = None,
    prompt: Optional[str] = None,
    summary: Optional[str] = None,
    keywords: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Centralized media update processing (DB-layer only; no FastAPI deps).

    Behavior:
    - If content is provided: create a new DocumentVersion with provided content,
      and use provided prompt/summary (analysis_content) when present; otherwise
      fallback to latest version's prompt/analysis when available.
    - If only prompt/summary provided (no content): clone latest content into a
      new DocumentVersion while updating prompt/analysis accordingly.
    - If keywords provided: synchronize via db.update_keywords_for_media.

    Returns a concise result with the latest document version metadata.
    """
    # Verify media exists (active)
    exists_id = _check_media_exists(db, media_id=media_id)
    if not exists_id:
        return {"status": "Error", "error": "Media not found", "media_id": media_id}

    # Get latest document version for fallback fields
    latest_dv = _get_document_version(db, media_id=media_id, version_number=None, include_content=True)
    latest_content = (latest_dv or {}).get("content")
    latest_prompt = (latest_dv or {}).get("prompt")
    latest_analysis = (latest_dv or {}).get("analysis_content")

    # Decide what to write
    new_content = content if content is not None else latest_content
    new_prompt = prompt if prompt is not None else latest_prompt
    new_analysis = summary if summary is not None else latest_analysis

    if new_content is None:
        return {"status": "Error", "error": "No content available to create version", "media_id": media_id}

    with db.transaction() as conn:
        # Create a new document version
        db.create_document_version(
            media_id=media_id,
            content=new_content,
            prompt=new_prompt,
            analysis_content=new_analysis,
        )

        # Update keywords if requested
        if keywords is not None:
            db.update_keywords_for_media(media_id, keywords, conn=conn)

    # Return concise details about latest version after update
    latest_after = _get_document_version(db, media_id=media_id, version_number=None, include_content=False) or {}
    result: dict[str, Any] = {
        "status": "Success",
        "media_id": media_id,
        "latest_version": {
            "uuid": latest_after.get("uuid"),
            "version_number": latest_after.get("version_number"),
            "prompt": latest_after.get("prompt"),
            "analysis_content": latest_after.get("analysis_content"),
            "created_at": latest_after.get("created_at"),
        },
    }
    if keywords is not None:
        result["keywords_updated"] = True
    return result


def process_synced_media_update(
    db: MediaDatabase,
    *,
    media_id: int,
    content: str,
    prompt: Optional[str] = None,
    summary: Optional[str] = None,
    safe_metadata: Optional[str] = None,
) -> dict[str, Any]:
    """
    Apply a sync-driven content update while preserving main Media/FTS/version invariants.
    """
    return db.apply_synced_document_content_update(
        media_id=media_id,
        content=content,
        prompt=prompt,
        analysis_content=summary,
        safe_metadata=safe_metadata,
    )

#
# End of Media_Update_lib.py
########################################################################################################################
