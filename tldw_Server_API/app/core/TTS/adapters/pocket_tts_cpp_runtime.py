from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Optional

from loguru import logger


PROVIDER_KEY = "pocket_tts_cpp"


def get_runtime_dir(*, voice_manager, user_id: int) -> Path:
    """Return the user-scoped PocketTTS.cpp runtime directory."""
    voices_root = voice_manager.get_user_voices_path(user_id)
    runtime_dir = voices_root / "providers" / PROVIDER_KEY
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


async def materialize_custom_voice_reference(*, voice_manager, user_id: int, voice_id: str) -> Path:
    """Materialize a stored custom voice into the provider runtime cache."""
    runtime_dir = get_runtime_dir(voice_manager=voice_manager, user_id=user_id)
    target_path = runtime_dir / f"custom_{voice_id}.wav"
    voice_bytes = await voice_manager.load_voice_reference_audio(user_id, voice_id)
    target_path.write_bytes(voice_bytes)
    return target_path


async def materialize_direct_voice_reference(
    *,
    voice_manager,
    user_id: int,
    voice_reference: bytes,
    persist_direct_voice_references: bool,
) -> tuple[Path, bool]:
    """Materialize a direct voice reference into the provider runtime cache."""
    runtime_dir = get_runtime_dir(voice_manager=voice_manager, user_id=user_id)
    digest = hashlib.sha256(voice_reference).hexdigest()
    target_path = runtime_dir / f"ref_{digest}.wav"
    target_path.write_bytes(voice_reference)
    return target_path, not persist_direct_voice_references


def prune_materialized_voice_cache(
    runtime_dir: Path,
    *,
    cache_ttl_hours: Optional[int],
    cache_max_bytes: Optional[int],
) -> list[Path]:
    """Remove expired or oversize materialized voice files from the runtime cache."""
    if not runtime_dir.exists():
        return []

    removed: list[Path] = []
    files: list[tuple[Path, float, int]] = []
    now = time.time()
    ttl_seconds = max(0, int(cache_ttl_hours or 0)) * 3600

    for path in runtime_dir.glob("*.wav"):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        mtime = float(stat.st_mtime)
        size = int(stat.st_size)
        if ttl_seconds and (now - mtime) > ttl_seconds:
            try:
                path.unlink()
                removed.append(path)
            except OSError as exc:
                logger.warning("Failed pruning expired PocketTTS.cpp cache file {}: {}", path, exc)
            continue
        files.append((path, mtime, size))

    if cache_max_bytes is None or cache_max_bytes <= 0:
        return removed

    total_bytes = sum(size for _, _, size in files)
    if total_bytes <= cache_max_bytes:
        return removed

    for path, _, size in sorted(files, key=lambda item: item[1]):
        if total_bytes <= cache_max_bytes:
            break
        try:
            path.unlink()
            removed.append(path)
            total_bytes -= size
        except OSError as exc:
            logger.warning("Failed pruning oversized PocketTTS.cpp cache file {}: {}", path, exc)

    return removed


def cleanup_transient_voice_reference(path: Optional[Path], is_transient: bool) -> None:
    """Delete a transient direct-reference materialization after request completion."""
    if not is_transient or path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Failed cleaning transient PocketTTS.cpp cache file {}: {}", path, exc)
