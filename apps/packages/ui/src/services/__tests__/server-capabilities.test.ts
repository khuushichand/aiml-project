import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"

const cacheState = vi.hoisted(() => ({
  value: undefined as unknown
}))

const mocks = vi.hoisted(() => ({
  getConfig: vi.fn(),
  getOpenAPISpec: vi.fn(),
  bgRequest: vi.fn(),
  storageGet: vi.fn(async () => cacheState.value),
  storageSet: vi.fn(async (_key: string, value: unknown) => {
    cacheState.value = value
  })
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    getConfig: (...args: unknown[]) =>
      (mocks.getConfig as (...args: unknown[]) => unknown)(...args),
    getOpenAPISpec: (...args: unknown[]) =>
      (mocks.getOpenAPISpec as (...args: unknown[]) => unknown)(...args)
  }
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: (...args: unknown[]) =>
    (mocks.bgRequest as (...args: unknown[]) => unknown)(...args)
}))

vi.mock("@/utils/safe-storage", () => ({
  createSafeStorage: () => ({
    get: (...args: unknown[]) =>
      (mocks.storageGet as (...args: unknown[]) => unknown)(...args),
    set: (...args: unknown[]) =>
      (mocks.storageSet as (...args: unknown[]) => unknown)(...args)
  })
}))

const importCapabilitiesModule = async () =>
  import("@/services/tldw/server-capabilities")

describe("server capabilities docs-info merge", () => {
  beforeEach(() => {
    vi.resetModules()
    vi.useRealTimers()
    cacheState.value = undefined
    mocks.getConfig.mockReset()
    mocks.getOpenAPISpec.mockReset()
    mocks.bgRequest.mockReset()
    mocks.storageGet.mockReset()
    mocks.storageSet.mockReset()
    mocks.storageGet.mockImplementation(async () => cacheState.value)
    mocks.storageSet.mockImplementation(async (_key: string, value: unknown) => {
      cacheState.value = value
    })
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user"
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("requires both persona route support and docs-info persona feature flag", async () => {
    mocks.getOpenAPISpec.mockResolvedValue({
      info: { version: "test-version" },
      paths: {
        "/api/v1/persona/catalog": {},
        "/api/v1/persona/session": {},
        "/api/v1/personalization/profile": {}
      }
    })
    mocks.bgRequest.mockResolvedValue({
      capabilities: {
        persona: false,
        personalization: true
      }
    })

    const { getServerCapabilities } = await importCapabilitiesModule()
    const capabilities = await getServerCapabilities()

    expect(capabilities.hasPersona).toBe(false)
    expect(capabilities.hasPersonalization).toBe(true)
    expect(capabilities.specVersion).toBe("test-version")
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/config/docs-info",
        method: "GET",
        noAuth: true
      })
    )
  })

  it("does not enable persona when docs-info says true but persona routes are missing", async () => {
    mocks.getOpenAPISpec.mockResolvedValue({
      info: { version: "test-version" },
      paths: {
        "/api/v1/chat/completions": {}
      }
    })
    mocks.bgRequest.mockResolvedValue({
      capabilities: {
        persona: true
      }
    })

    const { getServerCapabilities } = await importCapabilitiesModule()
    const capabilities = await getServerCapabilities()

    expect(capabilities.hasPersona).toBe(false)
  })

  it("falls back to openapi-only capability detection when docs-info fetch fails", async () => {
    mocks.getOpenAPISpec.mockResolvedValue({
      info: { version: "test-version" },
      paths: {
        "/api/v1/persona/catalog": {}
      }
    })
    mocks.bgRequest.mockRejectedValue(new Error("docs-info unavailable"))

    const { getServerCapabilities } = await importCapabilitiesModule()
    const capabilities = await getServerCapabilities()

    expect(capabilities.hasPersona).toBe(true)
  })

  it("detects media capability from ingest jobs endpoint alone", async () => {
    mocks.getOpenAPISpec.mockResolvedValue({
      info: { version: "ingest-jobs-only" },
      paths: {
        "/api/v1/media/ingest/jobs": {}
      }
    })
    mocks.bgRequest.mockResolvedValue({})

    const { getServerCapabilities } = await importCapabilitiesModule()
    const capabilities = await getServerCapabilities()

    expect(capabilities.hasMedia).toBe(true)
  })

  it("derives hasAudio from STT-only support while keeping TTS/voice flags explicit", async () => {
    mocks.getOpenAPISpec.mockResolvedValue({
      info: { version: "audio-split-stt" },
      paths: {
        "/api/v1/audio/transcriptions": {},
        "/api/v1/audio/transcriptions/health": {}
      }
    })
    mocks.bgRequest.mockResolvedValue({})

    const { getServerCapabilities } = await importCapabilitiesModule()
    const capabilities = await getServerCapabilities()

    expect(capabilities.hasStt).toBe(true)
    expect(capabilities.hasTts).toBe(false)
    expect(capabilities.hasVoiceChat).toBe(false)
    expect(capabilities.hasAudio).toBe(true)
  })

  it("derives hasAudio from TTS-only support", async () => {
    mocks.getOpenAPISpec.mockResolvedValue({
      info: { version: "audio-split-tts" },
      paths: {
        "/api/v1/audio/speech": {},
        "/api/v1/audio/health": {}
      }
    })
    mocks.bgRequest.mockResolvedValue({})

    const { getServerCapabilities } = await importCapabilitiesModule()
    const capabilities = await getServerCapabilities()

    expect(capabilities.hasStt).toBe(false)
    expect(capabilities.hasTts).toBe(true)
    expect(capabilities.hasVoiceChat).toBe(false)
    expect(capabilities.hasAudio).toBe(true)
  })

  it("keeps legacy hasAudio true for voice-chat-only route exposure", async () => {
    mocks.getOpenAPISpec.mockResolvedValue({
      info: { version: "audio-split-voice-chat" },
      paths: {
        "/api/v1/audio/chat/stream": {}
      }
    })
    mocks.bgRequest.mockResolvedValue({})

    const { getServerCapabilities } = await importCapabilitiesModule()
    const capabilities = await getServerCapabilities()

    expect(capabilities.hasVoiceChat).toBe(true)
    expect(capabilities.hasAudio).toBe(true)
  })

  it("infers voice chat support from combined STT and TTS routes", async () => {
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

    expect(capabilities.hasStt).toBe(true)
    expect(capabilities.hasTts).toBe(true)
    expect(capabilities.hasVoiceChat).toBe(true)
    expect(capabilities.hasAudio).toBe(true)
  })

  it("reuses a fresh cached capability payload for repeated calls", async () => {
    mocks.getOpenAPISpec.mockResolvedValue({
      info: { version: "cached-version" },
      paths: {
        "/api/v1/chat/completions": {}
      }
    })
    mocks.bgRequest.mockResolvedValue({})

    const { getServerCapabilities } = await importCapabilitiesModule()
    const first = await getServerCapabilities()
    const second = await getServerCapabilities()

    expect(first.specVersion).toBe("cached-version")
    expect(second.specVersion).toBe("cached-version")
    expect(mocks.getOpenAPISpec).toHaveBeenCalledTimes(1)
    expect(mocks.bgRequest).toHaveBeenCalledTimes(1)
  })

  it("refreshes capabilities after cache TTL expires", async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2026-02-11T10:50:00.000Z"))

    mocks.getOpenAPISpec.mockResolvedValue({
      info: { version: "ttl-version" },
      paths: {
        "/api/v1/chat/completions": {}
      }
    })
    mocks.bgRequest.mockResolvedValue({})

    const { getServerCapabilities } = await importCapabilitiesModule()
    await getServerCapabilities()
    vi.setSystemTime(new Date("2026-02-11T10:56:01.000Z"))
    await getServerCapabilities()

    expect(mocks.getOpenAPISpec).toHaveBeenCalledTimes(2)
    expect(mocks.bgRequest).toHaveBeenCalledTimes(2)
  })

  it("keeps cache entries isolated by server URL", async () => {
    mocks.getConfig
      .mockResolvedValueOnce({
        serverUrl: "http://127.0.0.1:8000",
        authMode: "single-user"
      })
      .mockResolvedValueOnce({
        serverUrl: "http://127.0.0.1:8100",
        authMode: "single-user"
      })
    mocks.getOpenAPISpec.mockResolvedValue({
      info: { version: "multi-server-version" },
      paths: {
        "/api/v1/chat/completions": {}
      }
    })
    mocks.bgRequest.mockResolvedValue({})

    const { getServerCapabilities } = await importCapabilitiesModule()
    await getServerCapabilities()
    await getServerCapabilities()

    expect(mocks.getOpenAPISpec).toHaveBeenCalledTimes(2)
    expect(mocks.bgRequest).toHaveBeenCalledTimes(2)
  })

  it("tracks cache hit diagnostics across miss -> network -> memory hit", async () => {
    mocks.getOpenAPISpec.mockResolvedValue({
      info: { version: "diag-version" },
      paths: {
        "/api/v1/chat/completions": {}
      }
    })
    mocks.bgRequest.mockResolvedValue({})

    const { getServerCapabilities, getServerCapabilitiesCacheDiagnostics } =
      await importCapabilitiesModule()

    await getServerCapabilities()
    await getServerCapabilities()

    const diagnostics = getServerCapabilitiesCacheDiagnostics()
    expect(diagnostics.calls).toBe(2)
    expect(diagnostics.networkFetches).toBe(1)
    expect(diagnostics.inMemoryHits).toBe(1)
    expect(diagnostics.persistedHits).toBe(0)
    expect(diagnostics.lastSource).toBe("in-memory")
  })

  it("records in-flight dedupe hits for concurrent requests", async () => {
    let resolveSpec: ((value: unknown) => void) | null = null
    const openApiDeferred = new Promise((resolve) => {
      resolveSpec = resolve
    })
    mocks.getOpenAPISpec.mockReturnValue(openApiDeferred)
    mocks.bgRequest.mockResolvedValue({})

    const { getServerCapabilities, getServerCapabilitiesCacheDiagnostics } =
      await importCapabilitiesModule()

    const p1 = getServerCapabilities()
    const p2 = getServerCapabilities()
    resolveSpec?.({
      info: { version: "dedupe-version" },
      paths: { "/api/v1/chat/completions": {} }
    })

    await Promise.all([p1, p2])
    const diagnostics = getServerCapabilitiesCacheDiagnostics()
    expect(diagnostics.calls).toBe(2)
    expect(diagnostics.networkFetches).toBe(1)
    expect(diagnostics.inFlightHits).toBe(1)
  })

  it("keeps fallback spec aligned with TTS voice-catalog route checks", () => {
    const source = readFileSync(
      resolve(process.cwd(), "src/services/tldw/server-capabilities.ts"),
      "utf8"
    )

    const fallbackPathsBlock = source.match(
      /const fallbackSpec = \{[\s\S]*?paths:\s*Object\.fromEntries\(\s*\[([\s\S]*?)\]\.map/
    )?.[1]

    expect(fallbackPathsBlock).toContain('"/api/v1/audio/voices/catalog"')
  })
})
