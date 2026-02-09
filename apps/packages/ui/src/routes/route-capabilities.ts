import type { ServerCapabilities } from "@/services/tldw/server-capabilities"

export const GUARDIAN_SETTINGS_PATH = "/settings/guardian"
export const SKILLS_PATH = "/skills"
export const PERSONA_DOCK_PATH = "/persona"

export const isGuardianSettingsAvailable = (
  capabilities: ServerCapabilities | null | undefined
): boolean => Boolean(capabilities?.hasGuardian && capabilities?.hasSelfMonitoring)

export const isSkillsAvailable = (
  capabilities: ServerCapabilities | null | undefined
): boolean => Boolean(capabilities?.hasSkills)

export const isPersonaDockAvailable = (
  capabilities: ServerCapabilities | null | undefined
): boolean => Boolean(capabilities?.hasPersona)

export const isRouteEnabledForCapabilities = (
  routePath: string,
  capabilities: ServerCapabilities | null | undefined
): boolean => {
  if (routePath === GUARDIAN_SETTINGS_PATH) {
    return isGuardianSettingsAvailable(capabilities)
  }
  if (routePath === SKILLS_PATH) {
    return isSkillsAvailable(capabilities)
  }
  if (routePath === PERSONA_DOCK_PATH) {
    return isPersonaDockAvailable(capabilities)
  }
  return true
}
