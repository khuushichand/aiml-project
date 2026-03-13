"""Export utilities for Slides presentations."""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import tempfile
import zipfile
from collections.abc import Callable, Iterable
from html import escape
from pathlib import Path
from typing import Any

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

try:
    from playwright.sync_api import Error as PlaywrightError  # type: ignore
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError  # type: ignore
    from playwright.sync_api import sync_playwright  # type: ignore
except Exception:  # pragma: no cover - playwright is an optional dependency
    sync_playwright = None
    PlaywrightError = Exception  # type: ignore
    PlaywrightTimeoutError = TimeoutError  # type: ignore

from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.Slides.slides_assets import SlidesAssetError, resolve_slide_asset
from tldw_Server_API.app.core.Slides.slides_images import SlidesImageError, validate_images_payload
from tldw_Server_API.app.core.testing import is_truthy


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

_PDF_FORMAT_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_PDF_DIMENSION_RE = re.compile(r"^\d+(\.\d+)?(px|in|cm|mm)$")
_PDF_MARGIN_RE = re.compile(r"^\d+(\.\d+)?(px|in|cm|mm)?$")

_DEFAULT_PDF_FORMAT = "A4"
_DEFAULT_PDF_MARGIN = "0.4in"
_DEFAULT_PDF_TIMEOUT_SECONDS = 60
_DEFAULT_PDF_MAX_SLIDES = 200
_DEFAULT_PDF_MAX_HTML_BYTES = 25 * 1024 * 1024
SlideAssetResolver = Callable[[str], dict[str, Any]]


def _get_slide_value(slide: Any, key: str, default: Any = None) -> Any:
    if isinstance(slide, dict):
        return slide.get(key, default)
    return getattr(slide, key, default)


def _sorted_slides(slides: Iterable[Any]) -> list[Any]:
    return sorted(slides, key=lambda s: int(_get_slide_value(s, "order", 0)))


def _env_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = str(raw).strip()
    return value or default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        logger.warning("slides export: invalid {} value {}", name, raw)
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = str(raw).strip().lower()
    if is_truthy(value):
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    logger.warning("slides export: invalid {} value {}", name, raw)
    return default


def _normalize_pdf_dimension(value: Any, *, key: str) -> str:
    if not isinstance(value, str):
        raise SlidesExportInputError(f"pdf_{key}_invalid")
    cleaned = value.strip()
    if not cleaned or not _PDF_DIMENSION_RE.match(cleaned):
        raise SlidesExportInputError(f"pdf_{key}_invalid")
    return cleaned


def _normalize_pdf_margin_value(value: Any, *, key: str, default_value: str, default_unit: str = "in") -> str:
    if value is None:
        value = default_value
    if isinstance(value, (int, float)):
        return f"{value}{default_unit}"
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            cleaned = default_value
        if not _PDF_MARGIN_RE.match(cleaned):
            raise SlidesExportInputError(f"pdf_margin_{key}_invalid")
        if cleaned[-1].isdigit():
            return f"{cleaned}{default_unit}"
        return cleaned
    raise SlidesExportInputError(f"pdf_margin_{key}_invalid")


def _normalize_pdf_options(options: dict[str, Any] | None) -> dict[str, Any]:
    opts = options or {}
    if not isinstance(opts, dict):
        raise SlidesExportInputError("pdf_options_invalid")

    width = opts.get("width")
    height = opts.get("height")
    pdf_format = opts.get("format")
    landscape = opts.get("landscape")
    margin_opts = opts.get("margin") or {}

    if margin_opts and not isinstance(margin_opts, dict):
        raise SlidesExportInputError("pdf_margin_invalid")

    pdf_options: dict[str, Any] = {}
    if width is not None or height is not None:
        if width is None or height is None:
            raise SlidesExportInputError("pdf_width_height_required")
        pdf_options["width"] = _normalize_pdf_dimension(width, key="width")
        pdf_options["height"] = _normalize_pdf_dimension(height, key="height")
    else:
        if pdf_format is None or not str(pdf_format).strip():
            pdf_format = _env_str("SLIDES_PDF_FORMAT", _DEFAULT_PDF_FORMAT)
        pdf_format = str(pdf_format).strip()
        if not _PDF_FORMAT_RE.match(pdf_format):
            raise SlidesExportInputError("pdf_format_invalid")
        pdf_options["format"] = pdf_format

    margin_defaults = {
        "top": _env_str("SLIDES_PDF_MARGIN_TOP", _DEFAULT_PDF_MARGIN),
        "bottom": _env_str("SLIDES_PDF_MARGIN_BOTTOM", _DEFAULT_PDF_MARGIN),
        "left": _env_str("SLIDES_PDF_MARGIN_LEFT", _DEFAULT_PDF_MARGIN),
        "right": _env_str("SLIDES_PDF_MARGIN_RIGHT", _DEFAULT_PDF_MARGIN),
    }
    pdf_options["margin"] = {
        "top": _normalize_pdf_margin_value(margin_opts.get("top"), key="top", default_value=margin_defaults["top"]),
        "bottom": _normalize_pdf_margin_value(
            margin_opts.get("bottom"), key="bottom", default_value=margin_defaults["bottom"]
        ),
        "left": _normalize_pdf_margin_value(margin_opts.get("left"), key="left", default_value=margin_defaults["left"]),
        "right": _normalize_pdf_margin_value(
            margin_opts.get("right"), key="right", default_value=margin_defaults["right"]
        ),
    }
    if landscape is None:
        landscape = _env_bool("SLIDES_PDF_LANDSCAPE", False)
    pdf_options["landscape"] = bool(landscape)
    pdf_options["print_background"] = bool(opts.get("print_background", True))
    return pdf_options


def _resolve_pdf_timeout_ms() -> int:
    seconds = _env_int("SLIDES_PDF_TIMEOUT_SECONDS", _DEFAULT_PDF_TIMEOUT_SECONDS)
    if seconds <= 0:
        seconds = _DEFAULT_PDF_TIMEOUT_SECONDS
    return seconds * 1000


def _resolve_pdf_limits() -> tuple[int, int]:
    max_slides = _env_int("SLIDES_PDF_MAX_SLIDES", _DEFAULT_PDF_MAX_SLIDES)
    if max_slides < 0:
        max_slides = _DEFAULT_PDF_MAX_SLIDES
    max_bytes = _env_int("SLIDES_PDF_MAX_HTML_BYTES", _DEFAULT_PDF_MAX_HTML_BYTES)
    if max_bytes <= 0:
        max_bytes = _DEFAULT_PDF_MAX_HTML_BYTES
    return max_slides, max_bytes


def _resolve_image_asset(
    image: dict[str, Any],
    *,
    asset_resolver: SlideAssetResolver | None,
) -> dict[str, Any]:
    asset_ref = image.get("asset_ref")
    if not isinstance(asset_ref, str) or not asset_ref.strip():
        return image
    resolver = asset_resolver or resolve_slide_asset
    try:
        resolved = resolver(asset_ref.strip())
    except SlidesAssetError as exc:
        raise SlidesExportInputError(exc.code) from exc
    if not isinstance(resolved, dict):
        raise SlidesExportInputError("slide_asset_unresolved")
    candidate = {
        "id": image.get("id") or resolved.get("id"),
        "mime": resolved.get("mime") or image.get("mime"),
        "data_b64": resolved.get("data_b64"),
        "alt": image.get("alt") if image.get("alt") is not None else resolved.get("alt"),
        "width": image.get("width") if image.get("width") is not None else resolved.get("width"),
        "height": image.get("height") if image.get("height") is not None else resolved.get("height"),
    }
    try:
        return validate_images_payload([candidate])[0]
    except SlidesImageError as exc:
        raise SlidesExportInputError(exc.code) from exc


def _extract_images(
    slide: Any,
    *,
    asset_resolver: SlideAssetResolver | None = None,
) -> list[dict[str, Any]]:
    metadata = _get_slide_value(slide, "metadata", {}) or {}
    if not isinstance(metadata, dict):
        return []
    images = metadata.get("images")
    if images is None:
        return []
    try:
        normalized = validate_images_payload(images)
    except SlidesImageError as exc:
        raise SlidesExportInputError(exc.code) from exc
    return [_resolve_image_asset(image, asset_resolver=asset_resolver) for image in normalized]


def _escape_markdown_alt(text: str) -> str:
    value = text.replace("\\", "\\\\")
    value = value.replace("[", "\\[").replace("]", "\\]")
    return value


def _render_image_html(image: dict[str, Any]) -> str:
    alt = escape(str(image.get("alt") or ""))
    attrs = f' alt="{alt}"'
    width = image.get("width")
    if isinstance(width, int):
        attrs += f' width="{width}"'
    height = image.get("height")
    if isinstance(height, int):
        attrs += f' height="{height}"'
    src = f"data:{image['mime']};base64,{image['data_b64']}"
    return f"<img src=\"{src}\"{attrs} />"


def _render_images_html(images: list[dict[str, Any]]) -> str:
    if not images:
        return ""
    rendered = "\n".join(_render_image_html(image) for image in images)
    return f"<div class=\"slide-images\">\n{rendered}\n</div>"


def _render_image_markdown(image: dict[str, Any]) -> str:
    alt = str(image.get("alt") or "")
    alt = _escape_markdown_alt(alt.replace("\r", " ").replace("\n", " ").strip())
    src = f"data:{image['mime']};base64,{image['data_b64']}"
    return f"![{alt}]({src})"


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


def _sanitize_custom_css(css_text: str | None) -> str | None:
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
            logger.warning("slides export: css sanitizer failed: {}", exc)
            cleaned = ""
    cleaned = cleaned.replace("\x00", "").strip()
    return cleaned or None


def _resolve_assets_dir(assets_dir: Path | str | None) -> Path:
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


def _find_license_file(assets_dir: Path) -> Path | None:
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


def _find_notice_file(assets_dir: Path) -> Path | None:
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


def _render_sections(
    slides: Iterable[Any],
    *,
    asset_resolver: SlideAssetResolver | None = None,
) -> str:
    sections: list[str] = []
    for slide in _sorted_slides(slides):
        layout = escape(str(_get_slide_value(slide, "layout", "content")))
        title = _get_slide_value(slide, "title")
        content = _get_slide_value(slide, "content", "")
        notes = _get_slide_value(slide, "speaker_notes")
        images = _extract_images(slide, asset_resolver=asset_resolver)
        images_html = _render_images_html(images)

        title_html = f"<h2>{escape(str(title))}</h2>" if title else ""
        content_html = _sanitize_markdown(str(content or "")) if content else ""
        body_html = f"{content_html}{images_html}" if content_html or images_html else ""
        notes_html = f"<aside class=\"notes\">{escape(str(notes))}</aside>" if notes else ""

        section = (
            f"      <section data-layout=\"{layout}\">\n"
            f"        {title_html}\n"
            f"        <div class=\"content\">{body_html}</div>\n"
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
    asset_resolver: SlideAssetResolver | None = None,
) -> str:
    css_link = "  <link rel=\"stylesheet\" href=\"assets/custom.css\">\n" if include_custom_css else ""
    title_html = escape(title or "Presentation")
    sections_html = _render_sections(slides, asset_resolver=asset_resolver)
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
    settings: dict[str, Any] | None,
    custom_css: str | None,
    assets_dir: Path | str | None = None,
    asset_resolver: SlideAssetResolver | None = None,
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
        asset_resolver=asset_resolver,
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
    marp_theme: str | None = None,
    asset_resolver: SlideAssetResolver | None = None,
) -> str:
    resolved_theme = marp_theme or _REVEAL_THEME_TO_MARP.get(theme, "default")
    lines: list[str] = [
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
        images = _extract_images(slide, asset_resolver=asset_resolver)
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
        for image in images:
            lines.append(_render_image_markdown(image))
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


def export_presentation_pdf(
    *,
    title: str,
    slides: Iterable[Any],
    theme: str,
    settings: dict[str, Any] | None,
    custom_css: str | None,
    assets_dir: Path | str | None = None,
    pdf_options: dict[str, Any] | None = None,
    asset_resolver: SlideAssetResolver | None = None,
) -> bytes:
    slides_list = list(slides)
    max_slides, max_html_bytes = _resolve_pdf_limits()
    if max_slides and len(slides_list) > max_slides:
        raise SlidesExportInputError("pdf_slides_too_many")

    resolved_assets = _resolve_assets_dir(assets_dir)
    _validate_reveal_assets(resolved_assets, theme)
    settings_json = json.dumps(settings or {}, ensure_ascii=True)
    sanitized_css = _sanitize_custom_css(custom_css)
    index_html = _render_index_html(
        title=title,
        slides=slides_list,
        theme=theme,
        settings_json=settings_json,
        include_custom_css=bool(sanitized_css),
        asset_resolver=asset_resolver,
    )
    if max_html_bytes and len(index_html.encode("utf-8")) > max_html_bytes:
        raise SlidesExportInputError("pdf_html_too_large")

    if sync_playwright is None:
        raise SlidesExportError("playwright_unavailable")

    pdf_settings = _normalize_pdf_options(pdf_options)
    timeout_ms = _resolve_pdf_timeout_ms()

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        assets_target = base_dir / "assets" / "reveal"
        assets_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(resolved_assets, assets_target, dirs_exist_ok=True)

        (base_dir / "index.html").write_text(index_html, encoding="utf-8")
        if sanitized_css:
            (base_dir / "assets" / "custom.css").write_text(sanitized_css, encoding="utf-8")

        pdf_url = (base_dir / "index.html").resolve().as_uri() + "?print-pdf"

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    page.set_default_timeout(timeout_ms)
                    page.goto(pdf_url, wait_until="load", timeout=timeout_ms)
                    try:
                        page.emulate_media(media="print")
                    except PlaywrightError:
                        logger.debug("slides export: emulate_media not supported by playwright")
                    try:
                        page.wait_for_function(
                            "window.Reveal && window.Reveal.isReady && window.Reveal.isReady()",
                            timeout=timeout_ms,
                        )
                    except PlaywrightTimeoutError:
                        logger.warning("slides export: reveal did not signal ready before timeout")
                    pdf_bytes = page.pdf(timeout=timeout_ms, **pdf_settings)
                finally:
                    browser.close()
        except PlaywrightTimeoutError as exc:
            raise SlidesExportError("pdf_timeout") from exc
        except PlaywrightError as exc:
            raise SlidesExportError("pdf_render_failed") from exc
        except Exception as exc:
            raise SlidesExportError("pdf_render_failed") from exc

    return pdf_bytes


def export_presentation_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, indent=2)
