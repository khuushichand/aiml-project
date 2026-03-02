import type { LucideIcon } from "lucide-react"
import { optionRoutes, type NavGroupKey } from "@/routes/route-registry"
import { isRouteEnabledForCapabilities } from "@/routes/route-capabilities"
import type { ServerCapabilities } from "@/services/tldw/server-capabilities"

export type SettingsNavItem = {
  to: string
  icon: LucideIcon
  labelToken: string
  beta?: boolean
}

export type SettingsNavGroup = {
  key: string
  titleToken: string
  items: SettingsNavItem[]
}

const NAV_GROUPS: Array<{ key: NavGroupKey; titleToken: string }> = [
  { key: "server", titleToken: "settings:navigation.serverAndAuth" },
  { key: "knowledge", titleToken: "settings:navigation.knowledgeTools" },
  { key: "workspace", titleToken: "settings:navigation.workspace" },
  { key: "about", titleToken: "settings:navigation.about" }
]

type NavItemWithOrder = SettingsNavItem & { order: number }

const SETTINGS_ROUTE_PREFIX = "/settings"

const SETTINGS_BETA_BADGE_WINDOWS: Record<string, string> = {
  "/settings/family-guardrails": "2026-12-31",
  "/settings/guardian": "2026-12-31",
  "/settings/prompt-studio": "2026-09-30"
}

const parseAnnouncementWindowEnd = (value: string): number | null => {
  const normalized = String(value || "").trim()
  if (!normalized) return null
  const expiresAt = Date.parse(`${normalized}T23:59:59.999Z`)
  if (Number.isNaN(expiresAt)) return null
  return expiresAt
}

export const isSettingsAnnouncementBadgeActive = (
  routePath: string,
  now: Date = new Date()
): boolean => {
  const announcementEnd = parseAnnouncementWindowEnd(
    SETTINGS_BETA_BADGE_WINDOWS[routePath]
  )
  if (announcementEnd == null) return false
  return now.getTime() <= announcementEnd
}

const buildNavItemsByGroup = (
  capabilities: ServerCapabilities | null | undefined
) =>
  optionRoutes.reduce((acc, route) => {
    if (!route.nav) return acc
    if (!route.path.startsWith(SETTINGS_ROUTE_PREFIX)) return acc
    const capabilitiesResolved = capabilities !== undefined
    if (
      capabilitiesResolved &&
      !isRouteEnabledForCapabilities(route.path, capabilities)
    ) {
      return acc
    }
    const { group, labelToken, icon, beta, order } = route.nav
    const items = acc.get(group) ?? []
    const badgeActive = Boolean(beta && isSettingsAnnouncementBadgeActive(route.path))
    items.push({
      to: route.path,
      icon,
      labelToken,
      beta: badgeActive ? true : undefined,
      order
    })
    acc.set(group, items)
    return acc
  }, new Map<NavGroupKey, NavItemWithOrder[]>())

export const getSettingsNavGroups = (
  capabilities?: ServerCapabilities | null
): SettingsNavGroup[] => {
  const navItemsByGroup = buildNavItemsByGroup(capabilities)
  return NAV_GROUPS.map((group) => {
    const items = (navItemsByGroup.get(group.key) ?? [])
      .sort((a, b) => a.order - b.order)
      .map(({ order, ...item }) => item)
    return {
      key: group.key,
      titleToken: group.titleToken,
      items
    }
  }).filter((group) => group.items.length > 0)
}
