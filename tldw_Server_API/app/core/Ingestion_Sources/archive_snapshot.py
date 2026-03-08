from __future__ import annotations

import hashlib
import io
import stat
import zipfile
from pathlib import PurePosixPath
from typing import Any
from uuid import uuid4

from tldw_Server_API.app.core.Ingestion_Sources.diffing import normalize_archive_members


def _is_safe_archive_member_name(member_name: str) -> bool:
    if not member_name:
        return False
    normalized = member_name.replace("\\", "/")
    if normalized.startswith("/"):
        return False
    pure_path = PurePosixPath(normalized)
    if ".." in pure_path.parts:
        return False
    return True


async def stage_archive_candidate(
    *,
    source_id: int,
    filename: str,
    current_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "id": f"candidate-{uuid4()}",
        "source_id": int(source_id),
        "filename": filename,
        "status": "candidate",
        "previous_snapshot_id": None if current_snapshot is None else current_snapshot.get("id"),
    }


async def mark_snapshot_failed(candidate: dict[str, Any]) -> dict[str, Any]:
    candidate["status"] = "failed"
    return candidate


def validate_archive_members(
    archive_bytes: bytes,
    *,
    filename: str,
) -> list[tuple[zipfile.ZipInfo, bytes]]:
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as archive:
            members: list[tuple[zipfile.ZipInfo, bytes]] = []
            for member in archive.infolist():
                if member.is_dir():
                    continue
                if not _is_safe_archive_member_name(member.filename):
                    raise ValueError(f"Archive contains unsafe path: {member.filename}")
                if getattr(member, "flag_bits", 0) & 0x1:
                    raise ValueError("Encrypted ZIP archives are not supported.")
                external_type = (member.external_attr >> 16) & 0xFFFF
                if external_type and stat.S_ISLNK(external_type):
                    raise ValueError(f"Archive contains symbolic link: {member.filename}")
                with archive.open(member, "r") as handle:
                    members.append((member, handle.read()))
            return members
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Invalid ZIP archive: {filename}") from exc


def build_archive_snapshot(
    members: list[tuple[zipfile.ZipInfo, bytes]],
) -> dict[str, dict[str, str | None]]:
    hashes: dict[str, str] = {}
    member_names: list[str] = []
    for member, content in members:
        member_names.append(member.filename)
        hashes[member.filename] = hashlib.sha256(content).hexdigest()
    return normalize_archive_members(member_names, hashes)


async def apply_archive_candidate(
    *,
    source_id: int,
    archive_bytes: bytes,
    filename: str,
    current_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    candidate = await stage_archive_candidate(
        source_id=source_id,
        filename=filename,
        current_snapshot=current_snapshot,
    )
    try:
        members = validate_archive_members(archive_bytes, filename=filename)
        items = build_archive_snapshot(members)
    except Exception:
        await mark_snapshot_failed(candidate)
        raise

    candidate["status"] = "staged"
    return {
        "candidate_snapshot": candidate,
        "items": items,
    }
