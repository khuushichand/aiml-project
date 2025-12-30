from __future__ import annotations

import shutil


def has_ffmpeg() -> bool:
    """Detect whether ffmpeg is on PATH (scaffold)."""
    return shutil.which("ffmpeg") is not None


def has_cuda() -> bool:
    """Best-effort CUDA presence check (scaffold)."""
    # Avoid importing heavy libs; leave real checks to full implementation
    return False
