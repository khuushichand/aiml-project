from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess  # nosec B404
import tempfile
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from loguru import logger

_DEFAULT_MINERU_TIMEOUT_SEC = 120
_DEFAULT_MINERU_MAX_CONCURRENCY = 1
_MINERU_SEMAPHORE_LOCK = threading.Lock()
_MINERU_SEMAPHORE_LIMIT = _DEFAULT_MINERU_MAX_CONCURRENCY
_MINERU_SEMAPHORE = threading.BoundedSemaphore(_DEFAULT_MINERU_MAX_CONCURRENCY)
_MINERU_TEXT_MARKDOWN_FILES = ("document.md", "output.md", "result.md")


def _coerce_positive_int(raw_value: str | None, default: int) -> int:
    try:
        value = int(str(raw_value).strip())
    except (TypeError, ValueError, AttributeError):
        return default
    return value if value > 0 else default


def _coerce_int(raw_value: Any, default: int) -> int:
    try:
        return int(str(raw_value).strip())
    except (TypeError, ValueError, AttributeError):
        return default


def _coerce_bool(raw_value: str | None, default: bool = False) -> bool:
    if raw_value is None:
        return default
    return str(raw_value).strip().lower() in {"1", "true", "yes", "on"}


def _get_timeout_sec() -> int:
    return _coerce_positive_int(os.getenv("MINERU_TIMEOUT_SEC"), _DEFAULT_MINERU_TIMEOUT_SEC)


def _get_max_concurrency() -> int:
    return _coerce_positive_int(os.getenv("MINERU_MAX_CONCURRENCY"), _DEFAULT_MINERU_MAX_CONCURRENCY)


def _get_tmp_root() -> Path | None:
    raw = (os.getenv("MINERU_TMP_ROOT") or "").strip()
    return Path(raw).expanduser() if raw else None


def _debug_save_raw() -> bool:
    return _coerce_bool(os.getenv("MINERU_DEBUG_SAVE_RAW"), default=False)


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


def _get_mineru_semaphore() -> threading.BoundedSemaphore:
    global _MINERU_SEMAPHORE, _MINERU_SEMAPHORE_LIMIT

    limit = _get_max_concurrency()
    with _MINERU_SEMAPHORE_LOCK:
        if limit != _MINERU_SEMAPHORE_LIMIT:
            _MINERU_SEMAPHORE = threading.BoundedSemaphore(limit)
            _MINERU_SEMAPHORE_LIMIT = limit
        return _MINERU_SEMAPHORE


def _read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _read_json_if_exists(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_requested_format(output_format: str | None) -> str:
    fmt = (output_format or "").strip().lower()
    if fmt in {"text", "markdown", "json"}:
        return fmt
    return "markdown"


def _markdown_to_text(markdown_text: str) -> str:
    lines: list[str] = []
    for raw_line in markdown_text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("```"):
            continue
        if set(stripped) <= {"|", "-", ":", " "}:
            continue
        stripped = stripped.lstrip("#").strip()
        if stripped.startswith(("- ", "* ", "+ ")):
            stripped = stripped[2:].strip()
        if "|" in stripped:
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            stripped = " ".join(cell for cell in cells if cell)
        if stripped:
            lines.append(stripped)
    return "\n".join(lines).strip()


def _coerce_text_output(markdown_text: str, output_format: str | None) -> str:
    fmt = _normalize_requested_format(output_format)
    if fmt == "text":
        return _markdown_to_text(markdown_text)
    return markdown_text


def _pages_from_content_list(content_list: Any) -> list[dict[str, Any]]:
    if not isinstance(content_list, list):
        return []

    pages_by_index: dict[int, list[str]] = defaultdict(list)
    for entry in content_list:
        if not isinstance(entry, dict):
            continue
        page_idx = max(_coerce_int(entry.get("page_idx"), 0), 0)
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


def _include_raw_artifacts(artifacts: dict[str, Any], *, content_list: Any, middle: Any) -> dict[str, Any]:
    if not _debug_save_raw():
        return artifacts

    artifacts = dict(artifacts)
    artifacts["content_list_raw"] = content_list if isinstance(content_list, list) else []
    artifacts["middle_json_raw"] = middle if isinstance(middle, dict) else {}
    return artifacts


def _candidate_output_dirs(output_dir: Path) -> list[Path]:
    candidates = [output_dir]
    if output_dir.exists():
        for child in output_dir.iterdir():
            if child.is_dir():
                candidates.append(child)
    return candidates


def _resolve_primary_output_dir(output_dir: Path) -> Path:
    best_dir = output_dir
    best_score = -1

    for candidate in _candidate_output_dirs(output_dir):
        score = 0
        if any((candidate / name).exists() for name in _MINERU_TEXT_MARKDOWN_FILES):
            score += 2
        if (candidate / "content_list.json").exists():
            score += 1
        if (candidate / "middle.json").exists():
            score += 1
        if score > best_score:
            best_dir = candidate
            best_score = score
    return best_dir


def _read_first_existing(output_dir: Path, names: tuple[str, ...]) -> str:
    for name in names:
        candidate = output_dir / name
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    return ""


def _normalize_mineru_output_dir(
    output_dir: Path,
    *,
    output_format: str | None,
    prompt_preset: str | None,
) -> dict[str, Any]:
    primary_output_dir = _resolve_primary_output_dir(output_dir)
    markdown_text = _read_first_existing(primary_output_dir, _MINERU_TEXT_MARKDOWN_FILES)
    content_list = _read_json_if_exists(primary_output_dir / "content_list.json")
    middle = _read_json_if_exists(primary_output_dir / "middle.json")
    pages = _pages_from_content_list(content_list)
    tables = _tables_from_middle(middle)
    artifacts = {
        "content_list_excerpt": content_list[:10] if isinstance(content_list, list) else [],
        "middle_json_excerpt": _bounded_middle_excerpt(middle),
    }
    artifacts = _include_raw_artifacts(artifacts, content_list=content_list, middle=middle)

    structured = {
        "schema_version": 1,
        "text": markdown_text,
        "format": _normalize_requested_format(output_format),
        "pages": pages,
        "tables": tables,
        "artifacts": artifacts,
        "meta": {
            "backend": "mineru",
            "mode": "cli",
            "supports_per_page_metrics": bool(pages),
            "prompt_preset": prompt_preset,
            "requested_output_format": output_format,
            "output_dir_layout": str(primary_output_dir.relative_to(output_dir)) if primary_output_dir != output_dir else ".",
        },
    }
    return {
        "text": _coerce_text_output(markdown_text, output_format),
        "structured": structured,
    }


def _summarize_process_output(completed: subprocess.CompletedProcess[str]) -> str:
    stderr = (completed.stderr or "").strip()
    stdout = (completed.stdout or "").strip()
    message = stderr or stdout or "no process output"
    return message[:400]


def run_mineru_document_ocr(
    *,
    pdf_path: Path,
    output_format: str | None = None,
    prompt_preset: str | None = None,
    requested_lang: str | None = None,
    requested_dpi: int | None = None,
) -> dict[str, Any]:
    if not pdf_path.exists():
        raise FileNotFoundError(f"MinerU input PDF not found: {pdf_path}")

    timeout_sec = _get_timeout_sec()
    max_concurrency = _get_max_concurrency()
    tmp_root = _get_tmp_root()
    if tmp_root is not None:
        tmp_root.mkdir(parents=True, exist_ok=True)

    start_time = time.monotonic()
    temp_dir_kwargs: dict[str, Any] = {"prefix": "mineru_"}
    if tmp_root is not None:
        temp_dir_kwargs["dir"] = str(tmp_root)

    with tempfile.TemporaryDirectory(**temp_dir_kwargs) as tmp_dir:
        output_dir = Path(tmp_dir)
        command = _build_mineru_command(pdf_path=pdf_path, output_dir=output_dir)
        semaphore = _get_mineru_semaphore()

        try:
            with semaphore:
                # Command tokens are argv-based, shell-free, and built from validated local paths.
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec,
                    check=False,
                )  # nosec B603
        except subprocess.TimeoutExpired as exc:
            logger.warning("MinerU timed out for {} after {}s", pdf_path, timeout_sec)
            raise TimeoutError(f"MinerU timed out after {timeout_sec}s") from exc

        if completed.returncode != 0:
            summary = _summarize_process_output(completed)
            logger.warning(
                "MinerU command failed for {} with code {}: {}",
                pdf_path,
                completed.returncode,
                summary,
            )
            raise RuntimeError(f"MinerU exited with code {completed.returncode}: {summary}")

        normalized = _normalize_mineru_output_dir(
            output_dir,
            output_format=output_format,
            prompt_preset=prompt_preset,
        )
        structured = normalized["structured"]
        pages = structured.get("pages") if isinstance(structured, dict) else []
        page_count = len(pages) if isinstance(pages, list) else 0
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        details = {
            "backend": "mineru",
            "mode": "cli",
            "lang": requested_lang or "eng",
            "dpi": requested_dpi or 300,
            "output_format": output_format,
            "prompt_preset": prompt_preset,
            "timeout_sec": timeout_sec,
            "max_concurrency": max_concurrency,
            "elapsed_ms": elapsed_ms,
            "total_pages": page_count,
            "ocr_pages": page_count,
            "artifacts_found": {
                "markdown": bool(structured.get("text")),
                "content_list_excerpt": bool(structured.get("artifacts", {}).get("content_list_excerpt")),
                "middle_json_excerpt": bool(structured.get("artifacts", {}).get("middle_json_excerpt")),
            },
            "supports_per_page_metrics": bool(structured.get("meta", {}).get("supports_per_page_metrics")),
        }

        return {
            "text": str(normalized.get("text") or ""),
            "structured": structured,
            "details": details,
            "warnings": [],
        }


def describe_mineru_backend() -> dict[str, Any]:
    return {
        "available": _mineru_available(),
        "pdf_only": True,
        "document_level": True,
        "opt_in_only": True,
        "supports_per_page_metrics": True,
        "mode": "cli",
        "timeout_sec": _get_timeout_sec(),
        "max_concurrency": _get_max_concurrency(),
        "tmp_root": str(_get_tmp_root()) if _get_tmp_root() is not None else None,
        "debug_save_raw": _debug_save_raw(),
    }
