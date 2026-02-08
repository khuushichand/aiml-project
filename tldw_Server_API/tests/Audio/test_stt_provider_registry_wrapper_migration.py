from __future__ import annotations

from collections.abc import Sequence
import importlib
from pathlib import Path
import sys
from typing import Any, Callable
import types

import pytest


pytestmark = pytest.mark.unit


_EXCEPTIONS_MODULE = "tldw_Server_API.app.core.exceptions"
_AUDIO_LIB_MODULE = "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib"


def _install_py39_compat_stubs() -> None:
    exceptions_stub = types.ModuleType(_EXCEPTIONS_MODULE)
    exceptions_stub.BadRequestError = type("BadRequestError", (Exception,), {})
    exceptions_stub.CancelCheckError = type("CancelCheckError", (Exception,), {})
    exceptions_stub.TranscriptionCancelled = type("TranscriptionCancelled", (Exception,), {})
    exceptions_stub.InvalidStoragePathError = type("InvalidStoragePathError", (Exception,), {})
    exceptions_stub.StorageUnavailableError = type("StorageUnavailableError", (Exception,), {})
    exceptions_stub.NetworkError = type("NetworkError", (Exception,), {})
    exceptions_stub.RetryExhaustedError = type("RetryExhaustedError", (Exception,), {})
    exceptions_stub.__file__ = __file__

    def _exception_getattr(name: str):
        if name.startswith("__"):
            raise AttributeError(name)
        return type(str(name), (Exception,), {})

    exceptions_stub.__getattr__ = _exception_getattr  # type: ignore[assignment]
    sys.modules[_EXCEPTIONS_MODULE] = exceptions_stub

    audio_lib_stub = types.ModuleType(_AUDIO_LIB_MODULE)
    audio_lib_stub.__file__ = __file__
    audio_lib_stub.parse_transcription_model = lambda model_name: ("whisper", str(model_name or ""), None)
    audio_lib_stub.speech_to_text = lambda *args, **kwargs: ([], kwargs.get("selected_source_lang"))
    audio_lib_stub.strip_whisper_metadata_header = lambda segments: segments
    sys.modules[_AUDIO_LIB_MODULE] = audio_lib_stub


def _import_module():
    module_name = "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.stt_provider_adapter"
    try:
        return importlib.import_module(module_name)
    except TypeError as exc:
        # Python 3.9 test env cannot import some project modules that use
        # PEP-604 runtime unions. Inject a minimal exceptions stub so this
        # wrapper-level test can still validate registry behavior.
        if "unsupported operand type(s) for |" not in str(exc):
            raise
        _install_py39_compat_stubs()
        sys.modules.pop(module_name, None)
        return importlib.import_module(module_name)


def test_registry_wraps_base_for_default_lookup_and_aliases() -> None:
    spa = _import_module()
    registry = spa.SttProviderRegistry()

    adapter1 = registry.get_adapter("faster_whisper")
    adapter2 = registry.get_adapter("fw")

    assert adapter1.name.value == "faster-whisper"
    assert adapter2 is adapter1


def test_registry_registers_custom_adapter_and_caches_instance() -> None:
    spa = _import_module()
    init_state = {"count": 0}

    class _CustomAdapter(spa.SttProviderAdapter):
        def __init__(self) -> None:
            init_state["count"] += 1
            super().__init__(spa.SttProviderName.EXTERNAL)

        def get_capabilities(self) -> Any:
            return spa.SttProviderCapabilities(
                name=self.name,
                supports_batch=True,
                supports_streaming=False,
                supports_diarization=False,
            )

        def transcribe_batch(
            self,
            audio_path: str,
            *,
            model: str | None = None,
            language: str | None = None,
            task: str = "transcribe",
            word_timestamps: bool = False,
            prompt: str | None = None,
            hotwords: Sequence[str] | None = None,
            base_dir: Path | None = None,
            cancel_check: Callable[[], bool] | None = None,
        ) -> dict[str, Any]:
            return {
                "text": "ok",
                "language": language,
                "segments": [],
                "diarization": {"enabled": False, "speakers": None},
                "usage": {"duration_ms": None, "tokens": None},
                "metadata": {"provider": self.name.value, "model": model or "custom"},
            }

    registry = spa.SttProviderRegistry()
    registry.register_adapter("custom-provider", _CustomAdapter, aliases=["custom_provider"])

    adapter1 = registry.get_adapter("custom-provider")
    adapter2 = registry.get_adapter("custom_provider")

    assert adapter2 is adapter1
    assert init_state["count"] == 1


def test_registry_status_tracking_reflects_failed_provider_materialization() -> None:
    spa = _import_module()
    registry = spa.SttProviderRegistry()

    registry.register_adapter("broken-provider", "not.a.real.module.Adapter")

    fallback = registry.get_adapter("broken-provider")

    assert fallback.name.value == "faster-whisper"
    assert registry.get_status("broken-provider") == "failed"


def test_registry_list_capabilities_uses_base_envelope() -> None:
    spa = _import_module()
    registry = spa.SttProviderRegistry()

    entries = {entry["provider"]: entry for entry in registry.list_capabilities()}

    assert "faster-whisper" in entries
    assert entries["faster-whisper"]["availability"] in {"enabled", "failed", "disabled", "unknown"}
    assert entries["faster-whisper"]["capabilities"] is not None


def test_registry_callback_wiring_supports_domain_overrides() -> None:
    spa = _import_module()

    class _ConfigDisabledRegistry(spa.SttProviderRegistry):
        def _is_provider_enabled_by_config(self, provider_name: str):
            if provider_name == "faster-whisper":
                return False
            return None

    default_registry = spa.SttProviderRegistry()
    assert default_registry.get_status("faster-whisper") == "enabled"

    overridden_registry = _ConfigDisabledRegistry()
    assert overridden_registry.get_status("faster-whisper") == "disabled"
