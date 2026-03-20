import { readFileSync, statSync } from "node:fs"
import path from "node:path"

import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../utils/fixtures"
import { expectApiCall } from "../utils/api-assertions"
import {
  seedAuth,
  fetchWithApiKey,
  TEST_CONFIG,
  generateTestId,
} from "../utils/helpers"
import { WorkspacePlaygroundPage } from "../utils/page-objects"

const DESKTOP_VIEWPORT = { width: 1440, height: 900 }

type LiveWorkspaceSource = {
  mediaId: number
  title: string
  type: "document"
  url: string
}

const normalizeWhitespace = (value: string): string =>
  value.replace(/\s+/g, " ").trim()

const seedLiveWorkspaceDocument = async (
  title: string,
  content: string,
): Promise<LiveWorkspaceSource> => {
  const fileName = `${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.txt`
  const body = new FormData()
  body.append("media_type", "document")
  body.append("title", title)
  body.append("perform_analysis", "false")
  body.append("perform_chunking", "false")
  body.append("files", new Blob([content], { type: "text/plain" }), fileName)

  const response = await fetchWithApiKey(
    `${TEST_CONFIG.serverUrl}/api/v1/media/add`,
    TEST_CONFIG.apiKey,
    {
      method: "POST",
      body,
    },
  )
  if (!response.ok) {
    throw new Error(
      `Failed to seed output-matrix media "${title}": ${response.status} ${await response.text()}`,
    )
  }

  const payload = await response.json().catch(() => ({}))
  const result = Array.isArray(payload?.results)
    ? payload.results[0]
    : payload?.result || payload
  const mediaId = Number(result?.db_id ?? result?.media_id ?? result?.id)
  if (!Number.isFinite(mediaId) || mediaId <= 0) {
    throw new Error(
      `Output-matrix media seed for "${title}" returned no usable media id: ${JSON.stringify(
        payload,
      )}`,
    )
  }

  const expectedSnippet = normalizeWhitespace(content).slice(0, 48)
  await expect
    .poll(
      async () => {
        const details = await fetchWithApiKey(
          `${TEST_CONFIG.serverUrl}/api/v1/media/${mediaId}?include_content=true&include_versions=false&include_version_content=false`,
          TEST_CONFIG.apiKey,
        )
        if (!details.ok) return ""
        const body = await details.json().catch(() => ({}))
        return normalizeWhitespace(
          String(
            body?.content?.text ??
              body?.content?.content ??
              body?.transcript ??
              "",
          ),
        )
      },
      {
        timeout: 30_000,
        message: `Media ${mediaId} never exposed usable content for the workspace output matrix`,
      },
    )
    .toContain(expectedSnippet)

  return {
    mediaId,
    title,
    type: "document",
    url: `file://${fileName}`,
  }
}

const buildLiveWorkspaceSources = async (): Promise<LiveWorkspaceSource[]> => {
  const fixtureId = generateTestId("workspace-output-matrix")
  return Promise.all([
    seedLiveWorkspaceDocument(
      `WS ${fixtureId} Alpha`,
      `Workspace output matrix alpha source. Claim: rollout improved by 12 percent. Token ${fixtureId}-alpha.`,
    ),
    seedLiveWorkspaceDocument(
      `WS ${fixtureId} Beta`,
      `Workspace output matrix beta source. Claim: retention improved by 18 percent. Token ${fixtureId}-beta.`,
    ),
  ])
}

const OUTPUTS = [
  { label: "Report", textDownload: true },
  { label: "Compare Sources", textDownload: true },
  { label: "Timeline", textDownload: true },
  { label: "Data Table", textDownload: true },
  { label: "Mind Map", textDownload: true },
  { label: "Slides", textDownload: false },
  { label: "Quiz", textDownload: true },
  { label: "Flashcards", textDownload: true },
] as const

const hasErrorText = (content: string) =>
  /error encountered|generation failed|no usable|download failed|could not/i.test(
    content,
  )

const disableNextJsPortalPointerInterception = async (
  page: import("@playwright/test").Page,
) => {
  await page.evaluate(() => {
    document.querySelectorAll("nextjs-portal").forEach((portal) => {
      ;(portal as HTMLElement).style.pointerEvents = "none"
    })
  })
}

const activateButton = async (
  page: import("@playwright/test").Page,
  button: import("@playwright/test").Locator,
) => {
  try {
    await button.click({ timeout: 5_000 })
  } catch (error) {
    if (!String(error).includes("nextjs-portal")) {
      throw error
    }
    await button.focus()
    await expect(button).toBeFocused({ timeout: 5_000 })
    await button.press("Enter")
  }
}

const prepareWorkspaceForOutput = async (
  page: import("@playwright/test").Page,
  outputLabel: string,
) => {
  const workspacePage = new WorkspacePlaygroundPage(page)
  const liveSources = await buildLiveWorkspaceSources()

  await workspacePage.goto()
  await workspacePage.waitForReady()
  await workspacePage.resetWorkspace(`Workspace ${generateTestId(outputLabel)}`)
  await workspacePage.seedSources(liveSources)
  await expect
    .poll(async () => (await workspacePage.getSourceIds()).length, {
      timeout: 10_000,
    })
    .toBeGreaterThanOrEqual(2)

  const sourceIds = await workspacePage.getSourceIds()
  await workspacePage.selectSourceById(sourceIds[0])
  await workspacePage.selectSourceById(sourceIds[1])
  await workspacePage.expectSourceSelected(sourceIds[0])
  await workspacePage.expectSourceSelected(sourceIds[1])
  await expect(workspacePage.getStudioArtifactCards()).toHaveCount(0)

  return workspacePage
}

const verifyDownloadedArtifact = async (
  download: import("@playwright/test").Download,
  textDownload: boolean,
) => {
  const artifactPath = path.join(
    process.cwd(),
    "test-results",
    download.suggestedFilename(),
  )
  await download.saveAs(artifactPath)

  if (textDownload) {
    const content = readFileSync(artifactPath, "utf8")
    expect(content.trim().length).toBeGreaterThan(20)
    expect(hasErrorText(content)).toBe(false)
    return
  }

  expect(statSync(artifactPath).size).toBeGreaterThan(32)
}

const generateAndDownloadOutput = async (
  page: import("@playwright/test").Page,
  workspacePage: WorkspacePlaygroundPage,
  output: (typeof OUTPUTS)[number],
) => {
  const cards = workspacePage.getStudioArtifactCards()
  const chatCompletionCall =
    output.label === "Data Table"
      ? expectApiCall(
          page,
          { method: "POST", url: "/api/v1/chat/completions" },
          20_000,
        )
      : null

  const outputButton = workspacePage.getStudioOutputButton(output.label)
  await disableNextJsPortalPointerInterception(page)
  await expect(outputButton).toBeVisible({ timeout: 15_000 })
  await expect(outputButton).toBeEnabled({ timeout: 15_000 })
  await outputButton.scrollIntoViewIfNeeded()
  await activateButton(page, outputButton)

  await expect(cards).toHaveCount(1, { timeout: 90_000 })
  const artifactCard = cards.first()
  await expect(artifactCard).toBeVisible({ timeout: 30_000 })
  await expect(artifactCard).toContainText(output.label, { timeout: 30_000 })

  if (chatCompletionCall) {
    const { request, response } = await chatCompletionCall
    const responseBody = await response.json().catch(() => null)
    if (response.status() !== 200) {
      throw new Error(
        `Data Table chat completion failed with ${response.status()}: ${JSON.stringify({
          requestBody: request.postDataJSON(),
          responseBody,
        })}`,
      )
    }
  }

  await expect
    .poll(
      async () => {
        const downloadVisible = await artifactCard
          .getByRole("button", { name: "Download" })
          .isVisible()
          .catch(() => false)
        if (downloadVisible) {
          return "completed"
        }

        const cardText = (await artifactCard.textContent()) || ""
        if (/failed|encountered an error|no usable/i.test(cardText)) {
          return `failed:${cardText}`
        }

        return "pending"
      },
      {
        timeout: output.label === "Slides" ? 180_000 : 120_000,
        message: `${output.label} did not reach a completed state`,
      },
    )
    .toBe("completed")

  await expect(artifactCard).not.toContainText(/failed|encountered an error/i, {
    timeout: 5_000,
  })

  const downloadButton = artifactCard.getByRole("button", { name: "Download" })
  await expect(downloadButton).toBeVisible({ timeout: 30_000 })
  await disableNextJsPortalPointerInterception(page)
  await downloadButton.scrollIntoViewIfNeeded()

  if (output.label === "Slides") {
    const directSlidesDownload = page
      .waitForEvent("download", { timeout: 3_000 })
      .then((event) => event)
      .catch(() => null)
    await disableNextJsPortalPointerInterception(page)
    await activateButton(page, downloadButton)
    const markdownOption = page.getByRole("button", { name: /Markdown/i }).last()
    const download =
      (await directSlidesDownload) ||
      (await markdownOption.isVisible({ timeout: 3_000 }).catch(() => false)
        ? await (async () => {
            await disableNextJsPortalPointerInterception(page)
            await markdownOption.scrollIntoViewIfNeeded()
            return Promise.all([
              page.waitForEvent("download", { timeout: 30_000 }),
              activateButton(page, markdownOption),
            ]).then(([event]) => event)
          })()
        : null)

    if (!download) {
      throw new Error(
        "Slides export did not trigger a direct download or show a format picker",
      )
    }

    if (download.suggestedFilename().toLowerCase().endsWith(".md")) {
      await verifyDownloadedArtifact(download, true)
    } else {
      await verifyDownloadedArtifact(download, false)
    }
    return
  }

  const download = await Promise.all([
    page.waitForEvent("download", { timeout: 30_000 }),
    activateButton(page, downloadButton),
  ]).then(([event]) => event)

  await verifyDownloadedArtifact(download, output.textDownload)
}

test.describe("Workspace Playground output matrix probe", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    await page.setViewportSize(DESKTOP_VIEWPORT)
  })

  for (const output of OUTPUTS) {
    test(`generates and downloads ${output.label}`, async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      test.setTimeout(output.label === "Slides" ? 240_000 : 180_000)
      skipIfServerUnavailable(serverInfo)

      const workspacePage = await prepareWorkspaceForOutput(
        authedPage,
        output.label.toLowerCase().replace(/\s+/g, "-"),
      )
      await generateAndDownloadOutput(authedPage, workspacePage, output)
      await assertNoCriticalErrors(diagnostics)
    })
  }
})
