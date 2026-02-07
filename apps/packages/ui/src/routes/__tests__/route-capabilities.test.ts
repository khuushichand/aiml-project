import { describe, expect, it } from "vitest"

import {
  GUARDIAN_SETTINGS_PATH,
  isGuardianSettingsAvailable,
  isRouteEnabledForCapabilities
} from "../route-capabilities"
import type { ServerCapabilities } from "@/services/tldw/server-capabilities"

const makeCapabilities = (
  overrides: Partial<ServerCapabilities> = {}
): ServerCapabilities =>
  ({
    hasGuardian: false,
    hasSelfMonitoring: false,
    ...overrides
  } as ServerCapabilities)

describe("route capability gating", () => {
  it("hides guardian route when guardian capability is missing", () => {
    const caps = makeCapabilities({
      hasGuardian: false,
      hasSelfMonitoring: true
    })
    expect(isRouteEnabledForCapabilities(GUARDIAN_SETTINGS_PATH, caps)).toBe(false)
  })

  it("hides guardian route when self-monitoring capability is missing", () => {
    const caps = makeCapabilities({
      hasGuardian: true,
      hasSelfMonitoring: false
    })
    expect(isRouteEnabledForCapabilities(GUARDIAN_SETTINGS_PATH, caps)).toBe(false)
  })

  it("enables guardian route only when both capabilities are present", () => {
    const caps = makeCapabilities({
      hasGuardian: true,
      hasSelfMonitoring: true
    })
    expect(isGuardianSettingsAvailable(caps)).toBe(true)
    expect(isRouteEnabledForCapabilities(GUARDIAN_SETTINGS_PATH, caps)).toBe(true)
  })

  it("does not gate unrelated routes", () => {
    const caps = makeCapabilities({
      hasGuardian: false,
      hasSelfMonitoring: false
    })
    expect(isRouteEnabledForCapabilities("/settings/chat", caps)).toBe(true)
  })
})
