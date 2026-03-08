from __future__ import annotations

from pathlib import Path
from typing import Any

from tldw_Server_API.app.core.Ingestion_Media_Processing.path_utils import resolve_safe_local_path
from tldw_Server_API.app.core.config import get_ingestion_source_allowed_roots


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
