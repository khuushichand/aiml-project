"""
File-based template storage for Watchlists outputs.

Templates are persisted under Config_Files/templates/watchlists (or the directory
specified via WATCHLIST_TEMPLATE_DIR). Each template is stored as <name>.<format>
where format is 'md' or 'html'. Optional metadata (currently description only) is
stored in a sibling <name>.meta.json file.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from tldw_Server_API.app.core.config import settings

_SLUG_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
_SUPPORTED_SUFFIXES = {".md", ".html"}


@dataclass
class TemplateRecord:
    name: str
    format: str
    content: str
    description: Optional[str]
    updated_at: str


class TemplateNotFoundError(FileNotFoundError):
    """Raised when a requested template does not exist."""


class TemplateExistsError(FileExistsError):
    """Raised when creating a template that already exists and overwrite=False."""


def _resolved_dir() -> Path:
    configured = settings.get("WATCHLIST_TEMPLATE_DIR")
    if configured:
        base = Path(configured)
    else:
        base = (
            Path(__file__).resolve().parent.parent.parent.parent / "Config_Files" / "templates" / "watchlists"
        )
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.error(f"Failed to ensure watchlist template directory {base}: {exc}")
        raise
    return base


def _template_path(name: str, fmt: str) -> Path:
    fmt = fmt.lower()
    suffix = ".md" if fmt == "md" else ".html"
    return _resolved_dir() / f"{name}{suffix}"


def _meta_path(name: str) -> Path:
    return _resolved_dir() / f"{name}.meta.json"


def _load_description(meta_file: Path) -> Optional[str]:
    if not meta_file.exists():
        return None
    try:
        data = json.loads(meta_file.read_text(encoding="utf-8"))
        desc = data.get("description")
        return str(desc) if desc is not None else None
    except Exception as exc:
        logger.debug(f"Failed to read template metadata from {meta_file}: {exc}")
        return None


def _save_description(meta_file: Path, description: Optional[str]) -> None:
    if description:
        meta_file.write_text(json.dumps({"description": description}, ensure_ascii=False, indent=2), encoding="utf-8")
    elif meta_file.exists():
        meta_file.unlink()


def _sanitize_name(name: str) -> str:
    if not _SLUG_RE.fullmatch(name):
        raise ValueError("Template name must match ^[A-Za-z0-9_\\-]{1,64}$")
    return name


def list_templates() -> List[TemplateRecord]:
    directory = _resolved_dir()
    records: List[TemplateRecord] = []
    for path in sorted(directory.glob("*")):
        if not path.is_file() or path.suffix.lower() not in _SUPPORTED_SUFFIXES:
            continue
        name = path.stem
        fmt = path.suffix.lower().lstrip(".")
        description = _load_description(_meta_path(name))
        updated_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
        records.append(
            TemplateRecord(
                name=name,
                format=fmt,
                content="",
                description=description,
                updated_at=updated_at,
            )
        )
    return records


def load_template(name: str) -> TemplateRecord:
    name = _sanitize_name(name)
    directory = _resolved_dir()
    for suffix in _SUPPORTED_SUFFIXES:
        candidate = directory / f"{name}{suffix}"
        if candidate.exists():
            fmt = suffix.lstrip(".")
            content = candidate.read_text(encoding="utf-8")
            description = _load_description(_meta_path(name))
            updated_at = datetime.fromtimestamp(candidate.stat().st_mtime, timezone.utc).isoformat()
            return TemplateRecord(
                name=name,
                format=fmt,
                content=content,
                description=description,
                updated_at=updated_at,
            )
    raise TemplateNotFoundError(name)


def save_template(
    name: str,
    fmt: str,
    content: str,
    *,
    description: Optional[str] = None,
    overwrite: bool = False,
) -> TemplateRecord:
    name = _sanitize_name(name)
    fmt = fmt.lower()
    if fmt not in {"md", "html"}:
        raise ValueError("Template format must be 'md' or 'html'")
    path = _template_path(name, fmt)
    directory = path.parent

    # Determine if any variant exists
    existing_variants = [
        directory / f"{name}{suffix}" for suffix in _SUPPORTED_SUFFIXES if (directory / f"{name}{suffix}").exists()
    ]
    if existing_variants and not overwrite:
        raise TemplateExistsError(name)

    # Clean up other variants when overwriting
    for other in existing_variants:
        if other != path:
            other.unlink()

    path.write_text(content, encoding="utf-8")
    _save_description(_meta_path(name), description)
    return load_template(name)


def delete_template(name: str) -> None:
    name = _sanitize_name(name)
    directory = _resolved_dir()
    removed = False
    for suffix in _SUPPORTED_SUFFIXES:
        candidate = directory / f"{name}{suffix}"
        if candidate.exists():
            candidate.unlink()
            removed = True
    meta = _meta_path(name)
    if meta.exists():
        meta.unlink()
    if not removed:
        raise TemplateNotFoundError(name)
