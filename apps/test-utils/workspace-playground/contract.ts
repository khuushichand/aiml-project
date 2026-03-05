import { WorkspacePlaygroundParityPage } from "./page"
import type { WorkspacePlaygroundParityContext } from "./types"

export async function runWorkspacePlaygroundParityContract(
  ctx: WorkspacePlaygroundParityContext
): Promise<void> {
  const workspacePage = new WorkspacePlaygroundParityPage(ctx.page)

  await workspacePage.goto(ctx.platform, ctx.optionsUrl)
  await workspacePage.waitForReady()

  await workspacePage.assertBaselinePanesVisible()

  await workspacePage.openOutputTypesSection()
  await workspacePage.openGeneratedOutputsSection()
  await workspacePage.seedDeterministicArtifact()

  await workspacePage.expectParityArtifactVisible()
  await workspacePage.expectArtifactActionButtons()

  await workspacePage.collapseGeneratedOutputsSection()
  await workspacePage.expectGeneratedOutputsSectionHidden()
  await workspacePage.openGeneratedOutputsSection()
  await workspacePage.expectParityArtifactVisible()
}
