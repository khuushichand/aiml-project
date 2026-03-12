import { test, expect } from "@playwright/test"
import path from "path"

import { launchWithExtensionOrSkip } from "./utils/real-server"
import {
  forceConnected,
  waitForConnectionStore
} from "./utils/connection"

async function seedQueuedMessages(
  page: import("@playwright/test").Page,
  queuedMessages: Array<Record<string, unknown>>
) {
  await page.evaluate((messages) => {
    const store: any = (window as any).__tldw_useStoreMessageOption
    store?.getState?.().setQueuedMessages?.(messages)
  }, queuedMessages)
}

async function readQueuedState(page: import("@playwright/test").Page) {
  return page.evaluate(() => {
    const store: any = (window as any).__tldw_useStoreMessageOption
    if (!store?.getState) {
      return { queuedLen: -1, prompts: [] as string[] }
    }

    const queued = store.getState().queuedMessages || []
    return {
      queuedLen: queued.length,
      prompts: queued.map((item: any) => String(item.promptText || item.message || ""))
    }
  })
}

test.describe("Queued requests panel", () => {
  test("Playground shows the shared queue panel when queued requests exist", async () => {
    const extPath = path.resolve("build/chrome-mv3")
    const { context, page } = await launchWithExtensionOrSkip(test, extPath)

    await waitForConnectionStore(page, "queued-playground-panel")
    await forceConnected(page, {}, "queued-playground-panel")
    await seedQueuedMessages(page, [{ promptText: "Queued from test" }])

    await expect(page.getByText(/1 queued/i)).toBeVisible({ timeout: 10_000 })
    await expect(page.getByRole("button", { name: /view queue/i })).toBeVisible()
    await expect(page.getByRole("button", { name: /run next|retry next/i })).toBeVisible()
    await expect(page.getByRole("button", { name: /clear all/i })).toBeVisible()
    await expect(
      page.getByRole("button", { name: /health & diagnostics/i })
    ).toBeVisible()

    await context.close()
  })

  test("Playground Clear all empties queued requests without sending messages", async () => {
    const extPath = path.resolve("build/chrome-mv3")
    const { context, page } = await launchWithExtensionOrSkip(test, extPath)

    await waitForConnectionStore(page, "queued-playground-clear")
    await forceConnected(page, {}, "queued-playground-clear")
    await seedQueuedMessages(page, [{ promptText: "Queued from test" }])

    await expect(page.getByText(/1 queued/i)).toBeVisible({ timeout: 10_000 })
    await page.getByRole("button", { name: /clear all/i }).click()

    await expect
      .poll(async () => (await readQueuedState(page)).queuedLen, {
        timeout: 5_000
      })
      .toBe(0)

    await context.close()
  })

  test("Sidepanel allows editing and deleting queued requests", async () => {
    const extPath = path.resolve("build/chrome-mv3")
    const { context, openSidepanel } = (await launchWithExtensionOrSkip(
      test,
      extPath
    )) as any
    const page = await openSidepanel()

    await waitForConnectionStore(page, "queued-sidepanel-edit")
    await forceConnected(page, {}, "queued-sidepanel-edit")
    await seedQueuedMessages(page, [{ promptText: "Queued from sidepanel" }])

    await expect(page.getByText(/1 queued/i)).toBeVisible({ timeout: 10_000 })
    await page.getByRole("button", { name: /view queue/i }).click()

    await page.getByRole("button", { name: /^edit$/i }).click()
    const editField = page.getByRole("textbox", { name: /edit queued request/i })
    await editField.fill("Edited queued request")
    await page.getByRole("button", { name: /^save$/i }).click()

    await expect
      .poll(async () => (await readQueuedState(page)).prompts[0] || "", {
        timeout: 5_000
      })
      .toContain("Edited queued request")

    await page.getByRole("button", { name: /^delete$/i }).click()
    await expect
      .poll(async () => (await readQueuedState(page)).queuedLen, {
        timeout: 5_000
      })
      .toBe(0)

    await context.close()
  })

  test("Sidepanel surfaces blocked queued requests with retry messaging", async () => {
    const extPath = path.resolve("build/chrome-mv3")
    const { context, openSidepanel } = (await launchWithExtensionOrSkip(
      test,
      extPath
    )) as any
    const page = await openSidepanel()

    await waitForConnectionStore(page, "queued-sidepanel-blocked")
    await forceConnected(page, {}, "queued-sidepanel-blocked")
    await seedQueuedMessages(page, [
      {
        promptText: "Needs retry",
        status: "blocked",
        blockedReason: "dispatch_failed"
      }
    ])

    await expect(page.getByText(/1 queued/i)).toBeVisible({ timeout: 10_000 })
    await expect(page.getByRole("button", { name: /retry next/i })).toBeVisible()
    await expect(page.getByText(/dispatch failed\. review and retry\./i)).toBeVisible()

    await context.close()
  })
})
