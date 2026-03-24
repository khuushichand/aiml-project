import { afterEach, describe, expect, it, vi } from "vitest"

describe("header shortcut items hosted mode", () => {
  afterEach(() => {
    vi.resetModules()
    vi.doUnmock("@/services/tldw/deployment-mode")
  })

  it("uses dedicated account and billing shortcut ids in hosted mode", async () => {
    vi.doMock("@/services/tldw/deployment-mode", () => ({
      isHostedTldwDeployment: () => true,
    }))

    const mod = await import("../header-shortcut-items")
    const shortcutItems = mod.getHeaderShortcutItems()

    expect(shortcutItems).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: "account", to: "/account" }),
        expect.objectContaining({ id: "billing", to: "/billing" }),
      ])
    )
    expect(shortcutItems).not.toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: "settings", to: "/account" }),
        expect.objectContaining({ id: "documentation", to: "/billing" }),
      ])
    )
  })

  it("re-evaluates deployment mode when shortcut groups are requested", async () => {
    const isHostedTldwDeployment = vi.fn(() => false)
    vi.doMock("@/services/tldw/deployment-mode", () => ({
      isHostedTldwDeployment,
    }))

    const mod = await import("../header-shortcut-items")

    expect(
      mod.getHeaderShortcutItems().some((item) => item.id === "account")
    ).toBe(false)

    isHostedTldwDeployment.mockReturnValue(true)

    expect(
      mod.getHeaderShortcutItems().some((item) => item.id === "account")
    ).toBe(true)
  })
})
