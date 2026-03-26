# Chat Voice Conversation Transport Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/chat` voice conversation work consistently in the WebUI playground and the extension sidepanel by gating it on the real `/api/v1/audio/chat/stream` transport, running shared startup validation before connect, and preserving transcript/assistant state when the stream fails mid-turn.

**Architecture:** Extend the shared server-capability contract with a strict voice-conversation transport signal that stays conservative when capability discovery falls back to the bundled OpenAPI stub. Add one shared voice-conversation contract module for availability, startup-preflight, and TTS normalization, then route both chat surfaces and `useVoiceChatStream` through that contract so they expose the same reasons, error messages, and turn-finalization behavior without changing the backend transport.

**Tech Stack:** TypeScript, React hooks, `@plasmohq/storage`, shared `apps/packages/ui` services/hooks, Vitest, existing FastAPI websocket tests for `/api/v1/audio/chat/stream`

---

## File Map

- `apps/packages/ui/src/services/tldw/server-capabilities.ts`
  Responsibility: expose both the legacy broad audio flags and the new strict voice-conversation transport flag, including authoritative-vs-fallback source tracking.
- `apps/packages/ui/src/services/__tests__/server-capabilities.test.ts`
  Responsibility: lock the strict transport semantics so `/chat` voice conversation is not inferred from STT+TTS-only specs or the bundled fallback spec.
- `apps/packages/ui/src/services/tldw/voice-conversation.ts`
  Responsibility: hold the shared voice-conversation availability result, startup preflight, and explicit TTS normalization logic used by both surfaces and the stream hook.
- `apps/packages/ui/src/services/__tests__/voice-conversation.test.ts`
  Responsibility: prove the shared contract returns stable reasons and correct browser-provider fallback behavior.
- `apps/packages/ui/src/hooks/useTldwAudioStatus.tsx`
  Responsibility: expose the strict transport signal alongside existing broad audio health fields without regressing current consumers.
- `apps/packages/ui/src/hooks/__tests__/useTldwAudioStatus.test.tsx`
  Responsibility: verify the hook does not light up voice conversation from `hasAudio` or `hasVoiceChat` alone.
- `apps/packages/ui/src/hooks/useVoiceChatStream.tsx`
  Responsibility: run shared preflight before opening the websocket, send the normalized config frame, and surface stable startup/runtime errors.
- `apps/packages/ui/src/hooks/__tests__/useVoiceChatStream.interrupt.test.tsx`
  Responsibility: cover missing auth, backend-default model behavior, provider-resolution failure, invalid TTS config, and disconnect/interrupt handling.
- `apps/packages/ui/src/hooks/useVoiceChatMessages.tsx`
  Responsibility: keep transcript integrity on mid-stream failures by removing empty assistant placeholders or finalizing partial assistant text with interrupted metadata.
- `apps/packages/ui/src/hooks/__tests__/useVoiceChatMessages.test.tsx`
  Responsibility: lock the shared turn-finalization rules for transcript-only, partial-assistant, and fully-complete turns.
- `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
  Responsibility: feed the shared availability result into the playground surface and pass it through to the playground voice controls.
- `apps/packages/ui/src/components/Option/Playground/hooks/usePlaygroundVoiceChat.ts`
  Responsibility: show the shared unavailable reason and stop using a hard-coded transport-missing string.
- `apps/packages/ui/src/components/Sidepanel/Chat/form.tsx`
  Responsibility: use the same shared availability result and same interrupted-turn hook methods as the playground.
- `apps/packages/ui/src/components/Option/Playground/__tests__/voice-conversation.cross-surface.contract.test.ts`
  Responsibility: assert both surfaces call the same shared availability helper and surface the same reason/message contract.

### Task 1: Add a Strict Voice-Conversation Transport Capability

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/server-capabilities.ts`
- Modify: `apps/packages/ui/src/services/__tests__/server-capabilities.test.ts`

- [x] **Step 1: Write the failing capability tests**

```ts
it("keeps legacy hasVoiceChat broad while strict transport stays false for STT+TTS-only specs", async () => {
  mocks.getOpenAPISpec.mockResolvedValue({
    info: { version: "audio-split-stt-tts" },
    paths: {
      "/api/v1/audio/transcriptions": {},
      "/api/v1/audio/speech": {}
    }
  })
  mocks.bgRequest.mockResolvedValue({})

  const { getServerCapabilities } = await importCapabilitiesModule()
  const capabilities = await getServerCapabilities()

  expect(capabilities.hasVoiceChat).toBe(true)
  expect(capabilities.hasVoiceConversationTransport).toBe(false)
  expect(capabilities.specSource).toBe("authoritative")
})

it("does not trust the bundled fallback spec for strict voice conversation transport", async () => {
  mocks.getOpenAPISpec.mockRejectedValue(new Error("openapi unavailable"))
  mocks.bgRequest.mockRejectedValue(new Error("docs-info unavailable"))

  const { getServerCapabilities } = await importCapabilitiesModule()
  const capabilities = await getServerCapabilities({ forceRefresh: true })

  expect(capabilities.hasVoiceChat).toBe(true)
  expect(capabilities.hasVoiceConversationTransport).toBe(false)
  expect(capabilities.specSource).toBe("fallback")
})
```

- [x] **Step 2: Run the focused capability tests and confirm they fail**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/services/__tests__/server-capabilities.test.ts
```

Expected: FAIL because `hasVoiceConversationTransport` and `specSource` do not exist yet, and the current code still infers voice chat from STT+TTS and the bundled fallback spec.

- [x] **Step 3: Implement the minimal strict capability contract**

```ts
export type ServerCapabilities = {
  // existing fields...
  hasVoiceConversationTransport: boolean
  specSource: "authoritative" | "fallback"
}

const computeCapabilities = (
  spec: any | null | undefined,
  specSource: "authoritative" | "fallback"
): ServerCapabilities => {
  const paths = normalizePaths(spec?.paths || {})
  const has = (path: string) => Boolean(paths[path])
  const hasVoiceTransportRoute = has("/api/v1/audio/chat/stream")
  const hasStt = /* existing broad STT logic */
  const hasTts = /* existing broad TTS logic */

  return {
    // existing fields...
    hasVoiceChat: hasVoiceTransportRoute || (hasStt && hasTts),
    hasVoiceConversationTransport:
      specSource === "authoritative" && hasVoiceTransportRoute,
    hasAudio: hasStt || hasTts || hasVoiceTransportRoute,
    specSource
  }
}

const source = spec ? "authoritative" : "fallback"
return applyDocsInfoFeatureGates(computeCapabilities(specToUse, source), docsInfo)
```

Implementation notes:

- Keep `hasVoiceChat` unchanged for broad compatibility.
- Persist `specSource` inside the cached capabilities payload so cached fallback results remain conservative.
- Do not add any new optimistic inference path for `hasVoiceConversationTransport`.

- [x] **Step 4: Re-run the capability tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/services/__tests__/server-capabilities.test.ts
```

Expected: PASS with the new strict transport flag only going true for authoritative `/api/v1/audio/chat/stream` discovery.

- [x] **Step 5: Commit the capability-contract change**

```bash
git add apps/packages/ui/src/services/tldw/server-capabilities.ts apps/packages/ui/src/services/__tests__/server-capabilities.test.ts
git commit -m "fix(chat): add strict voice conversation capability"
```

### Task 2: Create the Shared Voice-Conversation Availability and TTS Contract

**Files:**
- Create: `apps/packages/ui/src/services/tldw/voice-conversation.ts`
- Create: `apps/packages/ui/src/services/__tests__/voice-conversation.test.ts`
- Modify: `apps/packages/ui/src/hooks/useTldwAudioStatus.tsx`
- Modify: `apps/packages/ui/src/hooks/__tests__/useTldwAudioStatus.test.tsx`

- [x] **Step 1: Write the failing shared-contract tests**

```ts
import {
  buildVoiceConversationPreflight,
  normalizeVoiceConversationRuntimeError,
  resolveVoiceConversationAvailability,
  resolveVoiceConversationTtsConfig
} from "@/services/tldw/voice-conversation"

it("keeps voice conversation unavailable when only broad audio flags exist", () => {
  const result = resolveVoiceConversationAvailability({
    isConnectionReady: true,
    hasVoiceConversationTransport: false,
    audioHealthState: "healthy",
    authReady: true,
    selectedModel: "gpt-4o-mini",
    ttsConfigReady: true
  })

  expect(result.available).toBe(false)
  expect(result.reason).toBe("transport_missing")
})

it("maps browser TTS to server-backed tldw settings for voice conversation", () => {
  const result = resolveVoiceConversationTtsConfig({
    ttsProvider: "browser",
    tldwTtsModel: "kokoro",
    tldwTtsVoice: "af_heart",
    tldwTtsResponseFormat: "mp3",
    tldwTtsSpeed: 1,
    openAITTSModel: "tts-1",
    openAITTSVoice: "alloy",
    elevenLabsModel: "",
    elevenLabsVoiceId: "",
    speechPlaybackSpeed: 1,
    voiceChatTtsMode: "stream"
  })

  expect(result.ok).toBe(true)
  expect(result.value?.model).toBe("kokoro")
  expect(result.value?.voice).toBe("af_heart")
  expect(result.value?.format).toBe("mp3")
})

it("requires explicit OpenAI TTS model and voice when openai is selected", () => {
  const result = resolveVoiceConversationTtsConfig({
    ttsProvider: "openai",
    tldwTtsModel: "kokoro",
    tldwTtsVoice: "af_heart",
    tldwTtsResponseFormat: "mp3",
    tldwTtsSpeed: 1,
    openAITTSModel: "",
    openAITTSVoice: "",
    elevenLabsModel: "",
    elevenLabsVoiceId: "",
    speechPlaybackSpeed: 1,
    voiceChatTtsMode: "stream"
  })

  expect(result.ok).toBe(false)
  expect(result.reason).toBe("tts_config_missing")
})

it("requires explicit ElevenLabs model and voice id when elevenlabs is selected", () => {
  const result = resolveVoiceConversationTtsConfig({
    ttsProvider: "elevenlabs",
    tldwTtsModel: "kokoro",
    tldwTtsVoice: "af_heart",
    tldwTtsResponseFormat: "mp3",
    tldwTtsSpeed: 1,
    openAITTSModel: "tts-1",
    openAITTSVoice: "alloy",
    elevenLabsModel: "",
    elevenLabsVoiceId: "",
    speechPlaybackSpeed: 1,
    voiceChatTtsMode: "stream"
  })

  expect(result.ok).toBe(false)
  expect(result.reason).toBe("tts_config_missing")
})
```

Also extend `useTldwAudioStatus.test.tsx` with a failing assertion that `result.current.hasVoiceConversationTransport` stays `false` when `state.capabilities = { hasAudio: true, hasVoiceChat: true }`.

- [x] **Step 2: Run the new shared-contract tests and confirm they fail**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/services/__tests__/voice-conversation.test.ts ../packages/ui/src/hooks/__tests__/useTldwAudioStatus.test.tsx
```

Expected: FAIL because the shared voice-conversation module does not exist yet and `useTldwAudioStatus` does not expose the strict transport flag.

- [x] **Step 3: Implement the shared availability and TTS helpers**

```ts
export type VoiceConversationReason =
  | "ok"
  | "transport_missing"
  | "not_connected"
  | "auth_missing"
  | "model_missing"
  | "tts_config_missing"
  | "tts_provider_unsupported"
  | "audio_unhealthy"
  | "unknown"

export type VoiceConversationAvailability = {
  available: boolean
  reason: VoiceConversationReason
  message: string | null
}

export const resolveVoiceConversationTtsConfig = (
  input: VoiceConversationTtsInputs
) => {
  const provider = String(input.ttsProvider || "").trim().toLowerCase()

  if (!provider || provider === "browser" || provider === "tldw") {
    const model = String(input.tldwTtsModel || "").trim()
    const voice = String(input.tldwTtsVoice || "").trim()
    if (!model || !voice) {
      return {
        ok: false as const,
        reason: "tts_config_missing" as const,
        message: "Voice conversation needs a server TTS model and voice."
      }
    }

    return {
      ok: true as const,
      value: {
        provider: inferTldwProviderFromModel(model) ?? undefined,
        model,
        voice,
        speed: input.tldwTtsSpeed,
        format: normalizeVoiceConversationFormat(input.tldwTtsResponseFormat, input.voiceChatTtsMode)
      }
    }
  }

  if (provider === "openai") {
    const model = String(input.openAITTSModel || "").trim()
    const voice = String(input.openAITTSVoice || "").trim()
    if (!model || !voice) {
      return {
        ok: false as const,
        reason: "tts_config_missing" as const,
        message: "Voice conversation needs an OpenAI TTS model and voice."
      }
    }

    return {
      ok: true as const,
      value: {
        provider: "openai",
        model,
        voice,
        speed: input.speechPlaybackSpeed,
        format: "mp3"
      }
    }
  }

  if (provider === "elevenlabs") {
    const model = String(input.elevenLabsModel || "").trim()
    const voice = String(input.elevenLabsVoiceId || "").trim()
    if (!model || !voice) {
      return {
        ok: false as const,
        reason: "tts_config_missing" as const,
        message: "Voice conversation needs an ElevenLabs model and voice."
      }
    }

    return {
      ok: true as const,
      value: {
        provider: "elevenlabs",
        model,
        voice,
        speed: input.speechPlaybackSpeed,
        format: "mp3"
      }
    }
  }

  return {
    ok: false as const,
    reason: "tts_provider_unsupported" as const,
    message: `Voice conversation does not support the TTS provider \"${provider}\".`
  }
}

export const resolveVoiceConversationAvailability = (
  input: VoiceConversationAvailabilityInput
): VoiceConversationAvailability => {
  if (!input.isConnectionReady) {
    return unavailable("not_connected", "Connect to a tldw server first.")
  }
  if (!input.hasVoiceConversationTransport) {
    return unavailable(
      "transport_missing",
      "This server does not advertise voice conversation streaming."
    )
  }
  if (!input.authReady) {
    return unavailable("auth_missing", "Configure valid tldw credentials first.")
  }
  if (input.audioHealthState === "unhealthy") {
    return unavailable("audio_unhealthy", "Server audio is currently unhealthy.")
  }
  if (!input.ttsConfigReady) {
    return unavailable(
      "tts_config_missing",
      "Voice conversation needs a server TTS model and voice."
    )
  }
  if (!input.selectedModel && !input.allowBackendDefaultModel) {
    return unavailable("model_missing", "Select a chat model for voice conversation.")
  }
  return { available: true, reason: "ok", message: null }
}

export const buildVoiceConversationPreflight = async (
  input: VoiceConversationPreflightInput
) => {
  const serverUrl = String(input.serverUrl || "").trim()
  const token = String(input.token || "").trim()
  if (!serverUrl) {
    throw new Error("tldw server not configured")
  }
  if (!token) {
    throw new Error("Not authenticated. Configure tldw credentials in Settings.")
  }

  const tts = resolveVoiceConversationTtsConfig(input.tts)
  if (!tts.ok) {
    throw new Error(tts.message)
  }

  const requestedModel = String(input.requestedModel || "").trim()
  const llm =
    requestedModel.length === 0
      ? {}
      : {
          model: requestedModel,
          provider: await input.resolveProvider({ modelId: requestedModel })
        }

  return {
    websocketUrl: `${resolveBrowserWebSocketBase(serverUrl)}/api/v1/audio/chat/stream?token=${encodeURIComponent(token)}`,
    llm,
    tts: tts.value
  }
}

export const normalizeVoiceConversationRuntimeError = (message: string) => {
  const normalized = String(message || "").trim().toLowerCase()
  if (normalized.includes("disconnect")) {
    return {
      reason: "voice_chat_disconnected",
      message: "Voice chat disconnected"
    }
  }
  if (normalized.includes("tts")) {
    return {
      reason: "voice_chat_tts_error",
      message: String(message || "Voice chat TTS failed")
    }
  }
  return {
    reason: "voice_chat_error",
    message: String(message || "Voice chat failed")
  }
}
```

Implementation notes:

- Keep this module pure and reusable by both surfaces and by `useVoiceChatStream`.
- `useTldwAudioStatus` should continue returning `hasVoiceChat`, but add `hasVoiceConversationTransport` without deriving it from `hasAudio`.
- Do not import React into the new contract module.
- Keep provider-specific resolution explicit for `tldw`, `openai`, and `elevenlabs`; unsupported providers should return a stable `tts_provider_unsupported` reason.
- Add a small runtime error normalizer in the same module so both surfaces persist the same interrupted-turn reason codes.

- [x] **Step 4: Re-run the shared-contract tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/services/__tests__/voice-conversation.test.ts ../packages/ui/src/hooks/__tests__/useTldwAudioStatus.test.tsx
```

Expected: PASS with stable reasons/messages and the strict transport signal exposed from `useTldwAudioStatus`.

- [x] **Step 5: Commit the shared voice-conversation contract**

```bash
git add apps/packages/ui/src/services/tldw/voice-conversation.ts apps/packages/ui/src/services/__tests__/voice-conversation.test.ts apps/packages/ui/src/hooks/useTldwAudioStatus.tsx apps/packages/ui/src/hooks/__tests__/useTldwAudioStatus.test.tsx
git commit -m "fix(chat): add shared voice conversation contract"
```

### Task 3: Preflight the Stream Hook Before Opening the WebSocket

**Files:**
- Modify: `apps/packages/ui/src/hooks/useVoiceChatStream.tsx`
- Modify: `apps/packages/ui/src/hooks/__tests__/useVoiceChatStream.interrupt.test.tsx`
- Reuse: `apps/packages/ui/src/services/tldw/voice-conversation.ts`

- [x] **Step 1: Write the failing preflight tests**

```ts
it("does not open a websocket when auth is missing", async () => {
  vi.mocked(tldwClient.getConfig).mockResolvedValue({
    serverUrl: "http://localhost:8000",
    authMode: "single_user",
    apiKey: ""
  } as any)

  const onError = vi.fn()
  const { result } = renderHook(() =>
    useVoiceChatStream({
      active: false,
      onError
    })
  )

  await act(async () => {
    await result.current.start()
  })

  expect(MockWebSocket.instances).toHaveLength(0)
  expect(onError).toHaveBeenCalledWith("Not authenticated. Configure tldw credentials in Settings.")
})

it("allows backend-default model selection by omitting llm.model when no client model is selected", async () => {
  storageValues.set("selectedModel", "")
  vi.mocked(resolveApiProviderForModel).mockResolvedValue("stub")

  const { result } = renderHook(() => useVoiceChatStream({ active: false }))
  await act(async () => {
    await result.current.start()
  })

  const ws = MockWebSocket.instances[0]
  await act(async () => {
    ws.triggerOpen()
    await Promise.resolve()
  })

  const configFrame = JSON.parse(ws.sent[0]!)
  expect(configFrame.llm.model).toBeUndefined()
  expect(configFrame.llm.provider).toBeUndefined()
})

it("fails fast when the selected model cannot be resolved to a provider", async () => {
  storageValues.set("selectedModel", "bad-model")
  vi.mocked(resolveApiProviderForModel).mockRejectedValue(
    new Error("Unable to resolve provider for model \"bad-model\".")
  )

  const onError = vi.fn()
  const { result } = renderHook(() =>
    useVoiceChatStream({ active: false, onError })
  )

  await act(async () => {
    await result.current.start()
  })

  expect(MockWebSocket.instances).toHaveLength(0)
  expect(onError).toHaveBeenCalledWith(
    "Unable to resolve provider for model \"bad-model\"."
  )
})

it("fails fast when browser TTS has no server-backed fallback model", async () => {
  storageValues.set("ttsProvider", "browser")
  storageValues.set("tldwTtsModel", "")
  storageValues.set("tldwTtsVoice", "")

  const onError = vi.fn()
  const { result } = renderHook(() =>
    useVoiceChatStream({ active: false, onError })
  )

  await act(async () => {
    await result.current.start()
  })

  expect(MockWebSocket.instances).toHaveLength(0)
  expect(onError).toHaveBeenCalledWith("Voice conversation needs a server TTS model and voice.")
})

it("surfaces a stable disconnect error after the first transcript has started", async () => {
  const onTranscript = vi.fn()
  const onError = vi.fn()

  renderHook(() =>
    useVoiceChatStream({
      active: true,
      onTranscript,
      onError
    })
  )

  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
  })

  const ws = MockWebSocket.instances[0]
  await act(async () => {
    ws.triggerOpen()
    await Promise.resolve()
  })

  await act(async () => {
    ws.triggerJson({ type: "full_transcript", text: "hello there" })
    await Promise.resolve()
  })

  expect(onTranscript).toHaveBeenCalledWith("hello there", expect.any(Object))

  await act(async () => {
    ws.onclose?.()
    await Promise.resolve()
  })

  expect(onError).toHaveBeenCalledWith("Voice chat disconnected")
})
```

- [x] **Step 2: Run the hook tests and confirm they fail**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/hooks/__tests__/useVoiceChatStream.interrupt.test.tsx
```

Expected: FAIL because `useVoiceChatStream` currently opens the websocket before validating auth/model/TTS readiness and always builds the config frame inline.

- [x] **Step 3: Refactor `useVoiceChatStream` to use shared preflight**

```ts
const start = React.useCallback(async () => {
  const config = await tldwClient.getConfig()
  const token =
    config?.authMode === "multi-user"
      ? String(config?.accessToken || "").trim()
      : String(config?.apiKey || "").trim()
  const preflight = await buildVoiceConversationPreflight({
    serverUrl: config?.serverUrl,
    token,
    requestedModel: String(voiceChatModel || selectedModel || "").trim(),
    resolveProvider: resolveApiProviderForModel,
    tts: {
      ttsProvider,
      tldwTtsModel,
      tldwTtsVoice,
      tldwTtsResponseFormat,
      tldwTtsSpeed,
      openAITTSModel,
      openAITTSVoice,
      elevenLabsModel,
      elevenLabsVoiceId,
      speechPlaybackSpeed,
      voiceChatTtsMode
    }
  })
  const ws = new WebSocket(preflight.websocketUrl)
  ws.onopen = () => {
    ws.send(JSON.stringify({ type: "config", stt: sttConfig, llm: preflight.llm, tts: preflight.tts }))
    // then start mic
  }
}, [resolveApiProviderForModel, /* existing deps */])
```

Implementation notes:

- Do not open the websocket until preflight succeeds.
- Only call `resolveApiProviderForModel` when a client-selected model exists.
- Import and call the shared `buildVoiceConversationPreflight` helper from `apps/packages/ui/src/services/tldw/voice-conversation.ts`; do not rebuild the startup contract inside the hook.
- Resolve the auth token inside `start()` on each connection attempt so the preflight always uses current credentials.
- Preserve the current audio-player and interrupt behavior after startup.
- Keep the provider-resolution failure error stable enough that both surfaces can display and test it without string drift.
- Keep the `browser` provider fallback explicit: browser voice names are ignored, server-backed `tldwTts*` settings are required.

- [x] **Step 4: Re-run the hook tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/hooks/__tests__/useVoiceChatStream.interrupt.test.tsx
```

Expected: PASS with no socket opening on preflight failure and the config frame matching the shared contract.

- [x] **Step 5: Commit the stream-preflight refactor**

```bash
git add apps/packages/ui/src/hooks/useVoiceChatStream.tsx apps/packages/ui/src/hooks/__tests__/useVoiceChatStream.interrupt.test.tsx apps/packages/ui/src/services/tldw/voice-conversation.ts
git commit -m "fix(chat): preflight voice conversation stream startup"
```

### Task 4: Standardize Interrupted Turns and Wire Both Surfaces to the Shared Availability Contract

**Files:**
- Modify: `apps/packages/ui/src/hooks/useVoiceChatMessages.tsx`
- Create: `apps/packages/ui/src/hooks/__tests__/useVoiceChatMessages.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/hooks/usePlaygroundVoiceChat.ts`
- Modify: `apps/packages/ui/src/components/Sidepanel/Chat/form.tsx`
- Create: `apps/packages/ui/src/components/Option/Playground/__tests__/voice-conversation.cross-surface.contract.test.ts`

- [x] **Step 1: Write the failing turn-integrity and cross-surface contract tests**

```ts
it("removes the empty assistant placeholder when the stream fails before assistant text arrives", () => {
  const { result } = renderHook(() => useVoiceChatMessages(), {
    wrapper: buildVoiceChatMessageStoreWrapper()
  })

  act(() => {
    result.current.beginTurn("hello there")
    result.current.failTurn("voice_chat_error")
  })

  expect(getMessages().map((message) => message.role)).toEqual(["user"])
})

it("persists nothing when the stream fails before any transcript turn begins", () => {
  const { result } = renderHook(() => useVoiceChatMessages(), {
    wrapper: buildVoiceChatMessageStoreWrapper()
  })

  act(() => {
    result.current.failTurn("voice_chat_disconnected")
  })

  expect(getMessages()).toEqual([])
})

it("marks partial assistant text as interrupted when the stream fails mid-turn", () => {
  const { result } = renderHook(() => useVoiceChatMessages(), {
    wrapper: buildVoiceChatMessageStoreWrapper()
  })

  act(() => {
    result.current.beginTurn("hello there")
    result.current.appendAssistantDelta("Partial answer")
    result.current.failTurn("voice_chat_error")
  })

  const assistant = getMessages().find((message) => message.role === "assistant")
  expect(assistant?.message).toBe("Partial answer")
  expect(assistant?.generationInfo?.interrupted).toBe(true)
  expect(assistant?.generationInfo?.interruptionReason).toBe("voice_chat_error")
  expect(getHistory().at(-1)).toEqual({
    role: "assistant",
    content: "Partial answer"
  })
  expect(saveMessageOnSuccessMock).toHaveBeenCalledWith(
    expect.objectContaining({
      fullText: "Partial answer",
      generationInfo: expect.objectContaining({
        interrupted: true,
        interruptionReason: "voice_chat_error"
      })
    })
  )
})
```

```ts
expect(playgroundSource).toContain("resolveVoiceConversationAvailability(")
expect(sidepanelSource).toContain("resolveVoiceConversationAvailability(")
expect(playgroundSource).toContain("voiceConversationAvailability.message")
expect(sidepanelSource).toContain("voiceConversationAvailability.message")
expect(playgroundSource).toContain("voiceChatMessages.failTurn(")
expect(sidepanelSource).toContain("voiceChatMessages.failTurn(")
```

- [x] **Step 2: Run the turn-integrity and contract tests and confirm they fail**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/hooks/__tests__/useVoiceChatMessages.test.tsx ../packages/ui/src/components/Option/Playground/__tests__/voice-conversation.cross-surface.contract.test.ts
```

Expected: FAIL because `useVoiceChatMessages` does not expose a failure helper with interrupted metadata and neither surface currently consumes a shared voice-conversation availability object.

- [x] **Step 3: Implement shared turn failure handling and surface wiring**

```ts
const finalizeInterruptedAssistant = (
  message: Message,
  text: string,
  interruptionReason: string
) =>
  updateActiveVariant(message, {
    message: text,
    generationInfo: {
      ...(message.generationInfo || {}),
      interrupted: true,
      interruptionReason,
      interruptedAt: Date.now()
    }
  })

const failTurn = React.useCallback((reason: string) => {
  const turn = currentTurnRef.current
  if (!turn) return
  const finalText = turn.assistantText.trim()
  const generationInfo = {
    interrupted: true,
    interruptionReason: reason,
    interruptedAt: Date.now()
  }

  setMessages((prev) =>
    prev.flatMap((message) => {
      if (message.id !== turn.assistantId) return [message]
      if (!finalText) return []
      return [finalizeInterruptedAssistant(message, finalText, reason)]
    })
  )

  if (finalText) {
    setHistory((prev) => {
      const last = prev[prev.length - 1]
      if (last?.role === "assistant" && last.content === finalText) {
        return prev
      }
      return [...prev, { role: "assistant", content: finalText }]
    })

    void saveMessageOnSuccess({
      historyId,
      setHistoryId,
      isRegenerate: false,
      selectedModel: turn.modelName,
      message: turn.userText,
      image: "",
      fullText: finalText,
      source: [],
      message_source: "server",
      generationInfo,
      userMessageId: turn.userId,
      assistantMessageId: turn.assistantId
    })
  }

  currentTurnRef.current = null
}, [historyId, saveMessageOnSuccess, setHistory, setHistoryId, setMessages])
```

```ts
const voiceConversationAvailability = resolveVoiceConversationAvailability({
  isConnectionReady,
  hasVoiceConversationTransport:
    capabilities?.hasVoiceConversationTransport ?? false,
  audioHealthState,
  authReady: Boolean(serverUrl && authTokenOrApiKey),
  selectedModel: String(voiceChatModel || selectedModel || "").trim(),
  allowBackendDefaultModel: true,
  ttsConfigReady:
    resolveVoiceConversationTtsConfig(currentTtsInputs).ok
})

const voiceChatAvailable = voiceConversationAvailability.available

const runtimeError = normalizeVoiceConversationRuntimeError(msg)
notificationApi.error({
  message: t("playground:voiceChat.errorTitle", "Voice chat error"),
  description: runtimeError.message
})
voiceChatMessages.failTurn(runtimeError.reason)
```

Implementation notes:

- In `usePlaygroundVoiceChat.ts`, replace the hard-coded unavailable copy with `voiceConversationAvailability.message`.
- In both surfaces, call `normalizeVoiceConversationRuntimeError(msg)` and pass the returned `reason` into `voiceChatMessages.failTurn(...)` instead of inventing per-surface reason strings.
- Keep the pre-transcript failure path a no-op in `useVoiceChatMessages.failTurn(...)`, which is how the client satisfies the spec requirement to persist no turn before the first `full_transcript`.
- When partial assistant text exists, `failTurn(...)` must update in-memory messages, append the assistant entry to history, and persist through `saveMessageOnSuccess(...)` with interrupted-generation metadata so reload/export does not drop the partial turn.
- When the user manually toggles voice conversation off before any assistant text exists, keep using the non-error abandonment path.
- Keep autoplay behavior unchanged; this task is only about availability messaging and interrupted-turn integrity.

- [x] **Step 4: Re-run the turn-integrity and contract tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/hooks/__tests__/useVoiceChatMessages.test.tsx ../packages/ui/src/components/Option/Playground/__tests__/voice-conversation.cross-surface.contract.test.ts
```

Expected: PASS with both surfaces reading the same availability contract and partial assistant responses carrying the existing interrupted-generation metadata shape.

- [x] **Step 5: Commit the cross-surface wiring**

```bash
git add apps/packages/ui/src/hooks/useVoiceChatMessages.tsx apps/packages/ui/src/hooks/__tests__/useVoiceChatMessages.test.tsx apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx apps/packages/ui/src/components/Option/Playground/hooks/usePlaygroundVoiceChat.ts apps/packages/ui/src/components/Sidepanel/Chat/form.tsx apps/packages/ui/src/components/Option/Playground/__tests__/voice-conversation.cross-surface.contract.test.ts
git commit -m "fix(chat): unify voice conversation behavior across surfaces"
```

### Task 5: Run the Focused Verification Matrix and Finalize

**Files:**
- Modify: none unless a failing test reveals a missed code path

- [x] **Step 1: Run the focused frontend test suite**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  ../packages/ui/src/services/__tests__/server-capabilities.test.ts \
  ../packages/ui/src/services/__tests__/voice-conversation.test.ts \
  ../packages/ui/src/hooks/__tests__/useTldwAudioStatus.test.tsx \
  ../packages/ui/src/hooks/__tests__/useVoiceChatStream.interrupt.test.tsx \
  ../packages/ui/src/hooks/__tests__/useVoiceChatMessages.test.tsx \
  ../packages/ui/src/components/Option/Playground/__tests__/voice-conversation.cross-surface.contract.test.ts
```

Expected: PASS for the strict transport flag, shared availability contract, preflight logic, interrupted turn handling, and cross-surface parity checks.

- [x] **Step 2: Re-run the backend websocket route regression test**

Run:

```bash
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Audio/test_ws_audio_chat_stream.py
```

Expected: PASS, confirming the client-side hardening did not require backend transport changes.

- [x] **Step 3: Run the required security validation if backend/Python files changed**

Run only if Python/backend code was touched while implementing:

```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/audio tldw_Server_API/app/core/TTS -f json -o /tmp/bandit_voice_conversation.json
```

Expected: PASS or no new findings in changed Python scope. If implementation remains TypeScript-only, record that Bandit is not applicable for this change set.

- [ ] **Step 4: Execute the manual verification matrix on both surfaces**

Manual checks:

1. Server exposes STT+TTS pages but not `/api/v1/audio/chat/stream`.
Expected: standalone STT/TTS still work, `/chat` voice conversation is unavailable with an explicit reason.

2. Server exposes `/api/v1/audio/chat/stream`.
Expected: speaking in WebUI `/chat` auto-submits, assistant text streams, assistant audio autoplays.

3. Same server in extension sidepanel.
Expected: same availability message, same transcript flow, same assistant autoplay behavior.

4. TTS misconfigured (`ttsProvider="browser"` with empty `tldwTtsModel`/`tldwTtsVoice`).
Expected: startup fails immediately with the voice-conversation-specific TTS error instead of a transcript-only stall.

5. No client-selected model.
Expected: voice conversation still starts if backend defaults are valid; a selected model with unresolvable provider fails preflight before websocket open.

- [ ] **Step 5: Commit the verified integration result**

```bash
git add -A
git commit -m "test(chat): verify voice conversation transport flow"
```

Use a narrower `git add` set if the worktree contains unrelated user changes.
