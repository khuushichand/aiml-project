from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tldw_Server_API.app.core.Ingestion_Media_Processing.Plaintext.Plaintext_Files import (
    convert_document_to_text,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.path_utils import resolve_safe_local_path
from tldw_Server_API.app.core.Ingestion_Media_Processing.path_utils import open_safe_local_path
from tldw_Server_API.app.core.config import get_ingestion_source_allowed_roots

NOTES_SUPPORTED_SUFFIXES: frozenset[str] = frozenset(
    {
        ".docx",
        ".htm",
        ".html",
        ".json",
        ".markdown",
        ".md",
        ".rtf",
        ".txt",
        ".xml",
    }
)
MEDIA_SUPPORTED_SUFFIXES: frozenset[str] = frozenset(NOTES_SUPPORTED_SUFFIXES)


def validate_local_directory_source(config: dict[str, Any]) -> Path:
    raw_path = str(config.get("path") or "").strip()
    if not raw_path:
        raise ValueError("Local directory source requires a non-empty path.")

    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate

    resolved_candidate = candidate.resolve(strict=False)
    allowed_roots = get_ingestion_source_allowed_roots()
    if not allowed_roots:
        raise ValueError("No ingestion source allowed roots are configured.")

    for allowed_root in allowed_roots:
        safe_path = resolve_safe_local_path(resolved_candidate, allowed_root)
        if safe_path is None:
            continue
        if not safe_path.exists():
            raise ValueError(f"Local directory source path does not exist: {safe_path}")
        if not safe_path.is_dir():
            raise ValueError(f"Local directory source path is not a directory: {safe_path}")
        return safe_path

    allowed_display = ", ".join(str(root) for root in allowed_roots)
    raise ValueError(
        "Local directory source path must resolve under one of the configured allowed roots: "
        f"{allowed_display}"
    )


def _supported_suffixes_for_sink(sink_type: str) -> frozenset[str]:
    normalized = str(sink_type or "").strip().lower()
    if normalized == "notes":
        return NOTES_SUPPORTED_SUFFIXES
    return MEDIA_SUPPORTED_SUFFIXES


def _read_markdown_alias(path: Path, base_dir: Path) -> str:
    handle = open_safe_local_path(path, base_dir, mode="rb")
    if handle is None:
        raise ValueError(f"Local directory source path rejected: {path}")
    with handle:
        data = handle.read()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def build_local_directory_snapshot(
    config: dict[str, Any],
    *,
    sink_type: str,
) -> dict[str, dict[str, Any]]:
    source_root = validate_local_directory_source(config)
    supported_suffixes = _supported_suffixes_for_sink(sink_type)
    snapshot_items: dict[str, dict[str, Any]] = {}

    for candidate in sorted(source_root.rglob("*")):
        if not candidate.is_file() or candidate.is_symlink():
            continue
        safe_path = resolve_safe_local_path(candidate, source_root)
        if safe_path is None:
            continue
        suffix = safe_path.suffix.lower()
        if suffix not in supported_suffixes:
            continue

        if suffix == ".markdown":
            text_content = _read_markdown_alias(safe_path, source_root)
            source_format = "markdown"
            raw_metadata: dict[str, Any] = {}
        else:
            text_content, source_format, raw_metadata = convert_document_to_text(
                safe_path,
                base_dir=source_root,
            )

        stat = safe_path.stat()
        relative_path = safe_path.relative_to(source_root).as_posix()
        snapshot_items[relative_path] = {
            "relative_path": relative_path,
            "absolute_path": str(safe_path),
            "content_hash": hashlib.sha256(text_content.encode("utf-8")).hexdigest(),
            "modified_at": datetime.fromtimestamp(
                stat.st_mtime,
                tz=timezone.utc,
            ).strftime("%Y-%m-%d %H:%M:%S"),
            "size": int(stat.st_size),
            "source_format": source_format,
            "raw_metadata": raw_metadata,
            "text": text_content,
        }

    return snapshot_items
