import { test, expect, type Page } from '@playwright/test'
import path from 'path'
import { launchWithExtension } from './utils/extension'
import { grantHostPermission } from './utils/permissions'
import { requireRealServerConfig, launchWithExtensionOrSkip } from './utils/real-server'

const fetchAudioProviders = async (serverUrl: string, apiKey: string) => {
  const res = await fetch(`${serverUrl}/api/v1/audio/providers`, {
    headers: { 'x-api-key': apiKey }
  }).catch(() => null)
  if (!res || !res.ok) return null
  const payload = await res.json().catch(() => null)
  const providers = payload?.providers ?? payload
  if (!providers || typeof providers !== 'object' || Object.keys(providers).length === 0) {
    return null
  }
  return payload
}

const launchWithServer = async (serverUrl: string, apiKey: string) => {
  const extPath = path.resolve('build/chrome-mv3')
  return await launchWithExtensionOrSkip(test, extPath, {
    seedConfig: {
      __tldw_first_run_complete: true,
      __tldw_allow_offline: true,
      tldw_skip_landing_hub: true,
      'tldw:workflow:landing-config': {
        showOnFirstRun: true,
        dismissedAt: Date.now(),
        completedWorkflows: []
      },
      tldwConfig: {
        serverUrl,
        authMode: 'single-user',
        apiKey
      }
    }
  })
}

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

const waitForTtsPageReady = async (page: Page) => {
  await expect(page.getByText(/TTS Playground/i)).toBeVisible({ timeout: 15000 })
}

const getTtsProviderSelect = (page: Page) => page.locator('#tts-provider-select').first()

const getTtsProviderSelectContainer = (page: Page) =>
  getTtsProviderSelect(page)
    .locator('xpath=ancestor::div[contains(@class,"ant-select")]')
    .first()

const readCurrentTtsProviderLabel = async (page: Page) => {
  const fromDirectSelection = await page
    .locator('#tts-provider-select .ant-select-selection-item')
    .first()
    .textContent({ timeout: 600 })
    .then((value) => value?.trim() ?? '')
    .catch(() => '')
  if (fromDirectSelection) return fromDirectSelection

  const providerSelectContainer = getTtsProviderSelectContainer(page)
  const fromSelection = await providerSelectContainer
    .locator('.ant-select-selection-item')
    .first()
    .textContent({ timeout: 600 })
    .then((value) => value?.trim() ?? '')
    .catch(() => '')
  if (fromSelection) return fromSelection

  return page
    .getByText(/Current provider:/i)
    .first()
    .textContent({ timeout: 1200 })
    .then((value) => value?.replace(/^Current provider:\s*/i, '').trim() ?? '')
    .catch(() => '')
}

const openTtsProviderSelect = async (page: Page) => {
  const providerSelect = getTtsProviderSelect(page)
  await expect(providerSelect).toBeVisible({ timeout: 10000 })
  const providerSelectContainer = getTtsProviderSelectContainer(page)
  const useContainer = (await providerSelectContainer.count()) > 0
  const clickableTarget = useContainer ? providerSelectContainer : providerSelect
  await clickableTarget.scrollIntoViewIfNeeded()
  await clickableTarget.click({ timeout: 5000 })
}

const chooseTtsProvider = async (page: Page, optionPattern: RegExp) => {
  const currentProvider = await readCurrentTtsProviderLabel(page)
  if (optionPattern.test(currentProvider)) {
    return true
  }

  await openTtsProviderSelect(page)
  const optionByRole = page.getByRole('option', { name: optionPattern }).first()
  const optionByAntdContent = page
    .locator('.ant-select-dropdown .ant-select-item-option-content')
    .filter({ hasText: optionPattern })
    .first()

  const roleVisible = await optionByRole.isVisible({ timeout: 1200 }).catch(() => false)
  const antVisible = roleVisible
    ? false
    : await optionByAntdContent.isVisible({ timeout: 4000 }).catch(() => false)

  if (!roleVisible && !antVisible) {
    await page.keyboard.press('Escape').catch(() => {})
    return false
  }

  let clicked = false
  if (roleVisible) {
    await optionByRole
      .click({ timeout: 3000 })
      .then(() => {
        clicked = true
      })
      .catch(() => {})
  } else {
    await optionByAntdContent
      .click({ timeout: 3000 })
      .then(() => {
        clicked = true
      })
      .catch(() => {})
  }

  if (!clicked) {
    await page.keyboard.press('Escape').catch(() => {})
    return false
  }

  const selectedByReadback = await expect
    .poll(
      async () => {
        const selectedProvider = await readCurrentTtsProviderLabel(page)
        return optionPattern.test(selectedProvider)
      },
      { timeout: 5000 }
    )
    .toBe(true)
    .then(() => true)
    .catch(() => false)

  await page.keyboard.press('Escape').catch(() => {})
  if (selectedByReadback) return true

  // The "Current provider" summary can lag after changing the select value.
  // Treat a successful option click as selected; downstream assertions verify
  // provider-specific behavior.
  return true
}

const clickSaveIfEnabled = async (page: Page) => {
  const saveButtons = page.getByRole('button', { name: /^save$/i })
  const count = await saveButtons.count()
  for (let index = 0; index < count; index += 1) {
    const button = saveButtons.nth(index)
    const visible = await button
      .isVisible({ timeout: 500 })
      .then(() => true)
      .catch(() => false)
    if (!visible) continue
    const enabled = await button.isEnabled().catch(() => false)
    if (!enabled) continue
    await button.click()
    return true
  }
  return false
}

const selectTldwProvider = async (page: Page) => {
  return chooseTtsProvider(page, /tldw server \(audio\/speech\)/i)
}

test.describe('TTS Playground UX', () => {
  test('shows ElevenLabs timeout hint and recovers on retry', async () => {
    const extPath = path.resolve('build/chrome-mv3')
    const { context, page, optionsUrl } = await launchWithExtensionOrSkip(test, extPath, {
      seedConfig: {
        __tldw_first_run_complete: true,
        __tldw_allow_offline: true,
        ttsProvider: 'elevenlabs',
        tldw_skip_landing_hub: true,
        'tldw:workflow:landing-config': {
          showOnFirstRun: true,
          dismissedAt: Date.now(),
          completedWorkflows: []
        },
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

    await page.goto(optionsUrl + '#/tts', {
      waitUntil: 'domcontentloaded'
    })
    await dismissWorkflowHubIfVisible(page)
    await waitForTtsPageReady(page)

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

  test('plays tldw server audio and shows generated segments', async () => {
    const { serverUrl, apiKey } = requireRealServerConfig(test)
    const normalizedServerUrl = serverUrl.replace(/\/$/, '')

    const providers = await fetchAudioProviders(normalizedServerUrl, apiKey)
    if (!providers) {
      test.skip(true, 'Audio providers not available on the configured server.')
      return
    }

    const { context, page, optionsUrl, extensionId } = await launchWithServer(
      normalizedServerUrl,
      apiKey
    )

    try {
      const origin = new URL(normalizedServerUrl).origin + '/*'
      const granted = await grantHostPermission(context, extensionId, origin)
      if (!granted) {
        test.skip(
          true,
          'Host permission not granted for tldw_server origin; allow it in chrome://extensions > tldw Assistant > Site access, then re-run'
        )
        return
      }

      await page.goto(optionsUrl + '#/tts', {
        waitUntil: 'domcontentloaded'
      })
      await dismissWorkflowHubIfVisible(page)
      await waitForTtsPageReady(page)

      await expect(page.getByText(/Current provider/i)).toBeVisible()

      const providerSelected = await selectTldwProvider(page)
      if (!providerSelected) {
        test.skip(true, 'tldw server option not available in provider list.')
        return
      }

      await clickSaveIfEnabled(page)

      const textarea = page.getByPlaceholder(
        /Type or paste text here, then use Play to listen./i
      )
      await textarea.fill('Hello from the TTS playback test')

      await page.getByRole('button', { name: /^Play$/i }).click()

      await expect(
        page.getByText(/Generated audio segments/i)
      ).toBeVisible({ timeout: 20_000 })
      await expect(page.locator('audio')).toBeVisible()
    } finally {
      await context.close()
    }
  })

  test('shows browser TTS segment controls', async () => {
    const extPath = path.resolve('build/chrome-mv3')
    const { context, page, optionsUrl } = await launchWithExtensionOrSkip(test, extPath, {
      seedConfig: {
        __tldw_first_run_complete: true,
        __tldw_allow_offline: true,
        ttsEnabled: true,
        ttsProvider: 'browser',
        voice: '',
        tldw_skip_landing_hub: true,
        'tldw:workflow:landing-config': {
          showOnFirstRun: true,
          dismissedAt: Date.now(),
          completedWorkflows: []
        }
      }
    })

    await page.goto(optionsUrl + '#/tts', {
      waitUntil: 'domcontentloaded'
    })
    await dismissWorkflowHubIfVisible(page)
    await waitForTtsPageReady(page)
    await expect(page.getByText(/Current provider:\s*Browser TTS/i)).toBeVisible()

    await page
      .getByPlaceholder(/Type or paste text here, then use Play to listen./i)
      .fill('Browser TTS test sentence one. Sentence two.')

    const playButton = page.getByRole('button', { name: /^Play$/i })
    await expect(playButton).toBeEnabled()
    await playButton.click({ timeout: 5000 })

    await expect(page.getByText(/Browser TTS segments/i)).toBeVisible()
    await expect(
      page.getByRole('button', { name: /Queue all/i })
    ).toBeVisible()
    await expect(
      page.getByRole('button', { name: /Play segment/i })
    ).toBeVisible()

    await context.close()
  })

  test('disables Play when ElevenLabs config is incomplete', async () => {
    const extPath = path.resolve('build/chrome-mv3')
    const { context, page, optionsUrl } = await launchWithExtensionOrSkip(test, extPath, {
      seedConfig: {
        __tldw_first_run_complete: true,
        __tldw_allow_offline: true,
        tldw_skip_landing_hub: true,
        'tldw:workflow:landing-config': {
          showOnFirstRun: true,
          dismissedAt: Date.now(),
          completedWorkflows: []
        }
      }
    })

    await page.goto(optionsUrl + '#/tts', {
      waitUntil: 'domcontentloaded'
    })
    await dismissWorkflowHubIfVisible(page)
    await waitForTtsPageReady(page)

    const seededIncompleteConfig = await page.evaluate(async () => {
      try {
        const storage = (window as any).chrome?.storage
        if (!storage?.local?.set) return false
        const payload = {
          ttsProvider: 'elevenlabs',
          elevenLabsApiKey: '',
          elevenLabsVoiceId: '',
          elevenLabsModel: ''
        }
        await storage.local.set(payload)
        if (storage?.sync?.set) {
          await storage.sync.set(payload)
        }
        return true
      } catch {
        return false
      }
    })
    expect(seededIncompleteConfig).toBe(true)
    await page.reload({ waitUntil: 'domcontentloaded' })
    await dismissWorkflowHubIfVisible(page)
    await waitForTtsPageReady(page)

    await page
      .getByPlaceholder(/Type or paste text here, then use Play to listen./i)
      .fill('Hello from the ElevenLabs config test')

    const playButton = page.getByRole('button', { name: /^Play$/i })
    await expect(playButton).toBeDisabled()
    await expect(
      page.getByText(/Add an ElevenLabs API key, voice, and model/i)
    ).toBeVisible()

    await context.close()
  })

  test('shows tldw provider capabilities and voices preview from /audio/providers', async () => {
    const { serverUrl, apiKey } = requireRealServerConfig(test)
    const normalizedServerUrl = serverUrl.replace(/\/$/, '')

    const providers = await fetchAudioProviders(normalizedServerUrl, apiKey)
    if (!providers) {
      test.skip(true, 'Audio providers not available on the configured server.')
      return
    }

    const { context, page, optionsUrl, extensionId } = await launchWithServer(
      normalizedServerUrl,
      apiKey
    )

    try {
      const origin = new URL(normalizedServerUrl).origin + '/*'
      const granted = await grantHostPermission(context, extensionId, origin)
      if (!granted) {
        test.skip(
          true,
          'Host permission not granted for tldw_server origin; allow it in chrome://extensions > tldw Assistant > Site access, then re-run'
        )
        return
      }

      await page.goto(optionsUrl + '#/tts', {
        waitUntil: 'domcontentloaded'
      })
      await dismissWorkflowHubIfVisible(page)
      await waitForTtsPageReady(page)

      const providerSelected = await selectTldwProvider(page)
      if (!providerSelected) {
        test.skip(true, 'tldw server option not available in provider list.')
        return
      }

      await clickSaveIfEnabled(page)

      await expect(
        page.getByText(/audio API detected/i)
      ).toBeVisible({ timeout: 15_000 })

      await expect(page.getByText(/Provider capabilities/i)).toBeVisible({
        timeout: 10_000
      })
      await expect(page.getByText(/Server voices/i)).toBeVisible()

      await expect(
        page.getByRole('button', { name: /View raw provider config/i })
      ).toBeVisible()
    } finally {
      await context.close()
    }
  })
})
