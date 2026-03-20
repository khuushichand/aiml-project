# Admin Audio Installer Shared UI Design

## Summary

This design promotes the existing setup audio bundle installer into a shared, admin-facing audio installer that can be used from both the extension/options UI and the Next.js WebUI.

The current platform already has most of the backend primitives:

- setup audio recommendation endpoints
- setup audio provisioning
- setup audio verification
- install status polling
- curated bundle definitions

The main gaps are:

- no installer entry point in the normal React UIs
- current curated bundles are too conservative and underrepresent major local speech paths
- current backend access semantics are "local setup access with optional remote-admin override", not "ongoing admin tool"
- the installer lifecycle is tied too closely to setup enablement

This design fixes those problems without creating a second installer backend.

## Goals

- Expose a shared audio installer panel in both the extension/options UI and the Next.js WebUI.
- Restrict installation actions to server administrators.
- Make the installer usable after initial setup is complete.
- Reuse the existing `/api/v1/setup/audio/*` backend workflow instead of inventing a separate installer API.
- Expand curated bundle recommendations so they cover the major local speech paths, not only `faster_whisper + kokoro`.
- Keep V1 focused on curated bundles only, not the advanced per-engine installer.

## Non-Goals

- Exposing the advanced per-engine installer in the first React integration.
- Making every runtime-supported STT/TTS provider available via curated bundles.
- Solving the existing schema/runtime mismatch for non-curated TTS engines such as `echo_tts`, `pocket_tts`, and `neutts`.
- Replacing the existing static `/setup` screen immediately.
- Adding a new generic package-management or native dependency installation framework.

## Current Constraints

### 1. Current setup access is not truly admin-only

The backend guard in [setup_deps.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/api/v1/API_Deps/setup_deps.py) currently allows loopback access without admin claims, and only requires admin when remote setup access is explicitly enabled.

That behavior is acceptable for the legacy first-run setup flow, but it is not a correct policy for an ongoing shared admin installer surface in the extension and WebUI.

### 2. Audio installer endpoints depend on setup being enabled

The audio installer endpoints in [setup.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/api/v1/endpoints/setup.py) check `status_snapshot["enabled"]`.

They do not require `needs_setup`, which is good, but they still disappear if setup is fully disabled after bootstrap. That is a mismatch for ongoing admin tooling.

### 3. Curated bundles are too narrow

The current curated bundle catalog in [audio_bundle_catalog.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/Setup/audio_bundle_catalog.py) effectively recommends:

- STT: `faster_whisper`
- TTS: `kokoro`

for every bundle/resource profile combination, with only model size changes.

That undersells the strongest local speech paths already supported by the runtime.

### 4. Runtime support is wider than curated provisioning

The STT runtime in [stt_provider_adapter.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/stt_provider_adapter.py) and the TTS runtime in [adapter_registry.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/TTS/adapter_registry.py) support substantially more providers than curated setup currently provisions.

This design should narrow that gap for the main local speech paths, but it should stay opinionated rather than trying to expose every provider.

## Design Principles

- One installer backend, multiple React entry points
- Admin-only for shared UI-triggered installs
- Usable after first-run setup
- Curated and conservative by default
- Bundle-first, provider-details-later
- Verification should confirm the specific bundle profile path, not generic STT/TTS availability

## Product Shape

Introduce a shared `Audio Installer` panel in React and surface it in:

- the extension/options UI
- the Next.js WebUI

This panel is an admin/server-configuration tool, not a casual speech playground feature.

V1 flow:

1. fetch machine profile and recommended curated bundle
2. show the recommended profile and profile alternatives
3. provision the selected bundle/profile
4. poll install status while provisioning runs
5. verify the selected bundle/profile
6. show remediation items if prerequisites or assets are still missing

The static setup UI in `tldw_Server_API/app/static/setup/js/setup.js` remains supported, but the shared React panel becomes the preferred operator path.

## Access Control

### Desired policy

For the shared installer panel:

- all install/provision/verify/status actions should require an authenticated admin or equivalent server-admin principal
- local loopback access should not automatically bypass admin checks for the new shared UI path

### Recommended implementation approach

Do not weaken the existing legacy setup behavior. Instead:

- add a dedicated admin-oriented setup-audio access dependency for the shared UI path
- reuse the same install manager, bundle catalog, and verification logic
- allow the legacy static setup experience to continue using the current local-first setup guard if needed

This keeps first-run local setup convenient while making the new shared installer consistent with the requested "admins/server admin only" rule.

## Backend Architecture

### 1. Preserve the existing installer engine

Keep using the logic in:

- [setup.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/api/v1/endpoints/setup.py)
- [install_manager.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/Setup/install_manager.py)
- [audio_bundle_catalog.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/Setup/audio_bundle_catalog.py)

Do not create a separate provisioning engine.

### 2. Decouple audio installer availability from first-time setup

The audio installer endpoints should remain available to administrators even after first-time setup is complete and even if the full setup wizard is no longer the active operator path.

Practical requirement:

- audio recommendation/provision/verify/install-status should not disappear simply because first-run setup is completed

If necessary, split "setup flow enabled" from "audio installer enabled".

### 3. Expand curated bundle definitions conservatively

Curated parity should mean the bundle catalog now covers the main local speech paths the runtime already supports well.

Recommended curated profiles:

- `cpu_local`
  - light/balanced/performance:
    - STT: `faster_whisper`
    - TTS: `kokoro`

- `apple_silicon_local`
  - light:
    - STT: `faster_whisper`
    - TTS: `kokoro`
  - balanced/performance:
    - STT: `nemo_parakeet_mlx`
    - TTS: `kokoro`

- `nvidia_local`
  - light:
    - STT: `faster_whisper`
    - TTS: `kokoro`
  - balanced:
    - STT: `nemo_parakeet_standard` or `nemo_parakeet_onnx`
    - TTS: `kokoro`
  - performance:
    - STT: `nemo_parakeet_standard`
    - TTS: `dia` or `higgs`

- `hosted_plus_local_backup`
  - local fallback only:
    - STT: `faster_whisper`
    - TTS: `kokoro`
  - hosted components remain configuration guidance, not model downloads

### 4. Keep non-curated engines manual/config-only

The following remain supported by runtime but out of curated bundle scope for this slice:

- STT: `qwen2_audio`, `qwen3-asr`, `vibevoice`, `external`
- TTS: `openai`, `elevenlabs`, `vibevoice_realtime`, `chatterbox`, `index_tts`, `supertonic`, `supertonic2`, `qwen3_tts`, `lux_tts`, `echo_tts`, `pocket_tts`, `neutts`

They can continue to be installed or configured manually until a later advanced-installer slice.

### 5. Verification must become profile-aware

Verification should confirm the exact bundle path that the selected profile writes into config and expects at runtime.

Examples:

- Apple Silicon balanced profile should verify `parakeet mlx` readiness, not merely "some STT is available"
- NVIDIA performance profile with `dia` should verify that `dia` is the active/default TTS path when that profile claims to install it

Remediation output should be specific to the profile’s expected engines and prerequisites.

## Frontend Architecture

### Shared component

Create a shared React panel in `apps/packages/ui` that:

- loads audio recommendations
- renders the machine profile summary
- renders the recommended bundle and resource profiles
- starts provisioning
- polls install status
- runs verification
- displays remediation items and readiness output

This panel should own only installer state. It should not be coupled to persona, playground, or speech testing state.

### Host integration

Mount the shared panel in:

- extension/options UI admin/setup area
- Next.js WebUI admin/server configuration area

Host wrappers should be thin:

- page layout
- route/section placement
- host-specific breadcrumbs or headings

The actual installer logic and network interactions should remain in the shared component.

### Failure behavior

Fail closed:

- forbidden/not-admin -> show concise access message
- installer unavailable -> show concise unavailable message
- setup endpoint disabled -> show unavailable state, not dead controls
- downloads blocked or prerequisites missing -> show remediation clearly

## Recommended UI Behavior

Primary content:

- "Recommended audio bundle"
- bundle explanation
- detected machine profile summary
- resource profile selector (`Light`, `Balanced`, `Performance` when available)

Primary actions:

- `Provision bundle`
- `Run verification`
- `Safe rerun`

Supporting output:

- install status timeline
- remediation items
- readiness summary

Copy must clearly say that these actions affect the connected server, not the browser/extension.

## Risks

### 1. Policy mismatch between legacy setup and admin installer

If the project wants to preserve local-no-auth setup for bootstrap but also make the shared UI admin-only, there will be two access paths with slightly different trust models. That is acceptable, but it must be explicit in code and tests.

### 2. Bundle recommendations may overreach

If richer bundles are recommended too aggressively, operators will be pushed into large installs that their machines cannot sustain. Recommendation logic should stay conservative.

### 3. Shared UI could drift by host

If each host adds bespoke state or network logic, parity will degrade. The shared component should remain the only place that knows the installer flow.

## Testing Strategy

### Backend

- access control tests for admin-only shared installer behavior
- endpoint availability tests after setup completion
- recommendation tests for CPU / Apple Silicon / NVIDIA bundle selection
- bundle expansion tests for updated curated profiles
- verification/remediation tests for new profile-specific expectations

### Shared frontend

- recommendation loading
- provisioning action and install-status polling
- verification result rendering
- forbidden/unavailable handling
- remediation rendering

### Host integration

- extension/options mount renders the shared panel in the intended admin surface
- Next.js WebUI mount renders the same shared panel
- no host-specific divergence in action behavior

## Open Decisions Resolved

- Curated bundles only for V1 shared UI: yes
- Shared UI in both extension and Next.js WebUI: yes
- Admin/server-admin only: yes
- Curated parity means expanding bundle coverage for major local speech paths, not only surfacing the current `/setup` flow: yes

## Expected Outcome

After this slice:

- admins can provision server-side STT/TTS bundles from both main React UIs
- the installer remains usable after setup is complete
- curated bundles better represent the strongest local speech paths on CPU, Apple Silicon, and NVIDIA systems
- runtime-only providers remain available, but intentionally outside curated provisioning
