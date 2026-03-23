import {
  assertNoCriticalErrors,
  expect,
  test
} from "../utils/fixtures"

test.describe("Queued chat requests", () => {
  test("restores queued requests after reload", async ({
    authedPage,
    diagnostics
  }) => {
    await authedPage.goto("/chat", { waitUntil: "domcontentloaded" })
    await expect(
      authedPage.getByTestId("chat-input")
    ).toBeVisible({ timeout: 20_000 })

    const dismissConnectionModal = authedPage.getByRole("button", {
      name: /^dismiss$/i
    })
    if (await dismissConnectionModal.isVisible().catch(() => false)) {
      await dismissConnectionModal.click()
    }

    await expect
      .poll(
        () =>
          authedPage.evaluate(() =>
            Boolean(
              (window as any).__tldw_useStoreMessageOption?.getState?.()
                .setQueuedMessages &&
                (window as any).__tldw_usePlaygroundSessionStore?.getState?.()
                  .saveSession
            )
          ),
        { timeout: 10_000 }
      )
      .toBe(true)

    const queuedPrompt = `Queued follow-up ${Date.now()}`
    await authedPage.evaluate((promptText) => {
      const queuedMessages = [{ promptText }]
      const store = (window as any).__tldw_useStoreMessageOption

      store?.getState?.().setQueuedMessages?.(queuedMessages)
    }, queuedPrompt)

    await expect
      .poll(
        () =>
          authedPage.evaluate(() => {
            const state =
              (window as any).__tldw_usePlaygroundSessionStore?.getState?.() ?? {}
            return {
              queuedCount: state.queuedMessages?.length ?? 0,
              scopeKey: typeof state.scopeKey === "string" ? state.scopeKey : "",
              lastUpdated: Number(state.lastUpdated ?? 0)
            }
          }),
        { timeout: 15_000 }
      )
      .toEqual(
        expect.objectContaining({
          queuedCount: 1,
          lastUpdated: expect.any(Number)
        })
      )

    await expect(authedPage.getByText(/1 queued/i)).toBeVisible({
      timeout: 10_000
    })

    await authedPage.reload({ waitUntil: "domcontentloaded" })
    await expect(
      authedPage.getByTestId("chat-input")
    ).toBeVisible({ timeout: 20_000 })
    if (await dismissConnectionModal.isVisible().catch(() => false)) {
      await dismissConnectionModal.click()
    }

    await expect(authedPage.getByText(/1 queued/i)).toBeVisible({
      timeout: 10_000
    })
    await expect(authedPage.getByText(`Next: ${queuedPrompt}`)).toBeVisible({
      timeout: 10_000
    })
    await expect
      .poll(
        () =>
          authedPage.evaluate(() => {
            const store =
              (window as any).__tldw_useStoreMessageOption?.getState?.() ?? {}
            return {
              queuedCount: store.queuedMessages?.length ?? 0,
              nextPrompt:
                typeof store.queuedMessages?.[0]?.promptText === "string"
                  ? store.queuedMessages[0].promptText
                  : ""
            }
          }),
        { timeout: 10_000 }
      )
      .toEqual({
        queuedCount: 1,
        nextPrompt: queuedPrompt
      })

    await assertNoCriticalErrors(diagnostics)
  })
})
