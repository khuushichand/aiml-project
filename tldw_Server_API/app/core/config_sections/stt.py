from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from .types import ConfigParserLike

_TRUE_VALUES = {"1", "true", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "no", "n", "off"}


@dataclass(frozen=True)
class STTConfig:
    ws_control_v2_enabled: bool
    paused_audio_queue_cap_seconds: float
    overflow_warning_interval_seconds: float
    transcript_diagnostics_enabled: bool
    delete_audio_after_success: bool
    audio_retention_hours: float
    redact_pii: bool


def _get_raw(
    config_parser: ConfigParserLike,
    env_map: Mapping[str, str],
    env_keys: tuple[str, ...],
    options: tuple[str, ...],
    default: str,
) -> str:
    for env_key in env_keys:
        env_value = env_map.get(env_key)
        if env_value is not None and str(env_value).strip() != "":
            return str(env_value)

    for option in options:
        raw = config_parser.get("STT-Settings", option, fallback=None)
        if raw is not None and str(raw).strip() != "":
            return str(raw)
    return default


def _parse_bool(raw: object, default: bool) -> bool:
    text = str(raw).strip().lower()
    if not text:
        return default
    if text in _TRUE_VALUES:
        return True
    if text in _FALSE_VALUES:
        return False
    return default


def _parse_nonnegative_float(raw: object, default: float) -> float:
    text = str(raw).strip()
    if not text:
        return default
    try:
        value = float(text)
    except (TypeError, ValueError):
        return default
    if value < 0.0:
        return default
    return value


def load_stt_config(
    config_parser: ConfigParserLike,
    env: Mapping[str, str] | None = None,
) -> STTConfig:
    env_map: Mapping[str, str] = env if env is not None else os.environ

    ws_control_v2_enabled = _parse_bool(
        _get_raw(
            config_parser,
            env_map,
            ("STT_WS_CONTROL_V2_ENABLED",),
            ("ws_control_v2_enabled",),
            "false",
        ),
        False,
    )
    paused_audio_queue_cap_seconds = _parse_nonnegative_float(
        _get_raw(
            config_parser,
            env_map,
            ("STT_PAUSED_AUDIO_QUEUE_CAP_SECONDS",),
            ("paused_audio_queue_cap_seconds",),
            "2.0",
        ),
        2.0,
    )
    overflow_warning_interval_seconds = _parse_nonnegative_float(
        _get_raw(
            config_parser,
            env_map,
            ("STT_OVERFLOW_WARNING_INTERVAL_SECONDS",),
            ("overflow_warning_interval_seconds",),
            "5.0",
        ),
        5.0,
    )
    transcript_diagnostics_enabled = _parse_bool(
        _get_raw(
            config_parser,
            env_map,
            ("STT_TRANSCRIPT_DIAGNOSTICS_ENABLED",),
            ("transcript_diagnostics_enabled",),
            "false",
        ),
        False,
    )
    delete_audio_after_success = _parse_bool(
        _get_raw(
            config_parser,
            env_map,
            ("STT_DELETE_AUDIO_AFTER_SUCCESS", "STT_DELETE_AUDIO_AFTER"),
            ("delete_audio_after_success", "delete_audio_after"),
            "true",
        ),
        True,
    )
    audio_retention_hours = _parse_nonnegative_float(
        _get_raw(
            config_parser,
            env_map,
            ("STT_AUDIO_RETENTION_HOURS",),
            ("audio_retention_hours",),
            "0.0",
        ),
        0.0,
    )
    redact_pii = _parse_bool(
        _get_raw(
            config_parser,
            env_map,
            ("STT_REDACT_PII",),
            ("redact_pii",),
            "false",
        ),
        False,
    )

    return STTConfig(
        ws_control_v2_enabled=ws_control_v2_enabled,
        paused_audio_queue_cap_seconds=paused_audio_queue_cap_seconds,
        overflow_warning_interval_seconds=overflow_warning_interval_seconds,
        transcript_diagnostics_enabled=transcript_diagnostics_enabled,
        delete_audio_after_success=delete_audio_after_success,
        audio_retention_hours=audio_retention_hours,
        redact_pii=redact_pii,
    )
