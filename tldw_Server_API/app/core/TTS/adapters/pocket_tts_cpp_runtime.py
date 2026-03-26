from __future__ import annotations

import hashlib
import contextlib
import time
import tempfile
import uuid
import os
from pathlib import Path
from typing import Optional

from loguru import logger

from tldw_Server_API.app.core.TTS.audio_converter import AudioConverter
from tldw_Server_API.app.core.TTS.tts_exceptions import TTSModelNotFoundError


PROVIDER_KEY = "pocket_tts_cpp"
VALID_PRECISIONS = {"int8", "fp32"}


def get_required_model_filenames(precision: str) -> list[str]:
    suffix = "_int8" if precision == "int8" else ""
    return [
        f"flow_lm_main{suffix}.onnx",
        f"flow_lm_flow{suffix}.onnx",
        f"mimi_decoder{suffix}.onnx",
        "mimi_encoder.onnx",
        "text_conditioner.onnx",
    ]


def validate_runtime_assets(
    *,
    binary_path: Path,
    model_path: Path,
    tokenizer_path: Path,
    precision: str,
) -> None:
    """Validate the PocketTTS.cpp runtime files needed for CLI execution."""
    if not binary_path.exists() or not binary_path.is_file():
        raise TTSModelNotFoundError(
            f"PocketTTS.cpp binary not found at {binary_path}",
            provider=PROVIDER_KEY,
            details={"binary_path": str(binary_path)},
        )
    if not os.access(binary_path, os.X_OK):
        raise TTSModelNotFoundError(
            f"PocketTTS.cpp binary is not executable at {binary_path}",
            provider=PROVIDER_KEY,
            details={"binary_path": str(binary_path)},
        )

    if not tokenizer_path.exists():
        raise TTSModelNotFoundError(
            f"PocketTTS.cpp tokenizer not found at {tokenizer_path}",
            provider=PROVIDER_KEY,
            details={"tokenizer_path": str(tokenizer_path)},
        )

    if not model_path.exists():
        raise TTSModelNotFoundError(
            f"PocketTTS.cpp models directory not found at {model_path}",
            provider=PROVIDER_KEY,
            details={"model_path": str(model_path)},
        )

    missing = [name for name in get_required_model_filenames(precision) if not (model_path / name).exists()]
    if missing:
        raise TTSModelNotFoundError(
            "PocketTTS.cpp exported ONNX assets missing",
            provider=PROVIDER_KEY,
            details={"model_path": str(model_path), "missing": missing},
        )


def build_cli_command(
    *,
    binary_path: Path,
    text: str,
    voice_path: Path,
    model_path: Path,
    tokenizer_path: Path,
    output_path: Optional[Path],
    precision: str,
    prefer_stdout: bool,
    enable_voice_cache: bool,
    voices_dir: Optional[Path] = None,
    temperature: Optional[float] = None,
    lsd_steps: Optional[int] = None,
    eos_threshold: Optional[float] = None,
    eos_extra: Optional[float] = None,
    noise_clamp: Optional[float] = None,
    threads: Optional[int] = None,
    verbose: bool = False,
    profile: bool = False,
) -> list[str]:
    """Build a PocketTTS.cpp CLI invocation for a single synthesis request."""
    command = [str(binary_path)]

    if prefer_stdout:
        command.append("--stdout")
    if precision:
        command.extend(["--precision", precision])
    if temperature is not None:
        command.extend(["--temperature", str(temperature)])
    if lsd_steps is not None:
        command.extend(["--lsd-steps", str(lsd_steps)])
    if eos_threshold is not None:
        command.extend(["--eos-threshold", str(eos_threshold)])
    if eos_extra is not None:
        command.extend(["--eos-extra", str(eos_extra)])
    if noise_clamp is not None:
        command.extend(["--noise-clamp", str(noise_clamp)])
    if threads is not None:
        command.extend(["--threads", str(threads)])
    if model_path:
        command.extend(["--models-dir", str(model_path)])
    if tokenizer_path:
        command.extend(["--tokenizer", str(tokenizer_path)])
    if voices_dir is not None:
        command.extend(["--voices-dir", str(voices_dir)])
    if not enable_voice_cache:
        command.append("--no-cache")
    if verbose:
        command.append("--verbose")
    if profile:
        command.append("--profile")

    command.extend([text, str(voice_path)])
    if output_path is not None:
        command.append(str(output_path))
    return command


def get_runtime_dir(*, voice_manager, user_id: int) -> Path:
    """Return the user-scoped PocketTTS.cpp runtime directory."""
    voices_root = voice_manager.get_user_voices_path(user_id)
    runtime_dir = voices_root / "providers" / PROVIDER_KEY
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def _infer_audio_suffix(audio_bytes: bytes) -> str:
    """Infer a likely file suffix so the shared conversion path can decode bytes correctly."""
    if audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
        return ".wav"
    if audio_bytes[:3] == b"ID3" or (len(audio_bytes) > 1 and audio_bytes[0] == 0xFF and (audio_bytes[1] & 0xE0) == 0xE0):
        return ".mp3"
    if audio_bytes[:4] == b"fLaC":
        return ".flac"
    if audio_bytes[:4] == b"OggS":
        return ".ogg"
    if len(audio_bytes) >= 8 and audio_bytes[4:8] == b"ftyp":
        return ".m4a"
    return ".wav"


async def normalize_reference_audio_to_wav(
    audio_bytes: bytes,
    *,
    sample_rate: int = 24000,
    channels: int = 1,
) -> bytes:
    """Normalize incoming reference audio bytes into a provider-safe WAV payload."""
    suffix = _infer_audio_suffix(audio_bytes)
    input_fd, input_name = tempfile.mkstemp(prefix="pocket_tts_cpp_ref_", suffix=suffix)
    output_fd, output_name = tempfile.mkstemp(prefix="pocket_tts_cpp_ref_", suffix=".wav")
    try:
        with os.fdopen(input_fd, "wb") as input_file:
            input_file.write(audio_bytes)
        with os.fdopen(output_fd, "wb"):
            pass

        input_path = Path(input_name)
        output_path = Path(output_name)
        converted = await AudioConverter.convert_to_wav(
            input_path,
            output_path,
            sample_rate=sample_rate,
            channels=channels,
            bit_depth=16,
        )
        if not converted or not output_path.exists():
            raise RuntimeError("Failed to normalize PocketTTS.cpp reference audio to WAV")
        normalized = output_path.read_bytes()
        if normalized[:4] != b"RIFF" or normalized[8:12] != b"WAVE":
            raise RuntimeError("PocketTTS.cpp reference normalization did not produce WAV bytes")
        return normalized
    finally:
        with contextlib.suppress(OSError):
            Path(input_name).unlink()
        with contextlib.suppress(OSError):
            Path(output_name).unlink()


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
    normalized_bytes = await normalize_reference_audio_to_wav(voice_reference)
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
