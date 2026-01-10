"""
STT Provider adapter and registry.

This module introduces a lightweight adapter/registry for STT providers as
described in `Docs/Product/STT_Module_PRD.md`. It focuses on capability
discovery and config-driven provider selection without pulling in heavy ML
dependencies. Transcription methods will be layered on gradually.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from tldw_Server_API.app.core.config import get_stt_config
from tldw_Server_API.app.core.Ingestion_Media_Processing.path_utils import resolve_safe_local_path

try:
    # Reuse the central model-name parser so HTTP/OpenAI-style model
    # identifiers resolve consistently across REST, ingestion, and jobs.
    from .Audio_Transcription_Lib import parse_transcription_model
except Exception:  # pragma: no cover - defensive fallback for minimal envs

    def parse_transcription_model(model_name: str) -> Tuple[str, str, Optional[str]]:  # type: ignore[override]
        model_name = (model_name or "").strip()
        lowered = model_name.lower() or "whisper-1"
        # Default everything to Whisper when the real parser is unavailable.
        return "whisper", lowered, None


class SttProviderName(str, Enum):
    """Canonical provider identifiers used across the STT module."""

    FASTER_WHISPER = "faster-whisper"
    PARAKEET = "parakeet"
    CANARY = "canary"
    QWEN2AUDIO = "qwen2audio"
    EXTERNAL = "external"


@dataclass(frozen=True)
class SttProviderCapabilities:
    """
    Capability metadata for an STT provider.

    This is intentionally small and focused on the questions higher-level code
    needs to answer when routing work: can this provider handle batch
    transcriptions, streaming, and diarization?
    """

    name: SttProviderName
    supports_batch: bool = True
    supports_streaming: bool = False
    supports_diarization: bool = False
    notes: Optional[str] = None


class SttProviderAdapter(ABC):
    """
    Abstract base class for STT provider adapters.

    Concrete adapters will gradually add batch and streaming entrypoints
    (e.g. `transcribe_batch`, `create_streaming_transcriber`). For the first
    iteration we only require `get_capabilities` so that provider selection
    and capability discovery can be unified and tested.
    """

    def __init__(self, name: SttProviderName) -> None:
        self._name = name

    @property
    def name(self) -> SttProviderName:
        return self._name

    @abstractmethod
    def get_capabilities(self) -> SttProviderCapabilities:
        """Return capability metadata for this provider."""

    @abstractmethod
    def transcribe_batch(
        self,
        audio_path: str,
        *,
        model: Optional[str] = None,
        language: Optional[str] = None,
        task: str = "transcribe",
        word_timestamps: bool = False,
        prompt: Optional[str] = None,
        base_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Perform a batch transcription and return a normalized artifact.

        Normalized artifact shape (aligned with STT Module PRD):
        {
          "text": str,
          "language": Optional[str],
          "segments": list,
          "diarization": {"enabled": bool, "speakers": Optional[int]},
          "usage": {"duration_ms": Optional[int], "tokens": Optional[int]},
          "metadata": {...},
        }
        """


class FasterWhisperAdapter(SttProviderAdapter):
    """Adapter metadata for faster-whisper based transcription."""

    def __init__(self) -> None:
        super().__init__(SttProviderName.FASTER_WHISPER)

    def get_capabilities(self) -> SttProviderCapabilities:
        # Batch + streaming are supported; diarization is available via the
        # separate diarization library integration.
        return SttProviderCapabilities(
            name=self.name,
            supports_batch=True,
            supports_streaming=True,
            supports_diarization=True,
        )

    def transcribe_batch(
        self,
        audio_path: str,
        *,
        model: Optional[str] = None,
        language: Optional[str] = None,
        task: str = "transcribe",
        word_timestamps: bool = False,
        prompt: Optional[str] = None,
        base_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        # We reuse the core speech_to_text helper so behavior stays aligned
        # with existing REST/media ingestion flows.
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import (  # type: ignore
            speech_to_text as fw_speech_to_text,
            strip_whisper_metadata_header,
        )

        # Map task to STT language handling:
        #  - transcribe: honor explicit language when provided
        #  - translate: let backend auto-detect source language
        if task == "translate":
            selected_lang = None
        else:
            selected_lang = language or None

        model_name = model or "distil-large-v3"
        result = fw_speech_to_text(
            audio_path,
            whisper_model=model_name,
            selected_source_lang=selected_lang,
            vad_filter=False,
            diarize=False,
            word_timestamps=word_timestamps,
            return_language=True,
            initial_prompt=prompt,
            task=task,
            base_dir=base_dir,
        )

        segments_list, detected_lang = result
        # Strip Whisper metadata header so callers see only user content
        segments_for_response = strip_whisper_metadata_header(segments_list)
        text = " ".join(
            str(seg.get("Text", "")).strip()
            for seg in segments_for_response
            if isinstance(seg, dict)
        )

        return {
            "text": text,
            "language": language or detected_lang,
            "segments": segments_for_response,
            "diarization": {"enabled": False, "speakers": None},
            "usage": {"duration_ms": None, "tokens": None},
            "metadata": {
                "provider": self.name.value,
                "model": model_name,
            },
        }


class ParakeetAdapter(SttProviderAdapter):
    """Adapter metadata for NVIDIA Parakeet models."""

    def __init__(self) -> None:
        super().__init__(SttProviderName.PARAKEET)

    def get_capabilities(self) -> SttProviderCapabilities:
        # Parakeet supports batch and streaming; diarization is not a primary
        # focus in current usage.
        return SttProviderCapabilities(
            name=self.name,
            supports_batch=True,
            supports_streaming=True,
            supports_diarization=False,
        )

    def transcribe_batch(
        self,
        audio_path: str,
        *,
        model: Optional[str] = None,
        language: Optional[str] = None,
        task: str = "transcribe",
        word_timestamps: bool = False,
        prompt: Optional[str] = None,
        base_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        # Parakeet batch flows are routed through speech_to_text's Parakeet
        # branch by encoding the model name (e.g. "parakeet-standard").
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import (  # type: ignore
            speech_to_text,
        )

        model_name = model or "parakeet-standard"
        segments_list, lang = speech_to_text(
            audio_path,
            whisper_model=model_name,
            selected_source_lang=language,
            vad_filter=False,
            diarize=False,
            return_language=True,
            base_dir=base_dir,
        )
        text = " ".join(
            str(seg.get("Text", "")).strip()
            for seg in segments_list
            if isinstance(seg, dict)
        )
        return {
            "text": text,
            "language": language or lang,
            "segments": segments_list,
            "diarization": {"enabled": False, "speakers": None},
            "usage": {"duration_ms": None, "tokens": None},
            "metadata": {
                "provider": self.name.value,
                "model": model_name,
            },
        }


class CanaryAdapter(SttProviderAdapter):
    """Adapter metadata for NVIDIA Canary models."""

    def __init__(self) -> None:
        super().__init__(SttProviderName.CANARY)

    def get_capabilities(self) -> SttProviderCapabilities:
        # Canary is used for batch multilingual transcription today; streaming
        # support may be added later.
        return SttProviderCapabilities(
            name=self.name,
            supports_batch=True,
            supports_streaming=False,
            supports_diarization=False,
        )

    def transcribe_batch(
        self,
        audio_path: str,
        *,
        model: Optional[str] = None,
        language: Optional[str] = None,
        task: str = "transcribe",
        word_timestamps: bool = False,
        prompt: Optional[str] = None,
        base_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Nemo import (  # type: ignore
            transcribe_with_canary,
        )
        import soundfile as sf  # type: ignore
        import numpy as np  # type: ignore

        path_obj = Path(audio_path)
        if base_dir is not None:
            # Enforce that local audio paths stay within base_dir for path safety.
            safe_path = resolve_safe_local_path(path_obj, base_dir)
            if safe_path is None:
                raise ValueError(f"Audio path rejected outside base_dir: {audio_path}")
            path_obj = safe_path

        try:
            audio_np, sample_rate = sf.read(str(path_obj))
        except Exception as e:
            raise ValueError(f"Failed to read audio file {path_obj}: {e}") from e
        if not isinstance(audio_np, np.ndarray):
            audio_np = np.array(audio_np, dtype="float32")

        # For Canary we mirror the create_transcription behavior: language
        # controls ASR language, task="translate" can be interpreted by the
        # underlying helper (if supported).
        text = transcribe_with_canary(
            audio_np,
            sample_rate,
            language,
            task=task,
            target_language="en" if task == "translate" else None,
        )
        segments = [
            {
                "start_seconds": 0.0,
                "end_seconds": 0.0,
                "Text": text,
            }
        ]
        return {
            "text": text,
            "language": language or None,
            "segments": segments,
            "diarization": {"enabled": False, "speakers": None},
            "usage": {"duration_ms": None, "tokens": None},
            "metadata": {
                "provider": self.name.value,
                "model": model or "",
            },
        }


class Qwen2AudioAdapter(SttProviderAdapter):
    """Adapter metadata for Qwen2Audio models."""

    def __init__(self) -> None:
        super().__init__(SttProviderName.QWEN2AUDIO)

    def get_capabilities(self) -> SttProviderCapabilities:
        # Qwen2Audio currently exposes batch-style transcription only.
        return SttProviderCapabilities(
            name=self.name,
            supports_batch=True,
            supports_streaming=False,
            supports_diarization=False,
        )

    def transcribe_batch(
        self,
        audio_path: str,
        *,
        model: Optional[str] = None,
        language: Optional[str] = None,
        task: str = "transcribe",
        word_timestamps: bool = False,
        prompt: Optional[str] = None,
        base_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import (  # type: ignore
            speech_to_text,
        )

        model_name = model or "qwen2audio"
        segments_list, lang = speech_to_text(
            audio_path,
            whisper_model=model_name,
            selected_source_lang=language,
            vad_filter=False,
            diarize=False,
            return_language=True,
            base_dir=base_dir,
        )
        text = " ".join(
            str(seg.get("Text", "")).strip()
            for seg in segments_list
            if isinstance(seg, dict)
        )
        return {
            "text": text,
            "language": language or lang,
            "segments": segments_list,
            "diarization": {"enabled": False, "speakers": None},
            "usage": {"duration_ms": None, "tokens": None},
            "metadata": {
                "provider": self.name.value,
                "model": model_name,
            },
        }


class ExternalAdapter(SttProviderAdapter):
    """Adapter metadata for external/custom STT providers."""

    def __init__(self) -> None:
        super().__init__(SttProviderName.EXTERNAL)

    def get_capabilities(self) -> SttProviderCapabilities:
        # External providers are assumed to handle batch requests; streaming
        # and diarization support depend on the concrete integration.
        return SttProviderCapabilities(
            name=self.name,
            supports_batch=True,
            supports_streaming=False,
            supports_diarization=False,
        )

    def transcribe_batch(
        self,
        audio_path: str,
        *,
        model: Optional[str] = None,
        language: Optional[str] = None,
        task: str = "transcribe",
        word_timestamps: bool = False,
        prompt: Optional[str] = None,
        base_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_External_Provider import (  # type: ignore
            transcribe_with_external_provider,
        )

        provider_name = "default"
        model_id = model or "whisper-1"
        if model_id.startswith("external:"):
            provider_name = model_id.split(":", 1)[1] or "default"

        # Pass base_dir so external providers validate local paths consistently.
        text = transcribe_with_external_provider(
            audio_path,
            provider_name=provider_name,
            base_dir=base_dir,
        )
        segments = [
            {
                "start_seconds": 0.0,
                "end_seconds": 0.0,
                "Text": text,
            }
        ]
        return {
            "text": text,
            "language": language or None,
            "segments": segments,
            "diarization": {"enabled": False, "speakers": None},
            "usage": {"duration_ms": None, "tokens": None},
            "metadata": {
                "provider": self.name.value,
                "model": model_id,
                "external_provider_name": provider_name,
            },
        }


def _normalize_provider_name(name: Optional[str]) -> str:
    """
    Normalize provider identifiers from config or call sites.

    - Accepts both 'faster_whisper' and 'faster-whisper' and normalizes to
      'faster-whisper'.
    - Returns lower-cased identifiers for consistency.
    """
    if not name:
        return ""
    lowered = str(name).strip().lower()
    if lowered in {"faster-whisper", "faster_whisper"}:
        return "faster-whisper"
    return lowered


class SttProviderRegistry:
    """
    Registry for STT providers and their adapters.

    This registry is intentionally lightweight: it does not instantiate heavy
    ML models and only exposes capability metadata and config-driven selection.
    """

    def __init__(self) -> None:
        self._adapters: Dict[str, SttProviderAdapter] = {
            SttProviderName.FASTER_WHISPER.value: FasterWhisperAdapter(),
            SttProviderName.PARAKEET.value: ParakeetAdapter(),
            SttProviderName.CANARY.value: CanaryAdapter(),
            SttProviderName.QWEN2AUDIO.value: Qwen2AudioAdapter(),
            SttProviderName.EXTERNAL.value: ExternalAdapter(),
        }

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #

    def get_default_provider_name(self) -> str:
        """
        Return the default provider name based on `[STT-Settings]`.

        This mirrors the behavior of the config loader:
        - Prefer `default_transcriber` when present.
        - Fall back to `default_stt_provider`.
        - Final fallback is 'faster-whisper'.
        """
        cfg: Dict[str, Any]
        try:
            cfg = get_stt_config() or {}
        except Exception:
            cfg = {}

        raw_default = cfg.get("default_transcriber") or cfg.get("default_stt_provider") or "faster-whisper"
        normalized = _normalize_provider_name(raw_default)
        return normalized or "faster-whisper"

    def get_adapter(self, provider_name: Optional[str] = None) -> SttProviderAdapter:
        """
        Return the adapter for the given provider name.

        When `provider_name` is None or unknown, the default provider is
        resolved via config and used. As a final safety net, the
        'faster-whisper' adapter is returned.
        """
        if provider_name:
            key = _normalize_provider_name(provider_name)
        else:
            key = self.get_default_provider_name()

        adapter = self._adapters.get(key)
        if adapter is not None:
            return adapter

        # Defensive fallback to faster-whisper
        return self._adapters[SttProviderName.FASTER_WHISPER.value]

    def get_capabilities(self, provider_name: Optional[str] = None) -> SttProviderCapabilities:
        """
        Convenience helper to fetch capability metadata for a provider.
        """
        return self.get_adapter(provider_name).get_capabilities()

    def resolve_provider_for_model(self, model_name: Optional[str]) -> Tuple[str, str, Optional[str]]:
        """
        Resolve an HTTP/OpenAI-style model name to (provider, model, variant).

        This wraps `parse_transcription_model` so that all call sites rely on
        a single mapping from model identifiers to providers. The provider
        name returned is normalized (e.g. 'faster-whisper').
        """
        if not model_name:
            # When no model is specified, just return the default provider and
            # leave model/variant unspecified. Higher-level code can fill in
            # model defaults (e.g. whisper alias mapping).
            provider = self.get_default_provider_name()
            return provider, "", None

        try:
            normalized_name = (model_name or "").strip()
            lowered = normalized_name.lower()
            # Preserve legacy alias: bare "qwen" maps to Qwen2Audio.
            if lowered == "qwen":
                provider = SttProviderName.QWEN2AUDIO.value
                return provider, "qwen2audio", None

            raw_provider, model, variant = parse_transcription_model(normalized_name)
        except Exception:
            # Defensive: treat unknown models as Whisper-family
            raw_provider, model, variant = "whisper", (model_name or "").strip(), None

        provider = _normalize_provider_name(raw_provider)
        if provider == "whisper":
            # Internally, Whisper-family models are handled via faster-whisper.
            provider = SttProviderName.FASTER_WHISPER.value
        return provider, model, variant


_REGISTRY: Optional[SttProviderRegistry] = None


def get_stt_provider_registry() -> SttProviderRegistry:
    """
    Return the process-wide STT provider registry.

    This is a simple singleton to keep lookup overhead low while still
    allowing tests to reset/monkeypatch behavior if needed.
    """
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = SttProviderRegistry()
    return _REGISTRY


def reset_stt_provider_registry() -> None:
    """
    Reset the global registry (used by tests).
    """
    global _REGISTRY
    _REGISTRY = None
