from __future__ import annotations

import contextlib
import hashlib
import io
import stat
import tempfile
import zipfile
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any
from uuid import uuid4

from tldw_Server_API.app.core.Ingestion_Sources.diffing import normalize_archive_members
from tldw_Server_API.app.core.Ingestion_Sources.local_directory import (
    MEDIA_SUPPORTED_SUFFIXES,
    NOTES_SUPPORTED_SUFFIXES,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.Plaintext.Plaintext_Files import (
    convert_document_to_text,
)

SUPPORTED_ARCHIVE_SUFFIXES: frozenset[str] = frozenset(
    NOTES_SUPPORTED_SUFFIXES | MEDIA_SUPPORTED_SUFFIXES
)


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
) -> dict[str, dict[str, Any]]:
    hashes: dict[str, str] = {}
    member_names: list[str] = []
    raw_contents: dict[str, bytes] = {}
    for member, content in members:
        suffix = PurePosixPath(member.filename).suffix.lower()
        if suffix not in SUPPORTED_ARCHIVE_SUFFIXES:
            continue
        member_names.append(member.filename)
        raw_contents[member.filename] = content
        hashes[member.filename] = hashlib.sha256(content).hexdigest()

    items = normalize_archive_members(member_names, hashes)
    for member_name in member_names:
        relative_path = str(items[_normalized_relative_path(items, member_name)]["relative_path"])
        text_content, source_format, raw_metadata = _member_content_to_text(
            member_name=member_name,
            content=raw_contents[member_name],
        )
        items[relative_path].update(
            {
                "text": text_content,
                "source_format": source_format,
                "raw_metadata": raw_metadata,
                "size": len(raw_contents[member_name]),
                "content_hash": hashlib.sha256(text_content.encode("utf-8")).hexdigest(),
            }
        )
    return items


def _normalized_relative_path(items: dict[str, dict[str, Any]], member_name: str) -> str:
    for relative_path, item in items.items():
        if item.get("relative_path") == relative_path:
            normalized_member = member_name.replace("\\", "/").strip().strip("/")
            if normalized_member.endswith(relative_path):
                return relative_path
    raise KeyError(member_name)


def _member_content_to_text(
    *,
    member_name: str,
    content: bytes,
) -> tuple[str, str, dict[str, Any]]:
    suffix = PurePosixPath(member_name).suffix.lower()
    if suffix == ".markdown":
        try:
            text_content = content.decode("utf-8")
        except UnicodeDecodeError:
            text_content = content.decode("latin-1")
        return text_content, "markdown", {}

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            handle.write(content)
            temp_path = Path(handle.name)
        return convert_document_to_text(temp_path)
    finally:
        if temp_path is not None:
            with contextlib.suppress(FileNotFoundError, OSError):
                temp_path.unlink()


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
