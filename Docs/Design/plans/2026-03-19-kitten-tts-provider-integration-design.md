# KittenTTS Provider Integration Design

Date: 2026-03-19
Status: Approved for implementation planning
Owner: Codex + user collaboration

## 1. Goal

Add first-class local `kitten_tts` support to the existing TTS stack so it works through the current OpenAI-compatible speech endpoint, provider routing, voice catalog, storage/history flows, and setup provisioning flow.

This integration must also incorporate the behavior from KittenTTS upstream PR #25:

- remove the `misaki` dependency assumption,
- rely on the `phonemizer` stack directly,
- initialize eSpeak paths explicitly via `espeakng_loader`.

## 2. Confirmed Scope Decisions

Validated with the user:

1. Ship `kitten_tts` as a first-class optional local provider, not a hidden compatibility shim.
2. Surface it in setup/WebUI so users can provision and select it like other TTS engines.
3. Support model download on first use when auto-download is enabled.
4. Implement the PR #25 fixes as part of this work rather than waiting for upstream release packaging.
5. Keep curated setup bundles on Kokoro for now; add KittenTTS to the advanced engine picker and provisioning path first.

## 3. Approaches Considered

## Approach A: Direct adapter around the released `kittentts` package

- Add a normal adapter that imports `kittentts.KittenTTS`.
- Add optional dependencies for the package and expose it in routing.

Pros:

- Lowest code volume.
- Closest to the upstream public API.

Cons:

- Does not reliably satisfy the requested PR #25 fixes today because upstream `main` still imports `misaki` and still packages the older dependency shape.
- Leaves this repo exposed to upstream packaging churn for a core runtime path.

## Approach B (Recommended): Native provider + local compatibility runtime

- Add a normal `kitten_tts` provider to the registry.
- Implement a small local runtime helper that uses the upstream model asset format (`config.json`, ONNX model, voices file) but performs the PR #25 eSpeak/phonemizer initialization itself.
- Keep the adapter interface fully native to `tldw_server`.

Pros:

- Meets the user’s PR #25 requirement immediately.
- Keeps provider behavior aligned with existing local TTS adapters.
- Avoids pinning this project to an unreleased upstream commit or a broken dependency set.

Cons:

- Slightly more code than a thin wrapper.
- Requires maintaining a small compatibility layer until upstream packaging stabilizes.

## Approach C: External KittenTTS sidecar service

- Run KittenTTS as a separate local HTTP server and call it from `tldw_server`.

Pros:

- Strong dependency isolation.

Cons:

- Breaks the current in-process local-provider pattern.
- Adds process-management, health, and setup complexity for no clear product win.

Decision: Approach B.

## 4. Reviewed Risks and Design Adjustments

The original design was adjusted after a repo-level review:

1. The request `model` field is used for provider routing in this stack, not just provider-specific model selection.
   - `model="KittenML/kitten-tts-nano-0.8"` must explicitly map to `kitten_tts` in the TTS model registry.

2. The released upstream `kittentts` package is not yet a safe source of truth for the requested PR #25 behavior.
   - The repo must not depend on the upstream import path alone for correctness.

3. `/api/v1/audio/voices/catalog` must not trigger model downloads.
   - KittenTTS voices should be statically declared in adapter capabilities.

4. Setup integration is not just UI text.
   - `install_schema.py`, `install_manager.py`, and the setup engine picker must all be updated together.

5. This change should not add another legacy `default_<provider>_tts_model` config key to `config.txt`.
   - Use `providers.kitten_tts.model` in `tts_providers_config.yaml` as the canonical model selection.

## 5. Architecture

## 5.1 Provider Registration and Routing

Add `kitten_tts` as a new `TTSProvider` and register a new adapter:

- `tldw_Server_API.app.core.TTS.adapters.kitten_tts_adapter.KittenTTSAdapter`

Routing updates:

- Add provider aliases for `kitten_tts`, `kitten-tts`, and `kittentts`.
- Add `MODEL_PROVIDER_MAP` entries for:
  - `kitten_tts`
  - `kitten-tts`
  - `kittentts`
  - `KittenML/kitten-tts-mini-0.8`
  - `KittenML/kitten-tts-micro-0.8`
  - `KittenML/kitten-tts-nano-0.8`
  - `KittenML/kitten-tts-nano-0.8-int8`

This keeps both of these valid:

- `model="kitten_tts"`
- `model="KittenML/kitten-tts-nano-0.8"`

The concrete repo ID used for downloads remains configurable under `providers.kitten_tts.model`.

## 5.2 Configuration Model

Add a new provider entry in `tts_providers_config.yaml`:

```yaml
kitten_tts:
  enabled: false
  model: "KittenML/kitten-tts-nano-0.8"
  cache_dir: "cache/kitten_tts"
  device: "cpu"
  sample_rate: 24000
  auto_download: true
  extra_params:
    clean_text: false
```

Global config plumbing must also include `kitten_tts` anywhere this repo fans out local-provider defaults:

- `local_device`
- `auto_download_local_models`
- provider-specific auto-download flags if supported

No new `config.txt` legacy default key is required for model selection.

## 5.3 Local Compatibility Runtime

Add a small helper module under the TTS vendor/runtime layer, for example:

- `tldw_Server_API/app/core/TTS/vendors/kittentts_compat.py`

Responsibilities:

1. Resolve the configured Hugging Face repo ID.
2. Download `config.json`, the ONNX model file, and the voice embeddings file through `huggingface_hub`.
3. Initialize eSpeak paths exactly once via:
   - `espeakng_loader.get_library_path()`
   - `espeakng_loader.get_data_path()`
   - `phonemizer.backend.espeak.wrapper.EspeakWrapper`
4. Build the phonemizer backend without relying on `misaki`.
5. Load the ONNX session and voice embeddings.
6. Expose a small runtime API for:
   - `available_voices()`
   - `generate(text, voice, speed, clean_text)`

This helper should use the upstream asset contract, not the upstream package import path, so the requested PR #25 behavior is under this repo’s control.

## 5.4 Adapter Behavior

`KittenTTSAdapter` should:

- declare `PROVIDER_KEY = "kitten_tts"`,
- expose static built-in voices in capabilities,
- support `wav`, `mp3`, `opus`, `flac`, and `pcm` output through the existing audio writer/conversion path,
- default to 24 kHz sample rate,
- validate voice names against the built-in Kitten voice set,
- accept both display-name voices (`Bella`, `Jasper`, etc.) and normalized lowercase aliases,
- keep service-level chunking enabled by supporting PCM output instead of reimplementing the entire chunk pipeline locally.

Voice catalog should list the user-facing names:

- Bella
- Jasper
- Luna
- Bruno
- Rosie
- Hugo
- Kiki
- Leo

## 5.5 Endpoint and Service Flow

1. `POST /api/v1/audio/speech` receives an existing `OpenAISpeechRequest`.
2. `TTSServiceV2` resolves the provider from either:
   - explicit provider override,
   - `request.model`,
   - default provider.
3. `KittenTTSAdapter.initialize()` validates dependencies and prepares static capabilities.
4. On first synthesis, the adapter loads or downloads the configured Kitten model assets into the local cache.
5. The adapter generates float audio via the local compatibility runtime.
6. The adapter converts/streams audio with the existing `StreamingAudioWriter` / normalizer path used by other local providers.
7. `GET /api/v1/audio/voices/catalog` returns Kitten voices without requiring model download.

## 5.6 Setup and Provisioning

Add KittenTTS to the advanced setup engine picker and provisioning path, but do not replace Kokoro in curated bundles.

Required setup changes:

- add `kitten_tts` to the allowed TTS engine schema,
- add KittenTTS dependency installation requirements,
- add a `_install_kitten_tts()` asset/bootstrap step,
- add a setup card in `setup.js`.

Because KittenTTS also needs eSpeak/phonemizer support, setup copy should clearly state that eSpeak NG is still required.

## 6. Dependency Strategy

Use direct dependencies needed for the compatibility runtime instead of depending on the released upstream `kittentts` package for correctness.

Expected optional dependency group:

- `huggingface_hub`
- `numpy`
- `onnxruntime`
- `soundfile`
- `phonemizer-fork`
- `espeakng_loader`
- `num2words`
- `spacy`

Import behavior remains `import phonemizer`, since `phonemizer-fork` provides that package namespace.

## 7. Error Handling

Errors should align with existing TTS provider behavior:

- Missing Python dependencies:
  - `TTSProviderNotConfiguredError`
  - detail should name the missing module(s)

- Missing model assets with `auto_download=false`:
  - `TTSModelNotFoundError`
  - include configured repo/model path and remediation guidance

- Missing or unusable eSpeak runtime:
  - `TTSProviderInitializationError` or `TTSModelLoadError`
  - include whether library path or data path resolution failed

- Unknown voice:
  - `TTSInvalidVoiceReferenceError` or equivalent invalid-voice path used by the TTS service

- Unsupported format/language:
  - stay within the normal capability-validation path

## 8. Test Strategy

Add targeted tests only; avoid live model-download tests in the default suite.

### Unit Tests

- compatibility runtime:
  - repo/config file resolution
  - PR #25 eSpeak initialization hook
  - voice alias mapping

- adapter:
  - initialization without download
  - static capabilities and voice catalog
  - generation in streaming and non-streaming modes using mocked runtime output
  - invalid voice handling

- routing/config:
  - provider alias resolution
  - `MODEL_PROVIDER_MAP` entries for HF repo IDs
  - local-device / auto-download fanout includes `kitten_tts`

### Endpoint/Service Tests

- `/api/v1/audio/speech` with `model="kitten_tts"`
- `/api/v1/audio/speech` with `model="KittenML/kitten-tts-nano-0.8"`
- `/api/v1/audio/voices/catalog?provider=kitten_tts`

### Setup Tests

- setup schema accepts `kitten_tts`
- install manager dependencies/install routine include `kitten_tts`
- setup JS source includes a KittenTTS engine card

### Verification Gates

- targeted pytest for touched areas,
- Bandit on touched backend paths before completion.

## 9. Non-Goals

This change does not include:

- replacing Kokoro as the recommended curated audio bundle,
- adding a new legacy `default_kitten_tts_model` config.txt key,
- live upstream sync or auto-discovery of future Kitten models,
- a separate KittenTTS HTTP microservice.

## 10. Rollout Notes

Recommended rollout order:

1. Ship backend adapter + routing + tests.
2. Ship setup provisioning support.
3. Add docs for install prerequisites and configuration.
4. Revisit whether KittenTTS should appear in curated audio bundles after real usage validation.
