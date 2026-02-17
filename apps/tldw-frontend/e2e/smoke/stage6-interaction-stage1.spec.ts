import { test, expect, seedAuth } from "./smoke.setup"

const LOAD_TIMEOUT = 30_000
const UNRESOLVED_TEMPLATE_PATTERN = /\{\{[^{}\n]{1,120}\}\}/g

test.describe("Stage 6 interaction stage 1 defect closures", () => {
  test("chat route does not expose unresolved template placeholders", async ({
    page
  }) => {
    await seedAuth(page)

    await page.goto("/chat", {
      waitUntil: "domcontentloaded",
      timeout: LOAD_TIMEOUT
    })
    await page.waitForLoadState("networkidle", { timeout: LOAD_TIMEOUT }).catch(() => {})

    const input = page.locator("#textarea-message, [data-testid='chat-input']").first()
    await expect(input).toBeVisible({ timeout: LOAD_TIMEOUT })

    const bodyText = await page.evaluate(() => document.body?.innerText || "")
    const unresolvedTemplates = Array.from(bodyText.matchAll(UNRESOLVED_TEMPLATE_PATTERN)).map(
      (match) => match[0]
    )
    const uniqueUnresolvedTemplates = Array.from(new Set(unresolvedTemplates))

    expect(
      uniqueUnresolvedTemplates,
      `Unresolved template placeholders on /chat: ${uniqueUnresolvedTemplates.join(" | ")}`
    ).toHaveLength(0)
    expect(bodyText).not.toContain("{{percentage}}")
  })

  test("home route exposes an explicit theme toggle control", async ({
    page
  }) => {
    await seedAuth(page)

    await page.goto("/", {
      waitUntil: "domcontentloaded",
      timeout: LOAD_TIMEOUT
    })
    await page.waitForLoadState("networkidle", { timeout: LOAD_TIMEOUT }).catch(() => {})

    const toggle = page.getByTestId("chat-header-theme-toggle")
    await expect(toggle).toBeVisible({ timeout: LOAD_TIMEOUT })

    const initialTheme = await page.evaluate(() =>
      document.documentElement.classList.contains("dark") ? "dark" : "light"
    )

    await toggle.click()

    await expect
      .poll(
        async () =>
          page.evaluate(() =>
            document.documentElement.classList.contains("dark") ? "dark" : "light"
          ),
        { timeout: LOAD_TIMEOUT }
      )
      .not.toBe(initialTheme)
  })
})
