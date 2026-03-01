import { expect, test } from "@playwright/test"
import { launchWithBuiltExtension } from "./utils/extension-build"

test("repo2txt route loads in options", async () => {
  const { context, page, optionsUrl } = await launchWithBuiltExtension()
  try {
    await page.goto(`${optionsUrl}#/repo2txt`, { waitUntil: "domcontentloaded" })
    await expect(page.getByTestId("repo2txt-route-root")).toBeVisible()
  } finally {
    await context.close()
  }
})
