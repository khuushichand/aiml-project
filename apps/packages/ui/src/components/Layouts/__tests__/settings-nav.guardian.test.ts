import { describe, expect, it, vi } from "vitest"

import { getSettingsNavGroups } from "../settings-nav"
import type { ServerCapabilities } from "@/services/tldw/server-capabilities"
import { GUARDIAN_SETTINGS_PATH } from "@/routes/route-capabilities"

vi.mock("@/routes/route-registry", () => {
  const MockIcon = () => null
  return {
    optionRoutes: [
      {
        kind: "options",
        path: "/settings/chat",
        nav: {
          group: "server",
          labelToken: "settings:chatSettingsNav",
          icon: MockIcon,
          order: 1
        }
      },
      {
        kind: "options",
        path: "/settings/guardian",
        nav: {
          group: "server",
          labelToken: "settings:guardianNav",
          icon: MockIcon,
          order: 2
        }
      }
    ]
  }
})

const makeCapabilities = (
  overrides: Partial<ServerCapabilities> = {}
): ServerCapabilities =>
  ({
    hasGuardian: false,
    hasSelfMonitoring: false,
    ...overrides
  } as ServerCapabilities)

const flattenPaths = (caps?: ServerCapabilities | null): string[] =>
  getSettingsNavGroups(caps).flatMap((group) => group.items.map((item) => item.to))

describe("settings nav guardian gating", () => {
  it("includes guardian route by default when capabilities are not resolved", () => {
    const paths = flattenPaths(undefined)
    expect(paths).toContain(GUARDIAN_SETTINGS_PATH)
  })

  it("hides guardian route when guardian/self-monitoring endpoints are unavailable", () => {
    const paths = flattenPaths(
      makeCapabilities({
        hasGuardian: false,
        hasSelfMonitoring: false
      })
    )
    expect(paths).not.toContain(GUARDIAN_SETTINGS_PATH)
  })

  it("keeps guardian route when both guardian capabilities are present", () => {
    const paths = flattenPaths(
      makeCapabilities({
        hasGuardian: true,
        hasSelfMonitoring: true
      })
    )
    expect(paths).toContain(GUARDIAN_SETTINGS_PATH)
  })
})
