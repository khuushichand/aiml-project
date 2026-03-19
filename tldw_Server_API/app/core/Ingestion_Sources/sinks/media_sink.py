from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from tldw_Server_API.app.core.DB_Management.media_db.api import get_media_repository


def _require_change_text(change: dict[str, Any]) -> str:
    text = change.get("text")
    if text is None:
        raise ValueError("Change text is required for media create/update events.")
    return str(text)


def _title_from_relative_path(relative_path: str) -> str:
    name = PurePosixPath(relative_path).name
    return name or relative_path or "synced-document"


def apply_media_change(
    media_db,
    *,
    binding: dict[str, Any] | None,
    change: dict[str, Any],
    policy: str,
) -> dict[str, Any]:
    event_type = str(change.get("event_type") or "").strip().lower()
    relative_path = str(change.get("relative_path") or "").strip()

    if event_type == "deleted":
        if binding and policy == "canonical":
            media_id = int(binding["media_id"])
            media_db.mark_as_trash(media_id)
            return {"action": "archived", "media_id": media_id}
        return {"action": "ignored_delete", "media_id": None if not binding else int(binding["media_id"])}

    text = _require_change_text(change)
    prompt = change.get("prompt")
    analysis_content = change.get("analysis_content")
    safe_metadata = change.get("safe_metadata")

    if binding:
        media_id = int(binding["media_id"])
        update_result = media_db.apply_synced_document_content_update(
            media_id=media_id,
            content=text,
            prompt=prompt,
            analysis_content=analysis_content,
            safe_metadata=safe_metadata,
        )
        return {
            "action": "version_created",
            "media_id": media_id,
            "version_number": update_result.get("document_version_number"),
        }

    create_result = get_media_repository(media_db).add_media_with_keywords(
        url=f"ingestion://{relative_path or 'document'}",
        title=_title_from_relative_path(relative_path),
        media_type="document",
        content=text,
        keywords=[],
        prompt=prompt,
        analysis_content=analysis_content,
        safe_metadata=safe_metadata,
        overwrite=False,
    )
    media_id = create_result[0] if isinstance(create_result, tuple) else create_result
    return {"action": "created", "media_id": int(media_id)}
