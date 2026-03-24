/**
 * Reusable helpers for cross-feature journey specs.
 * Each helper performs a common setup action and returns an identifier.
 */
import { type Locator, type Page, expect } from "@playwright/test"
import { expectApiCall } from "./api-assertions"
import { TEST_CONFIG, fetchWithApiKey, waitForConnection } from "./helpers"
import { NotesPage } from "./page-objects"

const QUICK_INGEST_JOB_STATUS_PATH = "/api/v1/media/ingest/jobs/"
const QUICK_INGEST_SUBMIT_MATCHER =
  /\/api\/v1\/media\/(?:ingest\/jobs|process-web-scraping|add)(?:[/?]|$)/i

const extractMediaId = (payload: unknown): string | undefined => {
  const body = payload as Record<string, any> | null
  const candidate =
    body?.result?.media_id ??
    body?.media_id ??
    body?.data?.media_id ??
    body?.job?.result?.media_id

  return typeof candidate === "string" && candidate.trim() ? candidate.trim() : undefined
}

const extractIngestJobIds = (payload: unknown): number[] => {
  const body = payload as Record<string, any> | null
  const rawIds = [
    body?.job_id,
    body?.id,
    ...(Array.isArray(body?.job_ids) ? body.job_ids : []),
    ...(Array.isArray(body?.jobs) ? body.jobs.map((job: any) => job?.id) : []),
  ]

  return rawIds
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value) && value > 0)
}

const waitForQuickIngestDialog = async (page: Page): Promise<Locator> => {
  const dialog = page.getByRole("dialog", { name: /quick ingest/i }).first()
  await expect(dialog).toBeVisible({ timeout: 30_000 })
  return dialog
}

const waitForQuickIngestQueueAdvance = async (
  dialog: Locator,
  timeoutMs: number
): Promise<void> => {
  await expect
    .poll(
      async () => {
        const useDefaultsVisible = await dialog
          .getByRole("button", { name: /use defaults/i })
          .isVisible()
          .catch(() => false)
        const configureVisible = await dialog
          .getByRole("button", { name: /configure \d+ items/i })
          .isVisible()
          .catch(() => false)
        const runVisible = await dialog
          .getByTestId("quick-ingest-run")
          .isVisible()
          .catch(() => false)
        return useDefaultsVisible || configureVisible || runVisible
      },
      {
        timeout: Math.min(timeoutMs, 20_000),
        message: "Timed out waiting for quick ingest to queue the submitted input",
      }
    )
    .toBe(true)
}

const waitForQuickIngestCompletionUi = async (
  dialog: Locator,
  timeoutMs: number
): Promise<void> => {
  const resultsStep = dialog.getByTestId("wizard-results-step")
  const completionSummary = dialog.getByTestId("quick-ingest-complete")
  const completedRegion = dialog.getByRole("region", { name: /completed items/i }).first()

  await expect
    .poll(
      async () => {
        const resultsVisible = await resultsStep.isVisible().catch(() => false)
        const summaryVisible = await completionSummary.isVisible().catch(() => false)
        const regionVisible = await completedRegion.isVisible().catch(() => false)
        return resultsVisible || summaryVisible || regionVisible
      },
      { timeout: timeoutMs, message: "Timed out waiting for quick ingest completion UI" }
    )
    .toBe(true)
}

const waitForCompletedIngestJob = async (
  page: Page,
  jobIds: number[],
  timeoutMs: number
): Promise<string | undefined> => {
  if (jobIds.length === 0) return undefined

  const response = await page
    .waitForResponse(
      async (candidate) => {
        if (candidate.request().method().toUpperCase() !== "GET") return false
        if (
          !jobIds.some((jobId) =>
            candidate.url().includes(`${QUICK_INGEST_JOB_STATUS_PATH}${jobId}`)
          )
        ) {
          return false
        }

        const payload = await candidate.json().catch(() => null)
        if (!payload) return false

        const status = String(
          payload?.status ?? payload?.job?.status ?? payload?.result?.status ?? ""
        ).toLowerCase()

        return (
          status === "completed" ||
          status === "succeeded" ||
          status === "success" ||
          Boolean(extractMediaId(payload))
        )
      },
      { timeout: timeoutMs }
    )
    .catch(() => null)

  if (!response) return undefined

  const payload = await response.json().catch(() => null)
  return extractMediaId(payload)
}

/**
 * Ingest content via the media page and wait until processing completes.
 * Returns the media_id from the completed ingest job when available.
 */
export async function ingestAndWaitForReady(
  page: Page,
  input: { url: string } | { file: string },
  timeoutMs = 120_000
): Promise<string> {
  await page.goto("/media", { waitUntil: "domcontentloaded" })
  await waitForConnection(page)

  const quickIngestBtn = page.getByTestId("open-quick-ingest")
  if (!(await quickIngestBtn.isVisible({ timeout: 5_000 }).catch(() => false))) {
    await page
      .getByRole("button", { name: /quick ingest|add content/i })
      .first()
      .click()
  } else {
    await quickIngestBtn.click()
  }

  const quickIngestDialog = await waitForQuickIngestDialog(page)

  const submitRequest = expectApiCall(
    page,
    {
      method: "POST",
      url: QUICK_INGEST_SUBMIT_MATCHER,
    },
    timeoutMs
  )

  if ("url" in input) {
    const namedUrlInput = quickIngestDialog
      .getByRole("textbox", { name: /paste urls input/i })
      .first()
    const urlInput = (await namedUrlInput.isVisible({ timeout: 5_000 }).catch(() => false))
      ? namedUrlInput
      : quickIngestDialog.locator("textarea").first()

    await urlInput.fill(input.url)

    const addUrlsBtn = quickIngestDialog.getByRole("button", { name: /add url/i }).first()
    if (await addUrlsBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await addUrlsBtn.click()
      await waitForQuickIngestQueueAdvance(quickIngestDialog, timeoutMs)
    }

    const useDefaultsBtn = quickIngestDialog.getByRole("button", { name: /use defaults/i }).first()
    if (await useDefaultsBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await useDefaultsBtn.click()
    } else {
      const configureBtn = quickIngestDialog
        .getByRole("button", { name: /configure \d+ items/i })
        .first()
      if (await configureBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
        await configureBtn.click()
        await expect(
          quickIngestDialog.getByRole("button", { name: /standard preset/i }).first()
        ).toBeVisible({ timeout: 20_000 })
      }

      const nextBtn = quickIngestDialog.getByRole("button", { name: /^next$/i }).first()
      if (await nextBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
        await nextBtn.click()
        await expect(quickIngestDialog.getByText(/ready to process/i)).toBeVisible({
          timeout: 20_000,
        })
      }

      const runBtn = quickIngestDialog.getByTestId("quick-ingest-run").first()
      if (await runBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
        await runBtn.click()
      } else {
        const startProcessingBtn = quickIngestDialog
          .getByRole("button", { name: /start processing|run quick ingest/i })
          .first()
        await startProcessingBtn.click()
      }
    }
  } else {
    const fileInput = quickIngestDialog.locator('input[type="file"]').first()
    await fileInput.setInputFiles(input.file)

    const runBtn = quickIngestDialog.getByTestId("quick-ingest-run").first()
    if (await runBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await runBtn.click()
    } else {
      await quickIngestDialog
        .getByRole("button", { name: /upload|ingest|submit|process/i })
        .first()
        .click()
    }
  }

  const { response } = await submitRequest
  const body = await response.json().catch(() => ({}))
  const ingestJobIds = extractIngestJobIds(body)
  const completedMediaIdPromise = waitForCompletedIngestJob(page, ingestJobIds, timeoutMs)

  await waitForQuickIngestCompletionUi(quickIngestDialog, timeoutMs)

  return (
    (await completedMediaIdPromise) ??
    extractMediaId(body) ??
    String(body.id ?? ingestJobIds[0] ?? body.batch_id ?? "unknown")
  )
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
  const assistantMessages = page.locator("article[aria-label*='Assistant message']")

  await expect
    .poll(
      async () => {
        const assistantCount = await assistantMessages.count()
        if (assistantCount === 0) return false

        const latestAssistant = assistantMessages.last()
        const isGenerating = await latestAssistant
          .getByText(/Generating response/i)
          .isVisible()
          .catch(() => false)
        const hasStopStreaming = await latestAssistant
          .getByRole("button", { name: /Stop streaming response|Stop Streaming|Stop/i })
          .isVisible()
          .catch(() => false)
        const text = ((await latestAssistant.textContent().catch(() => "")) || "")
          .replace(/▋/g, "")
          .trim()

        return Boolean(text) && !isGenerating && !hasStopStreaming
      },
      {
        timeout: timeoutMs,
        message: "Timed out waiting for a completed streamed assistant response",
      }
    )
    .toBe(true)
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
