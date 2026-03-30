import {
  CompanionHomeParityPage,
  type CompanionHomeParityContext
} from "./companion-home.page"

export async function runCompanionHomeParityContract(
  ctx: CompanionHomeParityContext
): Promise<void> {
  const homePage = new CompanionHomeParityPage(ctx.page)

  await homePage.goto(ctx.platform, ctx.optionsUrl)
  await homePage.waitForReady()

  await homePage.assertDashboardVisible()
  await homePage.assertSummaryCounts()
  await homePage.assertFixtureContent()

  await homePage.openCustomizeDrawer()
  await homePage.assertCustomizeDrawerVisible()
  await homePage.closeCustomizeDrawer()
}
