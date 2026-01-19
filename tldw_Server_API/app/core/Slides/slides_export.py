"""Export utilities for Slides presentations."""

from __future__ import annotations

import io
import json
import os
import re
import zipfile
from html import escape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from loguru import logger

try:
    import bleach  # type: ignore
    from bleach.css_sanitizer import CSSSanitizer  # type: ignore
except Exception:  # pragma: no cover - bleach is a declared dependency
    bleach = None
    CSSSanitizer = None  # type: ignore

try:
    import markdown  # type: ignore
except Exception as exc:  # pragma: no cover - markdown is a declared dependency
    raise RuntimeError("markdown package is required for slides export") from exc

from tldw_Server_API.app.core.config import settings


class SlidesExportError(Exception):
    """Base exception for slides export errors."""


class SlidesAssetsMissingError(SlidesExportError):
    """Raised when Reveal.js assets are missing."""


class SlidesExportInputError(SlidesExportError):
    """Raised for invalid export inputs."""


_REVEAL_THEME_TO_MARP = {
    "black": "default",
    "white": "default",
    "league": "gaia",
    "beige": "gaia",
    "sky": "uncover",
    "night": "uncover",
    "serif": "gaia",
    "simple": "default",
    "solarized": "gaia",
    "blood": "uncover",
    "moon": "uncover",
    "dracula": "uncover",
}

_ALLOWED_HTML_TAGS = [
    "a",
    "blockquote",
    "br",
    "code",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
]

_ALLOWED_HTML_ATTRS = {
    "a": ["href", "title", "rel", "target"],
    "code": ["class"],
    "pre": ["class"],
    "h1": ["id"],
    "h2": ["id"],
    "h3": ["id"],
    "h4": ["id"],
    "h5": ["id"],
    "h6": ["id"],
}

_ALLOWED_PROTOCOLS = ["http", "https", "mailto"]

_ALLOWED_CSS_PROPERTIES = [
    "align-content",
    "align-items",
    "align-self",
    "background",
    "background-color",
    "border",
    "border-color",
    "border-radius",
    "border-style",
    "border-width",
    "box-shadow",
    "color",
    "display",
    "flex",
    "flex-direction",
    "flex-grow",
    "flex-wrap",
    "font",
    "font-family",
    "font-size",
    "font-style",
    "font-weight",
    "height",
    "justify-content",
    "letter-spacing",
    "line-height",
    "margin",
    "margin-bottom",
    "margin-left",
    "margin-right",
    "margin-top",
    "max-height",
    "max-width",
    "min-height",
    "min-width",
    "opacity",
    "overflow",
    "padding",
    "padding-bottom",
    "padding-left",
    "padding-right",
    "padding-top",
    "position",
    "text-align",
    "text-decoration",
    "text-transform",
    "text-shadow",
    "top",
    "right",
    "bottom",
    "left",
    "width",
]


def _get_slide_value(slide: Any, key: str, default: Any = None) -> Any:
    if isinstance(slide, dict):
        return slide.get(key, default)
    return getattr(slide, key, default)


def _sorted_slides(slides: Iterable[Any]) -> List[Any]:
    return sorted(list(slides), key=lambda s: int(_get_slide_value(s, "order", 0)))


def _sanitize_markdown(markdown_text: str) -> str:
    html = markdown.markdown(markdown_text or "", extensions=["extra", "sane_lists"], output_format="html5")
    if bleach is None:
        return escape(html)
    return bleach.clean(
        html,
        tags=_ALLOWED_HTML_TAGS,
        attributes=_ALLOWED_HTML_ATTRS,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=True,
    )


def _sanitize_custom_css(css_text: Optional[str]) -> Optional[str]:
    if not css_text:
        return None
    if re.search(r"@import", css_text, flags=re.IGNORECASE):
        raise SlidesExportInputError("custom_css_import_blocked")
    if re.search(r"url\s*\(", css_text, flags=re.IGNORECASE):
        raise SlidesExportInputError("custom_css_url_blocked")
    cleaned = css_text
    if CSSSanitizer is not None:
        try:
            sanitizer = CSSSanitizer(allowed_css_properties=_ALLOWED_CSS_PROPERTIES)
            cleaned = sanitizer.sanitize_css(css_text)
        except Exception as exc:
            logger.warning("slides export: css sanitizer failed: %s", exc)
            cleaned = ""
    cleaned = cleaned.replace("\x00", "").strip()
    return cleaned or None


def _resolve_assets_dir(assets_dir: Optional[Path | str]) -> Path:
    if assets_dir:
        return Path(assets_dir).expanduser().resolve()
    env_path = os.getenv("SLIDES_REVEALJS_ASSETS_DIR")
    if env_path:
        base = Path(env_path).expanduser()
        if not base.is_absolute():
            project_root = settings.get("PROJECT_ROOT")
            if project_root:
                base = Path(project_root) / base
        return base.resolve()
    return (Path(__file__).resolve().parent / "revealjs").resolve()


def _find_license_file(assets_dir: Path) -> Optional[Path]:
    candidates = [
        assets_dir / "LICENSE.revealjs.txt",
        assets_dir / "LICENSE",
        assets_dir / "LICENSE.txt",
        assets_dir / "LICENSE.md",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _find_notice_file(assets_dir: Path) -> Optional[Path]:
    candidates = [
        assets_dir / "NOTICE.revealjs.txt",
        assets_dir / "NOTICE",
        assets_dir / "NOTICE.txt",
        assets_dir / "NOTICE.md",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _validate_reveal_assets(assets_dir: Path, theme: str) -> None:
    required = [
        assets_dir / "reveal.js",
        assets_dir / "reveal.css",
        assets_dir / "plugin" / "notes" / "notes.js",
        assets_dir / "theme" / f"{theme}.css",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        missing_list = ", ".join(str(p) for p in missing)
        raise SlidesAssetsMissingError(f"Reveal.js assets missing: {missing_list}")
    if _find_license_file(assets_dir) is None:
        raise SlidesAssetsMissingError("Reveal.js LICENSE file missing")


def _render_sections(slides: Iterable[Any]) -> str:
    sections: List[str] = []
    for slide in _sorted_slides(slides):
        layout = escape(str(_get_slide_value(slide, "layout", "content")))
        title = _get_slide_value(slide, "title")
        content = _get_slide_value(slide, "content", "")
        notes = _get_slide_value(slide, "speaker_notes")

        title_html = f"<h2>{escape(str(title))}</h2>" if title else ""
        content_html = _sanitize_markdown(str(content or "")) if content else ""
        notes_html = f"<aside class=\"notes\">{escape(str(notes))}</aside>" if notes else ""

        section = (
            f"      <section data-layout=\"{layout}\">\n"
            f"        {title_html}\n"
            f"        <div class=\"content\">{content_html}</div>\n"
            f"        {notes_html}\n"
            f"      </section>"
        )
        sections.append(section)
    return "\n".join(sections)


def _render_index_html(
    *,
    title: str,
    slides: Iterable[Any],
    theme: str,
    settings_json: str,
    include_custom_css: bool,
) -> str:
    css_link = "  <link rel=\"stylesheet\" href=\"assets/custom.css\">\n" if include_custom_css else ""
    title_html = escape(title or "Presentation")
    sections_html = _render_sections(slides)
    return (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        f"  <title>{title_html}</title>\n"
        "  <link rel=\"stylesheet\" href=\"assets/reveal/reveal.css\">\n"
        f"  <link rel=\"stylesheet\" href=\"assets/reveal/theme/{escape(theme)}.css\">\n"
        f"{css_link}"
        "</head>\n"
        "<body>\n"
        "  <div class=\"reveal\">\n"
        "    <div class=\"slides\">\n"
        f"{sections_html}\n"
        "    </div>\n"
        "  </div>\n"
        "  <script src=\"assets/reveal/reveal.js\"></script>\n"
        "  <script src=\"assets/reveal/plugin/notes/notes.js\"></script>\n"
        "  <script>\n"
        f"    const settings = {settings_json};\n"
        "    settings.plugins = [ RevealNotes ];\n"
        "    Reveal.initialize(settings);\n"
        "  </script>\n"
        "</body>\n"
        "</html>"
    )


def export_presentation_bundle(
    *,
    title: str,
    slides: Iterable[Any],
    theme: str,
    settings: Optional[Dict[str, Any]],
    custom_css: Optional[str],
    assets_dir: Optional[Path | str] = None,
) -> bytes:
    resolved_assets = _resolve_assets_dir(assets_dir)
    _validate_reveal_assets(resolved_assets, theme)
    settings_json = json.dumps(settings or {}, ensure_ascii=True)
    sanitized_css = _sanitize_custom_css(custom_css)
    index_html = _render_index_html(
        title=title,
        slides=slides,
        theme=theme,
        settings_json=settings_json,
        include_custom_css=bool(sanitized_css),
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.html", index_html)
        if sanitized_css:
            zf.writestr("assets/custom.css", sanitized_css)

        license_file = _find_license_file(resolved_assets)
        if license_file:
            zf.write(license_file, "LICENSE.revealjs.txt")
        notice_file = _find_notice_file(resolved_assets)
        if notice_file:
            zf.write(notice_file, "NOTICE.revealjs.txt")

        for path in resolved_assets.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(resolved_assets)
            zf.write(path, (Path("assets") / "reveal" / rel).as_posix())

    return buffer.getvalue()


def export_presentation_markdown(
    *,
    title: str,
    slides: Iterable[Any],
    theme: str,
    marp_theme: Optional[str] = None,
) -> str:
    resolved_theme = marp_theme or _REVEAL_THEME_TO_MARP.get(theme, "default")
    lines: List[str] = [
        "---",
        "marp: true",
        f"theme: {resolved_theme}",
        "---",
        "",
    ]
    for slide in _sorted_slides(slides):
        layout = str(_get_slide_value(slide, "layout", "content"))
        slide_title = _get_slide_value(slide, "title")
        content = _get_slide_value(slide, "content", "")
        notes = _get_slide_value(slide, "speaker_notes")
        if layout in {"title", "section"} and slide_title:
            header = "# " if layout == "title" else "## "
            lines.append(f"{header}{slide_title}")
            lines.append("")
        elif slide_title:
            lines.append(f"## {slide_title}")
            lines.append("")
        if content:
            lines.append(str(content))
            lines.append("")
        if notes:
            lines.append("<!--")
            lines.append(str(notes))
            lines.append("-->")
            lines.append("")
        lines.append("---")
        lines.append("")
    if lines and lines[-1] == "":
        lines.pop()
    if lines and lines[-1] == "---":
        lines.pop()
    return "\n".join(lines).strip() + "\n"


def export_presentation_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, indent=2)
