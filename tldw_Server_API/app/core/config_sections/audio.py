from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class AudioConfig:
    default_tts_provider: str
    default_tts_voice: str
    local_tts_device: str


def load_audio_config(config_parser, env: Mapping[str, str] | None = None) -> AudioConfig:
    env_map: Mapping[str, str] = env if env is not None else os.environ

    default_tts_provider = str(
        env_map.get("TTS_DEFAULT_PROVIDER")
        or config_parser.get("TTS-Settings", "default_tts_provider", fallback="openai")
    ).strip() or "openai"

    default_tts_voice = str(
        env_map.get("TTS_DEFAULT_VOICE")
        or config_parser.get("TTS-Settings", "default_tts_voice", fallback="shimmer")
    ).strip() or "shimmer"

    local_tts_device = str(
        env_map.get("LOCAL_TTS_DEVICE")
        or config_parser.get("TTS-Settings", "local_tts_device", fallback="cpu")
    ).strip() or "cpu"

    return AudioConfig(
        default_tts_provider=default_tts_provider,
        default_tts_voice=default_tts_voice,
        local_tts_device=local_tts_device,
    )
