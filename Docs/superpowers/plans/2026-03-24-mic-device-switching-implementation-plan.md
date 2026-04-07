# Mic Device Switching Everywhere Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add shared microphone-device switching across dictation, live voice, and the Speech playground in both WebUI and extension, with per-feature remembered preferences and deterministic capture ownership.

**Architecture:** Add a small shared audio-source subsystem that keeps `capture source` separate from existing dictation speech-path selection. The first implementation slice supports `default_mic` and `mic_device` everywhere, routes non-default dictation away from browser speech recognition when necessary, and adds a capture-session coordinator so mic-driven features do not fight each other. WebUI share-style capture (`tab_audio`, `system_audio`) remains a follow-up plan after this rollout is stable.

**Tech Stack:** React 18, TypeScript, MediaDevices API, MediaRecorder, AudioContext, Web Speech API, Plasmo storage hooks, WXT extension surface, Vitest, Playwright

---

## Scope Note

This plan intentionally implements Phase 1 and Phase 2 of the approved design spec in [2026-03-24-audio-input-source-switching-design.md](/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/superpowers/specs/2026-03-24-audio-input-source-switching-design.md):

- shared resolver/coordinator foundation
- microphone-device switching everywhere
- per-feature remembered preferences
- inline picker plus settings management

This plan does **not** implement WebUI share-style capture yet. The types and resolver should leave room for `tab_audio` and `system_audio`, but the shipped behavior in this plan is mic-only.

## File Structure

- `apps/packages/ui/src/audio/source-types.ts`
  Purpose: canonical source, feature-group, and speech-path types shared across hooks and UI.
- `apps/packages/ui/src/audio/index.ts`
  Purpose: stable barrel export for the new audio-source subsystem so tests and consumers can import a small surface.
- `apps/packages/ui/src/audio/resolve-audio-capture-plan.ts`
  Purpose: central policy for `requested source + requested speech path + capabilities -> resolved plan`.
- `apps/packages/ui/src/audio/audio-capture-session-coordinator.ts`
  Purpose: arbitrate active capture ownership so dictation, live voice, and speech-playground recording do not overlap unpredictably.
- `apps/packages/ui/src/audio/__tests__/resolve-audio-capture-plan.test.ts`
  Purpose: lock resolver behavior for default-mic vs explicit-mic requests and browser-dictation incompatibility.
- `apps/packages/ui/src/audio/__tests__/audio-capture-session-coordinator.test.ts`
  Purpose: lock capture ownership handoff and release behavior.
- `apps/packages/ui/src/hooks/useAudioSourceCatalog.tsx`
  Purpose: enumerate available `audioinput` devices, normalize labels, and react to `devicechange`.
- `apps/packages/ui/src/hooks/useAudioSourcePreferences.tsx`
  Purpose: persist one remembered mic-source preference per feature group using storage-backed keys.
- `apps/packages/ui/src/hooks/__tests__/useAudioSourcePreferences.test.tsx`
  Purpose: verify per-feature persistence and default values.
- `apps/packages/ui/src/components/Common/AudioSourcePicker.tsx`
  Purpose: reusable compact picker for default mic vs explicit devices.
- `apps/packages/ui/src/components/Common/__tests__/AudioSourcePicker.test.tsx`
  Purpose: verify picker rendering, disabled states, and requested/resolved mismatch messaging.
- `apps/packages/ui/src/components/Option/Settings/SSTSettings.tsx`
  Purpose: expose full source management in speech settings.
- `apps/packages/ui/src/assets/locale/en/settings.json`
  Purpose: source-management strings for settings.
- `apps/packages/ui/src/assets/locale/en/playground.json`
  Purpose: inline picker, mismatch, and fallback strings for chat/speech surfaces.
- `apps/packages/ui/src/hooks/useDictationStrategy.tsx`
  Purpose: incorporate source compatibility so browser dictation is only chosen when the selected source is actually compatible.
- `apps/packages/ui/src/hooks/__tests__/useDictationStrategy.test.tsx`
  Purpose: lock source-aware dictation resolution and fallback behavior.
- `apps/packages/ui/src/hooks/useMicStream.ts`
  Purpose: capture PCM from the requested microphone device instead of always using the browser default.
- `apps/packages/ui/src/hooks/useAudioRecorder.ts`
  Purpose: record the requested microphone device for speech-playground capture.
- `apps/packages/ui/src/hooks/useServerDictation.tsx`
  Purpose: record server-dictation audio from the requested microphone device and surface consistent source-related errors.
- `apps/packages/ui/src/hooks/__tests__/useMicStream.test.tsx`
  Purpose: verify `getUserMedia` constraints, teardown, and capture ownership release for streamed mic audio.
- `apps/packages/ui/src/hooks/__tests__/useAudioRecorder.test.ts`
  Purpose: verify selected-device constraints for clip recording.
- `apps/packages/ui/src/hooks/__tests__/useServerDictation.source.test.tsx`
  Purpose: verify server dictation honors selected-device constraints and source-related failures.
- `apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx`
  Purpose: become the first full surface using the shared mic-source picker and remembered `speech_playground` preference.
- `apps/packages/ui/src/components/Option/Speech/__tests__/SpeechPlaygroundPage.render.test.tsx`
  Purpose: keep render contract stable after adding source UI.
- `apps/packages/ui/src/components/Option/Speech/__tests__/SpeechPlaygroundPage.audio-source.test.tsx`
  Purpose: verify source selection, fallback, and requested/resolved status in the speech playground.
- `apps/packages/ui/src/components/Option/Playground/hooks/usePlaygroundVoiceChat.ts`
  Purpose: resolve dictation capture plans for the main Playground chat.
- `apps/packages/ui/src/components/Sidepanel/Chat/form.tsx`
  Purpose: resolve dictation and live-voice mic plans in the extension/WebUI sidepanel surface.
- `apps/packages/ui/src/utils/dictation-diagnostics.ts`
  Purpose: bump diagnostics schema and include requested/resolved source fields without leaking sensitive content.
- `apps/packages/ui/src/utils/__tests__/dictation-diagnostics.test.ts`
  Purpose: lock the schema bump and new source fields.
- `apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.image-refine.integration.test.tsx`
  Purpose: keep the Playground dictation integration honest when a non-default mic is selected.
- `apps/packages/ui/src/components/Option/Playground/__tests__/dictation.cross-surface.contract.test.ts`
  Purpose: ensure Playground and Sidepanel stay on the same shared dictation path.
- `apps/packages/ui/src/hooks/useVoiceChatStream.tsx`
  Purpose: route live-voice streaming through the selected microphone device and capture-session coordinator.
- `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`
  Purpose: apply the shared mic-source model to persona live voice.
- `apps/packages/ui/src/hooks/__tests__/useVoiceChatStream.interrupt.test.tsx`
  Purpose: retain existing interrupt behavior while source selection is added.
- `apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx`
  Purpose: verify live-voice startup and restart behavior still works when a selected mic is in play.
- `apps/extension/tests/e2e/sidepanel-dictation-fallback.spec.ts`
  Purpose: verify sidepanel dictation still falls back correctly after source-aware changes.
- `apps/extension/tests/e2e/speech-playground.spec.ts`
  Purpose: verify extension speech playground exposes mic-device switching without surfacing unsupported share capture.
- `apps/tldw-frontend/e2e/workflows/tier-2-features/speech-playground.spec.ts`
  Purpose: verify WebUI speech playground mic-device switching.
- `apps/tldw-frontend/e2e/smoke/stage7-audio-regression.spec.ts`
  Purpose: keep broader audio regressions under watch.
- `Docs/User_Guides/WebUI_Extension/Dictation_Strategy_and_Settings.md`
  Purpose: document per-feature mic selection and the browser-dictation limitation for explicit device requests.
- `Docs/Published/User_Guides/WebUI_Extension/Dictation_Strategy_and_Settings.md`
  Purpose: keep the published docs mirror aligned if this repo expects checked-in published copies.

## Task 1: Build the shared source model, resolver, and capture coordinator

**Files:**
- Create: `apps/packages/ui/src/audio/source-types.ts`
- Create: `apps/packages/ui/src/audio/index.ts`
- Create: `apps/packages/ui/src/audio/resolve-audio-capture-plan.ts`
- Create: `apps/packages/ui/src/audio/audio-capture-session-coordinator.ts`
- Create: `apps/packages/ui/src/audio/__tests__/resolve-audio-capture-plan.test.ts`
- Create: `apps/packages/ui/src/audio/__tests__/audio-capture-session-coordinator.test.ts`
- Modify: `apps/packages/ui/src/hooks/useDictationStrategy.tsx`
- Modify: `apps/packages/ui/src/hooks/__tests__/useDictationStrategy.test.tsx`

- [ ] **Step 1: Write the failing foundation tests**

```ts
import { describe, expect, it } from "vitest"
import {
  createAudioCaptureSessionCoordinator,
  resolveAudioCapturePlan
} from "@/audio"

describe("resolveAudioCapturePlan", () => {
  it("forces browser dictation off when a non-default mic is selected", () => {
    const plan = resolveAudioCapturePlan({
      featureGroup: "dictation",
      requestedSource: { sourceKind: "mic_device", deviceId: "usb-1" },
      requestedSpeechPath: "browser_dictation",
      capabilities: {
        browserDictationSupported: true,
        serverDictationSupported: true,
        liveVoiceSupported: true,
        secureContextAvailable: true
      }
    })

    expect(plan.requestedSourceKind).toBe("mic_device")
    expect(plan.resolvedSpeechPath).toBe("server_dictation")
    expect(plan.reason).toBe("browser_dictation_incompatible_with_selected_source")
  })
})

describe("audioCaptureSessionCoordinator", () => {
  it("hands off ownership when a second feature claims capture", () => {
    const coordinator = createAudioCaptureSessionCoordinator()
    coordinator.claim("dictation")
    expect(coordinator.claim("live_voice").ownerBeforeClaim).toBe("dictation")
    expect(coordinator.getActiveOwner()).toBe("live_voice")
  })
})
```

Add a `useDictationStrategy` test that passes a source-compatibility flag and expects browser mode to be ruled out for explicit devices.

- [ ] **Step 2: Run the failing foundation tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  ../packages/ui/src/audio/__tests__/resolve-audio-capture-plan.test.ts \
  ../packages/ui/src/audio/__tests__/audio-capture-session-coordinator.test.ts \
  ../packages/ui/src/hooks/__tests__/useDictationStrategy.test.tsx \
  --reporter=verbose
```

Expected: FAIL with missing-module or missing-export errors for the new audio source modules, plus source-awareness assertion failures in `useDictationStrategy`.

- [ ] **Step 3: Implement the shared model**

```ts
export type AudioSourceKind = "default_mic" | "mic_device" | "tab_audio" | "system_audio"
export type AudioFeatureGroup = "dictation" | "live_voice" | "speech_playground"
export type AudioSpeechPath =
  | "browser_dictation"
  | "server_dictation"
  | "live_voice_stream"
  | "speech_playground_recording"

export function resolveAudioCapturePlan(input: ResolveAudioCapturePlanInput): ResolvedAudioCapturePlan {
  if (input.requestedSource.sourceKind === "mic_device" && input.requestedSpeechPath === "browser_dictation") {
    return {
      requestedSourceKind: "mic_device",
      resolvedSourceKind: "mic_device",
      requestedSpeechPath: "browser_dictation",
      resolvedSpeechPath: input.capabilities.serverDictationSupported ? "server_dictation" : "browser_dictation",
      reason: input.capabilities.serverDictationSupported
        ? "browser_dictation_incompatible_with_selected_source"
        : "selected_source_unavailable"
    }
  }
  // keep default-mic behavior aligned with current dictation strategy
}
```

`useDictationStrategy` should accept a new source-compatibility input, for example `browserDictationCompatible: boolean`, and use it during resolved-mode/toggle-intent calculation instead of assuming browser mode is always viable when the API exists.

Implement a coordinator that exposes `claim`, `release`, and `getActiveOwner`, and keep it framework-agnostic so hooks can share it without React-specific state.

- [ ] **Step 4: Re-run the foundation tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  ../packages/ui/src/audio/__tests__/resolve-audio-capture-plan.test.ts \
  ../packages/ui/src/audio/__tests__/audio-capture-session-coordinator.test.ts \
  ../packages/ui/src/hooks/__tests__/useDictationStrategy.test.tsx \
  --reporter=verbose
```

Expected: PASS for resolver, coordinator, and source-aware dictation strategy behavior.

- [ ] **Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/audio/source-types.ts \
  apps/packages/ui/src/audio/index.ts \
  apps/packages/ui/src/audio/resolve-audio-capture-plan.ts \
  apps/packages/ui/src/audio/audio-capture-session-coordinator.ts \
  apps/packages/ui/src/audio/__tests__/resolve-audio-capture-plan.test.ts \
  apps/packages/ui/src/audio/__tests__/audio-capture-session-coordinator.test.ts \
  apps/packages/ui/src/hooks/useDictationStrategy.tsx \
  apps/packages/ui/src/hooks/__tests__/useDictationStrategy.test.tsx
git commit -m "feat: add shared audio capture plan resolver"
```

## Task 2: Add storage-backed source preferences, device catalog, and reusable picker UI

**Files:**
- Create: `apps/packages/ui/src/hooks/useAudioSourceCatalog.tsx`
- Create: `apps/packages/ui/src/hooks/useAudioSourcePreferences.tsx`
- Create: `apps/packages/ui/src/hooks/__tests__/useAudioSourcePreferences.test.tsx`
- Create: `apps/packages/ui/src/components/Common/AudioSourcePicker.tsx`
- Create: `apps/packages/ui/src/components/Common/__tests__/AudioSourcePicker.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/Settings/SSTSettings.tsx`
- Modify: `apps/packages/ui/src/assets/locale/en/settings.json`
- Modify: `apps/packages/ui/src/assets/locale/en/playground.json`

- [ ] **Step 1: Write the failing preference and picker tests**

```tsx
import { act, renderHook } from "@testing-library/react"
import { render, screen } from "@testing-library/react"
import { beforeEach, vi } from "vitest"

const { storageValues, useStorageMock } = vi.hoisted(() => ({
  storageValues: new Map<string, unknown>(),
  useStorageMock: vi.fn()
}))

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: useStorageMock
}))

beforeEach(() => {
  storageValues.clear()
  useStorageMock.mockImplementation((key: string, defaultValue: unknown) => [
    storageValues.has(key) ? storageValues.get(key) : defaultValue,
    (nextValue: unknown) => storageValues.set(key, nextValue),
    { isLoading: false }
  ])
})

it("stores separate source preferences for dictation and live voice", () => {
  const { result } = renderHook(() => useAudioSourcePreferences("dictation"))
  act(() => {
    result.current.setPreference({
      featureGroup: "dictation",
      sourceKind: "mic_device",
      deviceId: "usb-1",
      lastKnownLabel: "USB microphone"
    })
  })
  expect(storageValues.get("dictationAudioSourcePreference")).toMatchObject({
    sourceKind: "mic_device",
    deviceId: "usb-1"
  })
  expect(storageValues.has("liveVoiceAudioSourcePreference")).toBe(false)
})

it("renders default mic plus enumerated devices", () => {
  render(
    <AudioSourcePicker
      requestedSourceKind="default_mic"
      resolvedSourceKind="default_mic"
      devices={[
        { deviceId: "default", label: "Default microphone" },
        { deviceId: "usb-1", label: "USB microphone" }
      ]}
    />
  )

  expect(screen.getByText("Default microphone")).toBeInTheDocument()
  expect(screen.getByText("USB microphone")).toBeInTheDocument()
})
```

Add a settings test assertion that the speech settings surface now includes a source-management section.

- [ ] **Step 2: Run the failing preference and picker tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  ../packages/ui/src/hooks/__tests__/useAudioSourcePreferences.test.tsx \
  ../packages/ui/src/components/Common/__tests__/AudioSourcePicker.test.tsx \
  --reporter=verbose
```

Expected: FAIL because the hooks and picker do not exist yet, and the speech settings surface does not expose source-management UI.

- [ ] **Step 3: Implement storage and UI**

```ts
const STORAGE_KEYS = {
  dictation: "dictationAudioSourcePreference",
  live_voice: "liveVoiceAudioSourcePreference",
  speech_playground: "speechPlaygroundAudioSourcePreference"
} as const

export function useAudioSourcePreferences(featureGroup: AudioFeatureGroup) {
  const [value, setValue] = useStorage<StoredAudioSourcePreference | null>(
    STORAGE_KEYS[featureGroup],
    { featureGroup, sourceKind: "default_mic" }
  )
  return { preference: value, setPreference: setValue }
}
```

`useAudioSourceCatalog` should:

- call `navigator.mediaDevices.enumerateDevices()`
- filter to `audioinput`
- normalize missing labels to safe placeholders
- subscribe to `devicechange`

`AudioSourcePicker` should be intentionally small:

- current source select
- optional mismatch badge when requested and resolved differ
- no share-style choices yet

Update `SSTSettings.tsx` so the user can set a default mic source for each feature group without duplicating storage code in three places.

- [ ] **Step 4: Re-run the preference and picker tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  ../packages/ui/src/hooks/__tests__/useAudioSourcePreferences.test.tsx \
  ../packages/ui/src/components/Common/__tests__/AudioSourcePicker.test.tsx \
  --reporter=verbose
```

Expected: PASS with storage-backed per-feature preferences and visible picker/settings UI.

- [ ] **Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/hooks/useAudioSourceCatalog.tsx \
  apps/packages/ui/src/hooks/useAudioSourcePreferences.tsx \
  apps/packages/ui/src/hooks/__tests__/useAudioSourcePreferences.test.tsx \
  apps/packages/ui/src/components/Common/AudioSourcePicker.tsx \
  apps/packages/ui/src/components/Common/__tests__/AudioSourcePicker.test.tsx \
  apps/packages/ui/src/components/Option/Settings/SSTSettings.tsx \
  apps/packages/ui/src/assets/locale/en/settings.json \
  apps/packages/ui/src/assets/locale/en/playground.json
git commit -m "feat: add speech input source preferences"
```

## Task 3: Teach low-level recording hooks to honor the selected microphone device

**Files:**
- Modify: `apps/packages/ui/src/hooks/useMicStream.ts`
- Modify: `apps/packages/ui/src/hooks/useAudioRecorder.ts`
- Modify: `apps/packages/ui/src/hooks/useServerDictation.tsx`
- Create: `apps/packages/ui/src/hooks/__tests__/useMicStream.test.tsx`
- Modify: `apps/packages/ui/src/hooks/__tests__/useAudioRecorder.test.ts`
- Create: `apps/packages/ui/src/hooks/__tests__/useServerDictation.source.test.tsx`

- [ ] **Step 1: Write the failing low-level hook tests**

```tsx
it("passes the selected deviceId to getUserMedia for PCM streaming", async () => {
  const mockGetUserMedia = vi.fn(async () => mockStream())
  vi.stubGlobal("navigator", {
    mediaDevices: { getUserMedia: mockGetUserMedia }
  })

  const { result } = renderHook(() => useMicStream(vi.fn()))
  await result.current.start({ deviceId: "usb-1" })

  expect(mockGetUserMedia).toHaveBeenCalledWith({
    audio: { deviceId: { exact: "usb-1" } }
  })
})

it("records server dictation from the selected mic device", async () => {
  await result.current.startServerDictation({ sourceKind: "mic_device", deviceId: "usb-1" })
  expect(mockGetUserMedia).toHaveBeenCalledWith({
    audio: { deviceId: { exact: "usb-1" } }
  })
})
```

Also add a test where `deviceId` is absent and the hooks still fall back to `audio: true`.

- [ ] **Step 2: Run the failing low-level hook tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  ../packages/ui/src/hooks/__tests__/useMicStream.test.tsx \
  ../packages/ui/src/hooks/__tests__/useAudioRecorder.test.ts \
  ../packages/ui/src/hooks/__tests__/useServerDictation.source.test.tsx \
  --reporter=verbose
```

Expected: FAIL because the hooks currently hard-code `getUserMedia({ audio: true })`.

- [ ] **Step 3: Implement selected-device support**

```ts
type MicCaptureOptions = {
  deviceId?: string | null
}

function buildAudioConstraints(deviceId?: string | null): MediaStreamConstraints["audio"] {
  return deviceId ? { deviceId: { exact: deviceId } } : true
}

const stream = await navigator.mediaDevices.getUserMedia({
  audio: buildAudioConstraints(options.deviceId)
})
```

Apply the same constraint builder in `useMicStream`, `useAudioRecorder`, and `useServerDictation`, and add coordinator claim/release calls so only one capture owner is active at a time.

- [ ] **Step 4: Re-run the low-level hook tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  ../packages/ui/src/hooks/__tests__/useMicStream.test.tsx \
  ../packages/ui/src/hooks/__tests__/useAudioRecorder.test.ts \
  ../packages/ui/src/hooks/__tests__/useServerDictation.source.test.tsx \
  --reporter=verbose
```

Expected: PASS with explicit-device constraints and default-mic fallback behavior.

- [ ] **Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/hooks/useMicStream.ts \
  apps/packages/ui/src/hooks/useAudioRecorder.ts \
  apps/packages/ui/src/hooks/useServerDictation.tsx \
  apps/packages/ui/src/hooks/__tests__/useMicStream.test.tsx \
  apps/packages/ui/src/hooks/__tests__/useAudioRecorder.test.ts \
  apps/packages/ui/src/hooks/__tests__/useServerDictation.source.test.tsx
git commit -m "feat: route audio capture through selected mic devices"
```

## Task 4: Integrate mic-device switching into the Speech playground

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx`
- Modify: `apps/packages/ui/src/components/Option/Speech/__tests__/SpeechPlaygroundPage.render.test.tsx`
- Create: `apps/packages/ui/src/components/Option/Speech/__tests__/SpeechPlaygroundPage.audio-source.test.tsx`

- [ ] **Step 1: Write the failing Speech playground tests**

Reuse the `storageValues`-backed `useStorage` mock pattern from Task 2 in these surface tests so the remembered mic preference is explicit in the fixture.

```tsx
it("shows the shared audio source picker in the speech playground", async () => {
  render(<SpeechPlaygroundPage />)
  expect(screen.getByLabelText("Speech playground input source")).toBeInTheDocument()
})

it("uses the remembered speech_playground mic preference when recording starts", async () => {
  storageValues.set("speechPlaygroundAudioSourcePreference", {
    featureGroup: "speech_playground",
    sourceKind: "mic_device",
    deviceId: "usb-1",
    lastKnownLabel: "USB microphone"
  })
  render(<SpeechPlaygroundPage />)
  await user.click(screen.getByRole("button", { name: /start dictation/i }))
  expect(mockGetUserMedia).toHaveBeenCalledWith({
    audio: { deviceId: { exact: "usb-1" } }
  })
})
```

- [ ] **Step 2: Run the failing Speech playground tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  ../packages/ui/src/components/Option/Speech/__tests__/SpeechPlaygroundPage.render.test.tsx \
  ../packages/ui/src/components/Option/Speech/__tests__/SpeechPlaygroundPage.audio-source.test.tsx \
  --reporter=verbose
```

Expected: FAIL because the speech playground has no source picker and still uses the default mic implicitly.

- [ ] **Step 3: Implement the Speech playground wiring**

```tsx
const { preference, setPreference } = useAudioSourcePreferences("speech_playground")
const { devices } = useAudioSourceCatalog()
const resolvedSource =
  preference.sourceKind === "mic_device" &&
  !devices.some((device) => device.deviceId === preference.deviceId)
    ? { sourceKind: "default_mic" as const }
    : preference

const capturePlan = resolveAudioCapturePlan({
  featureGroup: "speech_playground",
  requestedSource: preference,
  requestedSpeechPath: "speech_playground_recording",
  capabilities
})

<AudioSourcePicker
  ariaLabel={t("playground:stt.sourcePickerLabel", "Speech playground input source")}
  devices={devices}
  requestedSourceKind={preference.sourceKind}
  resolvedSourceKind={resolvedSource.sourceKind}
  onChange={setPreference}
/>
```

Update the record/transcribe flows so they pass `capturePlan.deviceId` into `useAudioRecorder` and any server-dictation entry point the page uses.

- [ ] **Step 4: Re-run the Speech playground tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  ../packages/ui/src/components/Option/Speech/__tests__/SpeechPlaygroundPage.render.test.tsx \
  ../packages/ui/src/components/Option/Speech/__tests__/SpeechPlaygroundPage.audio-source.test.tsx \
  --reporter=verbose
```

Expected: PASS with source picker rendering and selected-device wiring.

- [ ] **Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx \
  apps/packages/ui/src/components/Option/Speech/__tests__/SpeechPlaygroundPage.render.test.tsx \
  apps/packages/ui/src/components/Option/Speech/__tests__/SpeechPlaygroundPage.audio-source.test.tsx
git commit -m "feat: add mic source switching to speech playground"
```

## Task 5: Integrate source-aware dictation into Playground and Sidepanel, and bump diagnostics

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Playground/hooks/usePlaygroundVoiceChat.ts`
- Modify: `apps/packages/ui/src/components/Sidepanel/Chat/form.tsx`
- Modify: `apps/packages/ui/src/utils/dictation-diagnostics.ts`
- Modify: `apps/packages/ui/src/utils/__tests__/dictation-diagnostics.test.ts`
- Modify: `apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.image-refine.integration.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/__tests__/dictation.cross-surface.contract.test.ts`

- [ ] **Step 1: Write the failing dictation integration tests**

Reuse the `storageValues` map-based `useStorage` mock pattern from Task 2 so the dictation source preference is seeded through the same mechanism the app uses at runtime.

```tsx
it("routes explicit mic selection away from browser dictation", async () => {
  storageValues.set("dictationAudioSourcePreference", {
    featureGroup: "dictation",
    sourceKind: "mic_device",
    deviceId: "usb-1",
    lastKnownLabel: "USB microphone"
  })

  render(<PlaygroundForm {...props} />)
  await user.click(screen.getByTestId("dictation-button"))

  expect(startSpeechRecognitionMock).not.toHaveBeenCalled()
  expect(startServerDictationMock).toHaveBeenCalledWith(
    expect.objectContaining({ deviceId: "usb-1" })
  )
})

it("emits diagnostics version 2 with requested and resolved source fields", () => {
  const payload = sanitizeDictationDiagnosticsPayload({
    surface: "playground",
    kind: "toggle",
    requestedMode: "browser",
    resolvedMode: "server",
    requestedSourceKind: "mic_device",
    resolvedSourceKind: "mic_device"
  } as any)

  expect(payload.version).toBe(2)
  expect(payload.requested_source_kind).toBe("mic_device")
  expect(payload.resolved_source_kind).toBe("mic_device")
})
```

Update the cross-surface contract test so it asserts that both the Playground and Sidepanel use the shared source preference and source-aware dictation path.

- [ ] **Step 2: Run the failing dictation integration tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  ../packages/ui/src/utils/__tests__/dictation-diagnostics.test.ts \
  ../packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.image-refine.integration.test.tsx \
  ../packages/ui/src/components/Option/Playground/__tests__/dictation.cross-surface.contract.test.ts \
  --reporter=verbose
```

Expected: FAIL because dictation surfaces still assume browser dictation is viable whenever the API exists, and diagnostics are still version `1`.

- [ ] **Step 3: Implement source-aware dictation wiring**

```ts
const plan = resolveAudioCapturePlan({
  featureGroup: "dictation",
  requestedSource: dictationSourcePreference,
  requestedSpeechPath: dictationModeOverride === "browser" ? "browser_dictation" : "server_dictation",
  capabilities
})

const browserDictationCompatible = plan.resolvedSpeechPath === "browser_dictation"
const dictationStrategy = useDictationStrategy({
  ...existingInputs,
  browserDictationCompatible
})
```

Update `usePlaygroundVoiceChat.ts` and `form.tsx` so:

- the inline picker reads/writes the `dictation` preference
- non-default mic selection suppresses browser speech-recognition start
- server dictation receives the selected `deviceId`
- diagnostics include requested/resolved source fields and use schema version `2`

- [ ] **Step 4: Re-run the dictation integration tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  ../packages/ui/src/utils/__tests__/dictation-diagnostics.test.ts \
  ../packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.image-refine.integration.test.tsx \
  ../packages/ui/src/components/Option/Playground/__tests__/dictation.cross-surface.contract.test.ts \
  --reporter=verbose
```

Expected: PASS with version-2 diagnostics and source-aware dictation routing.

- [ ] **Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/hooks/usePlaygroundVoiceChat.ts \
  apps/packages/ui/src/components/Sidepanel/Chat/form.tsx \
  apps/packages/ui/src/utils/dictation-diagnostics.ts \
  apps/packages/ui/src/utils/__tests__/dictation-diagnostics.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.image-refine.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/dictation.cross-surface.contract.test.ts
git commit -m "feat: add source-aware dictation routing"
```

## Task 6: Integrate mic-device switching into live voice, update docs, and run focused verification

**Files:**
- Modify: `apps/packages/ui/src/hooks/useVoiceChatStream.tsx`
- Modify: `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`
- Modify: `apps/packages/ui/src/hooks/__tests__/useVoiceChatStream.interrupt.test.tsx`
- Modify: `apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx`
- Modify: `apps/extension/tests/e2e/sidepanel-dictation-fallback.spec.ts`
- Modify: `apps/extension/tests/e2e/speech-playground.spec.ts`
- Modify: `apps/tldw-frontend/e2e/workflows/tier-2-features/speech-playground.spec.ts`
- Modify: `apps/tldw-frontend/e2e/smoke/stage7-audio-regression.spec.ts`
- Modify: `Docs/User_Guides/WebUI_Extension/Dictation_Strategy_and_Settings.md`
- Modify: `Docs/Published/User_Guides/WebUI_Extension/Dictation_Strategy_and_Settings.md`

- [ ] **Step 1: Write the failing live-voice and focused end-to-end assertions**

Reuse the `storageValues` map-based `useStorage` mock pattern from Task 2 for the live-voice preference fixture instead of inventing a test-only storage helper.

```tsx
it("starts live voice with the remembered live_voice mic device", async () => {
  storageValues.set("liveVoiceAudioSourcePreference", {
    featureGroup: "live_voice",
    sourceKind: "mic_device",
    deviceId: "usb-1",
    lastKnownLabel: "USB microphone"
  })

  const { result } = renderHook(() => useVoiceChatStream({ active: true }))
  await act(async () => {
    await result.current.start()
  })

  expect(mockGetUserMedia).toHaveBeenCalledWith({
    audio: { deviceId: { exact: "usb-1" } }
  })
})
```

Add or update Playwright assertions so:

- the speech playground exposes a mic-device picker
- extension surfaces do not expose active `tab_audio` / `system_audio` options
- sidepanel dictation fallback still works after the selected-device changes

- [ ] **Step 2: Run the failing live-voice tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  ../packages/ui/src/hooks/__tests__/useVoiceChatStream.interrupt.test.tsx \
  ../packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx \
  --reporter=verbose
```

Expected: FAIL because live voice still starts `useMicStream` without any selected-device input.

- [ ] **Step 3: Implement live-voice wiring and docs**

```ts
const { preference: liveVoiceSourcePreference } = useAudioSourcePreferences("live_voice")

const liveVoicePlan = resolveAudioCapturePlan({
  featureGroup: "live_voice",
  requestedSource: liveVoiceSourcePreference,
  requestedSpeechPath: "live_voice_stream",
  capabilities
})

await micStart({ deviceId: liveVoicePlan.deviceId })
```

Apply the same selected-device plan in both `useVoiceChatStream.tsx` and `usePersonaLiveVoiceController.tsx`, and make sure both paths claim/release the shared capture coordinator.

Update the docs to explain:

- mic-device switching is available now
- browser dictation cannot honor an explicit non-default source directly
- share-style capture is not yet available in the extension

- [ ] **Step 4: Run focused verification**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  ../packages/ui/src/audio/__tests__/resolve-audio-capture-plan.test.ts \
  ../packages/ui/src/audio/__tests__/audio-capture-session-coordinator.test.ts \
  ../packages/ui/src/hooks/__tests__/useAudioSourcePreferences.test.tsx \
  ../packages/ui/src/components/Common/__tests__/AudioSourcePicker.test.tsx \
  ../packages/ui/src/hooks/__tests__/useMicStream.test.tsx \
  ../packages/ui/src/hooks/__tests__/useAudioRecorder.test.ts \
  ../packages/ui/src/hooks/__tests__/useServerDictation.source.test.tsx \
  ../packages/ui/src/hooks/__tests__/useVoiceChatStream.interrupt.test.tsx \
  ../packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx \
  ../packages/ui/src/utils/__tests__/dictation-diagnostics.test.ts \
  ../packages/ui/src/components/Option/Speech/__tests__/SpeechPlaygroundPage.render.test.tsx \
  ../packages/ui/src/components/Option/Speech/__tests__/SpeechPlaygroundPage.audio-source.test.tsx \
  ../packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.image-refine.integration.test.tsx \
  ../packages/ui/src/components/Option/Playground/__tests__/dictation.cross-surface.contract.test.ts \
  --reporter=verbose
```

Expected: PASS across the focused mic-source suite.

Then run focused browser verification:

```bash
cd apps/tldw-frontend && bunx playwright test \
  e2e/workflows/tier-2-features/speech-playground.spec.ts \
  e2e/smoke/stage7-audio-regression.spec.ts \
  --reporter=line
```

Expected: PASS for speech playground and audio regression coverage.

And extension verification:

```bash
cd apps/extension && bunx playwright test \
  tests/e2e/sidepanel-dictation-fallback.spec.ts \
  tests/e2e/speech-playground.spec.ts \
  --reporter=line
```

Expected: PASS with sidepanel dictation fallback intact and no unsupported share-source UI exposed.

- [ ] **Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/hooks/useVoiceChatStream.tsx \
  apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx \
  apps/packages/ui/src/hooks/__tests__/useVoiceChatStream.interrupt.test.tsx \
  apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx \
  apps/extension/tests/e2e/sidepanel-dictation-fallback.spec.ts \
  apps/extension/tests/e2e/speech-playground.spec.ts \
  apps/tldw-frontend/e2e/workflows/tier-2-features/speech-playground.spec.ts \
  apps/tldw-frontend/e2e/smoke/stage7-audio-regression.spec.ts \
  Docs/User_Guides/WebUI_Extension/Dictation_Strategy_and_Settings.md \
  Docs/Published/User_Guides/WebUI_Extension/Dictation_Strategy_and_Settings.md
git commit -m "feat: add shared mic device switching for speech surfaces"
```

## Execution Notes

- Keep the resolver future-proof for `tab_audio` and `system_audio`, but do not surface those options in v1 UI.
- Do not change `useSpeechRecognition.tsx` unless tests prove that a minimal compatibility hook is insufficient. The preferred approach is to keep browser speech recognition untouched and decide compatibility before calling it.
- Prefer adding small focused files over expanding `form.tsx` and `SpeechPlaygroundPage.tsx` further unless the existing patterns force local wiring.
- If Playwright audio-device control is too flaky in CI, keep E2E assertions focused on visible UI state and mocked `getUserMedia` constraints rather than true hardware switching.
