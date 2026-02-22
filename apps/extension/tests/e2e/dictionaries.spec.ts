import { test, expect } from '@playwright/test'
import { launchWithExtensionOrSkip } from "./utils/real-server"
import path from 'path'

const serverUrl = process.env.TLDW_E2E_SERVER_URL || 'http://127.0.0.1:8000'
const apiKey = process.env.TLDW_E2E_API_KEY || ''
const seededDictionariesConfig = {
  __tldw_first_run_complete: true,
  __tldw_allow_offline: true,
  tldwConfig: {
    serverUrl,
    authMode: 'single-user',
    ...(apiKey ? { apiKey } : {})
  }
}

test.describe('Chat Dictionaries page', () => {
  test('renders Dictionaries manager and actions', async () => {
    test.setTimeout(180000)
    const extPath = path.resolve('build/chrome-mv3')
    const { context, page, optionsUrl } = await launchWithExtensionOrSkip(test, extPath, {
      launchTimeoutMs: 90000,
      seedConfig: seededDictionariesConfig
    })

    // Navigate to Chat Dictionaries
    await page.goto(`${optionsUrl}#/settings/chat-dictionaries`, {
      waitUntil: 'domcontentloaded'
    })

    // Some builds gate the manager behind a workspace launch card.
    const openWorkspaceButton = page.getByRole('button', {
      name: /open chat dictionaries workspace/i
    })
    await openWorkspaceButton.click({ timeout: 15000 }).catch(() => {})

    // Basic UI presence
    await expect(page.getByRole('button', { name: /New Dictionary/i })).toBeVisible({ timeout: 15000 })
    await expect(page.getByRole('button', { name: /Import/i })).toBeVisible({ timeout: 15000 })

    // Manager-level helper copy is stable across loading, error, and loaded data states.
    await expect(page.getByText(/Processing order for active dictionaries/i)).toBeVisible({
      timeout: 15000
    })

    await context.close()
  })
})
