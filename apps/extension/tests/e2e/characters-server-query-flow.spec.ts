import { expect, test } from "@playwright/test"
import { launchWithExtension } from "./utils/extension"
import { grantHostPermission } from "./utils/permissions"
import { requireRealServerConfig } from "./utils/real-server"

const normalizeServerUrl = (value: string) =>
  value.match(/^https?:\/\//) ? value : `http://${value}`

test.describe("Characters server query flow", () => {
  test("uses server-driven query endpoint with lightweight avatar payload", async () => {
    test.setTimeout(90000)
    const { serverUrl, apiKey } = requireRealServerConfig(test)
    const normalizedServerUrl = normalizeServerUrl(serverUrl)

    const { context, page, extensionId, optionsUrl } = await launchWithExtension("", {
      seedConfig: {
        __tldw_first_run_complete: true,
        tldw_skip_landing_hub: true,
        "tldw:workflow:landing-config": {
          showOnFirstRun: true,
          dismissedAt: Date.now(),
          completedWorkflows: []
        },
        tldwConfig: {
          serverUrl: normalizedServerUrl,
          authMode: "single-user",
          apiKey
        }
      }
    })

    const origin = new URL(normalizedServerUrl).origin + "/*"
    const granted = await grantHostPermission(context, extensionId, origin)
    if (!granted) {
      await context.close()
      test.skip(
        true,
        "Host permission not granted for tldw_server origin; allow it in chrome://extensions and re-run"
      )
      return
    }

    const characterQueryUrls: string[] = []
    page.on("request", (request) => {
      const url = request.url()
      if (url.includes("/api/v1/characters/query")) {
        characterQueryUrls.push(url)
      }
    })

    try {
      await page.goto(`${optionsUrl}#/characters`, {
        waitUntil: "domcontentloaded"
      })

      await expect.poll(() => characterQueryUrls.length, {
        timeout: 25000
      }).toBeGreaterThan(0)

      const initialUrl = new URL(characterQueryUrls[0])
      expect(initialUrl.searchParams.get("include_image_base64")).toBe("false")

      const searchInput = page.getByPlaceholder(/Search characters/i).first()
      await expect(searchInput).toBeVisible({ timeout: 15000 })
      await searchInput.fill("stage4-rollout-check")

      await expect.poll(
        () =>
          characterQueryUrls.some((url) => {
            const parsed = new URL(url)
            return parsed.searchParams.get("query") === "stage4-rollout-check"
          }),
        { timeout: 25000 }
      ).toBe(true)
    } finally {
      await context.close()
    }
  })
})
