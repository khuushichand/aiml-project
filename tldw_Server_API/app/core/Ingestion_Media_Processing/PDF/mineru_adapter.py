from __future__ import annotations

import json
import os
import shlex
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any


def _mineru_command_tokens() -> list[str]:
    raw = os.getenv("MINERU_CMD", "mineru").strip() or "mineru"
    return shlex.split(raw)


def _build_mineru_command(*, pdf_path: Path, output_dir: Path) -> list[str]:
    return [
        *_mineru_command_tokens(),
        "-p",
        str(pdf_path),
        "-o",
        str(output_dir),
    ]


def _mineru_available() -> bool:
    cmd = _mineru_command_tokens()
    executable = cmd[0] if cmd else "mineru"
    return shutil.which(executable) is not None


def _read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _read_json_if_exists(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _coerce_text_output(markdown_text: str, output_format: str | None) -> str:
    fmt = (output_format or "markdown").strip().lower()
    if fmt == "text":
        return markdown_text.replace("# ", "").replace("|", " ").strip()
    return markdown_text


def _pages_from_content_list(content_list: Any) -> list[dict[str, Any]]:
    if not isinstance(content_list, list):
        return []

    pages_by_index: dict[int, list[str]] = defaultdict(list)
    for entry in content_list:
        if not isinstance(entry, dict):
            continue
        page_idx = int(entry.get("page_idx") or 0)
        text = str(entry.get("text") or "").strip()
        if text:
            pages_by_index[page_idx].append(text)

    pages: list[dict[str, Any]] = []
    for page_idx in sorted(pages_by_index):
        pages.append(
            {
                "page": page_idx + 1,
                "text": "\n".join(pages_by_index[page_idx]).strip(),
                "tables": [],
                "blocks": [],
                "meta": {},
            }
        )
    return pages


def _tables_from_middle(middle: Any) -> list[dict[str, Any]]:
    if not isinstance(middle, dict):
        return []

    tables = middle.get("tables")
    if not isinstance(tables, list):
        return []

    out: list[dict[str, Any]] = []
    for entry in tables:
        if not isinstance(entry, dict):
            continue
        html = str(entry.get("html") or "").strip()
        if not html:
            continue
        out.append(
            {
                "page": int(entry.get("page") or 1),
                "format": "html",
                "content": html,
            }
        )
    return out


def _bounded_middle_excerpt(middle: Any) -> dict[str, Any]:
    if not isinstance(middle, dict):
        return {}

    excerpt: dict[str, Any] = {}
    tables = middle.get("tables")
    if isinstance(tables, list):
        excerpt["tables"] = tables[:5]
    return excerpt


def _normalize_mineru_output_dir(
    output_dir: Path,
    *,
    output_format: str | None,
    prompt_preset: str | None,
) -> dict[str, Any]:
    markdown_text = _read_text_if_exists(output_dir / "document.md")
    content_list = _read_json_if_exists(output_dir / "content_list.json")
    middle = _read_json_if_exists(output_dir / "middle.json")
    pages = _pages_from_content_list(content_list)
    tables = _tables_from_middle(middle)

    structured = {
        "schema_version": 1,
        "text": markdown_text,
        "format": "markdown",
        "pages": pages,
        "tables": tables,
        "artifacts": {
            "content_list_excerpt": content_list[:10] if isinstance(content_list, list) else [],
            "middle_json_excerpt": _bounded_middle_excerpt(middle),
        },
        "meta": {
            "backend": "mineru",
            "mode": "cli",
            "supports_per_page_metrics": bool(pages),
            "prompt_preset": prompt_preset,
            "requested_output_format": output_format,
        },
    }
    return {
        "text": _coerce_text_output(markdown_text, output_format),
        "structured": structured,
    }


def describe_mineru_backend() -> dict[str, Any]:
    return {
        "available": _mineru_available(),
        "pdf_only": True,
        "document_level": True,
        "opt_in_only": True,
        "supports_per_page_metrics": True,
        "mode": "cli",
    }
