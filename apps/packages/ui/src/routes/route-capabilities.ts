import type { ServerCapabilities } from "@/services/tldw/server-capabilities"

export const GUARDIAN_SETTINGS_PATH = "/settings/guardian"
export const FAMILY_WIZARD_SETTINGS_PATH = "/settings/family-guardrails"
export const SKILLS_PATH = "/skills"
export const PERSONA_DOCK_PATH = "/persona"
export const COMPANION_PATH = "/companion"

export const isGuardianSettingsAvailable = (
  capabilities: ServerCapabilities | null | undefined
): boolean => Boolean(capabilities?.hasGuardian && capabilities?.hasSelfMonitoring)

export const isSkillsAvailable = (
  capabilities: ServerCapabilities | null | undefined
): boolean => Boolean(capabilities?.hasSkills)

export const isFamilyWizardAvailable = (
  capabilities: ServerCapabilities | null | undefined
): boolean => Boolean(capabilities?.hasGuardian)

export const isPersonaDockAvailable = (
  capabilities: ServerCapabilities | null | undefined
): boolean => Boolean(capabilities?.hasPersona)

export const isCompanionAvailable = (
  capabilities: ServerCapabilities | null | undefined
): boolean => Boolean(capabilities?.hasPersonalization)

export const isRouteEnabledForCapabilities = (
  routePath: string,
  capabilities: ServerCapabilities | null | undefined
): boolean => {
  if (routePath === FAMILY_WIZARD_SETTINGS_PATH) {
    return isFamilyWizardAvailable(capabilities)
  }
  if (routePath === GUARDIAN_SETTINGS_PATH) {
    return isGuardianSettingsAvailable(capabilities)
  }
  if (routePath === SKILLS_PATH) {
    return isSkillsAvailable(capabilities)
  }
  if (routePath === PERSONA_DOCK_PATH) {
    return isPersonaDockAvailable(capabilities)
  }
  if (routePath === COMPANION_PATH) {
    return isCompanionAvailable(capabilities)
  }
  return true
}
