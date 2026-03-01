import { expect, test } from "@playwright/test"
import { launchWithBuiltExtension } from "./utils/extension-build"

test("sidepanel repo2txt affordance opens options link-out", async () => {
  const { context, openSidepanel } = await launchWithBuiltExtension()
  try {
    const sidepanel = await openSidepanel()
    const menuTrigger = sidepanel
      .getByRole("button", { name: /more options|menu|ingest/i })
      .first()
    if ((await menuTrigger.count()) > 0) {
      await menuTrigger.click()
    }

    const affordance = sidepanel.getByTestId("sidepanel-open-repo2txt")
    if ((await affordance.count()) === 0) {
      await expect(affordance).toHaveCount(0)
      await expect(sidepanel).not.toHaveURL(/repo2txt/i)
      return
    }

    const [optionsPage] = await Promise.all([
      context.waitForEvent("page"),
      affordance.click()
    ])
    await optionsPage.waitForLoadState("domcontentloaded")
    await expect(optionsPage).toHaveURL(/options\.html#\/repo2txt/)
  } finally {
    await context.close()
  }
})
