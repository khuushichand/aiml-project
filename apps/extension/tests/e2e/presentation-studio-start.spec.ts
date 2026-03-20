import { expect, test } from "@playwright/test"

import { forceConnected, waitForConnectionStore } from "./utils/connection"
import { launchWithBuiltExtensionOrSkip } from "./utils/real-server"

const SERVER_URL = "http://127.0.0.1:8000"

test.describe("Presentation Studio quick start", () => {
  test("creates a seeded project and opens the WebUI editor", async () => {
    let createdPayload: Record<string, any> | null = null

    const { context, page, optionsUrl } = await launchWithBuiltExtensionOrSkip(test, {
      seedConfig: {
        __tldw_first_run_complete: true,
        tldwConfig: {
          serverUrl: SERVER_URL,
          authMode: "single-user",
          apiKey: "test-key"
        }
      }
    })

    await context.route(`${SERVER_URL}/api/v1/slides/presentations`, async (route) => {
      if (route.request().method() !== "POST") {
        await route.fulfill({ status: 204 })
        return
      }

      createdPayload = route.request().postDataJSON() as Record<string, any>
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        headers: {
          "access-control-allow-origin": "*"
        },
        body: JSON.stringify({
          id: "presentation-quickstart-1",
          title: createdPayload?.title ?? "Untitled Presentation",
          description: null,
          theme: "black",
          studio_data: createdPayload?.studio_data ?? null,
          slides: createdPayload?.slides ?? [],
          created_at: "2026-03-13T00:00:00Z",
          last_modified: "2026-03-13T00:00:00Z",
          deleted: false,
          client_id: "1",
          version: 1
        })
      })
    })

    try {
      await page.goto(`${optionsUrl}#/presentation-studio/start`, {
        waitUntil: "domcontentloaded"
      })
      await waitForConnectionStore(page, "presentation-studio-start")
      await forceConnected(page, { serverUrl: SERVER_URL }, "presentation-studio-start")

      await page.evaluate(() => {
        ;(window as any).__presentationStudioOpenedUrls = []
        window.open = ((url?: string | URL | undefined) => {
          if (typeof url === "string") {
            ;(window as any).__presentationStudioOpenedUrls.push(url)
          } else if (url instanceof URL) {
            ;(window as any).__presentationStudioOpenedUrls.push(url.toString())
          }
          return null
        }) as typeof window.open
      })

      await expect(
        page.getByRole("heading", { name: /Presentation Studio Quick Start/i })
      ).toBeVisible()

      await page.getByLabel("Project title").fill("Extension storyboard")
      await page
        .getByLabel("Narration seed")
        .fill("Open with the problem statement, then walk through the proposed workflow.")
      await page.getByRole("button", { name: "Create seeded project" }).click()

      await expect
        .poll(() => createdPayload, {
          message: "presentation create payload should be captured"
        })
        .not.toBeNull()

      expect(createdPayload).toMatchObject({
        title: "Extension storyboard",
        studio_data: {
          origin: "extension_capture",
          entry_surface: "extension_start",
          has_narration_seed: true,
          has_image_seed: false
        }
      })
      expect(createdPayload?.slides?.[0]).toMatchObject({
        order: 0,
        layout: "content",
        title: "Extension storyboard",
        speaker_notes: "Open with the problem statement, then walk through the proposed workflow."
      })

      await expect
        .poll(async () =>
          page.evaluate(() => (window as any).__presentationStudioOpenedUrls?.[0] ?? null)
        )
        .toBe(`${SERVER_URL}/presentation-studio/presentation-quickstart-1`)
    } finally {
      await context.close()
    }
  })
})
