import type { ServerCapabilities } from "@/services/tldw/server-capabilities"

export const GUARDIAN_SETTINGS_PATH = "/settings/guardian"

export const isGuardianSettingsAvailable = (
  capabilities: ServerCapabilities | null | undefined
): boolean => Boolean(capabilities?.hasGuardian && capabilities?.hasSelfMonitoring)

export const isRouteEnabledForCapabilities = (
  routePath: string,
  capabilities: ServerCapabilities | null | undefined
): boolean => {
  if (routePath === GUARDIAN_SETTINGS_PATH) {
    return isGuardianSettingsAvailable(capabilities)
  }
  return true
}
