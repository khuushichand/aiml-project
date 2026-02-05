"""Audio endpoints package.

Compatibility shim: expose attributes from audio.audio at package level so
imports like `tldw_Server_API.app.api.v1.endpoints.audio` keep working.
"""

from importlib import import_module as _import_module
from types import ModuleType as _ModuleType
from typing import Any as _Any

import soundfile as sf

from tldw_Server_API.app.core.Audio.tokenizer_service import (
    _get_qwen3_tokenizer_settings,
    _load_qwen3_tokenizer,
)
from tldw_Server_API.app.core.Audio.tts_service import (
    _sanitize_speech_request,
    _tts_fallback_resolver,
)
from tldw_Server_API.app.core.Storage.generated_file_helpers import (
    save_and_register_tts_audio,
)
from tldw_Server_API.app.core.Usage.audio_quota import (
    add_daily_minutes,
    can_start_job,
    check_daily_minutes_allow,
    finish_job,
    get_job_heartbeat_interval_seconds,
    get_limits_for_user,
    heartbeat_jobs,
    increment_jobs_started,
)

_AUDIO_MODULE_PATH = "tldw_Server_API.app.api.v1.endpoints.audio.audio"
_audio_module: _ModuleType | None = None


def _load_audio_module() -> _ModuleType:
    global _audio_module
    if _audio_module is None:
        _audio_module = _import_module(_AUDIO_MODULE_PATH)
    return _audio_module


def __getattr__(name: str) -> _Any:
    return getattr(_load_audio_module(), name)


def __dir__() -> list[str]:
    mod = _load_audio_module()
    return sorted(set(globals().keys()) | set(dir(mod)))
