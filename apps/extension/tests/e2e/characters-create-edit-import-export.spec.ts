import { expect, test } from "@playwright/test"
import { grantHostPermission } from "./utils/permissions"
import { requireRealServerConfig, launchWithExtensionOrSkip } from "./utils/real-server"

const normalizeServerUrl = (value: string) =>
  value.match(/^https?:\/\//) ? value : `http://${value}`

const requestJson = async (
  serverUrl: string,
  apiKey: string,
  path: string,
  init?: RequestInit
) => {
  const response = await fetch(`${serverUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      ...(init?.headers || {})
    }
  })
  const text = await response.text().catch(() => "")
  if (!response.ok) {
    throw new Error(`Request failed ${response.status}: ${text}`)
  }
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

const parseItems = (payload: any): any[] => {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.items)) return payload.items
  if (Array.isArray(payload?.results)) return payload.results
  return []
}

const listCharactersByPrefix = async (
  serverUrl: string,
  apiKey: string,
  prefix: string
) => {
  const queryPayload = await requestJson(
    serverUrl,
    apiKey,
    `/api/v1/characters/query?page=1&page_size=100&query=${encodeURIComponent(prefix)}`
  )
  return parseItems(queryPayload).filter((item) =>
    String(item?.name || "").startsWith(prefix)
  )
}

const deleteCharactersByPrefix = async (
  serverUrl: string,
  apiKey: string,
  prefix: string
) => {
  try {
    const matches = await listCharactersByPrefix(serverUrl, apiKey, prefix)
    for (const item of matches) {
      const id = String(item?.id || "")
      if (!id) continue
      try {
        await requestJson(serverUrl, apiKey, `/api/v1/characters/${id}`, {
          method: "DELETE"
        })
      } catch {
        // best-effort cleanup
      }
    }
  } catch {
    // best-effort cleanup
  }
}

test.describe("Characters create/edit/import/export", () => {
  test("supports critical creation and migration-safe edit/import/export paths", async () => {
    test.setTimeout(120000)

    const { serverUrl, apiKey } = requireRealServerConfig(test)
    const normalizedServerUrl = normalizeServerUrl(serverUrl)
    const namePrefix = `Stage4 Flow ${Date.now()}`
    const createdName = `${namePrefix} - Created`
    const importedName = `${namePrefix} - Imported`

    const { context, page, extensionId, optionsUrl } = await launchWithExtensionOrSkip(test, "", {
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

    try {
      await page.goto(`${optionsUrl}#/characters`, {
        waitUntil: "domcontentloaded"
      })

      await expect(
        page.getByRole("button", { name: /New character/i })
      ).toBeVisible({ timeout: 15000 })

      // Create
      await page.getByRole("button", { name: /New character/i }).click()
      await page.getByPlaceholder(/e\.g\. Writing coach/i).fill(createdName)
      await page
        .getByPlaceholder(/patient math teacher/i)
        .fill("You are a reliable assistant for stage-4 form checks.")
      await page
        .getByPlaceholder(/Set a first message/i)
        .fill("Hello from stage 4 test")
      await page
        .getByRole("button", { name: /Create character/i })
        .click()

      await expect(page.getByText(/Character created/i)).toBeVisible({ timeout: 15000 })
      await expect(page.getByText(createdName)).toBeVisible({ timeout: 15000 })

      // Edit
      await page
        .getByRole("button", { name: new RegExp(`Edit character ${createdName}`, "i") })
        .click()
      await page
        .getByPlaceholder(/one-line summary/i)
        .fill("Updated from stage-4 critical path e2e.")
      await page.getByRole("button", { name: /Save changes/i }).click()

      await expect(page.getByText(/Character updated/i)).toBeVisible({ timeout: 15000 })

      // Export
      await page
        .getByRole("button", { name: new RegExp(`More actions for ${createdName}`, "i") })
        .click()
      await page.getByText(/Export as JSON/i).first().click()
      await expect(page.getByText(/Character exported/i)).toBeVisible({ timeout: 15000 })

      // Import
      const uploadInput = page.locator("input[type='file']").first()
      await uploadInput.setInputFiles({
        name: `${importedName}.json`,
        mimeType: "application/json",
        buffer: Buffer.from(
          JSON.stringify({
            name: importedName,
            description: "Imported by stage-4 e2e",
            system_prompt: "You are imported in stage-4 e2e.",
            greeting: "Imported greeting"
          })
        )
      })

      await expect(page.getByText(importedName)).toBeVisible({ timeout: 20000 })
    } finally {
      await context.close()
      await deleteCharactersByPrefix(normalizedServerUrl, apiKey, namePrefix)
    }
  })

  test("runs batch import preview/confirm/summary flow and retries only failed files", async () => {
    test.setTimeout(120000)

    const { serverUrl, apiKey } = requireRealServerConfig(test)
    const normalizedServerUrl = normalizeServerUrl(serverUrl)
    const namePrefix = `Stage4 Batch ${Date.now()}`
    const importedSuccessName = `${namePrefix} Success`

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

    try {
      await deleteCharactersByPrefix(normalizedServerUrl, apiKey, namePrefix)

      await page.goto(`${optionsUrl}#/characters`, {
        waitUntil: "domcontentloaded"
      })
      await expect(
        page.getByRole("button", { name: /New character/i })
      ).toBeVisible({ timeout: 15000 })

      const uploadInput = page.locator("input[type='file']").first()
      await uploadInput.setInputFiles([
        {
          name: `${importedSuccessName}.json`,
          mimeType: "application/json",
          buffer: Buffer.from(
            JSON.stringify({
              name: importedSuccessName,
              description: "Batch import success payload",
              system_prompt: "You are a batch import success persona.",
              greeting: "Hello from batch import success"
            })
          )
        },
        {
          name: `${namePrefix}-broken.png`,
          mimeType: "image/png",
          buffer: Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])
        }
      ])

      const importDialog = page.getByRole("dialog", { name: /Import preview/i })
      await expect(importDialog).toBeVisible({ timeout: 20000 })
      await expect(importDialog.getByTestId("character-import-progress-summary")).toContainText(
        /Queued 2/i
      )

      await importDialog.getByRole("button", { name: /Confirm import/i }).click()

      await expect(importDialog.getByTestId("character-import-status-success")).toBeVisible({
        timeout: 30000
      })
      await expect(importDialog.getByTestId("character-import-status-failure")).toBeVisible({
        timeout: 30000
      })
      await expect(importDialog.getByTestId("character-import-progress-summary")).toContainText(
        /Success 1/i
      )
      await expect(importDialog.getByTestId("character-import-progress-summary")).toContainText(
        /Failed 1/i
      )
      await expect(importDialog.getByRole("button", { name: /Retry failed/i })).toBeVisible()

      await expect
        .poll(
          async () =>
            (await listCharactersByPrefix(normalizedServerUrl, apiKey, namePrefix)).length,
          { timeout: 20000 }
        )
        .toBe(1)

      await importDialog.getByRole("button", { name: /Retry failed/i }).click()
      await expect(importDialog.getByTestId("character-import-status-success")).toBeVisible({
        timeout: 30000
      })
      await expect(importDialog.getByTestId("character-import-status-failure")).toBeVisible({
        timeout: 30000
      })
      await expect(importDialog.getByTestId("character-import-progress-summary")).toContainText(
        /Success 1/i
      )

      await expect
        .poll(
          async () =>
            (await listCharactersByPrefix(normalizedServerUrl, apiKey, namePrefix)).length,
          { timeout: 20000 }
        )
        .toBe(1)
    } finally {
      await context.close()
      await deleteCharactersByPrefix(normalizedServerUrl, apiKey, namePrefix)
    }
  })
})
