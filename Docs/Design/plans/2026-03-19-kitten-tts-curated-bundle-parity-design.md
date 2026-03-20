# KittenTTS Curated Bundle Parity Design

Date: 2026-03-19
Status: Approved for implementation planning
Owner: Codex + user collaboration

## 1. Goal

Verify the existing `kitten_tts` provider through the real speech API path and add it to curated low-resource local audio setup as a first-class peer to `kokoro`.

This is not a new provider-runtime project. `kitten_tts` already exists in the registry, adapter layer, setup installer schema, and WebUI provider lists. The new work is:

- prove the existing `/api/v1/audio/speech` route resolves and invokes `kitten_tts` correctly,
- extend curated CPU-local setup so `light` and `balanced` profiles can select either `kokoro` or `kitten_tts`,
- persist that curated TTS choice everywhere the setup flow already persists bundle/profile selection.

## 2. Confirmed Scope Decisions

Validated with the user:

1. `kitten_tts` should be verified through the real backend speech path.
2. Curated setup should include `kitten_tts`, not leave it advanced-only.
3. `kitten_tts` should be a similar-weight option to `kokoro` for CPU-only / low-resource local setup.
4. V1 should stay narrow:
   - CPU-local curated profiles only,
   - no Apple Silicon or NVIDIA curated Kitten defaults yet,
   - no recommendation duplication or ranking overhaul.

## 3. Approaches Considered

### Approach A: Duplicate CPU bundles

- Add `cpu_local_kokoro` and `cpu_local_kitten`.
- Let the existing recommendation system rank them separately.

Pros:

- Minimal changes to install-plan expansion.
- No new `tts_choice` field.

Cons:

- Duplicates nearly identical bundle definitions.
- Pollutes recommendation output with repeated CPU-local rows.
- Makes offline pack and readiness reporting noisier for operators.

### Approach B (Recommended): Keep one CPU bundle and add curated `tts_choice`

- Keep `cpu_local` and existing `light` / `balanced` / `performance` profiles.
- Add explicit curated TTS choices on low-resource profiles.
- Persist the selected choice across provision, verification, readiness, and offline-pack metadata.

Pros:

- Matches the user request exactly: Kitten is a peer choice inside the curated flow.
- Preserves the current recommendation architecture.
- Avoids copying bundle definitions.

Cons:

- Requires a new persisted selection dimension.
- Touches several setup identity and persistence paths together.

### Approach C: Make Kitten the new CPU default everywhere

- Replace curated `kokoro` with `kitten_tts` on CPU-local profiles.

Pros:

- Smallest data change.

Cons:

- Does not match the requested “similar weight” behavior.
- Removes Kokoro as the default curated low-resource path.

Decision: Approach B.

## 4. Reviewed Risks and Design Adjustments

The design was tightened after reviewing the current setup contracts:

1. Selection identity currently only includes `bundle_id + resource_profile`.
   - `selection_key`, readiness, install status, and audio-pack manifests all need an optional `tts_choice` dimension or `kokoro` and `kitten_tts` selections will collide.

2. `AudioResourceProfile.tts_plan` is already the concrete installer plan.
   - Curated peer choices must not be encoded by placing both engines in `tts_plan`, or the installer will provision both.

3. Verification currently assumes `selected_profile.tts_plan[0]` is the primary TTS engine.
   - Verification must resolve the chosen curated TTS engine first and then check that exact provider path.

4. Recommendation ranking should stay at the bundle/profile level.
   - The UI should expose `kokoro` vs `kitten_tts` as a selector inside a recommended profile, not as duplicate top-level recommendation rows.

5. Offline-pack metadata must stay faithful.
   - Exported/imported packs need to remember which curated TTS choice was selected, not only bundle/profile.

## 5. Architecture

### 5.1 Existing Provider Verification

Before changing curated bundles, add a focused backend integration test proving the existing speech route already works for `kitten_tts`:

- `POST /api/v1/audio/speech`
- `model="kitten_tts"`
- provider inference resolves to `kitten_tts`
- the Kitten adapter is invoked through the normal TTS service path

This test should mock at the adapter/service boundary. It should validate routing and endpoint integration, not trigger real model downloads.

### 5.2 Curated Bundle Model

Keep the existing bundle/profile structure and add an explicit curated TTS choice layer.

Add to `AudioResourceProfile`:

- `tts_choices: list[CuratedTtsChoice] = []`
- `default_tts_choice: str | None = None`

Where each curated choice contains:

- `choice_id` such as `kokoro` or `kitten_tts`
- `label`
- concrete `tts_plan` for installer expansion
- choice-specific `default_config_updates`
- choice-specific `verification_targets`
- optional `estimated_disk_gb_delta`
- optional `notes`

Rules:

- `cpu_local.light` and `cpu_local.balanced` expose:
  - `kokoro`
  - `kitten_tts`
- `cpu_local.performance` remains unchanged in V1.
- profiles with no `tts_choices` continue to use the existing profile-level `tts_plan`.

### 5.3 Selection Identity and Persistence

Introduce a third selection dimension: `tts_choice`.

Extend:

- `build_audio_selection_key(...)`
- `AudioReadinessRecord`
- install-result payloads
- verification payloads
- audio-pack manifest/export/import metadata

Recommended key shape:

- existing behavior unchanged when `tts_choice` is absent
- CPU-local curated Kitten/Kokoro selections become distinct keys, for example:
  - `v2:cpu_local:balanced:kokoro`
  - `v2:cpu_local:balanced:kitten_tts`

Persisted readiness fields should include:

- `selected_tts_choice: str | None`

This keeps safe-rerun, verification, and offline-pack imports aligned with the operator’s actual TTS selection.

### 5.4 Provision and Install-Plan Resolution

Add optional `tts_choice` to:

- provision request models
- verify request models
- admin equivalents

Install-plan generation should:

1. load the bundle,
2. load the selected profile,
3. resolve the chosen curated TTS choice when present,
4. build a one-engine concrete `tts_plan`,
5. return a normal `InstallPlan`.

Profiles without curated TTS choices keep the current path.

### 5.5 Verification

Verification must become choice-aware for profiles that expose curated TTS choices.

Resolution rules:

- if `tts_choice` is provided, verify the matching curated choice’s primary TTS engine
- else if the profile defines curated choices, use `default_tts_choice`
- else use the existing profile-level `tts_plan`

Verification output and readiness persistence should include:

- `selected_tts_choice`
- the resolved primary TTS provider

This prevents Kokoro-specific checks from running when the selected curated path was Kitten.

### 5.6 Recommendation and UI Flow

Recommendation ranking remains unchanged at the bundle/profile level.

The recommendation payload should include the profile’s curated TTS choices and default choice when present. The shared installer UI should then:

- select the recommended bundle/profile as it does now,
- show a TTS selector only when the selected profile exposes curated TTS choices,
- default the selector to the profile’s `default_tts_choice`,
- submit `tts_choice` on provision and verify actions,
- keep the selector hidden for profiles with only one concrete TTS path.

This keeps KittenTTS visible and peer-level without producing duplicate CPU-local recommendation rows.

## 6. File-Level Impact

Likely touched backend files:

- `tldw_Server_API/app/api/v1/endpoints/setup.py`
- `tldw_Server_API/app/core/Setup/audio_bundle_catalog.py`
- `tldw_Server_API/app/core/Setup/audio_readiness_store.py`
- `tldw_Server_API/app/core/Setup/audio_pack_service.py`
- `tldw_Server_API/app/core/Setup/install_manager.py`

Likely touched frontend files:

- `apps/packages/ui/src/components/Option/Setup/hooks/useAudioInstaller.ts`
- `apps/packages/ui/src/components/Option/Setup/AudioInstallerPanel.tsx`

Likely new or updated tests:

- `tldw_Server_API/tests/Audio/test_tts_provider_inference.py`
- a focused audio speech endpoint integration test
- `tldw_Server_API/tests/Setup/test_audio_bundle_catalog.py`
- `tldw_Server_API/tests/Setup/test_audio_bundle_verification.py`
- `tldw_Server_API/tests/Setup/test_audio_pack_service.py`
- `apps/packages/ui/src/components/Option/Setup/__tests__/AudioInstallerPanel.test.tsx`

## 7. Testing Strategy

### Backend verification of existing Kitten support

- prove `/api/v1/audio/speech` routes `model="kitten_tts"` correctly
- prove repo-id aliases still map to `kitten_tts`

### Bundle/catalog tests

- `cpu_local.light` exposes `kokoro` and `kitten_tts`
- `cpu_local.balanced` exposes `kokoro` and `kitten_tts`
- `default_tts_choice` is set and stable

### Install/verification/readiness tests

- selected `tts_choice` changes the generated `tts_plan`
- selected `tts_choice` is persisted in readiness
- verification checks Kokoro when `kokoro` is selected
- verification checks KittenTTS when `kitten_tts` is selected
- selection keys differ across curated TTS choices

### Offline-pack tests

- manifest stores `selected_tts_choice`
- imported pack restores `selected_tts_choice`

### Frontend tests

- selector renders only for profiles with curated choices
- selector defaults correctly
- provision/verify submits `tts_choice`

## 8. Out of Scope

This slice does not:

- add KittenTTS to Apple Silicon or NVIDIA curated profiles,
- replace Kokoro as the default local curated TTS everywhere,
- create duplicate bundle recommendations for Kokoro vs Kitten,
- perform a runtime/install-manager redesign beyond what the new `tts_choice` dimension requires.

## 9. Success Criteria

This design is successful when:

1. `/api/v1/audio/speech` is covered by a focused integration test proving `kitten_tts` routing works.
2. CPU-local curated low-resource profiles expose KittenTTS as a peer choice to Kokoro.
3. Provision, verification, readiness, install status, and audio-pack metadata all preserve the selected curated TTS choice.
4. The shared admin audio installer UI lets admins choose KittenTTS from the curated CPU-local flow without duplicating recommendation rows.
