from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .audio import AudioConfig, load_audio_config
from .auth import AuthConfig, load_auth_config
from .providers import ProvidersConfig, load_providers_config
from .rag import RAGConfig, load_rag_config
from .types import ConfigParserLike


@dataclass(frozen=True)
class ConfigSections:
    auth: AuthConfig
    rag: RAGConfig
    audio: AudioConfig
    providers: ProvidersConfig


def load_config_sections(config_parser: ConfigParserLike | None = None) -> ConfigSections:
    if config_parser is None:
        from tldw_Server_API.app.core import config as config_mod

        config_parser = config_mod.load_comprehensive_config()

    return ConfigSections(
        auth=load_auth_config(config_parser),
        rag=load_rag_config(config_parser),
        audio=load_audio_config(config_parser),
        providers=load_providers_config(config_parser),
    )


__all__ = [
    "AudioConfig",
    "AuthConfig",
    "ConfigSections",
    "ProvidersConfig",
    "RAGConfig",
    "load_audio_config",
    "load_auth_config",
    "load_config_sections",
    "load_providers_config",
    "load_rag_config",
]
