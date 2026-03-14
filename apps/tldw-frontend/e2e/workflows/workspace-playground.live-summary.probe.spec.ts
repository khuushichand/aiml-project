import { readFileSync } from "node:fs"
import path from "node:path"

import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../utils/fixtures"
import { seedAuth } from "../utils/helpers"
import { WorkspacePlaygroundPage } from "../utils/page-objects"

const DESKTOP_VIEWPORT = { width: 1440, height: 900 }

const REAL_SOURCE = {
  mediaId: 1,
  title: "Let the LLM Write the Prompts: An Intro to DSPy in Compound AI Pipelines",
  type: "video" as const,
  url: "https://www.youtube.com/watch?v=I9ZtkgYZnOw",
}

test.describe("Workspace Playground live summary probe", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    await page.setViewportSize(DESKTOP_VIEWPORT)
  })

  test("generates and downloads a live summary artifact without error text", async ({
    authedPage,
    serverInfo,
    diagnostics,
  }) => {
    test.setTimeout(120_000)
    skipIfServerUnavailable(serverInfo)

    const workspacePage = new WorkspacePlaygroundPage(authedPage)
    await workspacePage.goto()
    await workspacePage.waitForReady()

    await workspacePage.seedSources([REAL_SOURCE])
    await expect
      .poll(async () => (await workspacePage.getSourceIds()).length, {
        timeout: 10_000,
      })
      .toBeGreaterThanOrEqual(1)

    const sourceIds = await workspacePage.getSourceIds()
    await workspacePage.selectSourceById(sourceIds[0])
    await workspacePage.expectSourceSelected(sourceIds[0])

    const ragResponsePromise = authedPage.waitForResponse(
      (response) =>
        /\/api\/v1\/rag\/search(?:\/)?$/i.test(response.url()) &&
        response.request().method().toUpperCase() === "POST",
      { timeout: 60_000 },
    )

    await authedPage.getByRole("button", { name: "Summary", exact: true }).click()

    const ragResponse = await ragResponsePromise
    expect(ragResponse.status()).toBe(200)

    const artifactCard = authedPage.locator("[data-testid^='studio-artifact-card-']").first()
    await expect(artifactCard).toBeVisible({ timeout: 60_000 })
    await expect(
      artifactCard.getByRole("button", { name: "Download" }),
    ).toBeVisible({ timeout: 60_000 })

    const download = await Promise.all([
      authedPage.waitForEvent("download", { timeout: 30_000 }),
      artifactCard.getByRole("button", { name: "Download" }).click(),
    ]).then(([event]) => event)

    const suggestedName = download.suggestedFilename()
    const artifactPath = path.join(process.cwd(), "test-results", suggestedName)
    await download.saveAs(artifactPath)

    const content = readFileSync(artifactPath, "utf8")
    expect(content.trim().length).toBeGreaterThan(20)
    expect(content).not.toMatch(/error encountered|generation failed|no usable summary/i)

    await assertNoCriticalErrors(diagnostics)
  })
})
