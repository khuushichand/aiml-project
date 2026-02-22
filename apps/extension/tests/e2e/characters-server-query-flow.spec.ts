import { expect, test } from "@playwright/test"
import { grantHostPermission } from "./utils/permissions"
import { requireRealServerConfig, launchWithExtensionOrSkip } from "./utils/real-server"

const normalizeServerUrl = (value: string) =>
  value.match(/^https?:\/\//) ? value : `http://${value}`

test.describe("Characters server query flow", () => {
  test("uses server-driven query endpoint with lightweight avatar payload", async () => {
    test.setTimeout(90000)
    const { serverUrl, apiKey } = requireRealServerConfig(test)
    const normalizedServerUrl = normalizeServerUrl(serverUrl)

    const { context, page, extensionId, optionsUrl } = await launchWithExtensionOrSkip(
      test,
      "",
      {
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
      }
    )

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
    const legacyCharacterListUrls: string[] = []
    page.on("request", (request) => {
      const url = request.url()
      if (url.includes("/api/v1/characters/query")) {
        characterQueryUrls.push(url)
        return
      }
      try {
        const parsed = new URL(url)
        if (parsed.pathname === "/api/v1/characters") {
          legacyCharacterListUrls.push(url)
        }
      } catch {
        // ignore invalid request URLs
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
      expect(initialUrl.searchParams.get("page")).toBe("1")
      expect(initialUrl.searchParams.get("page_size")).toBeTruthy()
      expect(initialUrl.searchParams.get("sort_by")).toBeTruthy()
      expect(initialUrl.searchParams.get("sort_order")).toMatch(/^(asc|desc)$/)
      expect(initialUrl.searchParams.get("include_image_base64")).toBe("false")
      expect(legacyCharacterListUrls).toHaveLength(0)

      const searchInput = page
        .locator(
          'input[aria-label="Search characters"]:visible, input[placeholder*="Search characters" i]:visible'
        )
        .first()
      const hasVisibleSearchInput = await searchInput
        .isVisible({ timeout: 15000 })
        .catch(() => false)
      if (!hasVisibleSearchInput) {
        test.skip(
          true,
          "Visible characters search input not available in current UI variant."
        )
        return
      }
      await searchInput.fill("stage4-rollout-check")

      await expect.poll(
        () =>
          characterQueryUrls.some((url) => {
            const parsed = new URL(url)
            return (
              parsed.searchParams.get("query") === "stage4-rollout-check" &&
              parsed.searchParams.get("include_image_base64") === "false"
            )
          }),
        { timeout: 25000 }
      ).toBe(true)
      expect(legacyCharacterListUrls).toHaveLength(0)
    } finally {
      await context.close()
    }
  })
})
