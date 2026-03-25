# Audio Input Source Switching Design

Date: 2026-03-24
Status: Approved for planning
Owner: Codex brainstorming session

## Summary

Add shared audio input source selection for microphone-based features across the WebUI and extension, while keeping behavior honest about browser and platform limits. Ship microphone-device switching everywhere first. Add WebUI-first share-style capture later for tab and system audio where browser APIs and UX make that safe.

The design separates capture source selection from speech-path selection. This avoids overloading the current dictation strategy and prevents the UI from claiming that browser-native dictation can bind to a specific non-default source when the browser cannot actually honor that request.

## Problem

Current microphone capture paths in the shared UI package use default browser microphone access only.

Today:

- [useServerDictation.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useServerDictation.tsx) starts recording with `getUserMedia({ audio: true })`.
- [useMicStream.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useMicStream.ts) streams PCM from `getUserMedia({ audio: true })`.
- [useAudioRecorder.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useAudioRecorder.ts) records from `getUserMedia({ audio: true })`.
- [useSpeechRecognition.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useSpeechRecognition.tsx) wraps browser speech recognition and has no input-device binding layer.

As a result:

- users cannot pick a specific microphone for dictation, live voice, or the Speech playground
- features cannot remember different preferred sources per use case
- the product has no path for tab or system audio capture
- browser dictation and app-managed capture are conflated conceptually even though they have different source-control limits

This creates a weak UX contract. Users who care enough to pick an input source expect the app to either honor that source or clearly explain why it cannot.

## Goals

- Support microphone-device switching across all existing microphone-driven features.
- Remember separate preferred sources for:
  - `dictation`
  - `live_voice`
  - `speech_playground`
- Provide a shared source-resolution layer so WebUI and extension behavior stays aligned.
- Keep inline quick-switch UX near mic controls, with fuller management in settings.
- Allow pragmatic fallback:
  - missing remembered mic device may fall back to default mic
  - share-style sources require explicit re-pick or re-authorization
- Prepare the architecture for WebUI-first share-style capture:
  - `tab_audio`
  - `system_audio`
- Preserve existing dictation diagnostics privacy guarantees.

## Non-Goals

- Guarantee identical share-style capture behavior in the extension for v1.
- Promise that browser-native speech recognition can bind to a selected non-default source.
- Persist or silently reuse an exact tab/window share target across browser sessions.
- Redesign all STT or live voice backend selection logic from scratch.
- Add new backend APIs solely for source selection in the first phase.

## Current State

### Capture Paths

- Dictation uses a mix of browser speech recognition and server STT depending on [useDictationStrategy.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useDictationStrategy.tsx).
- Live voice paths depend on [useMicStream.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useMicStream.ts).
- The Speech playground records directly via `MediaRecorder`.

### Dictation Strategy

The current dictation strategy is backend-oriented:

- requested mode: `auto | server | browser`
- resolved mode: `server | browser | unavailable`

This is appropriate for deciding how transcription should run, but it is not sufficient for deciding which browser capture source should be used.

### Surface Constraints

- WebUI can use standard browser media APIs.
- Extension currently has no explicit `tabCapture` permission in [wxt.config.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/extension/wxt.config.ts).
- Share-style capture is therefore not a safe parity assumption for the extension.

## Proposed Design

### 1. Separate source selection from speech-path selection

Introduce two independent axes.

Capture source:

- `default_mic`
- `mic_device`
- `tab_audio`
- `system_audio`

Speech path:

- `browser_dictation`
- `server_dictation`
- `live_voice_stream`
- `speech_playground_recording`

The system resolves these late into a concrete capture plan. It must not assume that a source choice can always be mapped to every speech path.

Managed capture is an implementation detail used by non-browser speech paths. It should not be stored as a user-facing preference.

### 2. Add a shared audio source subsystem

Create a shared subsystem under `apps/packages/ui/src` for source discovery, preferences, capability checks, and capture-plan resolution.

Recommended units:

- `audio-source-types`
  - canonical enums and payload shapes
- `useAudioSourceCatalog`
  - enumerate `audioinput` devices
  - watch `navigator.mediaDevices.devicechange`
  - surface whether labels are available
  - report runtime support for share-style capture by surface/browser
- `useAudioSourcePreferences`
  - persist separate preferences for `dictation`, `live_voice`, and `speech_playground`
- `resolveAudioCapturePlan(...)`
  - combine feature group, preferred source, preferred speech path, capabilities, and availability into one resolved plan
- adapter families
  - `micCaptureAdapter`
  - `shareCaptureAdapter`
- `audioCaptureSessionCoordinator`
  - arbitrate active capture ownership per surface
  - prevent incompatible simultaneous capture sessions

Mic capture and share capture must be modeled as separate adapter families. They have different permissions, lifecycle rules, and failure states.

### 3. Capability model

Capability must be first-class. Source availability depends on:

- surface
  - `webui`
  - `extension`
- feature group
  - `dictation`
  - `live_voice`
  - `speech_playground`
- secure-context availability
- browser/runtime support
- speech-path compatibility

The capability layer must explicitly treat secure context as a prerequisite where browser APIs require it. Non-localhost HTTP WebUI deployments should fail capability checks early rather than surfacing confusing permission or unsupported-api errors later.

The resolver should return a result such as:

- `supported`
- `fallback_to_default_mic`
- `requires_repick`
- `incompatible_speech_path`
- `unavailable`

This keeps policy centralized and testable.

### 3a. Capture-session arbitration

The shared subsystem should include one capture-session coordinator so that:

- only one microphone or share-style input capture session is active per surface unless a feature explicitly supports coexistence
- starting one capture path can stop or block another in a predictable way
- dictation, live voice, and speech-playground capture do not race each other for the same device or permission prompt

This coordinator should be part of the design contract, not left to feature-local hook logic.

### 4. Hard compatibility rules

These rules are mandatory for v1:

- `browser_dictation` is compatible only with `default_mic`.
- Any explicit non-default source (`mic_device`, `tab_audio`, `system_audio`) must resolve away from `browser_dictation` and into a managed-capture speech path.
- If the user requests browser dictation while a non-default source is selected, the UI must show the resolved behavior rather than pretending the browser bound the source.
- Missing remembered `mic_device` may fall back to `default_mic`.
- Missing or expired `tab_audio` or `system_audio` capture must require re-pick or re-authorization.
- Share-style preferences remember the source class, not an exact reusable target.
- Extension v1 supports microphone-device switching, but share-style capture remains unsupported and must be hidden or disabled there.

### 5. Persistence model

Persist source preferences per feature group rather than globally.

Recommended stored shape:

```ts
type StoredAudioSourcePreference = {
  featureGroup: "dictation" | "live_voice" | "speech_playground"
  sourceKind: "default_mic" | "mic_device" | "tab_audio" | "system_audio"
  deviceId?: string
  lastKnownLabel?: string
}
```

Do not persist only a raw `deviceId`. Best-effort rematching should use both identifier and label context where available.

`deviceId` should be treated as an opaque hint, not a durable identity guarantee. Permissions, browser policies, or origin changes may invalidate it.

### 6. Feature integration

Existing hooks remain consumers of the new subsystem.

Hooks to adapt:

- [useServerDictation.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useServerDictation.tsx)
- [useSpeechRecognition.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useSpeechRecognition.tsx)
- [useMicStream.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useMicStream.ts)
- [useAudioRecorder.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useAudioRecorder.ts)
- [useVoiceChatStream.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useVoiceChatStream.tsx)
- [usePersonaLiveVoiceController.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx)

Expected behavior by feature:

- Dictation
  - `default_mic` may use browser dictation or server dictation based on existing strategy.
  - `mic_device`, `tab_audio`, and `system_audio` must resolve away from `browser_dictation` and into a managed-capture dictation path.
- Live voice
  - always uses a managed-capture speech path
  - source resolver decides which capture adapter to use
- Speech playground
  - can expose the widest source options first
  - acts as the first proving ground for share-style capture in WebUI

### 7. UX model

Use a hybrid model.

Inline UX:

- add a compact source picker near existing mic or dictation controls
- allow quick switching between compatible sources
- show requested source and resolved active source if they differ

Settings UX:

- add a fuller source-management section under speech settings
- allow one remembered source per feature group
- expose richer explanations, compatibility notes, and fallback rules

Unsupported options:

- WebUI may expose share-style sources when supported
- extension v1 must not expose share-style sources as active selectable options

Example mismatch messaging:

- Requested: USB microphone
- Active: default microphone
- Reason: browser dictation cannot bind a specific input device

### 8. Error handling and recovery

Recovery rules:

- missing remembered mic device
  - fall back to default mic
  - show a non-blocking notice
- missing or expired share-style source
  - require re-pick or re-authorization
  - do not silently switch to another share source
- incompatible speech-path/source combination
  - resolve to a supported managed-capture speech path when safe
  - otherwise block start and explain why
- share-style capture without a usable audio track
  - fail fast with explicit UX copy
  - do not proceed with a silent stream that will produce empty transcripts

Permission behavior:

- do not request capture permissions on page load
- request permissions only when the user starts capture or initiates a share flow
- if labels are unavailable before permission grant, show generic device entries until access is granted

### 9. Live voice anti-loop protections

Share-style capture creates a self-capture risk for live voice because assistant playback may feed back into the active source.

The design must include anti-loop policy before share-style live voice is enabled:

- detect when share-style capture is active
- restrict or modify playback behavior while that source is active
- prefer conservative v1 behavior, for example:
  - disable spoken playback while share-style capture is active, or
  - force text-only assistant output until the turn ends

This should be explicit product behavior, not a best-effort side effect.

### 10. Diagnostics and privacy

Extend the existing dictation diagnostics model rather than creating a separate telemetry shape.

If the new fields materially change the diagnostics contract, bump the event schema version rather than silently redefining version `1`.

Diagnostics should include:

- feature group
- requested source kind
- resolved source kind
- requested speech path
- resolved speech path
- fallback or incompatibility reason
- permission outcome

Diagnostics must not include:

- transcript text
- prompt text
- raw audio payloads
- sensitive persistent device details beyond what is required locally for UI state

## Architecture

### Dictation with default mic

1. User opens the inline source picker or relies on remembered `dictation` preference.
2. Resolver loads source preference and current dictation speech-path preference.
3. If source is `default_mic`, existing dictation strategy may resolve to browser or server path.
4. Feature starts the resolved capture plan.
5. Diagnostics record requested vs resolved source and speech path.

### Dictation with explicit mic device

1. User chooses a specific microphone for `dictation`.
2. Resolver sees `mic_device`.
3. Resolver marks `browser_dictation` incompatible with the requested source.
4. Feature starts a managed-capture dictation path using `getUserMedia({ audio: { deviceId } })`.
5. UI reflects that the speech path changed to honor the requested source.

### WebUI share-style capture

1. User chooses `tab_audio` or `system_audio` for `speech_playground` or another enabled feature.
2. Resolver checks WebUI capability and feature-specific safety rules.
3. Share capture adapter starts browser share flow.
4. Adapter validates that the returned stream contains a usable audio track and excludes unnecessary video from downstream processing.
5. If the browser returns no usable audio track, the feature fails clearly instead of pretending share-audio capture started.
6. Capture target is treated as session-scoped.
7. If permission expires or the source ends, the feature requires explicit re-pick.

## Testing

### Unit tests

- resolver matrix tests:
  - source preference x speech-path preference x capability x surface -> resolved plan
- preference persistence tests:
  - per-feature-group storage
  - missing device rematch
  - default-mic fallback
- adapter tests:
  - mic capture setup and teardown
  - share capture setup and teardown
  - permission-denied and source-ended behavior
  - returned share stream missing an audio track
  - returned share stream including audio plus video
- capture coordinator tests:
  - second capture request is blocked or cleanly hands off ownership
  - feature shutdown releases capture ownership

### Integration tests

- Playground and sidepanel dictation continue to share the same dictation path while also applying source resolution.
- Live voice hooks consume the shared source preference model and do not bypass it.
- Settings changes propagate correctly to inline source pickers and feature startup behavior.
- capture ownership stays coherent when switching between dictation and live voice.

### E2E coverage

- microphone-device switching on supported browsers
- missing remembered mic device falls back to default mic with visible notice
- extension does not expose share-style capture as an active option in v1
- browser dictation does not falsely claim explicit non-default source binding
- live voice anti-loop protections engage when share-style capture is active
- insecure WebUI deployments fail capability checks for browser capture features with clear guidance

### Safety checks

- diagnostics do not log transcript or raw audio data
- existing dictation auto-fallback behavior remains correct after source resolution is added
- unsupported source/speech-path combinations fail clearly rather than silently degrading

## Rollout

### Phase 1: microphone-device switching everywhere

- add shared source catalog and per-feature preferences
- support `default_mic` and `mic_device`
- enable across WebUI and extension

### Phase 2: shared resolver-backed UX completion

- add inline quick-switch controls
- add full settings management
- add requested vs resolved source status messaging
- add capture-session arbitration so feature switching is deterministic

### Phase 3: WebUI-first share-style capture

- enable `tab_audio` and `system_audio` for the Speech playground first
- add anti-loop protections before live voice support
- gate rollout behind an explicit feature flag or staged exposure

### Phase 4: evaluate extension share capture later

- assess extension permissions, browser support, and UX cost
- do not promise parity until those constraints are validated

## Decision Summary

- Scope: all microphone-driven features
- Persistence: separate remembered source per feature group
- UX: hybrid inline quick-switch plus settings management
- Fallback: missing mic devices may fall back to default mic; share-style sources require re-pick
- Delivery: microphone-device switching everywhere first; share-style capture WebUI-first
