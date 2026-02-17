import { test, expect, type Page } from '@playwright/test'
import path from 'path'
import { launchWithExtension } from './utils/extension'

const dismissWorkflowHubIfVisible = async (page: Page) => {
  const hubHeading = page.getByText(/What would you like to do\?/i).first()
  const hubDialog = page.locator("[role='dialog']").filter({ has: hubHeading }).first()

  const visible = await hubDialog.isVisible({ timeout: 3000 }).catch(() => false)
  if (!visible) return

  await page.keyboard.press('Escape').catch(() => {})
  const dismissedWithEscape = await hubDialog
    .waitFor({ state: 'hidden', timeout: 1500 })
    .then(() => true)
    .catch(() => false)
  if (dismissedWithEscape) return

  const closeButton = hubDialog
    .locator("button[aria-label='Close'], button.ant-modal-close, button:has-text('×')")
    .first()
  const closeVisible = await closeButton.isVisible({ timeout: 1000 }).catch(() => false)
  if (closeVisible) {
    await closeButton.click({ timeout: 2000 }).catch(() => {})
  }

  const dismissedWithClose = await hubDialog
    .waitFor({ state: 'hidden', timeout: 1500 })
    .then(() => true)
    .catch(() => false)
  if (dismissedWithClose) return

  const startChat = hubDialog.getByText(/Start Chatting/i).first()
  const startChatVisible = await startChat.isVisible({ timeout: 1000 }).catch(() => false)
  if (startChatVisible) {
    await startChat.click({ timeout: 2000 }).catch(() => {})
  }

  await hubDialog.waitFor({ state: 'hidden', timeout: 10000 }).catch(() => {})
}

const waitForSpeechPageReady = async (page: Page) => {
  await expect(page.getByText(/Speech Playground/i)).toBeVisible({ timeout: 15000 })
}

test.describe('Speech Playground UX', () => {
  test('shows ElevenLabs timeout hint and recovers on retry in listen mode', async () => {
    const extPath = path.resolve('build/chrome-mv3')
    const { context, page, optionsUrl } = await launchWithExtension(extPath, {
      seedConfig: {
        __tldw_first_run_complete: true,
        __tldw_allow_offline: true,
        speechPlaygroundMode: 'listen',
        ttsProvider: 'elevenlabs',
        elevenLabsApiKey: 'elevenlabs-e2e-key'
      }
    })

    await context.addInitScript(() => {
      const voices = [{ voiceName: 'E2E Voice', lang: 'en-US' }]
      const getVoices = async () => voices
      const setGetVoices = (ttsApi: any) => {
        if (!ttsApi || typeof ttsApi !== 'object') return
        try {
          ttsApi.getVoices = getVoices
          return
        } catch {}
        try {
          Object.defineProperty(ttsApi, 'getVoices', {
            value: getVoices,
            configurable: true
          })
        } catch {}
      }
      const w = window as any
      const chromeApi = w.chrome || {}
      const ttsApi = chromeApi.tts || {}
      setGetVoices(ttsApi)
      try {
        Object.defineProperty(chromeApi, 'tts', {
          value: ttsApi,
          configurable: true
        })
      } catch {}
      try {
        Object.defineProperty(w, 'chrome', {
          value: chromeApi,
          configurable: true
        })
      } catch {}
      setGetVoices(w.chrome?.tts)
      try {
        w.speechSynthesis = {
          getVoices: () => voices
        }
      } catch {}
    })

    const corsHeaders = {
      'access-control-allow-origin': '*',
      'access-control-allow-methods': 'GET, OPTIONS',
      'access-control-allow-headers': '*'
    }
    let shouldFailMetadata = true
    let voicesGetHits = 0
    let modelsGetHits = 0

    await page.route('https://api.elevenlabs.io/v1/voices**', async (route) => {
      const method = route.request().method()
      if (method !== 'GET') {
        await route.fulfill({ status: 204, headers: corsHeaders })
        return
      }
      voicesGetHits += 1
      if (shouldFailMetadata) {
        await route.abort('timedout')
        return
      }
      await route.fulfill({
        status: 200,
        headers: corsHeaders,
        contentType: 'application/json',
        body: JSON.stringify({
          voices: [{ voice_id: 'voice-1', name: 'Voice One' }]
        })
      })
    })

    await page.route('https://api.elevenlabs.io/v1/models**', async (route) => {
      const method = route.request().method()
      if (method !== 'GET') {
        await route.fulfill({ status: 204, headers: corsHeaders })
        return
      }
      modelsGetHits += 1
      if (shouldFailMetadata) {
        await route.abort('timedout')
        return
      }
      await route.fulfill({
        status: 200,
        headers: corsHeaders,
        contentType: 'application/json',
        body: JSON.stringify([{ model_id: 'model-1', name: 'Model One' }])
      })
    })

    await page.goto(optionsUrl + '#/speech', { waitUntil: 'domcontentloaded' })
    await dismissWorkflowHubIfVisible(page)
    await waitForSpeechPageReady(page)

    const timeoutAlert = page.locator('.ant-alert').filter({
      hasText: /ElevenLabs voices unavailable/i
    })
    await expect(timeoutAlert).toBeVisible()
    await expect(
      timeoutAlert.getByText(/Loading voices\/models took longer than 10 seconds/i)
    ).toBeVisible()

    shouldFailMetadata = false
    await timeoutAlert.getByRole('button', { name: /^Retry$/i }).click()

    await expect.poll(() => voicesGetHits).toBeGreaterThanOrEqual(2)
    await expect.poll(() => modelsGetHits).toBeGreaterThanOrEqual(2)

    await expect(page.getByLabel('ElevenLabs voice')).toBeVisible()
    await expect(page.getByLabel('ElevenLabs model')).toBeVisible()
    await expect(timeoutAlert).toBeHidden()

    await context.close()
  })

  test('supports transcript lock/unlock, copy toast, and download tooltip', async () => {
    const extPath = path.resolve('build/chrome-mv3')
    const { context, page, optionsUrl } = await launchWithExtension(extPath, {
      seedConfig: {
        tldwConfig: {
          serverUrl: 'http://127.0.0.1:8000',
          authMode: 'single-user',
          apiKey: 'test-key'
        },
        speechPlaygroundMode: 'listen',
        __tldw_first_run_complete: true,
        __tldw_allow_offline: true
      }
    })

    await context.addInitScript(() => {
      const AudioCtx = (window as any).AudioContext || (window as any).webkitAudioContext
      let fakeStream = null

      if (AudioCtx) {
        try {
          const ctx = new AudioCtx()
          const oscillator = ctx.createOscillator()
          const destination = ctx.createMediaStreamDestination()
          oscillator.connect(destination)
          oscillator.start()
          fakeStream = destination.stream
          ctx.resume().catch(() => {})
        } catch {
          fakeStream = null
        }
      }

      if (!fakeStream && typeof MediaStream !== 'undefined') {
        fakeStream = new MediaStream()
      }

      if (!fakeStream) {
        fakeStream = { getTracks: () => [], getAudioTracks: () => [] }
      }

      const mediaDevices = navigator.mediaDevices || {}
      try {
        mediaDevices.getUserMedia = async () => fakeStream
      } catch {}

      try {
        Object.defineProperty(mediaDevices, 'getUserMedia', {
          value: async () => fakeStream,
          configurable: true
        })
      } catch {}

      try {
        Object.defineProperty(navigator, 'mediaDevices', {
          value: mediaDevices,
          configurable: true
        })
      } catch {}

      try {
        Object.defineProperty(navigator, 'clipboard', {
          value: {
            writeText: async () => {}
          },
          configurable: true
        })
      } catch {}

      window.__lastRecorder = null

      class FakeMediaRecorder {
        static isTypeSupported() {
          return true
        }

        constructor(stream) {
          this.stream = stream
          this.mimeType = 'audio/webm'
          this.state = 'inactive'
          this.ondataavailable = null
          this.onstop = null
          this.onerror = null
          window.__lastRecorder = this
        }

        start() {
          this.state = 'recording'
          setTimeout(() => {
            if (typeof this.ondataavailable === 'function') {
              const blob = new Blob([new Uint8Array([1, 2, 3])], { type: 'audio/webm' })
              this.ondataavailable({ data: blob })
            }
          }, 50)
        }

        stop() {
          this.state = 'inactive'
          setTimeout(() => {
            if (typeof this.onstop === 'function') {
              this.onstop()
            }
          }, 50)
        }
      }

      const setMediaRecorder = () => {
        try {
          window.MediaRecorder = FakeMediaRecorder
          return
        } catch {}
        try {
          Object.defineProperty(window, 'MediaRecorder', {
            value: FakeMediaRecorder,
            configurable: true,
            writable: true
          })
        } catch {}
      }
      setMediaRecorder()

      const mockSendMessage = async (payload) => {
        if (payload?.type === 'tldw:request') {
          const path = payload?.payload?.path
          if (path === '/api/v1/media/transcription-models') {
            return { ok: true, status: 200, data: { all_models: ['whisper-1'] } }
          }
          return { ok: true, status: 200, data: {} }
        }
        if (payload?.type === 'tldw:upload') {
          const path = payload?.payload?.path
          if (path === '/api/v1/audio/transcriptions') {
            return { ok: true, status: 200, data: { text: 'Test transcript' } }
          }
          return { ok: true, status: 200, data: {} }
        }
        return { ok: true, status: 200, data: {} }
      }

      const setSendMessage = (runtime) => {
        if (!runtime) return
        try {
          runtime.sendMessage = mockSendMessage
          return
        } catch {}
        try {
          Object.defineProperty(runtime, 'sendMessage', {
            value: mockSendMessage,
            configurable: true,
            writable: true
          })
        } catch {}
      }

      if (window.chrome?.runtime) {
        setSendMessage(window.chrome.runtime)
      }

      if (window.browser?.runtime) {
        setSendMessage(window.browser.runtime)
      }

      window.__e2eMicStub = true
    })

    const baseUrl = `${optionsUrl}?e2e=1`
    await page.goto(baseUrl + '#/speech', { waitUntil: 'domcontentloaded' })
    await dismissWorkflowHubIfVisible(page)
    await waitForSpeechPageReady(page)
    await page.waitForFunction(() => window.__e2eMicStub === true)

    const ttsInput = page.getByPlaceholder('Type or paste text here, then use Play to listen.')
    await expect(ttsInput).toBeVisible()

    const listenToggle = page.locator('.ant-segmented-item').filter({ hasText: 'Listen' })
    await expect(listenToggle).toBeVisible()
    await listenToggle.click()
    await expect(
      page.locator('.ant-segmented-item-selected').filter({ hasText: 'Listen' })
    ).toBeVisible()

    const roundTripToggle = page.locator('.ant-segmented-item').filter({ hasText: 'Round-trip' })
    await roundTripToggle.click()
    await expect(page.locator('.ant-segmented-item-selected').filter({ hasText: 'Round-trip' })).toBeVisible()
    await page.keyboard.press('Escape')

    const sttCard = page.locator('.ant-card').filter({ hasText: 'Current transcription model' })
    await expect(sttCard).toBeVisible()
    const sttRecordButton = sttCard.getByRole('button', { name: 'Record' })
    await sttRecordButton.click({ force: true })

    const stopButton = sttCard.getByRole('button', { name: 'Stop' })
    await expect(stopButton).toBeVisible({ timeout: 10000 })

    const transcriptArea = sttCard.getByPlaceholder('Live transcript will appear here while recording.')
    await transcriptArea.scrollIntoViewIfNeeded()
    await expect(
      sttCard.getByText('Recording in progress; transcript is locked.')
    ).toBeVisible()
    await expect(sttCard.getByRole('button', { name: 'Unlock' })).toBeDisabled()

    await stopButton.click()
    await transcriptArea.scrollIntoViewIfNeeded()
    await expect(transcriptArea).toHaveValue('Test transcript', { timeout: 5000 })

    const unlockButton = sttCard.getByRole('button', { name: 'Unlock' })
    await unlockButton.click()
    await expect(transcriptArea).toBeEditable()
    await transcriptArea.fill('Edited transcript')
    await expect(transcriptArea).toHaveValue('Edited transcript')

    const lockButton = sttCard.getByRole('button', { name: 'Lock' })
    await lockButton.click()
    await expect(transcriptArea).not.toBeEditable()

    const historyCard = page.locator('.ant-card').filter({ hasText: /Speech history/i }).first()
    await historyCard.scrollIntoViewIfNeeded()

    const copyButton = historyCard.getByRole('button', { name: /^Copy$/i }).first()
    await expect(copyButton).toBeVisible({ timeout: 10000 })
    await copyButton.click()
    await expect(page.getByText('Copied to clipboard')).toBeVisible()

    const downloadButton = page.getByRole('button', { name: /^Download$/i }).first()
    await downloadButton.scrollIntoViewIfNeeded()
    await downloadButton.hover()
    await expect(
      page.getByText('Browser TTS does not create downloadable audio.')
    ).toBeVisible()
    await context.close()
  })
})
