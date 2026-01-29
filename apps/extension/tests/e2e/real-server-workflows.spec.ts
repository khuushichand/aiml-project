import { registerRealServerWorkflows, type CreateWorkflowDriver, withFeatures, ALL_FEATURE_FLAGS_ENABLED } from "../../../test-utils/real-server-workflows"
import { launchWithExtension } from "./utils/extension"
import { grantHostPermission } from "./utils/permissions"

const normalizeRoute = (route: string) => {
  const trimmed = String(route || "").trim()
  if (!trimmed) return "/"
  return trimmed.startsWith("/") ? trimmed : `/${trimmed}`
}

const createExtensionDriver: CreateWorkflowDriver = async ({
  serverUrl,
  apiKey,
  featureFlags
}) => {
  const baseSeed = {
    __tldw_first_run_complete: true,
    tldwConfig: {
      serverUrl,
      authMode: "single-user",
      apiKey
    },
    quickIngestInspectorIntroDismissed: true,
    quickIngestOnboardingDismissed: true
  }
  const enabledFlags = Object.entries(featureFlags || {})
    .filter(([, value]) => value)
    .map(([key]) => key as keyof typeof ALL_FEATURE_FLAGS_ENABLED)
  const seedConfig = enabledFlags.length
    ? withFeatures(enabledFlags, baseSeed)
    : baseSeed

  const launchResult = await launchWithExtension("", { seedConfig })
  const { context, page, extensionId, optionsUrl, sidepanelUrl, openSidepanel } =
    launchResult

  return {
    kind: "extension",
    serverUrl,
    apiKey,
    context,
    page,
    optionsUrl,
    sidepanelUrl,
    openSidepanel,
    goto: async (targetPage, route, options) => {
      const normalized = normalizeRoute(route)
      await targetPage.goto(`${optionsUrl}#${normalized}`, options)
    },
    ensureHostPermission: async () => {
      const origin = new URL(serverUrl).origin + "/*"
      return grantHostPermission(context, extensionId, origin)
    },
    close: async () => {
      await context.close()
    }
  }
}

registerRealServerWorkflows(createExtensionDriver)
