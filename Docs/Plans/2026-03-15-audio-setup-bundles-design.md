# Audio Setup Bundles Design

## Summary

This design proposes a bundle-first audio provisioning flow inside `/setup` that makes speech setup easier for two target outcomes:

- durable multi-provider operator setups
- easier fully-local or offline-capable setups

The current platform already has useful pieces:

- `/setup` config editing and install-plan submission
- installer execution for Python dependencies and model downloads
- basic audio walkthroughs and install status reporting
- health endpoints for STT and TTS

The main problem is not the absence of setup primitives. The problem is that operators still have to mentally assemble a working audio stack across multiple surfaces:

- generic first-run setup
- provider-level install choices
- config sections
- speech docs
- separate verification steps

This design makes `/setup` the canonical operator entry point for audio provisioning and verification.

## Goals

- Let operators choose a small set of curated audio bundles instead of individual providers during first setup.
- Recommend bundles automatically from detected hardware and operator preferences.
- Provision the selected bundle from `/setup` with as much automation as the platform can safely support.
- Produce a persistent, operator-readable audio readiness report.
- Support long-term multi-provider setups without forcing provider-level complexity into the first-run path.
- Support offline runtime after provisioning, and define a clear path for preseeded offline provisioning.

## Non-Goals

- Exposing every STT/TTS provider directly in the default first-run path.
- Replacing all provider-level configuration surfaces immediately.
- Claiming true offline provisioning without a preseed/import path.
- Claiming true workflow resume when the current installer can only support safe reruns.
- Fully automating every OS-level prerequisite in v1 on every platform.

## Current Constraints

The design must fit the platform as it exists today.

### 1. Installer scope is currently limited

The current setup installer can:

- install Python dependencies with `pip` or `uv pip`
- download model assets from Hugging Face
- persist install status snapshots

It does not yet manage all OS-level prerequisites such as:

- `ffmpeg`
- `espeak-ng`
- platform-specific CUDA/runtime packages

Therefore, the new design must distinguish between:

- automatically provisioned steps
- guided prerequisite steps

### 2. `/setup` completion is currently global, not module-specific

The current `/setup/complete` endpoint marks the first-run setup complete before background installation finishes. That means audio provisioning cannot reuse the global setup completion flag as its readiness signal.

The design must introduce a separate audio lifecycle object.

### 3. Install status is log-like, not resumable state

Current install status persistence records steps and outcomes, but it does not checkpoint a resumable workflow graph. The design should promise:

- safe rerun
- idempotent step skipping

It should not promise:

- exact resume from arbitrary mid-step state

### 4. Hardware recommendation must be scoped to reliable signals

The current platform has basic CUDA detection and some audio health checks, but not a full hardware inventory system. The recommender must start with reliable inputs:

- OS/platform
- Apple Silicon vs Intel
- CUDA availability
- FFmpeg presence
- eSpeak presence
- basic free disk checks

RAM/VRAM heuristics can be added later, but should not block v1.

## Design Principles

- Bundle-first, provider-details-later
- Evidence before “ready”
- Safe rerun over false resume
- One source of truth for bundle definitions
- One canonical operator path in `/setup`
- Explicit handling for offline runtime versus offline provisioning

## Proposed Architecture

The audio setup flow adds a first-class `Audio Setup` stage under `/setup` with four layers:

1. machine profile detection
2. bundle recommendation
3. provisioning
4. verification and readiness reporting

The current provider-level install plan remains an internal execution format. The user-facing contract becomes “select a bundle.”

Canonical happy path:

`install server -> open /setup -> view detected machine profile -> accept or change recommended bundle -> provision bundle -> run verification -> receive readiness report -> continue to the rest of the product`

## Core Components

### 1. Audio Bundle Catalog

Introduce a versioned bundle manifest that defines curated audio stacks such as:

- `cpu_local`
- `apple_silicon_local`
- `nvidia_local`
- `hosted_plus_local_backup`

Each bundle declares:

- supported machine profile predicates
- operator-facing name and explanation
- offline suitability
- estimated disk requirements
- automation tier per prerequisite
- STT stack
- TTS stack
- fallback order
- Python dependency groups
- model assets to prefetch
- config defaults to write
- verification targets

The bundle catalog becomes the source of truth for:

- `/setup` recommendations
- provisioning expansion
- verification expectations
- generated setup docs

### 2. Machine Profile Detector

Introduce a backend service that normalizes detectable local capabilities into a machine profile object.

V1 profile fields:

- `platform`: `macos|linux|windows`
- `arch`: `arm64|x86_64|other`
- `apple_silicon`: boolean
- `cuda_available`: boolean
- `ffmpeg_available`: boolean
- `espeak_available`: boolean
- `free_disk_gb`: best-effort numeric hint
- `network_available_for_downloads`: best-effort boolean

Operator preferences passed into recommendation:

- `prefer_offline_runtime`
- `allow_hosted_fallbacks`
- `prefer_local_only`

The detector returns:

- normalized machine profile
- ranked bundle recommendations
- exclusion reasons for unsupported bundles

### 3. Provisioning Orchestrator

Extend the current setup install manager so it can execute a bundle expansion result rather than only a flat provider selection.

Provisioning layers:

1. `system_prerequisites`
2. `python_dependencies`
3. `model_assets`
4. `config_defaults`
5. `verification`

Each step in a bundle declares an automation tier:

- `automatic`
- `guided`
- `manual_blocked`

Examples:

- `automatic`: install Python packages, download Faster Whisper models
- `guided`: tell the operator to install `ffmpeg` or `espeak-ng` with platform-specific commands
- `manual_blocked`: stop because the chosen bundle fundamentally cannot run on the detected machine

This preserves the user expectation that `/setup` owns the flow, while staying honest about what can actually be automated in v1.

### 4. Audio Verification Suite

Provisioning success must not be defined by completed downloads alone.

Verification should test one default path per capability:

- one primary STT path
- one primary TTS path

Secondary providers should be checked passively when possible, but should not be required to mark the bundle usable.

V1 verification targets:

- default STT provider import/init
- default TTS provider import/init
- required model assets present
- voice catalog available for default TTS path
- sample transcription succeeds
- sample synthesis succeeds

### 5. Audio Readiness State

Introduce a separate persisted `audio_readiness` object that is independent from global setup completion.

Proposed states:

- `not_started`
- `detecting`
- `recommended`
- `provisioning`
- `ready`
- `ready_with_warnings`
- `partial`
- `failed`

This object should also include:

- machine profile snapshot
- selected bundle id and version
- completed prerequisite status
- completed install steps
- last verification result
- operator-readable remediation items
- last updated timestamp

This solves the mismatch between:

- global setup completion
- asynchronous audio provisioning

### 6. `/setup` Audio Stage

Add a dedicated audio step in `/setup` that shows:

- detected machine profile
- recommended bundle
- alternative bundles
- what will be installed
- what cannot yet be automated
- disk estimate
- online/offline suitability
- current readiness state

Primary actions:

- `Provision recommended bundle`
- `Choose different bundle`
- `Run verification`
- `Safe rerun provisioning`
- `View readiness report`

Advanced actions:

- `Show provider details`
- `Switch to provider-level customization`

## Revised UX Contract

### Operator-facing promises

The setup UI should only promise what it can actually do.

It should say:

- “This setup will provision the Python packages and model assets for the selected bundle.”
- “These prerequisites still require operator action.”
- “You can rerun provisioning safely after fixing prerequisites.”

It should not say:

- “Everything is fully installed” before verification succeeds.
- “Resume” unless exact resumability exists.

### Readiness semantics

Terminal bundle outcomes:

- `ready`
- `ready_with_warnings`
- `partial`
- `failed`

Examples:

- `ready_with_warnings`: local STT/TTS are working, hosted fallback keys are missing
- `partial`: default STT works, TTS failed because `espeak-ng` is missing
- `failed`: default STT and default TTS could not be verified

### Remediation messaging

Every failed or partial state must map to a concrete action.

Examples:

- “Kokoro assets downloaded, but eSpeak NG was not found. Install `espeak-ng`, then run verification again.”
- “NVIDIA bundle is not supported because CUDA was not detected. Choose `cpu_local` or install CUDA runtime support.”

## Offline Model

The design must explicitly separate three different scenarios.

### 1. Online provisioning

The machine has internet during setup. Python dependencies and model assets may be downloaded automatically.

### 2. Preseeded offline provisioning

The operator prepares:

- Python wheels or local package source
- model snapshots
- optional local mirrors/cache paths

The setup flow then uses those local artifacts without internet access.

### 3. Offline runtime after provisioning

The machine is online during setup, but expected to run disconnected afterward.

This mode should bias recommendations toward:

- local STT/TTS
- no hosted-only defaults
- proactive asset prefetching

V1 should support:

- online provisioning
- offline runtime after provisioning

V1 should define, but not fully automate, preseeded offline provisioning. The bundle catalog should be compatible with that future path.

## Recommended V1 Bundles

### `cpu_local`

Target:

- CPU-only machines
- simple offline-capable local setup

Defaults:

- STT: `faster_whisper`
- TTS: `kokoro`
- optional fallback: none by default

### `apple_silicon_local`

Target:

- Apple Silicon machines

Defaults:

- STT: `nemo_parakeet_mlx` or `faster_whisper` fallback depending on actual support maturity
- TTS: `kokoro`

### `nvidia_local`

Target:

- machines with working CUDA

Defaults:

- STT: `nemo_parakeet_onnx` or `faster_whisper`
- TTS: `kokoro`, with room for stronger GPU-capable providers later

### `hosted_plus_local_backup`

Target:

- operators who want a durable multi-provider setup

Defaults:

- hosted default path for fast results
- local fallback path for resilience

This bundle should remain secondary for operators who explicitly prefer offline runtime.

## Data Flow

### Recommendation flow

`/setup loads -> backend computes machine profile -> backend ranks bundles -> UI renders recommendation and alternatives`

### Provisioning flow

`operator selects bundle -> bundle expands into layered provisioning steps -> orchestrator executes automatic steps -> guided steps are surfaced -> config defaults written -> verification runs -> audio_readiness updated`

### Safe rerun flow

`operator fixes prerequisites -> clicks safe rerun -> orchestrator reevaluates current machine profile and bundle -> satisfied steps are skipped or reused -> verification runs again`

## API and Persistence Changes

### New or expanded backend contracts

- machine profile endpoint or setup config payload enrichment
- bundle recommendation response
- bundle provisioning request
- audio readiness status endpoint
- verification trigger endpoint

### Persistence

Persist audio readiness separately from the current setup-complete flag.

The readiness record should survive:

- browser refresh
- app restart
- repeated provisioning attempts

## Documentation Strategy

The bundle catalog must drive generated setup docs to prevent drift.

Required outputs:

- operator-readable bundle matrix
- per-bundle prerequisites
- per-bundle automated versus guided steps
- offline suitability notes
- remediation guide

The current setup wizard guide and speech getting-started pages should be revised to point to the bundle model instead of explaining provider setup as the default path.

## Testing Strategy

### 1. Bundle recommendation tests

- machine profile X yields expected bundle ranking
- offline preference reorders recommendations
- unsupported bundles include explicit reasons

### 2. Provisioning expansion tests

- bundle manifest expands into expected automatic/guided/manual steps
- config writes are deterministic and idempotent
- safe rerun skips already-satisfied work

### 3. Verification tests

- success case marks bundle `ready`
- missing `ffmpeg` produces guided prerequisite failure
- missing `espeak-ng` produces partial readiness
- missing CUDA excludes or fails incompatible bundles correctly
- missing assets produce actionable remediation

### 4. Setup UI tests

- recommendation card renders for detected machine profile
- bundle selection submits the correct provisioning request
- readiness states render correctly
- safe rerun and verification actions are visible in non-ready states

## Rollout Plan

### Phase 1

- add bundle catalog
- add machine profile detector
- add bundle recommendation and provisioning APIs
- add audio readiness persistence
- add basic bundle-first `/setup` UI

### Phase 2

- make bundles the default setup path
- move provider-level install selection into advanced mode
- add generated docs from bundle definitions

### Phase 3

- add preseeded offline provisioning path
- expand recommender with richer hardware heuristics
- expand multi-provider bundle coverage

## Key Risks and Mitigations

### Risk: overpromising full automation

Mitigation:

- use automation tiers per step
- separate automatic from guided prerequisites

### Risk: readiness logic conflicts with current setup completion

Mitigation:

- use separate `audio_readiness`
- do not overload `setup_completed`

### Risk: docs drift from bundle behavior

Mitigation:

- generate docs from the bundle manifest

### Risk: verification becomes too slow

Mitigation:

- verify one primary STT path and one primary TTS path
- treat secondary fallbacks as warnings

### Risk: rerun corrupts state

Mitigation:

- keep config writes idempotent
- treat provisioning as convergent
- avoid partial mutable bundle state beyond persisted readiness records

## Recommendation

Proceed with a v1 that is:

- bundle-first
- honest about automation tiers
- safe-rerun instead of fake resume
- driven by a distinct audio readiness lifecycle
- optimized for local/offline-capable runtime and durable multi-provider setups

This provides a much clearer operator story without forcing the current platform to pretend it can fully automate what it cannot yet control.
