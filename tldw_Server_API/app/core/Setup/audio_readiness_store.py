"""Persistence helpers for setup audio readiness state."""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from loguru import logger
from pydantic import BaseModel, Field

from tldw_Server_API.app.core.Setup import setup_manager

CONFIG_ROOT = setup_manager.CONFIG_RELATIVE_PATH.parent
READINESS_FILENAME = "setup_audio_readiness.json"
_STORE: AudioReadinessStore | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AudioReadinessRecord(BaseModel):
    """Persisted setup audio readiness snapshot."""

    status: Literal[
        "not_started",
        "provisioning",
        "partial",
        "ready",
        "ready_with_warnings",
        "failed",
    ] = "not_started"
    selected_bundle_id: str | None = None
    machine_profile: dict[str, Any] | None = None
    last_verification: dict[str, Any] | None = None
    remediation_items: list[Any] = Field(default_factory=list)
    updated_at: str = Field(default_factory=_utc_now)


def _candidate_readiness_files() -> list[Path]:
    candidates: list[Path] = []

    override_file = os.getenv("TLDW_AUDIO_READINESS_FILE")
    if override_file:
        candidates.append(Path(override_file))

    override_dir = os.getenv("TLDW_INSTALL_STATE_DIR")
    if override_dir:
        candidates.append(Path(override_dir) / READINESS_FILENAME)

    candidates.append(CONFIG_ROOT / READINESS_FILENAME)

    try:
        home = Path.home()
    except Exception:  # noqa: BLE001
        home = None
    if home:
        candidates.append(home / ".cache" / "tldw_server" / READINESS_FILENAME)

    candidates.append(Path(tempfile.gettempdir()) / "tldw_server" / READINESS_FILENAME)
    return candidates


def _resolve_readiness_file() -> Path | None:
    for path in _candidate_readiness_files():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            probe = path.parent / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            with contextlib.suppress(FileNotFoundError):
                probe.unlink()
            return path
        except Exception:  # noqa: BLE001
            logger.debug("Audio readiness path {} not writable", path, exc_info=True)

    logger.warning("No writable location found for audio readiness persistence.")
    return None


class AudioReadinessStore:
    """Read and write the setup audio readiness snapshot."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        default_record = AudioReadinessRecord()
        if not self.path or not self.path.is_file():
            return default_record.model_dump()

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return AudioReadinessRecord.model_validate(data).model_dump()
        except Exception:  # noqa: BLE001
            logger.warning("Failed to read audio readiness from {}", self.path, exc_info=True)
            return default_record.model_dump()

    def save(self, readiness: dict[str, Any]) -> dict[str, Any]:
        payload = dict(readiness)
        payload["updated_at"] = _utc_now()
        record = AudioReadinessRecord.model_validate(payload)
        data = record.model_dump()

        if not self.path:
            return data

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data

    def update(self, **fields: Any) -> dict[str, Any]:
        current = self.load()
        current.update(fields)
        return self.save(current)

    def reset(self) -> dict[str, Any]:
        return self.save(AudioReadinessRecord().model_dump())


def get_audio_readiness_store() -> AudioReadinessStore:
    global _STORE
    if _STORE is None:
        _STORE = AudioReadinessStore(_resolve_readiness_file())
    return _STORE


def reset_audio_readiness_store() -> None:
    global _STORE
    _STORE = None


__all__ = [
    "AudioReadinessRecord",
    "AudioReadinessStore",
    "READINESS_FILENAME",
    "get_audio_readiness_store",
    "reset_audio_readiness_store",
]
