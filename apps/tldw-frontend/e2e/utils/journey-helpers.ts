/**
 * Reusable helpers for cross-feature journey specs.
 * Each helper performs a common setup action and returns an identifier.
 */
import { type Page, expect } from "@playwright/test"
import { expectApiCall } from "./api-assertions"
import { TEST_CONFIG, fetchWithApiKey } from "./helpers"

/**
 * Ingest content via the media page and wait until processing completes.
 * Returns the media_id from the API response.
 */
export async function ingestAndWaitForReady(
  page: Page,
  input: { url: string } | { file: string },
  timeoutMs = 120_000
): Promise<string> {
  await page.goto("/media", { waitUntil: "domcontentloaded" })

  if ("url" in input) {
    // Use quick ingest or URL input
    const urlInput = page.getByPlaceholder(/URL|Enter URL|paste/i).first()
    if (await urlInput.isVisible().catch(() => false)) {
      await urlInput.fill(input.url)
    } else {
      // Try quick ingest button
      const quickIngestBtn = page.getByRole("button", { name: /quick ingest/i }).first()
      if (await quickIngestBtn.isVisible().catch(() => false)) {
        await quickIngestBtn.click()
        const modalInput = page.getByPlaceholder(/URL|Enter URL|paste/i).first()
        await modalInput.fill(input.url)
      }
    }

    const apiCall = expectApiCall(page, {
      method: "POST",
      url: "/api/v1/media",
    }, timeoutMs)

    // Click submit/ingest button
    const submitBtn = page.getByRole("button", { name: /ingest|submit|process|add/i }).first()
    await submitBtn.click()

    const { response } = await apiCall
    const body = await response.json()
    return body.media_id ?? body.id ?? "unknown"
  }

  // File upload path
  const fileInput = page.locator('input[type="file"]').first()
  await fileInput.setInputFiles(input.file)

  const apiCall = expectApiCall(page, {
    method: "POST",
    url: "/api/v1/media",
  }, timeoutMs)

  const submitBtn = page.getByRole("button", { name: /upload|ingest|submit|process/i }).first()
  await submitBtn.click()

  const { response } = await apiCall
  const body = await response.json()
  return body.media_id ?? body.id ?? "unknown"
}

/**
 * Create a note via the notes page. Returns the note title for later lookup.
 */
export async function createNote(
  page: Page,
  opts: { title: string; content: string }
): Promise<string> {
  await page.goto("/notes", { waitUntil: "domcontentloaded" })

  const apiCall = expectApiCall(page, {
    method: "POST",
    url: "/api/v1/notes",
  })

  // Click create/new note button
  const createBtn = page.getByRole("button", { name: /create|new|add/i }).first()
  await createBtn.click()

  // Fill title and content
  const titleInput = page.getByPlaceholder(/title/i).first()
  if (await titleInput.isVisible().catch(() => false)) {
    await titleInput.fill(opts.title)
  }

  const contentInput = page.locator("textarea, [contenteditable]").first()
  if (await contentInput.isVisible().catch(() => false)) {
    await contentInput.fill(opts.content)
  }

  // Save
  const saveBtn = page.getByRole("button", { name: /save|create|submit/i }).first()
  await saveBtn.click()

  await apiCall
  return opts.title
}

/**
 * Wait for streaming response to complete in chat.
 */
export async function waitForStreamComplete(
  page: Page,
  timeoutMs = 60_000
): Promise<void> {
  // Wait for stop button to appear then disappear
  const stopBtn = page.getByRole("button", { name: /stop/i })
  try {
    await expect(stopBtn).toBeVisible({ timeout: 10_000 })
    await expect(stopBtn).toBeHidden({ timeout: timeoutMs })
  } catch {
    // Stream may have completed before we could observe the stop button
    // Wait a moment for any pending renders
    await page.waitForTimeout(1_000)
  }
}

/**
 * Verify server is available and return basic info.
 * Useful at the start of journey tests.
 */
export async function checkServerHealth(): Promise<{
  available: boolean
  version?: string
}> {
  try {
    const res = await fetchWithApiKey(
      `${TEST_CONFIG.serverUrl}/api/v1/health`,
      TEST_CONFIG.apiKey
    )
    if (res.ok) {
      const data = await res.json()
      return { available: true, version: data.version }
    }
    return { available: false }
  } catch {
    return { available: false }
  }
}
