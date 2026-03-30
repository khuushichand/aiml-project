# PocketTTS.cpp Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `pocket_tts_cpp` as a separate local TTS provider that supports direct `voice_reference` inputs, stored `custom:<voice_id>` voices, non-streaming CLI generation, and streaming with a gated loopback-server fallback when CLI stdout is not truly incremental.

**Architecture:** Keep `pocket_tts` unchanged and add a new `pocket_tts_cpp` adapter plus a provider-specific runtime helper. Resolve stored and direct reference audio into deterministic user-scoped files under `Databases/user_databases/<user_id>/voices/providers/pocket_tts_cpp/`, prune that cache locally with TTL and max-bytes rules, and exclude that runtime subtree from uploaded-voice quota accounting. Use the CLI path for non-streaming, probe CLI streaming explicitly, and allow an adapter-owned loopback-only PocketTTS.cpp server fallback for streaming only when the CLI cannot provide true incremental output.

**Tech Stack:** Python 3, FastAPI, Pydantic, Loguru, asyncio subprocess/process management, existing TTS adapter stack, pytest, Bandit

## Implementation Amendment (2026-03-26)

The branch implementation deliberately narrowed the streaming scope before merge: v1 keeps the CLI probe, allows explicit streaming only when that probe succeeds on the local install, and otherwise fails closed. The adapter therefore does not advertise streaming capability for automatic provider selection yet. The loopback-only fallback server remains a deferred follow-up instead of a shipped requirement for this branch.

---

## File Map

- Modify: `tldw_Server_API/app/core/TTS/adapter_registry.py`
  Responsibility: add `TTSProvider.POCKET_TTS_CPP`, model/provider aliases, default adapter mapping, and provider info exposure without changing `pocket_tts`.
- Modify: `tldw_Server_API/app/core/TTS/tts_config.py`
  Responsibility: preserve PocketTTS.cpp-specific config fields such as `binary_path`, `tokenizer_path`, `enable_voice_cache`, `cache_ttl_hours`, `cache_max_bytes_per_user`, `persist_direct_voice_references`, and streaming probe/server timeouts through config load and `to_dict()`.
- Modify: `tldw_Server_API/app/core/TTS/tts_validation.py`
  Responsibility: add `pocket_tts_cpp` limits and validation so the provider requires either `voice_reference` or `voice="custom:<voice_id>"` while keeping current providers unchanged.
- Modify: `tldw_Server_API/app/core/TTS/voice_manager.py`
  Responsibility: add `pocket_tts_cpp` provider requirements, keep the provider runtime subtree out of the visible voice catalog, and exclude `voices/providers/` runtime artifacts from uploaded-voice quota checks.
- Create: `tldw_Server_API/app/core/TTS/adapters/pocket_tts_cpp_runtime.py`
  Responsibility: own deterministic provider paths, WAV normalization, direct-reference hashing, cache pruning, CLI command construction, streaming probe helpers, and loopback server lifecycle coordination.
- Create: `tldw_Server_API/app/core/TTS/adapters/pocket_tts_cpp_adapter.py`
  Responsibility: implement PocketTTS.cpp initialization, non-streaming synthesis, streaming synthesis, CLI/stdout handling, fallback server transport, and output-format conversion.
- Modify: `tldw_Server_API/app/core/TTS/tts_service_v2.py`
  Responsibility: resolve `custom:<voice_id>` and direct `voice_reference` inputs into PocketTTS.cpp provider-managed files before adapter execution, while preserving current behavior for other providers.
- Modify: `tldw_Server_API/Config_Files/tts_providers_config.yaml`
  Responsibility: add a disabled-by-default `pocket_tts_cpp` block, voice-mapping `clone_required` placeholders, and supported output formats.
- Create: `tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_registry.py`
  Responsibility: prove model aliases, config round-trip, and provider registration work.
- Create: `tldw_Server_API/tests/TTS_NEW/unit/test_tts_validation_pocket_tts_cpp.py`
  Responsibility: cover PocketTTS.cpp-specific validation for clone-required inputs and allowed formats.
- Create: `tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_runtime.py`
  Responsibility: cover deterministic path materialization, cache pruning, and quota-exclusion logic.
- Create: `tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_service.py`
  Responsibility: cover `TTSServiceV2` plumbing for `custom:<voice_id>` and direct `voice_reference` requests targeting `pocket_tts_cpp`.
- Modify: `tldw_Server_API/tests/TTS_NEW/integration/test_custom_voice_resolution.py`
  Responsibility: prove the route-level custom-voice flow injects PocketTTS.cpp provider-managed paths rather than relying on random temp files.
- Create: `tldw_Server_API/tests/TTS/adapters/test_pocket_tts_cpp_adapter_mock.py`
  Responsibility: unit-test CLI command building, subprocess handling, non-streaming generation, streaming probe behavior, and server fallback using mocks.
- Create: `tldw_Server_API/tests/TTS/adapters/test_pocket_tts_cpp_adapter_integration.py`
  Responsibility: add an opt-in runtime-gated integration test that exercises the real binary when assets are present.
- Modify: `tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py`
  Responsibility: verify `/api/v1/audio/speech` streams and non-streams correctly for `pocket_tts_cpp` through the public API path.
- Create: `Helper_Scripts/TTS_Installers/install_tts_pocket_tts_cpp.py`
  Responsibility: check toolchain prerequisites, clone/build/export PocketTTS.cpp into repo-local paths, and patch `tts_providers_config.yaml`.
- Create: `tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_installer.py`
  Responsibility: cover installer config-patch and runtime-layout helper functions without needing network or a compiler.
- Modify: `README.md`
  Responsibility: list `pocket_tts_cpp` as a separate provider from `pocket_tts`.
- Modify: `Docs/API-related/TTS_API.md`
  Responsibility: document `pocket_tts_cpp` request expectations, especially clone-required behavior and streaming caveats.
- Modify: `Docs/Getting_Started/First_Time_Audio_Setup_CPU.md`
  Responsibility: explain when to choose `pocket_tts` versus `pocket_tts_cpp`.
- Modify: `Docs/Getting_Started/First_Time_Audio_Setup_GPU_Accelerated.md`
  Responsibility: explain the same provider split for GPU-accelerated setups.
- Modify: `Docs/User_Guides/WebUI_Extension/PocketTTS_Voice_Cloning_Guide.md`
  Responsibility: distinguish ONNX `pocket_tts` from compiled-binary `pocket_tts_cpp` and show the installer path.

## Implementation Notes

- Keep `providers.pocket_tts_cpp.enabled: false` until the adapter, streaming support, and installer land. Early tasks must not expose a half-working provider by default.
- Use `model_path` for the PocketTTS.cpp exported ONNX directory and add explicit `binary_path` plus `tokenizer_path` fields in `ProviderConfig`. Keep all remaining PocketTTS.cpp tuning knobs under `extra_params` unless they are needed for config round-trip or startup validation.
- Choose the simpler quota policy from the approved spec: exclude `voices/providers/pocket_tts_cpp/` from uploaded-voice quota accounting in `voice_manager.py`, and manage runtime cache size with provider-local TTL/max-bytes pruning in `pocket_tts_cpp_runtime.py`.
- Do not register PocketTTS.cpp runtime artifacts in `generated_files`. They are operational cache files, not uploaded voices and not user-download artifacts.
- Internal request plumbing should use explicit keys such as `extra_params["pocket_tts_cpp_voice_path"]` and `extra_params["pocket_tts_cpp_reference_text"]`; keep those keys internal and do not surface them in public API docs as user inputs.
- When `persist_direct_voice_references` is `false`, direct-reference materializations must be request-scoped and removed immediately after generation. Tests should prove both the persistent and transient paths.
- The runtime helper should own cache pruning and server-process cleanup. Do not extend `storage_cleanup_service.py` unless provider-local cleanup proves insufficient.
- The streaming fallback server must bind to `127.0.0.1` only, request an ephemeral port, and serialize startup so concurrent requests do not race.
- Do not edit `Docs/Published/*` in this plan. Update the source docs only.

### Task 1: Add Registry, Config, And Validation Scaffolding

**Files:**
- Modify: `tldw_Server_API/app/core/TTS/adapter_registry.py`
- Modify: `tldw_Server_API/app/core/TTS/tts_config.py`
- Modify: `tldw_Server_API/app/core/TTS/tts_validation.py`
- Modify: `tldw_Server_API/Config_Files/tts_providers_config.yaml`
- Test: `tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_registry.py`
- Test: `tldw_Server_API/tests/TTS_NEW/unit/test_tts_validation_pocket_tts_cpp.py`

- [ ] **Step 1: Write the failing registry, config-round-trip, and validation tests**

Add focused tests that prove:

- `TTSAdapterFactory.get_provider_for_model("pocket_tts_cpp")` resolves to the new provider
- dashed aliases such as `"pocket-tts-cpp"` resolve to the same provider
- `TTSConfigManager.to_dict()` preserves `binary_path`, `tokenizer_path`, `enable_voice_cache`, `cache_ttl_hours`, `cache_max_bytes_per_user`, and `persist_direct_voice_references`
- `validate_tts_request()` accepts `voice="custom:voice-1"` for `pocket_tts_cpp`
- `validate_tts_request()` rejects PocketTTS.cpp requests that supply neither a direct `voice_reference` nor a stored `custom:` voice

- [ ] **Step 2: Run the focused tests to verify the current code fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest -q \
  tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_registry.py \
  tldw_Server_API/tests/TTS_NEW/unit/test_tts_validation_pocket_tts_cpp.py
```

Expected:

- FAIL because `TTSProvider.POCKET_TTS_CPP` does not exist yet
- FAIL because `ProviderConfig` currently drops PocketTTS.cpp-specific fields
- FAIL because PocketTTS.cpp-specific clone validation does not exist yet

- [ ] **Step 3: Implement the minimal registry/config scaffold**

Make the smallest change set that satisfies the new tests:

- add `TTSProvider.POCKET_TTS_CPP`
- add the provider alias tokens and model mapping entries
- register a lazy default adapter path pointing at `pocket_tts_cpp_adapter.py`
- extend `ProviderConfig` with only the explicit fields needed for PocketTTS.cpp startup and cache policy
- add `ProviderLimits` / validation entries for `pocket_tts_cpp`
- add a disabled-by-default `pocket_tts_cpp` block to `tts_providers_config.yaml`
- add `pocket_tts_cpp` to the clone-required voice-mapping placeholders and supported-format tables

Guardrails:

- leave `pocket_tts` behavior unchanged
- keep `pocket_tts_cpp` disabled by default
- do not claim streaming support in docs or capability overrides until Task 4 lands

- [ ] **Step 4: Re-run the focused tests**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest -q \
  tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_registry.py \
  tldw_Server_API/tests/TTS_NEW/unit/test_tts_validation_pocket_tts_cpp.py \
  tldw_Server_API/tests/TTS/test_tts_validation.py -k pocket_tts
```

Expected:

- PASS for the new PocketTTS.cpp tests
- PASS for the existing PocketTTS validation coverage

- [ ] **Step 5: Commit the scaffold slice**

```bash
git add \
  tldw_Server_API/app/core/TTS/adapter_registry.py \
  tldw_Server_API/app/core/TTS/tts_config.py \
  tldw_Server_API/app/core/TTS/tts_validation.py \
  tldw_Server_API/Config_Files/tts_providers_config.yaml \
  tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_registry.py \
  tldw_Server_API/tests/TTS_NEW/unit/test_tts_validation_pocket_tts_cpp.py
git commit -m "feat(tts): add pocket_tts_cpp registry scaffold"
```

### Task 2: Add Stable Voice Materialization And Cache Policy Plumbing

**Files:**
- Create: `tldw_Server_API/app/core/TTS/adapters/pocket_tts_cpp_runtime.py`
- Modify: `tldw_Server_API/app/core/TTS/tts_service_v2.py`
- Modify: `tldw_Server_API/app/core/TTS/voice_manager.py`
- Test: `tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_runtime.py`
- Test: `tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_service.py`
- Modify: `tldw_Server_API/tests/TTS_NEW/integration/test_custom_voice_resolution.py`

- [ ] **Step 1: Write the failing runtime and service-plumbing tests**

Add tests that prove:

- stored voices materialize to `voices/providers/pocket_tts_cpp/custom_<voice_id>.wav`
- cached direct references materialize to deterministic `ref_<sha256>.wav` paths
- transient direct references are deleted when `persist_direct_voice_references` is disabled
- provider cache pruning removes expired or oversize files inside `voices/providers/pocket_tts_cpp/`
- `voice_manager` uploaded-voice quota checks ignore the `voices/providers/` subtree
- `TTSServiceV2` injects `extra_params["pocket_tts_cpp_voice_path"]` for both `custom:<voice_id>` and direct `voice_reference` requests
- the existing route-level custom-voice integration test can assert PocketTTS.cpp receives a stable path plus reference text

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest -q \
  tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_runtime.py \
  tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_service.py \
  tldw_Server_API/tests/TTS_NEW/integration/test_custom_voice_resolution.py -k pocket_tts_cpp
```

Expected:

- FAIL because no PocketTTS.cpp runtime helper exists yet
- FAIL because `TTSServiceV2` only loads bytes for `custom:` voices and does not materialize provider-managed paths
- FAIL because uploaded-voice quota currently counts all files under the user voices tree

- [ ] **Step 3: Implement the minimal runtime helper and service changes**

Implement the smallest change set that satisfies the tests:

- create `pocket_tts_cpp_runtime.py` with helpers for:
  - user-scoped runtime directory resolution
  - deterministic custom-voice materialization
  - deterministic direct-reference materialization
  - provider-local cache pruning by TTL and max bytes
  - temporary-file cleanup for non-persistent direct references
- update `tts_service_v2.py` so PocketTTS.cpp requests get provider-managed path injection before adapter execution
- keep existing provider-artifact loading for other providers unchanged
- add `pocket_tts_cpp` to `voice_manager.PROVIDER_REQUIREMENTS`
- exclude `voices/providers/` from uploaded-voice quota accounting in `voice_manager.py`

Guardrails:

- do not add provider runtime files to the visible voice list
- do not persist direct references when caching is disabled
- do not reach into private voice-manager internals from the adapter

- [ ] **Step 4: Re-run the runtime and service-plumbing tests**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest -q \
  tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_runtime.py \
  tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_service.py \
  tldw_Server_API/tests/TTS_NEW/integration/test_custom_voice_resolution.py -k pocket_tts_cpp
```

Expected:

- PASS for the new PocketTTS.cpp runtime and service tests
- PASS for the route-level PocketTTS.cpp custom-voice coverage

- [ ] **Step 5: Commit the materialization slice**

```bash
git add \
  tldw_Server_API/app/core/TTS/adapters/pocket_tts_cpp_runtime.py \
  tldw_Server_API/app/core/TTS/tts_service_v2.py \
  tldw_Server_API/app/core/TTS/voice_manager.py \
  tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_runtime.py \
  tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_service.py \
  tldw_Server_API/tests/TTS_NEW/integration/test_custom_voice_resolution.py
git commit -m "feat(tts): add pocket_tts_cpp voice materialization"
```

### Task 3: Implement The Non-Streaming CLI Adapter

**Files:**
- Create: `tldw_Server_API/app/core/TTS/adapters/pocket_tts_cpp_adapter.py`
- Modify: `tldw_Server_API/app/core/TTS/adapters/pocket_tts_cpp_runtime.py`
- Test: `tldw_Server_API/tests/TTS/adapters/test_pocket_tts_cpp_adapter_mock.py`
- Test: `tldw_Server_API/tests/TTS/adapters/test_pocket_tts_cpp_adapter_integration.py`

- [ ] **Step 1: Write the failing adapter tests for non-streaming behavior**

Add unit tests that prove:

- initialization fails when the PocketTTS.cpp binary, tokenizer, or exported ONNX assets are missing
- non-streaming generation uses `extra_params["pocket_tts_cpp_voice_path"]` instead of a random temp filename
- the adapter refuses requests without a usable direct or stored reference path
- stdout or file-based CLI output is normalized into the requested `wav`, `mp3`, `opus`, `flac`, `pcm`, or `aac` response format
- adapter metadata records whether stdout or file-output transport was used

Also add an opt-in integration test skeleton that:

- is skipped unless `RUN_TTS_CPP_INTEGRATION=1`
- looks for `bin/pocket-tts`, `models/pocket_tts_cpp/onnx`, and `models/pocket_tts_cpp/tokenizer.model`
- synthesizes a very short request with the sample voice file when assets are available

- [ ] **Step 2: Run the focused adapter tests to verify they fail**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest -q \
  tldw_Server_API/tests/TTS/adapters/test_pocket_tts_cpp_adapter_mock.py \
  tldw_Server_API/tests/TTS/adapters/test_pocket_tts_cpp_adapter_integration.py
```

Expected:

- FAIL because the PocketTTS.cpp adapter module does not exist yet
- SKIP or FAIL for the integration test depending on how the runtime gate is written

- [ ] **Step 3: Implement the minimal non-streaming adapter**

Implement the smallest change set that satisfies the new tests:

- parse `binary_path`, `model_path`, `tokenizer_path`, `timeout`, and probe-related config
- validate runtime assets during `initialize()`
- build the PocketTTS.cpp CLI command from the provider-managed voice path
- prefer stdout output when it is unambiguous for the requested format
- fall back to file output plus conversion when stdout is unsuitable
- return accurate `TTSResponse` metadata and declared capabilities

Guardrails:

- keep `supports_streaming=False` until Task 4 is finished
- do not duplicate audio conversion logic that already exists in the base adapter stack
- do not silently fall back to the Python `pocket_tts` runtime

- [ ] **Step 4: Re-run the adapter tests**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest -q \
  tldw_Server_API/tests/TTS/adapters/test_pocket_tts_cpp_adapter_mock.py \
  tldw_Server_API/tests/TTS/adapters/test_pocket_tts_cpp_adapter_integration.py \
  tldw_Server_API/tests/TTS/adapters/test_pocket_tts_adapter_mock.py
```

Expected:

- PASS for the new PocketTTS.cpp mock tests
- PASS or SKIP for the opt-in integration test
- PASS for the existing PocketTTS ONNX mock tests

- [ ] **Step 5: Commit the non-streaming adapter slice**

```bash
git add \
  tldw_Server_API/app/core/TTS/adapters/pocket_tts_cpp_adapter.py \
  tldw_Server_API/app/core/TTS/adapters/pocket_tts_cpp_runtime.py \
  tldw_Server_API/tests/TTS/adapters/test_pocket_tts_cpp_adapter_mock.py \
  tldw_Server_API/tests/TTS/adapters/test_pocket_tts_cpp_adapter_integration.py
git commit -m "feat(tts): add pocket_tts_cpp cli adapter"
```

### Task 4: Add Streaming Probe Support And Loopback Server Fallback

**Files:**
- Modify: `tldw_Server_API/app/core/TTS/adapters/pocket_tts_cpp_adapter.py`
- Modify: `tldw_Server_API/app/core/TTS/adapters/pocket_tts_cpp_runtime.py`
- Modify: `tldw_Server_API/tests/TTS/adapters/test_pocket_tts_cpp_adapter_mock.py`
- Modify: `tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py`

- [ ] **Step 1: Write the failing streaming tests**

Extend the PocketTTS.cpp adapter tests to prove:

- the adapter performs a one-time CLI streaming feasibility probe
- when the CLI probe proves incremental output, `generate()` returns a streaming response from stdout chunks
- when the CLI probe is not incremental, the adapter starts a loopback-only PocketTTS.cpp server on an ephemeral port and streams through that fallback
- fallback server startup is synchronized so concurrent requests share one coordinated startup path rather than racing
- the adapter rejects non-loopback fallback hosts

Add endpoint-level tests in `test_tts_endpoints.py` that prove:

- `/api/v1/audio/speech` with `model="pocket_tts_cpp"` and `stream=true` returns a streaming response
- the response has the expected content type and sample-rate headers for `pcm`
- custom voices and direct references both reach the streaming path

- [ ] **Step 2: Run the streaming tests to verify they fail**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest -q \
  tldw_Server_API/tests/TTS/adapters/test_pocket_tts_cpp_adapter_mock.py -k stream \
  tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py -k pocket_tts_cpp
```

Expected:

- FAIL because the adapter still reports no streaming support
- FAIL because there is no CLI probe or fallback server transport yet

- [ ] **Step 3: Implement the minimal streaming path**

Make the smallest change set that satisfies the tests:

- add a cached CLI streaming feasibility probe
- stream CLI stdout through `StreamingAudioWriter` when incremental output is real
- add a synchronized adapter-owned fallback server manager for the non-incremental case
- bind the fallback server to `127.0.0.1` on an ephemeral port only
- surface the selected internal transport in response metadata/logging for diagnostics
- update capabilities so PocketTTS.cpp advertises streaming only after the path is real

Guardrails:

- keep non-streaming on the CLI path
- keep the public `/api/v1/audio/speech` contract unchanged
- do not expose the fallback server publicly or require users to manage it manually

- [ ] **Step 4: Re-run the streaming tests and nearby regressions**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest -q \
  tldw_Server_API/tests/TTS/adapters/test_pocket_tts_cpp_adapter_mock.py \
  tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py -k pocket_tts_cpp \
  tldw_Server_API/tests/TTS/test_audio_endpoint_neutts_stream.py \
  tldw_Server_API/tests/TTS/test_audio_endpoint_neutts_stream_mp3.py
```

Expected:

- PASS for the new PocketTTS.cpp streaming tests
- PASS for the existing streaming endpoint regressions

- [ ] **Step 5: Commit the streaming slice**

```bash
git add \
  tldw_Server_API/app/core/TTS/adapters/pocket_tts_cpp_adapter.py \
  tldw_Server_API/app/core/TTS/adapters/pocket_tts_cpp_runtime.py \
  tldw_Server_API/tests/TTS/adapters/test_pocket_tts_cpp_adapter_mock.py \
  tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py
git commit -m "feat(tts): add pocket_tts_cpp streaming fallback"
```

### Task 5: Add The Installer Helper And User-Facing Documentation

**Files:**
- Create: `Helper_Scripts/TTS_Installers/install_tts_pocket_tts_cpp.py`
- Test: `tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_installer.py`
- Modify: `README.md`
- Modify: `Docs/API-related/TTS_API.md`
- Modify: `Docs/Getting_Started/First_Time_Audio_Setup_CPU.md`
- Modify: `Docs/Getting_Started/First_Time_Audio_Setup_GPU_Accelerated.md`
- Modify: `Docs/User_Guides/WebUI_Extension/PocketTTS_Voice_Cloning_Guide.md`

- [ ] **Step 1: Write the failing installer helper tests**

Add unit tests for helper functions inside the installer script that prove:

- the generated config patch contains a `pocket_tts_cpp` provider block with the expected repo-local paths
- the runtime layout resolves to `bin/pocket-tts` and `models/pocket_tts_cpp/`
- the config patch keeps `pocket_tts` and `pocket_tts_cpp` separate

Keep the tests pure-Python and offline. Do not require cloning the upstream repo or running a compiler.

- [ ] **Step 2: Run the installer tests to verify they fail**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest -q tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_installer.py
```

Expected:

- FAIL because the installer helper does not exist yet

- [ ] **Step 3: Implement the installer helper and docs**

Implement `install_tts_pocket_tts_cpp.py` so it:

- validates `git`, `cmake`, and a C++ compiler
- clones or updates PocketTTS.cpp into a temporary working directory
- builds the binary
- runs the export step needed for repo-local ONNX assets
- copies the binary and exported assets into `bin/` and `models/pocket_tts_cpp/`
- patches `tts_providers_config.yaml` with a `pocket_tts_cpp` block
- supports a non-destructive `--help` and a dry-run-friendly structure where practical

Update docs so they clearly explain:

- `pocket_tts` is the existing Python/ONNX runtime
- `pocket_tts_cpp` is the compiled-binary runtime
- both use the same `/api/v1/audio/speech` route
- both can use `custom:<voice_id>` and direct `voice_reference`, but they have different install/runtime expectations

- [ ] **Step 4: Re-run the installer test and smoke-check the script help**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest -q tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_installer.py
python Helper_Scripts/TTS_Installers/install_tts_pocket_tts_cpp.py --help
```

Expected:

- PASS for the installer helper tests
- the installer script prints usage information and exits successfully

- [ ] **Step 5: Commit the installer and docs slice**

```bash
git add \
  Helper_Scripts/TTS_Installers/install_tts_pocket_tts_cpp.py \
  tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_installer.py \
  README.md \
  Docs/API-related/TTS_API.md \
  Docs/Getting_Started/First_Time_Audio_Setup_CPU.md \
  Docs/Getting_Started/First_Time_Audio_Setup_GPU_Accelerated.md \
  Docs/User_Guides/WebUI_Extension/PocketTTS_Voice_Cloning_Guide.md
git commit -m "feat(tts): add pocket_tts_cpp installer and docs"
```

### Task 6: Run Verification, Security Checks, And Manual Runtime Validation

**Files:**
- Modify only if verification exposes real defects in the touched PocketTTS.cpp files

- [ ] **Step 1: Run the full targeted automated verification set**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest -q \
  tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_registry.py \
  tldw_Server_API/tests/TTS_NEW/unit/test_tts_validation_pocket_tts_cpp.py \
  tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_runtime.py \
  tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_service.py \
  tldw_Server_API/tests/TTS_NEW/unit/test_pocket_tts_cpp_installer.py \
  tldw_Server_API/tests/TTS_NEW/integration/test_custom_voice_resolution.py -k pocket_tts_cpp \
  tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py -k pocket_tts_cpp \
  tldw_Server_API/tests/TTS/adapters/test_pocket_tts_cpp_adapter_mock.py \
  tldw_Server_API/tests/TTS/adapters/test_pocket_tts_cpp_adapter_integration.py \
  tldw_Server_API/tests/TTS/test_tts_validation.py -k pocket_tts \
  tldw_Server_API/tests/TTS/adapters/test_pocket_tts_adapter_mock.py
```

Expected:

- PASS for all new PocketTTS.cpp coverage
- PASS for the nearby existing PocketTTS and validation regressions
- SKIP, not FAIL, for the opt-in real-runtime integration test when the environment is not provisioned

- [ ] **Step 2: Run Bandit on the touched security-relevant paths**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m bandit -f json -o /tmp/bandit_pocket_tts_cpp.json \
  tldw_Server_API/app/core/TTS/adapters/pocket_tts_cpp_adapter.py \
  tldw_Server_API/app/core/TTS/adapters/pocket_tts_cpp_runtime.py \
  tldw_Server_API/app/core/TTS/tts_service_v2.py \
  tldw_Server_API/app/core/TTS/voice_manager.py \
  Helper_Scripts/TTS_Installers/install_tts_pocket_tts_cpp.py
```

Expected:

- EXIT 0 or only pre-existing/accepted findings outside the new code paths
- `/tmp/bandit_pocket_tts_cpp.json` exists for review

- [ ] **Step 3: Perform manual runtime validation if the binary and assets are available**

Manual checks:

- run the installer helper or verify the repo-local runtime already exists
- send one non-streaming `curl` request using a direct `voice_reference`
- send one streaming `curl --no-buffer` request using a stored `custom:<voice_id>`
- confirm the provider-managed runtime subtree is created under the correct user voices directory
- confirm repeated requests reuse stable filenames rather than generating new random temp files
- confirm the fallback server, if used, binds only to loopback and tears down cleanly

- [ ] **Step 4: Fix any verification defects and re-run only the affected checks**

If any test, Bandit finding, or manual check exposes a real defect:

- fix the issue in the smallest possible scope
- re-run the exact failing automated check
- re-run any directly related regressions before moving on

- [ ] **Step 5: Commit final verification fixes if any were required**

```bash
git add tldw_Server_API/app/core/TTS/adapters/pocket_tts_cpp_adapter.py tldw_Server_API/app/core/TTS/adapters/pocket_tts_cpp_runtime.py tldw_Server_API/app/core/TTS/tts_service_v2.py tldw_Server_API/app/core/TTS/voice_manager.py Helper_Scripts/TTS_Installers/install_tts_pocket_tts_cpp.py
git commit -m "fix(tts): finalize pocket_tts_cpp verification"
```
