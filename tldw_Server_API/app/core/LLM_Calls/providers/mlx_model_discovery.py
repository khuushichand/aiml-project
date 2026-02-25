from __future__ import annotations

import copy
import os
import threading
import time
from pathlib import Path
from typing import Any


def _validate_manifest_files(file_names: set[str]) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    if "config.json" not in file_names:
        reasons.append("Missing config.json")

    if "tokenizer.json" not in file_names and "tokenizer.model" not in file_names:
        reasons.append("Missing tokenizer.json or tokenizer.model")

    has_weights = any(name.endswith(".safetensors") or name.endswith(".bin") for name in file_names)
    if not has_weights:
        reasons.append("Missing *.safetensors or *.bin weights")

    return (len(reasons) == 0, reasons)


def _safe_file_names(directory: Path, files: list[str]) -> set[str]:
    names: set[str] = set()
    for file_name in files:
        file_path = directory / file_name
        try:
            if file_path.is_symlink() or not file_path.is_file():
                continue
        except OSError:
            continue
        names.add(file_name)
    return names


def _safe_directory_stats(directory: Path, files: list[str]) -> tuple[int | None, float | None]:
    size_bytes = 0
    latest_mtime = 0.0
    has_stat = False

    for file_name in files:
        file_path = directory / file_name
        try:
            if file_path.is_symlink() or not file_path.is_file():
                continue
            stat = file_path.stat()
        except OSError:
            continue

        size_bytes += int(stat.st_size)
        latest_mtime = max(latest_mtime, float(stat.st_mtime))
        has_stat = True

    if not has_stat:
        return None, None
    return size_bytes, latest_mtime


def _normalize_model_root(model_dir: str | Path | None) -> tuple[Path | None, list[str], bool, str | None]:
    if model_dir is None:
        return None, ["MLX_MODEL_DIR is not configured"], False, None

    raw = str(model_dir).strip()
    if not raw:
        return None, ["MLX_MODEL_DIR is not configured"], False, None

    root = Path(raw).expanduser()
    display_path = str(root)

    if not root.exists():
        return None, [f"MLX_MODEL_DIR does not exist: {display_path}"], True, display_path

    if not root.is_dir():
        return None, [f"MLX_MODEL_DIR is not a directory: {display_path}"], True, display_path

    return root.resolve(), [], True, display_path


def discover_mlx_models(model_dir: str | Path | None) -> dict[str, Any]:
    root, warnings, configured, display_path = _normalize_model_root(model_dir)

    result: dict[str, Any] = {
        "model_dir": display_path,
        "model_dir_configured": configured,
        "warnings": list(warnings),
        "available_models": [],
    }

    if root is None:
        return result

    models: list[dict[str, Any]] = []

    try:
        for current_root, dirs, files in os.walk(root, topdown=True, followlinks=False):
            current_dir = Path(current_root)

            # Ignore symlinked directories entirely.
            dirs[:] = [name for name in dirs if not (current_dir / name).is_symlink()]

            if current_dir == root:
                continue

            file_names = _safe_file_names(current_dir, files)
            has_manifest_signal = (
                "config.json" in file_names
                or "tokenizer.json" in file_names
                or "tokenizer.model" in file_names
                or any(name.endswith(".safetensors") or name.endswith(".bin") for name in file_names)
            )

            if not has_manifest_signal:
                continue

            selectable, reasons = _validate_manifest_files(file_names)
            size_bytes, modified_at = _safe_directory_stats(current_dir, files)
            relative_path = current_dir.relative_to(root).as_posix()
            model_name = current_dir.name

            models.append(
                {
                    "id": relative_path,
                    "name": model_name,
                    "relative_path": relative_path,
                    "modified_at": modified_at,
                    "size_bytes": size_bytes,
                    "selectable": selectable,
                    "reasons": reasons,
                }
            )
    except OSError as exc:
        result["warnings"].append(f"Failed to scan MLX_MODEL_DIR: {exc}")
        return result

    models.sort(key=lambda item: (str(item.get("name", "")).casefold(), str(item.get("id", ""))))
    result["available_models"] = models
    return result


def _validate_model_id(model_id: str) -> Path:
    raw = model_id.strip()
    if not raw:
        raise ValueError("model_id is required")

    candidate = Path(raw)
    if candidate.is_absolute():
        raise ValueError("model_id must be a relative path")

    normalized = Path(os.path.normpath(raw))
    if str(normalized) in ("", "."):
        raise ValueError("model_id must resolve to a model directory")

    if any(part in ("", ".", "..") for part in normalized.parts):
        raise ValueError("model_id contains invalid path segments")

    return normalized


def resolve_mlx_model_id(
    *,
    model_dir: str | Path | None,
    model_id: str,
    discovered_models: list[dict[str, Any]] | None = None,
) -> Path:
    root, _, _, _ = _normalize_model_root(model_dir)
    if root is None:
        raise ValueError("MLX_MODEL_DIR is not configured")

    normalized_id = _validate_model_id(model_id)
    resolved = (root / normalized_id).resolve(strict=False)

    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("model_id resolves outside MLX_MODEL_DIR") from exc

    if not resolved.exists() or not resolved.is_dir():
        raise ValueError("model_id directory does not exist")

    model_key = normalized_id.as_posix()

    if discovered_models is not None:
        model = next((entry for entry in discovered_models if entry.get("id") == model_key), None)
        if model is None:
            raise ValueError("model_id is not present in discovered models")
        if not bool(model.get("selectable")):
            reasons = model.get("reasons") or []
            reason_text = ", ".join(str(item) for item in reasons) if reasons else "unknown reason"
            raise ValueError(f"model_id is not selectable: {reason_text}")

    return resolved


class MLXModelDiscoveryCache:
    def __init__(self, ttl_seconds: float = 3.0) -> None:
        self._ttl_seconds = max(1.0, float(ttl_seconds))
        self._lock = threading.Lock()
        self._cached_key: str | None = None
        self._cached_at: float = 0.0
        self._cached_result: dict[str, Any] | None = None

    def get(self, model_dir: str | Path | None, *, refresh: bool = False) -> dict[str, Any]:
        key = str(model_dir) if model_dir is not None else "__none__"
        now = time.monotonic()

        with self._lock:
            if (
                not refresh
                and self._cached_result is not None
                and self._cached_key == key
                and (now - self._cached_at) < self._ttl_seconds
            ):
                return copy.deepcopy(self._cached_result)

        result = discover_mlx_models(model_dir)

        with self._lock:
            self._cached_key = key
            self._cached_at = now
            self._cached_result = result

        return copy.deepcopy(result)
