from __future__ import annotations

import hashlib
import io
import time
import uuid
import wave
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


def normalize_reference_audio_to_wav(
    audio_bytes: bytes,
    *,
    sample_rate: int = 24000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    """Normalize incoming reference audio bytes into a WAV-compatible payload."""
    if audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
        return audio_bytes

    pcm_bytes = audio_bytes
    if sample_width > 0 and len(pcm_bytes) % sample_width:
        pcm_bytes += b"\x00" * (sample_width - (len(pcm_bytes) % sample_width))

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)
    return buffer.getvalue()


def _write_runtime_file(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


async def materialize_custom_voice_reference(
    *,
    voice_manager,
    user_id: int,
    voice_id: str,
    cache_max_bytes: Optional[int] = None,
) -> Path:
    """Materialize a stored custom voice into the provider runtime cache."""
    runtime_dir = get_runtime_dir(voice_manager=voice_manager, user_id=user_id)
    target_path = runtime_dir / f"custom_{voice_id}.wav"
    voice_bytes = await voice_manager.load_voice_reference_audio(user_id, voice_id)
    _write_runtime_file(target_path, voice_bytes)
    if cache_max_bytes is not None:
        prune_materialized_voice_cache(
            runtime_dir,
            cache_ttl_hours=None,
            cache_max_bytes=cache_max_bytes,
            protected_paths={target_path},
        )
    return target_path


async def materialize_direct_voice_reference(
    *,
    voice_manager,
    user_id: int,
    voice_reference: bytes,
    persist_direct_voice_references: bool,
    cache_max_bytes: Optional[int] = None,
) -> tuple[Path, bool]:
    """Materialize a direct voice reference into the provider runtime cache."""
    runtime_dir = get_runtime_dir(voice_manager=voice_manager, user_id=user_id)
    normalized_bytes = normalize_reference_audio_to_wav(voice_reference)
    digest = hashlib.sha256(normalized_bytes).hexdigest()
    if persist_direct_voice_references:
        target_path = runtime_dir / f"ref_{digest}.wav"
    else:
        target_path = runtime_dir / f"ref_{digest}_{uuid.uuid4().hex}.wav"
    _write_runtime_file(target_path, normalized_bytes)
    if cache_max_bytes is not None:
        prune_materialized_voice_cache(
            runtime_dir,
            cache_ttl_hours=None,
            cache_max_bytes=cache_max_bytes,
            protected_paths={target_path},
        )
    return target_path, not persist_direct_voice_references


def prune_materialized_voice_cache(
    runtime_dir: Path,
    *,
    cache_ttl_hours: Optional[int],
    cache_max_bytes: Optional[int],
    protected_paths: Optional[set[Path]] = None,
) -> list[Path]:
    """Remove expired or oversize materialized voice files from the runtime cache."""
    if not runtime_dir.exists():
        return []

    removed: list[Path] = []
    files: list[tuple[Path, float, int]] = []
    now = time.time()
    ttl_seconds = max(0, int(cache_ttl_hours or 0)) * 3600
    protected_resolved = {
        path.resolve() for path in (protected_paths or set()) if path is not None
    }

    for path in runtime_dir.glob("*.wav"):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
            resolved = path.resolve()
        except OSError:
            continue
        mtime = float(stat.st_mtime)
        size = int(stat.st_size)
        if ttl_seconds and (now - mtime) > ttl_seconds and resolved not in protected_resolved:
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
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in protected_resolved:
            continue
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
