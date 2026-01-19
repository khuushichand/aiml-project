"""Template loader for Slides presentations."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from tldw_Server_API.app.core.config import settings


class SlidesTemplateError(Exception):
    """Base exception for slides template errors."""


class SlidesTemplateNotFoundError(SlidesTemplateError):
    """Raised when a template id is not found."""


class SlidesTemplateInvalidError(SlidesTemplateError):
    """Raised when templates payload is invalid."""


@dataclass(frozen=True)
class SlidesTemplate:
    template_id: str
    name: str
    theme: str
    marp_theme: Optional[str]
    settings: Optional[Dict[str, Any]]
    default_slides: Optional[List[Dict[str, Any]]]
    custom_css: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.template_id,
            "name": self.name,
            "theme": self.theme,
            "marp_theme": self.marp_theme,
            "settings": self.settings,
            "default_slides": self.default_slides,
            "custom_css": self.custom_css,
        }


def _resolve_templates_path(path_override: Optional[Path | str] = None) -> Path:
    if path_override:
        return Path(path_override).expanduser().resolve()
    env_path = os.getenv("SLIDES_TEMPLATES_PATH")
    if env_path:
        base = Path(env_path).expanduser()
        if not base.is_absolute():
            project_root = settings.get("PROJECT_ROOT")
            if project_root:
                base = Path(project_root) / base
        return base.resolve()
    return (Path(__file__).resolve().parent / "templates.json").resolve()


@lru_cache(maxsize=4)
def _load_templates_from_path(path_str: str) -> List[Dict[str, Any]]:
    path = Path(path_str)
    if not path.exists():
        logger.debug("slides templates file not found: %s", path)
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SlidesTemplateInvalidError("templates_json_invalid") from exc
    templates = raw.get("templates") if isinstance(raw, dict) else raw
    if templates is None:
        return []
    if not isinstance(templates, list):
        raise SlidesTemplateInvalidError("templates_payload_invalid")
    return templates


def _normalize_template(raw: Dict[str, Any]) -> SlidesTemplate:
    if not isinstance(raw, dict):
        raise SlidesTemplateInvalidError("template_entry_invalid")
    template_id = str(raw.get("id") or "").strip()
    name = str(raw.get("name") or "").strip()
    if not template_id or not name:
        raise SlidesTemplateInvalidError("template_missing_fields")
    theme = str(raw.get("theme") or "black").strip() or "black"
    marp_theme = raw.get("marp_theme")
    if marp_theme is not None and not isinstance(marp_theme, str):
        raise SlidesTemplateInvalidError("template_marp_theme_invalid")
    settings = raw.get("settings")
    if settings is not None and not isinstance(settings, dict):
        raise SlidesTemplateInvalidError("template_settings_invalid")
    default_slides = raw.get("default_slides")
    if default_slides is not None and not isinstance(default_slides, list):
        raise SlidesTemplateInvalidError("template_slides_invalid")
    custom_css = raw.get("custom_css")
    if custom_css is not None and not isinstance(custom_css, str):
        raise SlidesTemplateInvalidError("template_custom_css_invalid")
    return SlidesTemplate(
        template_id=template_id,
        name=name,
        theme=theme,
        marp_theme=marp_theme,
        settings=settings,
        default_slides=default_slides,
        custom_css=custom_css,
    )


def list_slide_templates(path_override: Optional[Path | str] = None) -> List[SlidesTemplate]:
    path = _resolve_templates_path(path_override)
    raw_templates = _load_templates_from_path(str(path))
    templates: List[SlidesTemplate] = []
    seen: set[str] = set()
    for entry in raw_templates:
        template = _normalize_template(entry)
        if template.template_id in seen:
            raise SlidesTemplateInvalidError("template_duplicate_id")
        seen.add(template.template_id)
        templates.append(template)
    return templates


def get_slide_template(template_id: str, path_override: Optional[Path | str] = None) -> SlidesTemplate:
    lookup = (template_id or "").strip()
    if not lookup:
        raise SlidesTemplateNotFoundError("template_id_required")
    for template in list_slide_templates(path_override):
        if template.template_id == lookup:
            return template
    raise SlidesTemplateNotFoundError("template_not_found")
