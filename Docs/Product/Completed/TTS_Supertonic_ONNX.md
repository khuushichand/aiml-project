# PRD: Supertonic ONNX TTS Provider

## 1. Overview

This document specifies how to integrate Supertonic’s ONNX TTS pipeline as a first‑class local provider in the existing TTS module.

- **Scope**: Add a new adapter‑based provider (`supertonic`) that plugs into:
  - `TTSServiceV2` and the adapter registry
  - OpenAI‑compatible `/api/v1/audio/speech`
  - Voice catalog (`/api/v1/audio/voices/catalog`)
- **Asset model**: Users supply the Supertonic ONNX models and voice style files; the project ships:
  - A provider adapter
  - Configuration wiring
  - An optional installer script to help fetch / organize assets
- **Non‑goals**:
  - Training or fine‑tuning models
  - Voice cloning for Supertonic in v1
  - True incremental/low‑latency streaming from Supertonic (we’ll pseudo‑stream encoded bytes)

This PRD is specific to the current TTS architecture in `tldw_Server_API/app/core/TTS/`.

## 2. Goals & User Stories

### 2.1 Goals

- Add a **local** Supertonic ONNX TTS provider that:
  - Uses the existing `TTSAdapter` interface
  - Is selectable via `OpenAISpeechRequest.model` and TTS config
  - Supports both streaming and non‑streaming server responses
  - Exposes Supertonic voice styles via the unified voice catalog
- Allow users to control:
  - Speech **speed**
  - **Quality vs speed** via denoising steps
  - Voice **style** by selecting among provided style JSONs
- Keep behavior consistent with other local engines (Kokoro, NeuTTS, etc.) and with the TTS validation system.

### 2.2 User Stories

- **Local‑first user**
  - *As a self‑hoster*, I want a high‑quality local TTS based on Supertonic that doesn’t require remote APIs, so my data and voices never leave the machine.
- **Power user**
  - *As a power user*, I want to adjust speed and quality parameters (denoising steps) to trade latency for fidelity depending on my workload.
- **Voice variety**
  - *As a storyteller / roleplay user*, I want multiple distinct Supertonic voices (e.g., male/female styles) available through the same voice catalog and WebUI dropdown.
- **Long‑form listening**
  - *As a long‑form content consumer*, I want to paste long paragraphs and have them read aloud smoothly, without manual chunking.

## 3. Architectural Fit

### 3.1 Existing TTS Architecture (Short)

- Core orchestration: `TTSServiceV2` (`tts_service_v2.py`)
- Provider registry: `TTSAdapterRegistry` and `TTSAdapterFactory` (`adapter_registry.py`)
- Provider contract: `TTSAdapter`, `TTSRequest`, `TTSResponse`, `AudioFormat`, `TTSCapabilities` (`adapters/base.py`)
- Validation/sanitization: `TTSInputValidator` + `ProviderLimits` (`tts_validation.py`)
- Config: `TTSConfigManager` & `TTSConfig` (`tts_config.py`) + `tts_providers_config.yaml`
- Audio formatting: `StreamingAudioWriter` + `AudioNormalizer` (`streaming_audio_writer.py`) wrapped by `TTSAdapter.convert_audio_format`
- Voice catalog: `TTSServiceV2.get_capabilities()` + `TTSServiceV2.list_voices()` → `/api/v1/audio/voices/catalog`
- API entrypoint: `/api/v1/audio/speech` in `api/v1/endpoints/audio.py`, using `OpenAISpeechRequest`

Supertonic will be another provider in this ecosystem.

### 3.2 New Components & Touchpoints

1. **Enum & registry**
   - Add `SUPERTONIC = "supertonic"` to `TTSProvider` in `adapter_registry.py`.
   - Register a default adapter mapping:
     - `TTSProvider.SUPERTONIC: "tldw_Server_API.app.core.TTS.adapters.supertonic_adapter.SupertonicOnnxAdapter"`.
2. **New adapter**
   - File: `tldw_Server_API/app/core/TTS/adapters/supertonic_adapter.py`
   - Class: `SupertonicOnnxAdapter(TTSAdapter)`
3. **Vendor namespace**
   - Folder: `tldw_Server_API/app/core/TTS/vendors/supertonic/`
   - Purpose: wrap upstream helpers (`load_text_to_speech`, `load_voice_style`) so we can pin versions and avoid hard dependency on the upstream repo layout.
4. **Model routing**
   - Extend `TTSAdapterFactory.MODEL_PROVIDER_MAP` in `adapter_registry.py` with Supertonic model aliases:
     - Canonical model id: `"tts-supertonic-1"` (recommended in docs and examples).
     - Aliases: `"supertonic"`, `"supertonic-onnx"` (for backwards‑compatible or shorthand usage).
5. **Provider hinting for validation**
   - Extend `_infer_tts_provider_from_model()` in `api/v1/endpoints/audio.py` so model names starting with `supertonic` or `tts-supertonic` map to provider key `"supertonic"`.
6. **Config**
   - Add a `supertonic` block under `providers` in `tts_providers_config.yaml`, consumed via `TTSConfigManager`.
   - Optional installer: `Helper_Scripts/TTS_Installers/install_tts_supertonic.py` to download/prepare models and voice styles.

## 4. Functional Requirements

### 4.1 Provider Behavior

**Provider identity**

- Logical provider key: `"supertonic"` (used by config, validation, and metrics).
- Adapter class name: `SupertonicOnnxAdapter`.
- Exposed via:
  - `TTSServiceV2.get_capabilities()` → capabilities object under `capabilities["supertonic"]`
  - `TTSServiceV2.list_voices()` → `voices_by_provider["supertonic"]`

**TTSRequest handling**

- Input fields used:
  - `text`: main synthesis text.
  - `voice`: maps to a Supertonic voice style ID (e.g. `supertonic_m1`).
  - `format`: desired output `AudioFormat` (at minimum `MP3`, `WAV`).
  - `speed`: speech speed; clamped to Supertonic’s recommended range but still respects global `[0.25, 4.0]` contract.
  - `stream`: whether to return `audio_stream` vs `audio_data`.
  - `language`: optional; default `"en"` for Supertonic (the engine will still do its own preprocessing).
  - `extra_params`: provider‑specific options:
    - `total_step` (int): denoising steps (quality vs speed).
    - Optional: `onnx_dir`, `voice_style_file`, `n_test` overrides for advanced use.

**TTSResponse behavior**

- Non‑streaming:
  - Return `TTSResponse(audio_data=<bytes>, format=request.format, sample_rate=<engine_sr>, channels=1, voice_used=<voice_id>, provider="Supertonic")`.
- Streaming:
  - Return `TTSResponse(audio_stream=<async generator>, format=request.format, ...)`.
  - Streaming is “pseudo‑streaming”: we synthesize full audio from Supertonic and then chunk it into e.g. 8–16 kB pieces for the client.
  - Mark `supports_streaming=True` in capabilities, but clarify semantics.

### 4.2 Supertonic Engine Integration

**Upstream contract (reference)**

From Supertonic’s `example_onnx.py`:

- Engine load:
  - `text_to_speech = load_text_to_speech(onnx_dir, use_gpu)`
- Voice style load:
  - `style = load_voice_style(voice_style_paths, verbose=True)`
- Inference:
  - Non‑batch: `wav, duration = text_to_speech(text_list[0], style, total_step, speed)`
  - Batch: `wav, duration = text_to_speech.batch(text_list, style, total_step, speed)`
- Output handling:
  - `w = wav[b, : int(text_to_speech.sample_rate * duration[b].item())]`
  - `sf.write(...)` to produce `.wav` files.

**Adapter initialization**

`SupertonicOnnxAdapter.initialize()` should:

1. Resolve config:
   - `onnx_dir`: where ONNX models live.
   - `use_gpu`: boolean; used for future GPU support, but we keep behavior CPU‑first for v1.
   - `voice_styles_dir`: where `M1.json`, `F1.json`, etc., live.
   - Defaults: see §4.3.
2. Import vendored helpers:
   - `from tldw_Server_API.app.core.TTS.vendors.supertonic import load_text_to_speech, load_voice_style`.
3. Call `load_text_to_speech(onnx_dir, use_gpu)`:
   - Store engine in `self._engine`.
   - Store `self.sample_rate = self._engine.sample_rate`.
4. Discover or define voice styles:
   - Use a **fixed mapping** from voice IDs to filenames from config (see §4.3), e.g. `supertonic_m1 -> M1.json`, `supertonic_f1 -> F1.json`.
   - Build `VoiceInfo` entries for each mapped style and store them in the adapter.
   - If the configured **default voice** ID does not map to an existing JSON file, treat this as a hard initialization error (raise `TTSModelNotFoundError`).
5. Set status/capabilities:
   - On success: `_status = ProviderStatus.AVAILABLE`, `_initialized = True`, `_capabilities = await get_capabilities()`.
   - On failure: raise appropriate `TTSModelNotFoundError` / `TTSModelLoadError` and let the registry manage backoff.

**Text synthesis (non‑streaming)**

For a single `TTSRequest`:

1. Validate with `validate_tts_request(request, provider="supertonic")` (and let `TTSServiceV2` enforce additional checks).
2. Resolve voice style:
   - `voice_id = request.voice or self.default_voice` (from config).
   - Map `voice_id` → `style_path` (JSON file).
   - Call `style = load_voice_style([style_path], verbose=False)`.
3. Resolve parameters:
   - `total_step = extra_params.get("total_step") or self.default_total_step` (int, default 5).
   - `speed = request.speed`:
     - The validator enforces `0.9 <= speed <= 1.5` for `supertonic` via `ProviderLimits`; out‑of‑range values are rejected with `TTSInvalidInputError` before reaching the adapter.
     - `TTSRequest.__post_init__` still clamps to the global `[0.25, 4.0]` envelope, but Supertonic’s narrower range is authoritative for this provider.
4. Call Supertonic engine:
   - `wav, duration = self._engine(request.text, style, total_step, speed)`
   - Assume `wav` shape `[B, T]`; for v1 we enforce `B == 1`:
     - `bsz = wav.shape[0]` and assert `bsz == 1`.
     - `trimmed = wav[0, : int(self.sample_rate * duration[0].item())]`.
5. Convert to output format:
   - If `trimmed` is float, normalize to int16:
     - `normalizer = AudioNormalizer()`
     - `audio_i16 = normalizer.normalize(trimmed, target_dtype=np.int16)`
   - Use `convert_audio_format` (inherited from `TTSAdapter`) to get final bytes:
     - `audio_bytes = await self.convert_audio_format(audio_i16, source_format=AudioFormat.PCM, target_format=request.format, sample_rate=self.sample_rate)`.
6. Build `TTSResponse`:

```python
return TTSResponse(
    audio_data=audio_bytes,
    format=request.format,
    sample_rate=self.sample_rate,
    channels=1,
    text_processed=request.text,
    voice_used=voice_id,
    provider=self.provider_name,
    model="supertonic",
)
```

**Text synthesis (pseudo‑streaming)**

If `request.stream` is `True`:

1. Generate the full `audio_bytes` as above.
2. Wrap bytes in an async generator, following the pattern in `KokoroAdapter`:

```python
chunk_size = self.config.get("stream_chunk_size", 8192)

async def _byte_stream():
    for i in range(0, len(audio_bytes), chunk_size):
        chunk = audio_bytes[i:i + chunk_size]
        if chunk:
            yield chunk
```

3. Return `TTSResponse(audio_stream=_byte_stream(), ...)` instead of `audio_data`.

This provides streaming semantics at the API level with a higher TTFB than true incremental engines; it is explicitly non‑incremental and will feel similar to Kokoro’s ONNX backend rather than NeuTTS GGUF streaming.

**Engine concurrency**

- Protect calls into `self._engine` with an `asyncio.Lock` (per‑adapter) to avoid concurrent use of a potentially non‑thread‑safe engine object:
  - Add `self._engine_lock = asyncio.Lock()` in `__init__`.
  - Wrap calls to `self._engine(...)` (and, in the future, `self._engine.batch(...)`) inside `async with self._engine_lock:`.

**Batch vs long‑form**

- v1 will **always** use the non‑batch Supertonic API for requests (single `(text, voice)` pair), even for long‑form text.
- Long‑form handling relies on Supertonic’s own automatic text chunking in non‑batch mode.
- The `batch()` entry point is reserved for a future enhancement (e.g., multi‑voice or bulk generation) and will require separate design.

### 4.3 Configuration

**TTS YAML config (`tts_providers_config.yaml`)**

Add a `supertonic` provider section with fixed voice‑id→filename mapping:

```yaml
providers:
  supertonic:
    enabled: true
    model_path: "models/supertonic/onnx"        # maps to onnx_dir
    sample_rate: 24000                          # optional override; default to engine.sample_rate
    device: "cpu"                               # placeholder for future GPU support
    extra_params:
      voice_styles_dir: "models/supertonic/voice_styles"
      default_voice: "supertonic_m1"
      voice_files:
        supertonic_m1: "M1.json"
        supertonic_f1: "F1.json"
      default_total_step: 5
      default_speed: 1.05
      n_test: 1
```

**Adapter config resolution**

In `SupertonicOnnxAdapter.__init__(config)`:

- `self.onnx_dir = config.get("model_path", "models/supertonic/onnx")`
- `extras = config.get("extra_params", {}) or {}`
- `self.voice_styles_dir = extras.get("voice_styles_dir", "models/supertonic/voice_styles")`
- `self.default_voice = extras.get("default_voice", "supertonic_m1")`
- `self.voice_files = extras.get("voice_files", {})  # mapping: voice_id -> filename`
- `self.default_total_step = int(extras.get("default_total_step", 5))`
- `self.default_speed = float(extras.get("default_speed", 1.05))`
- `self.n_test = int(extras.get("n_test", 1))  # always treat as 1 in v1`

**Provider priority**

Users may add `supertonic` to `provider_priority`:

```yaml
provider_priority:
  - openai
  - kokoro
  - supertonic
```

`TTSAdapterRegistry` already filters this list to enabled providers.

### 4.4 Licensing & Model Acquisition

- **Licensing**: The project does **not** bundle Supertonic models or voice styles.
  - Users are responsible for:
    - Accepting upstream licensing / terms.
    - Downloading and placing ONNX models and voice styles into the configured paths.
- **Installer script (helper)**:
  - Add `Helper_Scripts/TTS_Installers/install_tts_supertonic.py` (future PR) that:
    - Prompts the user with clear licensing information and setup instructions.
    - Guides the user to run the upstream install commands *or* place ONNX models and voice styles manually into the recommended directories.
    - Optionally verifies that required files exist under `models/supertonic/onnx/` and `models/supertonic/voice_styles/`.
    - Optionally writes a minimal `supertonic` block into `tts_providers_config.yaml` if absent.
  - The installer should *not* run automatically; users must opt in.

### 4.5 Validation & Provider Limits

**ProviderLimits (`tts_validation.py`)**

Add limits for `supertonic`:

```python
"supertonic": {
    "max_text_length": 15000,
    "languages": ["en"],
    "valid_formats": {"mp3", "wav"},
    "min_speed": 0.9,
    "max_speed": 1.5,
}
```

**TTSInputValidator (`tts_validation.py`)**

- `MAX_TEXT_LENGTHS["supertonic"] = 15000`
- `SUPPORTED_LANGUAGES["supertonic"] = {"en"}`
- `SUPPORTED_FORMATS["supertonic"] = {AudioFormat.MP3, AudioFormat.WAV}`

The `valid_formats` entry in `ProviderLimits` and the `SUPPORTED_FORMATS["supertonic"]` set MUST remain in sync (and match the formats actually supported via `convert_audio_format`) to avoid inconsistent validation behavior.

Behavior:

- If text exceeds `max_text_length`, raise `TTSTextTooLongError`.
- If `response_format` is not in `{mp3, wav}`, raise `TTSUnsupportedFormatError`.
- `speed`:
  - For `supertonic`, we **enforce** `speed ∈ [0.9, 1.5]` via `ProviderLimits`.
  - If the original requested speed is outside this range, validation fails with `TTSInvalidInputError` (HTTP 400); the adapter is never called for such requests.

### 4.6 Capabilities & Voice Catalog

**get_capabilities()**

`SupertonicOnnxAdapter.get_capabilities()` should return:

- `provider_name="Supertonic"`
- `supported_languages={"en"}`
- `supported_voices=[VoiceInfo(...), ...]` for each voice style mapping.
- `supported_formats={AudioFormat.MP3, AudioFormat.WAV}` (extend only after testing).
- `max_text_length=15000`
- `supports_streaming=True` (pseudo).
- `supports_voice_cloning=False`
- `supports_speech_rate=True`
- All other capability flags `False`, unless we explicitly support them.
- `latency_ms ~ 3500` on CPU as an initial estimate (adjust after measurement).
- `sample_rate=self.sample_rate`
- `default_format=AudioFormat.WAV`

**VoiceInfo entries**

Example voice mapping:

```python
VoiceInfo(
    id="supertonic_m1",
    name="Supertonic Male 1",
    gender="male",
    language="en",
    description="Default Supertonic male voice style",
    styles=["neutral"],
    use_case=["general"]
)
```

These feed into:

- `TTSServiceV2.get_capabilities()` → provider capabilities map
- `TTSServiceV2.list_voices()` → `/api/v1/audio/voices/catalog`

If a configured **non‑default** voice style JSON is missing, skip that voice and log a warning. If the default voice is missing, treat this as an initialization error and fail adapter startup.

### 4.7 API Integration (OpenAI /audio/speech)

**Model routing**

- In `TTSAdapterFactory.MODEL_PROVIDER_MAP`:

```python
"tts-supertonic-1": TTSProvider.SUPERTONIC,   # canonical
"supertonic": TTSProvider.SUPERTONIC,         # alias
"supertonic-onnx": TTSProvider.SUPERTONIC,    # alias
```

**Provider hinting for validation**

- In `_infer_tts_provider_from_model` (`api/v1/endpoints/audio.py`):

```python
if m.startswith("supertonic") or m.startswith("tts-supertonic"):
    return "supertonic"
```

**OpenAISpeechRequest mapping**

`TTSServiceV2._convert_request()` already maps:

- `input` → `TTSRequest.text`
- `voice` → `TTSRequest.voice`
- `response_format` → `TTSRequest.format`
- `speed` → `TTSRequest.speed`
- `stream` → `TTSRequest.stream`
- `extra_params` → `TTSRequest.extra_params`

For Supertonic:

- `request.model` is preserved for metrics and adapter selection.
- `extra_params.total_step` should be honored by `SupertonicOnnxAdapter`.

## 5. Non‑Functional Requirements

### 5.1 Performance & Resource Use

- **CPU‑first**:
  - Implementation assumes CPU as the baseline.
  - `device` / `use_gpu` flags are read but can log “GPU not yet supported” as needed.
- **Initialization**:
  - Lazy: load Supertonic models on first adapter use, not at process startup.
  - Respect the existing `tts_resource_manager` memory checks:
    - The registry already skips adapter initialization if memory is critical.
- **Streaming**:
  - Provide stable pseudo‑streaming:
    - TTFB = full synthesis time + first encoding chunk.
    - Subsequent chunks stream out at network speed.
     - Expect TTFB behavior to be closer to Kokoro’s ONNX backend than to NeuTTS GGUF streaming (which can emit earlier, smaller chunks).

### 5.2 Reliability & Error Handling

- Initialization failures:
  - Missing ONNX dir → `TTSModelNotFoundError` with details (path).
  - Bad model or import → `TTSModelLoadError` with context.
  - The registry logs and marks provider as failed with optional retry window.
- Generation failures:
  - Errors in `self._engine(...)` → `TTSGenerationError`.
  - Empty or invalid audio → treat as a generation error; allow fallback if enabled.
- Integration with `TTSServiceV2`:
  - All failures flow through the existing metrics and fallback machinery.

### 5.4 Logging & Observability

- The adapter should log, at minimum:
  - On initialization:
    - Resolved `onnx_dir` and `voice_styles_dir`.
    - Loaded voices (voice ids and mapped filenames).
  - Per request (at info or debug level):
    - Provider name, voice id, text length, `speed`, `total_step`, and target format.
    - Any validation or engine errors before they propagate to `TTSServiceV2`.

### 5.3 Security

- No network calls for Supertonic; inference is entirely local.
- Path handling:
  - Voice style & ONNX paths come from config, not request bodies.
  - Reject obvious directory traversal from misconfigured paths (e.g., `..`) if we derive anything dynamically.
- No special authentication logic; reuse existing endpoint auth (Bearer/JWT).

## 6. Configuration & Deployment

### 6.1 File Layout (Recommended)

- `models/supertonic/onnx/` — user‑supplied ONNX models.
- `models/supertonic/voice_styles/` — user‑supplied style JSONs (`M1.json`, `F1.json`, etc.).
- `Docs/STT-TTS/` — can host a brief “Supertonic Setup Guide” pointing back to this PRD and installer usage.

### 6.2 Installer Script (Helper)

**File**: `Helper_Scripts/TTS_Installers/install_tts_supertonic.py` (future work)

- Behavior:
  - Confirm user intent (e.g., “This will download Supertonic assets per upstream license. Continue?”).
  - Acquire assets according to upstream docs (git clone, download, or manual instructions).
  - Place ONNX models and voice styles into the recommended layout.
  - Optionally:
    - Create `models/supertonic/` directories if missing.
    - Patch or create a `supertonic` section in `tts_providers_config.yaml` if safe to do so.

The core TTS integration should not depend on this script; it’s a convenience tool only.

## 7. Testing & Validation

### 7.1 Unit Tests

**Location**: `tldw_Server_API/tests/TTS/adapters/test_supertonic_adapter.py`

Scenarios:

- `initialize()`:
  - Happy path with mocked `load_text_to_speech` and `load_voice_style`.
  - Missing ONNX dir: raises `TTSModelNotFoundError`.
  - Missing voice style dir or file: logs warning and continues (or fails fast if default voice missing).
- `get_capabilities()`:
  - Returns expected provider name, formats, languages, voices, sample rate.
- `generate()`:
  - Normal text returns non‑empty `audio_data`.
  - Honors `extra_params.total_step`.
  - Clamps extreme `speed` values and logs.
  - Handles both `WAV` and `MP3` targets (if supported).

### 7.2 Integration Tests

**Location**: existing TTS test suites (`tldw_Server_API/tests/TTS/`, `tldw_Server_API/tests/TTS_NEW/`), adding Supertonic‑specific cases:

- `/api/v1/audio/speech` with:
  - `model: "supertonic"`, `voice: "supertonic_m1"`, short input → non‑empty bytes.
  - `stream: true` → streaming yields at least one audio chunk.
- `GET /api/v1/audio/voices/catalog`:
  - When `supertonic` enabled and assets present, response includes Supertonic voices under `provider="supertonic"`.

### 7.3 Manual QA

- With real assets installed:
  - Synthesize short and long texts via WebUI and curl.
  - Vary `speed` and `total_step` and subjectively evaluate quality vs latency.
  - Confirm behavior when assets are missing or misconfigured:
    - Supertonic disabled at runtime; fallback kicks in if configured.

## 8. Risks & Open Questions

- **Model licensing & redistribution**
  - Resolved direction: users supply models; project provides integration only.
  - Installer script must clearly state license boundaries and not silently assume distribution rights.
- **GPU support**
  - Direction: CPU‑first design; `device` / `use_gpu` are read but may be no‑ops until upstream GPU support is stable.
  - Future enhancement: add a GPU code path when upstream docs & tests confirm it’s safe and beneficial.
- **Batch support**
  - Direction: v1 focuses on single text per API request.
  - Upstream `batch()` support is reserved for a future enhancement (e.g., multi‑segment TTS or bulk generation).
  - Adapter should be designed so adding a `generate_batch()` style path later is straightforward.

Once this PRD is accepted, the next step is to draft an implementation plan (staged, test‑driven) and then add the `SupertonicOnnxAdapter`, registry entries, validation hooks, and optional installer script as separate, small PRs.
