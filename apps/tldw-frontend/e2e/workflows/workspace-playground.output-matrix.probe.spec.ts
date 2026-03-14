import { readFileSync, statSync } from "node:fs"
import path from "node:path"

import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../utils/fixtures"
import { expectApiCall } from "../utils/api-assertions"
import { seedAuth } from "../utils/helpers"
import { WorkspacePlaygroundPage } from "../utils/page-objects"

const DESKTOP_VIEWPORT = { width: 1440, height: 900 }

const REAL_SOURCES = [
  {
    mediaId: 1,
    title: "Let the LLM Write the Prompts: An Intro to DSPy in Compound AI Pipelines",
    type: "video" as const,
    url: "https://www.youtube.com/watch?v=I9ZtkgYZnOw",
  },
  {
    mediaId: 2,
    title: "E2E DB Media",
    type: "document" as const,
    url: "file://e2e_sample.txt",
  },
] as const

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

test.describe("Workspace Playground output matrix probe", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    await page.setViewportSize(DESKTOP_VIEWPORT)
  })

  test("generates and downloads the remaining non-audio studio outputs", async ({
    authedPage,
    serverInfo,
    diagnostics,
  }) => {
    test.setTimeout(240_000)
    skipIfServerUnavailable(serverInfo)

    const workspacePage = new WorkspacePlaygroundPage(authedPage)
    await workspacePage.goto()
    await workspacePage.waitForReady()

    await workspacePage.seedSources([...REAL_SOURCES])
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

    const cards = authedPage.locator("[data-testid^='studio-artifact-card-']")

    for (const output of OUTPUTS) {
      const beforeCount = await cards.count()
      const chatCompletionCall =
        output.label === "Data Table"
          ? expectApiCall(
              authedPage,
              { method: "POST", url: "/api/v1/chat/completions" },
              20_000,
            )
          : null
      await authedPage.getByRole("button", { name: output.label, exact: true }).click()

      await expect(cards).toHaveCount(beforeCount + 1, { timeout: 90_000 })
      const artifactCard = cards.first()
      await expect(artifactCard).toBeVisible({ timeout: 30_000 })

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
            timeout: 120_000,
            message: `${output.label} did not reach a completed state`
          }
        )
        .toBe("completed")

      await expect(artifactCard).not.toContainText(/failed|encountered an error/i, {
        timeout: 5_000
      })

      const downloadButton = artifactCard.getByRole("button", { name: "Download" })
      await expect(downloadButton).toBeVisible({ timeout: 30_000 })

      if (output.label === "Slides") {
        await downloadButton.click()
        const markdownOption = authedPage.getByRole("button", { name: /Markdown/i }).last()
        await expect(markdownOption).toBeVisible({ timeout: 10_000 })
        const download = await Promise.all([
          authedPage.waitForEvent("download", { timeout: 30_000 }),
          markdownOption.click(),
        ]).then(([event]) => event)
        const artifactPath = path.join(
          process.cwd(),
          "test-results",
          download.suggestedFilename(),
        )
        await download.saveAs(artifactPath)
        const content = readFileSync(artifactPath, "utf8")
        expect(content.trim().length).toBeGreaterThan(20)
        expect(hasErrorText(content)).toBe(false)
        continue
      }

      const download = await Promise.all([
        authedPage.waitForEvent("download", { timeout: 30_000 }),
        downloadButton.click(),
      ]).then(([event]) => event)

      const artifactPath = path.join(
        process.cwd(),
        "test-results",
        download.suggestedFilename(),
      )
      await download.saveAs(artifactPath)

      if (output.textDownload) {
        const content = readFileSync(artifactPath, "utf8")
        expect(content.trim().length).toBeGreaterThan(20)
        expect(hasErrorText(content)).toBe(false)
      } else {
        expect(statSync(artifactPath).size).toBeGreaterThan(32)
      }
    }

    await assertNoCriticalErrors(diagnostics)
  })
})
