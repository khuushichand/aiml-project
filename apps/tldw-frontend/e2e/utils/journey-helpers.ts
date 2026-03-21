/**
 * Reusable helpers for cross-feature journey specs.
 * Each helper performs a common setup action and returns an identifier.
 */
import { type Page, expect } from "@playwright/test"
import { expectApiCall } from "./api-assertions"
import { TEST_CONFIG, fetchWithApiKey, waitForConnection } from "./helpers"
import { NotesPage } from "./page-objects"

/**
 * Ingest content via the media page and wait until processing completes.
 * Returns the media_id from the API response.
 */
export async function ingestAndWaitForReady(
  page: Page,
  input: { url: string } | { file: string },
  timeoutMs = 120_000
): Promise<string> {
  // Quick ingest is available from any page via the sidebar button
  await page.goto("/media", { waitUntil: "domcontentloaded" })
  await waitForConnection(page)

  // Open quick ingest wizard
  const quickIngestBtn = page.getByTestId("open-quick-ingest")
  if (!(await quickIngestBtn.isVisible({ timeout: 5_000 }).catch(() => false))) {
    // Try sidebar button with text
    const sidebarBtn = page.getByRole("button", { name: /quick ingest|add content/i }).first()
    await sidebarBtn.click()
  } else {
    await quickIngestBtn.click()
  }

  // Wait for wizard modal to appear
  await page.waitForTimeout(1_000)

  if ("url" in input) {
    // Find URL input in the wizard (textarea with https:// placeholder)
    const urlInput = page.getByPlaceholder(/https:\/\//i).first()
    if (!(await urlInput.isVisible({ timeout: 5_000 }).catch(() => false))) {
      // Try any textarea in the modal
      const textarea = page.locator(".ant-modal textarea, .ant-drawer textarea").first()
      await textarea.fill(input.url)
    } else {
      await urlInput.fill(input.url)
    }

    // Click "Add URLs" button to queue the URL (button text: "+ Add URLs")
    const addUrlsBtn = page.getByRole("button", { name: /add url/i }).first()
    if (await addUrlsBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await addUrlsBtn.click()
      await page.waitForTimeout(1_000)
    }

    // Set up API expectation before proceeding through wizard steps
    const apiCall = expectApiCall(page, {
      method: "POST",
      url: /\/api\/v1\/media/,
    }, timeoutMs)

    // The wizard has steps: Add → Configure → Review → Processing → Results
    // Fast path: "Use defaults & process" skips Configure/Review (visible when ≤1 item)
    const useDefaultsBtn = page.getByRole("button", { name: /use defaults/i })
    if (await useDefaultsBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await useDefaultsBtn.click()
    } else {
      // Slow path: navigate through wizard steps
      for (let step = 0; step < 4; step++) {
        // Look for the run/process button (testid on ProcessButton component)
        const runBtn = page.getByTestId("quick-ingest-run")
        if (await runBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
          await runBtn.click()
          break
        }
        // "Start Processing" on Review step, or "Configure"/"Next" on earlier steps
        const nextBtn = page.getByRole("button", { name: /configure|next|review|proceed|start processing|ingest|run/i }).first()
        if (await nextBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
          await nextBtn.click()
          await page.waitForTimeout(1_000)
        } else {
          break
        }
      }
    }

    const { response } = await apiCall
    const body = await response.json().catch(() => ({}))
    return body.media_id ?? body.id ?? "unknown"
  }

  // File upload path
  const fileInput = page.locator('input[type="file"]').first()
  await fileInput.setInputFiles(input.file)

  const apiCall = expectApiCall(page, {
    method: "POST",
    url: /\/api\/v1\/media/,
  }, timeoutMs)

  const runBtn = page.getByTestId("quick-ingest-run")
  if (await runBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
    await runBtn.click()
  } else {
    const submitBtn = page.getByRole("button", { name: /upload|ingest|submit|process/i }).first()
    await submitBtn.click()
  }

  const { response } = await apiCall
  const body = await response.json().catch(() => ({}))
  return body.media_id ?? body.id ?? "unknown"
}

/**
 * Create a note via the notes page. Returns the note title for later lookup.
 * Uses the same selectors as NotesPage page object for reliability.
 */
export async function createNote(
  page: Page,
  opts: { title: string; content: string }
): Promise<string> {
  const notesPage = new NotesPage(page)
  await notesPage.goto()
  await notesPage.assertPageReady()
  await notesPage.createNote({
    title: opts.title,
    content: opts.content,
  })
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
