import { expect, test, type Locator, type Page } from "@playwright/test"
import { launchWithExtensionOrSkip } from "./utils/real-server"
import http from "node:http"
import { AddressInfo } from "node:net"
import path from "path"
import {
  forceConnected,
  setSelectedModel,
  waitForConnectionStore
} from "./utils/connection"
import { grantHostPermission } from "./utils/permissions"

const EXT_PATH = path.resolve("build/chrome-mv3")
const MODEL_ID = "mock-model"
const MODEL_KEY = `tldw:${MODEL_ID}`
const DICTATION_FALLBACK_E2E_ENABLED =
  process.env.TLDW_E2E_RUN_DICTATION_FALLBACK === "1"

const readBody = (req: http.IncomingMessage) =>
  new Promise<string>((resolve) => {
    let body = ""
    req.on("data", (chunk) => {
      body += chunk
    })
    req.on("end", () => resolve(body))
  })

const startDictationMockServer = async (dictationErrorClass: string) => {
  let transcriptionsCount = 0
  const requests: Array<{ method: string; path: string }> = []

  const server = http.createServer(async (req, res) => {
    const method = (req.method || "GET").toUpperCase()
    const rawUrl = req.url || "/"
    const parsedUrl = new URL(rawUrl, "http://127.0.0.1")
    const url = parsedUrl.pathname
    requests.push({ method, path: parsedUrl.pathname + parsedUrl.search })

    const sendJson = (code: number, payload: unknown) => {
      res.writeHead(code, {
        "content-type": "application/json",
        "access-control-allow-origin": "http://127.0.0.1",
        "access-control-allow-credentials": "true"
      })
      res.end(JSON.stringify(payload))
    }

    if (method === "OPTIONS") {
      res.writeHead(204, {
        "access-control-allow-origin": "http://127.0.0.1",
        "access-control-allow-credentials": "true",
        "access-control-allow-headers":
          "content-type, x-api-key, authorization"
      })
      return res.end()
    }

    if (url === "/api/v1/health" && method === "GET") {
      return sendJson(200, { status: "ok" })
    }

    if (url === "/api/v1/llm/models/metadata" && method === "GET") {
      return sendJson(200, [
        {
          id: MODEL_ID,
          name: "Mock Model",
          model: MODEL_ID,
          provider: "mock",
          context_length: 4096,
          capabilities: ["chat"]
        }
      ])
    }

    if (url === "/api/v1/llm/models" && method === "GET") {
      return sendJson(200, [MODEL_ID])
    }

    if (url === "/api/v1/audio/transcriptions/health" && method === "GET") {
      return sendJson(200, {
        ok: true,
        data: { available: true }
      })
    }

    if (url === "/api/v1/audio/transcriptions" && method === "POST") {
      transcriptionsCount += 1
      await readBody(req)
      return sendJson(503, {
        detail: {
          dictation_error_class: dictationErrorClass,
          status: dictationErrorClass,
          message: `Simulated ${dictationErrorClass}`
        }
      })
    }

    if (url === "/openapi.json" && method === "GET") {
      return sendJson(200, {
        openapi: "3.0.0",
        info: { version: "mock" },
        paths: {
          "/api/v1/health": {},
          "/api/v1/chat/completions": {},
          "/api/v1/llm/models": {},
          "/api/v1/llm/models/metadata": {},
          "/api/v1/audio/transcriptions": {},
          "/api/v1/audio/transcriptions/health": {}
        }
      })
    }

    if (url === "/api/v1/chat/completions" && method === "POST") {
      return sendJson(200, {
        choices: [
          {
            message: { role: "assistant", content: "Mock reply" }
          }
        ]
      })
    }

    return sendJson(404, { detail: "not found" })
  })

  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve))
  const addr = server.address() as AddressInfo
  return {
    server,
    baseUrl: `http://127.0.0.1:${addr.port}`,
    getTranscriptionsCount: () => transcriptionsCount,
    getRequestLog: () => requests.slice()
  }
}

const ensureChatInput = async (page: Page) => {
  const startButton = page.getByRole("button", { name: /Start chatting/i })
  if ((await startButton.count()) > 0) {
    await startButton.first().click()
  }

  const byTestId = page.getByTestId("chat-input")
  if ((await byTestId.count()) > 0) {
    await expect(byTestId.first()).toBeVisible({ timeout: 15000 })
    return byTestId.first()
  }

  const byPlaceholder = page.getByPlaceholder(/Type a message/i)
  await expect(byPlaceholder.first()).toBeVisible({ timeout: 15000 })
  return byPlaceholder.first()
}

const findVisibleButton = async (
  page: Page,
  name: string | RegExp
): Promise<Locator> => {
  const candidates = page.getByRole("button", { name })
  const count = await candidates.count()
  for (let index = 0; index < count; index += 1) {
    const candidate = candidates.nth(index)
    if (await candidate.isVisible()) {
      return candidate
    }
  }
  throw new Error(`Unable to find visible button: ${String(name)}`)
}

const waitForServerDictationMode = async (sidepanel: Page) => {
  await expect
    .poll(
      async () => {
        const startButton = await findVisibleButton(sidepanel, /Start dictation/i)
        await startButton.hover()
        const tooltip = sidepanel.getByText("Dictation via your tldw server")
        if ((await tooltip.count()) === 0) return false
        return tooltip.first().isVisible()
      },
      { timeout: 15000 }
    )
    .toBe(true)
}

const installDictationBrowserMocks = async (
  pageContext: any,
  dictationErrorClass: string
) => {
  await pageContext.addInitScript((errorClass: string) => {
    ;(window as any).__dictationSpeechStartCount = 0
    ;(window as any).__mediaRecorderStartCount = 0
    ;(window as any).__mediaRecorderStopCount = 0
    ;(window as any).__mediaRecorderOnStopCount = 0
    ;(window as any).__dictationRecorderImpl = "unknown"
    ;(window as any).__dictationUploadCount = 0
    ;(window as any).__dictationLastUploadPath = ""
    ;(window as any).__dictationLastUploadErrorClass = ""

    class FakeSpeechRecognition {
      lang = ""
      interimResults = true
      continuous = true
      maxAlternatives = 1
      grammars = null
      onresult: ((event: any) => void) | null = null
      onerror: ((event: Event) => void) | null = null
      onend: (() => void) | null = null

      start() {
        ;(window as any).__dictationSpeechStartCount += 1
      }

      stop() {}
    }

    const createFakeStream = () => ({
      getTracks: () => [{ stop: () => {} }],
      getAudioTracks: () => [{ stop: () => {} }]
    })

    const createAudioContextStream = () => {
      const AudioCtx =
        (window as any).AudioContext || (window as any).webkitAudioContext
      if (!AudioCtx) return null
      try {
        const ctx = new AudioCtx()
        const oscillator = ctx.createOscillator()
        const gain = ctx.createGain()
        gain.gain.value = 0.01
        const destination = ctx.createMediaStreamDestination()
        oscillator.connect(gain)
        gain.connect(destination)
        oscillator.start()
        void ctx.resume().catch(() => {})
        return destination.stream
      } catch {
        return null
      }
    }

    const fakeMediaDevices = navigator.mediaDevices || ({} as any)
    try {
      fakeMediaDevices.getUserMedia = async () =>
        createAudioContextStream() || createFakeStream()
      Object.defineProperty(navigator, "mediaDevices", {
        value: fakeMediaDevices,
        configurable: true
      })
    } catch {}

    ;(window as any).SpeechRecognition = FakeSpeechRecognition
    ;(window as any).webkitSpeechRecognition = FakeSpeechRecognition

    const patchRuntimeSendMessage = (runtime: any) => {
      if (!runtime?.sendMessage) return
      const previous = runtime.sendMessage
      if (typeof previous !== "function") return
      if ((runtime as any).__dictationUploadMockInstalled) return

      const wrapped = function (message: any, ...args: any[]) {
        if (
          message?.type === "tldw:upload" &&
          message?.payload?.path === "/api/v1/audio/transcriptions"
        ) {
          ;(window as any).__dictationUploadCount += 1
          ;(window as any).__dictationLastUploadPath = String(
            message?.payload?.path || ""
          )
          ;(window as any).__dictationLastUploadErrorClass = errorClass
          return Promise.resolve({
            ok: false,
            status: 503,
            error: `Simulated ${errorClass}`,
            data: {
              detail: {
                dictation_error_class: errorClass,
                status: errorClass,
                message: `Simulated ${errorClass}`
              }
            }
          })
        }
        return previous.apply(this, [message, ...args])
      }

      try {
        runtime.sendMessage = wrapped
      } catch {
        try {
          Object.defineProperty(runtime, "sendMessage", {
            value: wrapped,
            configurable: true,
            writable: true
          })
        } catch {
          return
        }
      }
      ;(runtime as any).__dictationUploadMockInstalled = true
    }

    patchRuntimeSendMessage((window as any).chrome?.runtime)
    patchRuntimeSendMessage((window as any).browser?.runtime)

    const NativeMediaRecorder = (window as any).MediaRecorder
    if (NativeMediaRecorder?.prototype) {
      const nativeStart = NativeMediaRecorder.prototype.start
      const nativeStop = NativeMediaRecorder.prototype.stop
      NativeMediaRecorder.prototype.start = function (...args: any[]) {
        ;(window as any).__mediaRecorderStartCount += 1
        ;(window as any).__dictationRecorderImpl = "native"
        return nativeStart.apply(this, args)
      }
      NativeMediaRecorder.prototype.stop = function (...args: any[]) {
        ;(window as any).__mediaRecorderStopCount += 1
        try {
          this.addEventListener?.(
            "stop",
            () => {
              ;(window as any).__mediaRecorderOnStopCount += 1
            },
            { once: true }
          )
        } catch {}
        return nativeStop.apply(this, args)
      }
    } else {
      class FakeMediaRecorder {
        static isTypeSupported() {
          return true
        }
        stream: any
        mimeType = "audio/webm"
        state: "inactive" | "recording" = "inactive"
        ondataavailable: ((event: any) => void) | null = null
        onstop: (() => void) | null = null
        onerror: ((event: Event) => void) | null = null

        constructor(stream: any) {
          this.stream = stream
        }

        start() {
          this.state = "recording"
          ;(window as any).__mediaRecorderStartCount += 1
          ;(window as any).__dictationRecorderImpl = "fake"
        }

        stop() {
          ;(window as any).__mediaRecorderStopCount += 1
          this.state = "inactive"
          this.ondataavailable?.({
            data: new Blob(["mock-audio"], { type: "audio/webm" })
          })
          ;(window as any).__mediaRecorderOnStopCount += 1
          this.onstop?.()
        }
      }
      try {
        Object.defineProperty(window, "MediaRecorder", {
          value: FakeMediaRecorder,
          configurable: true,
          writable: true
        })
      } catch {
        ;(window as any).MediaRecorder = FakeMediaRecorder
      }
    }
  }, dictationErrorClass)
}

const runFallbackScenario = async (
  dictationErrorClass: string
): Promise<{
  speechStartCount: number
  mediaRecorderStartCount: number
  recorderImpl: string
  uploadCount: number
}> => {
  const mock = await startDictationMockServer(dictationErrorClass)
  const { context, page, openSidepanel, extensionId } =
    (await launchWithExtensionOrSkip(test, EXT_PATH, {
      seedConfig: {
        __tldw_first_run_complete: true,
        __tldw_allow_offline: true,
        dictation_auto_fallback: true,
        dictationModeOverride: null,
        tldwConfig: {
          serverUrl: mock.baseUrl,
          authMode: "single-user",
          apiKey: "test-key"
        }
      }
    })) as any

  try {
    await installDictationBrowserMocks(context, dictationErrorClass)
    const origin = new URL(mock.baseUrl).origin + "/*"
    const granted = await grantHostPermission(context, extensionId, origin)
    test.skip(
      !granted,
      "Host permission not granted; allow it in chrome://extensions > tldw Assistant > Site access, then re-run."
    )

    await setSelectedModel(page, MODEL_KEY)

    const sidepanel = await openSidepanel()
    await waitForConnectionStore(sidepanel, "sidepanel-dictation:store")
    await forceConnected(
      sidepanel,
      { serverUrl: mock.baseUrl },
      "sidepanel-dictation:connected"
    )
    await ensureChatInput(sidepanel)
    await waitForServerDictationMode(sidepanel)

    const startButton = await findVisibleButton(sidepanel, /Start dictation/i)
    await startButton.click()
    await sidepanel.waitForTimeout(350)
    const stopButton = await findVisibleButton(sidepanel, /Stop dictation/i)
    await stopButton.click()

    const firstPassCounters = await sidepanel.evaluate(() => ({
      speechStartCount: Number((window as any).__dictationSpeechStartCount || 0),
      mediaRecorderStartCount: Number(
        (window as any).__mediaRecorderStartCount || 0
      ),
      mediaRecorderStopCount: Number((window as any).__mediaRecorderStopCount || 0),
      mediaRecorderOnStopCount: Number(
        (window as any).__mediaRecorderOnStopCount || 0
      ),
      recorderImpl: String((window as any).__dictationRecorderImpl || "unknown"),
      uploadCount: Number((window as any).__dictationUploadCount || 0),
      uploadPath: String((window as any).__dictationLastUploadPath || ""),
      uploadErrorClass: String(
        (window as any).__dictationLastUploadErrorClass || ""
      )
    }))

    await expect
      .poll(
        async () => {
          const value = await sidepanel.evaluate(
            () => Number((window as any).__dictationUploadCount || 0)
          )
          if (value !== 1) {
            const log = mock
              .getRequestLog()
              .map((entry) => `${entry.method} ${entry.path}`)
              .join("\n")
            console.log(
              `[DICTATION_E2E_DEBUG] waiting for dictation upload; current=${value}\n` +
                `[DICTATION_E2E_DEBUG] counters=${JSON.stringify(firstPassCounters)}\n` +
                `[DICTATION_E2E_DEBUG] requests=\n${log}`
            )
          }
          return value
        },
        { timeout: 20000 }
      )
      .toBe(1)
    await sidepanel.waitForTimeout(350)

    const startAfterError = await findVisibleButton(sidepanel, /Start dictation/i)
    await startAfterError.click()
    await sidepanel.waitForTimeout(200)

    const counters = await sidepanel.evaluate(() => ({
      speechStartCount: Number((window as any).__dictationSpeechStartCount || 0),
      mediaRecorderStartCount: Number(
        (window as any).__mediaRecorderStartCount || 0
      ),
      recorderImpl: String((window as any).__dictationRecorderImpl || "unknown"),
      uploadCount: Number((window as any).__dictationUploadCount || 0)
    }))

    return {
      ...counters
    }
  } finally {
    await context.close()
    await new Promise<void>((resolve) => mock.server.close(() => resolve()))
  }
}

test.describe("Sidepanel dictation fallback", () => {
  test.setTimeout(90000)

  test.skip(
    !DICTATION_FALLBACK_E2E_ENABLED,
    "Set TLDW_E2E_RUN_DICTATION_FALLBACK=1 to run dictation fallback E2E."
  )

  test("falls back to browser dictation for provider_unavailable", async () => {
    const result = await runFallbackScenario("provider_unavailable")

    expect(result.uploadCount).toBe(1)
    expect(result.speechStartCount).toBe(1)
    expect(result.mediaRecorderStartCount).toBe(1)
  })

  test("does not auto-fallback for quota_error", async () => {
    const result = await runFallbackScenario("quota_error")

    expect(result.uploadCount).toBe(1)
    expect(result.speechStartCount).toBe(0)
    expect(result.mediaRecorderStartCount).toBe(2)
  })
})
