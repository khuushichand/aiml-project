from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any


def _title_from_text(relative_path: str, text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            if title:
                return title
        return stripped

    fallback = PurePosixPath(relative_path).stem
    return fallback or "synced-note"


def _expected_version(binding: dict[str, Any]) -> int:
    raw = (
        binding.get("current_version")
        or binding.get("version")
        or binding.get("expected_version")
        or 1
    )
    return int(raw)


def apply_notes_change(
    notes_db,
    *,
    binding: dict[str, Any] | None,
    change: dict[str, Any],
    policy: str,
) -> dict[str, Any]:
    sync_status = None if not binding else binding.get("sync_status")
    if binding and sync_status == "conflict_detached":
        return {"action": "skipped_detached", "sync_status": "conflict_detached"}

    event_type = str(change.get("event_type") or "").strip().lower()
    if event_type == "deleted":
        if binding and policy == "canonical":
            note_id = str(binding["note_id"])
            if hasattr(notes_db, "soft_delete_note"):
                notes_db.soft_delete_note(note_id, _expected_version(binding))
            return {
                "action": "archived",
                "note_id": note_id,
                "sync_status": "archived_upstream_removed",
            }
        return {"action": "ignored_delete", "sync_status": sync_status}

    text = change.get("text")
    if text is None:
        raise ValueError("Change text is required for notes create/update events.")
    body = str(text)
    relative_path = str(change.get("relative_path") or "").strip()
    title = _title_from_text(relative_path, body)

    if binding:
        note_id = str(binding["note_id"])
        notes_db.update_note(
            note_id,
            {"title": title, "content": body},
            expected_version=_expected_version(binding),
        )
        return {"action": "updated", "note_id": note_id, "sync_status": "sync_managed"}

    note_id = notes_db.add_note(title=title, content=body)
    return {"action": "created", "note_id": note_id, "sync_status": "sync_managed"}
