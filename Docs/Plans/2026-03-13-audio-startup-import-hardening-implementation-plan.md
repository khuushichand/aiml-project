# Audio Startup Import Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent backend startup from importing heavy optional audio/STT backends while preserving existing audio route behavior.

**Architecture:** Keep the FastAPI route surface unchanged, but make the audio route and transcription modules import-safe. First lock the failure mode with import-resilience tests, then remove direct unified-streaming imports from `audio_streaming.py`, extract `QuotaExceeded` to a lightweight module, and finally lazy-load `faster_whisper` and `transformers` inside `Audio_Transcription_Lib.py`.

**Tech Stack:** Python, FastAPI, pytest, importlib, module stubs, Bandit

---

### Task 1: Lock Import-Resilience Regressions With Failing Tests

**Files:**
- Modify: `tldw_Server_API/tests/Audio/test_audio_router_import_resilience.py`
- Modify: `tldw_Server_API/tests/MediaIngestion_NEW/unit/test_audio_transcription.py`

**Step 1: Write the failing tests**

Add import-resilience tests that poison optional backends and verify import behavior directly.

```python
@pytest.mark.unit
def test_audio_streaming_import_survives_broken_unified_backend(monkeypatch):
    broken_name = "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified"
    module_name = "tldw_Server_API.app.api.v1.endpoints.audio.audio_streaming"
    ...
    monkeypatch.setitem(sys.modules, broken_name, _BrokenModule(broken_name))
    imported = importlib.import_module(module_name)
    assert imported.router is not None


@pytest.mark.unit
def test_app_main_import_survives_broken_unified_backend(monkeypatch):
    broken_name = "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified"
    module_name = "tldw_Server_API.app.main"
    ...
    monkeypatch.setitem(sys.modules, broken_name, _BrokenModule(broken_name))
    imported = importlib.import_module(module_name)
    assert getattr(imported, "app", None) is not None


@pytest.mark.unit
def test_audio_transcription_lib_import_survives_broken_optional_backends(monkeypatch):
    module_name = "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib"
    monkeypatch.setitem(sys.modules, "faster_whisper", _BrokenModule("faster_whisper"))
    monkeypatch.setitem(sys.modules, "transformers", _BrokenModule("transformers"))
    imported = importlib.import_module(module_name)
    assert hasattr(imported, "WhisperModel")
```

**Step 2: Run the tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Audio/test_audio_router_import_resilience.py tldw_Server_API/tests/MediaIngestion_NEW/unit/test_audio_transcription.py -k "import_survives_broken"`

Expected: FAIL because `audio_streaming.py` still imports unified streaming symbols eagerly and `Audio_Transcription_Lib.py` still imports `faster_whisper` and `transformers` at module load.

**Step 3: Commit the red test snapshot only if the repo already follows that workflow**

Do not commit a failing tree unless explicitly requested. Leave the worktree red locally and move immediately to implementation.

### Task 2: Remove Import-Time Unified Streaming Coupling

**Files:**
- Add: `tldw_Server_API/app/core/Audio/streaming_exceptions.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py`
- Modify: `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Streaming_Unified.py`

**Step 1: Write the minimal implementation**

Create a shared lightweight exception module:

```python
class QuotaExceeded(Exception):
    def __init__(self, quota: str):
        super().__init__(quota)
        self.quota = quota
```

Update `Audio_Streaming_Unified.py` to import `QuotaExceeded` from that module and remove the local class definition.

Update `audio_streaming.py` to stop importing unified streaming symbols directly. Add helpers such as:

```python
_AUDIO_UNIFIED_MODULE = (
    "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified"
)


def _load_audio_unified_module():
    return importlib.import_module(_AUDIO_UNIFIED_MODULE)


def _load_audio_unified_attr(name: str):
    return getattr(_load_audio_unified_module(), name)


def _new_unified_streaming_config(**kwargs):
    return _load_audio_unified_attr("UnifiedStreamingConfig")(**kwargs)


async def _handle_unified_websocket(*args, **kwargs):
    handler = _load_audio_unified_attr("handle_unified_websocket")
    return await handler(*args, **kwargs)
```

Use those helpers wherever the module currently instantiates configs, transcribers, VAD detectors, or invokes the websocket handler.

**Step 2: Run the focused tests**

Run: `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Audio/test_audio_router_import_resilience.py -k "import_survives_broken"`

Expected: PASS for the audio route and app import resilience tests.

**Step 3: Commit**

```bash
git add tldw_Server_API/app/core/Audio/streaming_exceptions.py tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Streaming_Unified.py tldw_Server_API/tests/Audio/test_audio_router_import_resilience.py
git commit -m "fix: lazy load unified audio streaming backends"
```

### Task 3: Lazy-Load Transcription Backends In `Audio_Transcription_Lib.py`

**Files:**
- Modify: `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Transcription_Lib.py`
- Modify: `tldw_Server_API/tests/MediaIngestion_NEW/unit/test_audio_transcription.py`

**Step 1: Write the minimal implementation**

Replace the eager imports with explicit loaders:

```python
def _get_original_whisper_model():
    module = importlib.import_module("faster_whisper")
    return getattr(module, "WhisperModel")


def _get_qwen2audio_classes():
    module = importlib.import_module("transformers")
    return (
        getattr(module, "AutoProcessor"),
        getattr(module, "Qwen2AudioForConditionalGeneration"),
    )
```

Refactor `WhisperModel` into a lazy wrapper that instantiates the real faster-whisper class in `__init__` and forwards attribute access via `__getattr__`. Keep:

- `WhisperModel` name
- `valid_model_sizes`
- existing cache behavior in `get_whisper_model`

Update `load_qwen2audio()` to resolve the transformers classes through `_get_qwen2audio_classes()` before calling `from_pretrained(...)`.

**Step 2: Run the focused tests**

Run: `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/MediaIngestion_NEW/unit/test_audio_transcription.py -k "import_survives_broken or processing_choice_safe"`

Expected: PASS for the new import-resilience test and the existing import-safety regression.

**Step 3: Run touched-scope verification**

Run:

- `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Audio/test_audio_router_import_resilience.py`
- `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/MediaIngestion_NEW/unit/test_audio_transcription.py -k "import_survives_broken or processing_choice_safe"`
- `source .venv/bin/activate && python -c "import tldw_Server_API.app.main; print('main ok')"`
- `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py tldw_Server_API/app/core/Audio/streaming_exceptions.py tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Streaming_Unified.py tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Transcription_Lib.py -f json -o /tmp/bandit_audio_startup_import_hardening.json`

Expected:

- pytest green on the touched tests
- the import probe prints `main ok`
- Bandit reports no new findings in the touched scope

**Step 4: Commit**

```bash
git add tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Transcription_Lib.py tldw_Server_API/tests/MediaIngestion_NEW/unit/test_audio_transcription.py
git commit -m "fix: defer heavy transcription backend imports"
```
