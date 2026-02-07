from __future__ import annotations

from pathlib import Path
from typing import Any


def detect_code_language(filename: str) -> str:
    """
    Infer a language label from the file extension.

    Mirrors the legacy `_detect_code_language` helper in `_legacy_media`.
    """
    ext = Path(filename).suffix.lower()
    return {
        ".py": "python",
        ".c": "c",
        ".h": "c-header",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".java": "java",
        ".kt": "kotlin",
        ".kts": "kotlin",
        ".swift": "swift",
        ".rs": "rust",
        ".go": "go",
        ".rb": "ruby",
        ".php": "php",
        ".pl": "perl",
        ".lua": "lua",
        ".sql": "sql",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".ini": "ini",
        ".cfg": "ini",
        ".conf": "conf",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".jsx": "jsx",
    }.get(ext, ext.lstrip(".") or "text")


def read_text_safe(path: Path) -> str:
    """
    Read text from a file path using UTF-8 with a Latin-1 fallback.

    Mirrors the legacy `_read_text_safe` helper in `_legacy_media`.
    """
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def chunk_code_lines(
    text: str,
    lines_per_chunk: int,
    overlap: int,
    language: str,
) -> list[dict[str, Any]]:
    """
    Simple line-based chunking used as a fallback for code processing.

    Mirrors the legacy `_chunk_code_lines` helper in `_legacy_media`.
    """
    lines = text.splitlines()
    chunks: list[dict[str, Any]] = []
    if lines_per_chunk <= 0:
        return chunks

    step = max(1, lines_per_chunk - max(0, overlap))
    start = 0
    total = len(lines)
    while start < total:
        end = min(total, start + lines_per_chunk)
        chunk_text = "\n".join(lines[start:end])
        chunks.append(
            {
                "text": chunk_text,
                "metadata": {
                    "language": language,
                    "start_line": start + 1,
                    "end_line": end,
                    "total_lines": total,
                    "chunk_method": "lines",
                },
            }
        )
        if end == total:
            break
        start += step
    return chunks


__all__ = ["detect_code_language", "read_text_safe", "chunk_code_lines"]
