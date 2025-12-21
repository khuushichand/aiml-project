from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterable


def atomic_write(path: Path, data: str, encoding: str = "utf-8") -> None:
    """Write file atomically by using a temp file and replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except Exception:
            pass


def ensure_gitignore(path: Path, entries: Iterable[str]) -> None:
    """Ensure .gitignore contains specified entries (no duplicates)."""
    existing: list[str] = []
    if path.exists():
        existing = path.read_text(encoding="utf-8").splitlines()
    existing_set = {line.strip() for line in existing if line.strip()}
    changed = False
    for e in entries:
        if e not in existing_set:
            existing.append(e)
            existing_set.add(e)
            changed = True
    if changed:
        atomic_write(path, "\n".join(existing) + "\n")
