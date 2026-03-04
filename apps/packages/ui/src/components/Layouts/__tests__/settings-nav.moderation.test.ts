import { describe, expect, it, vi } from "vitest"

import { getSettingsNavGroups } from "../settings-nav"

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
        path: "/moderation-playground",
        nav: {
          group: "server",
          labelToken: "option:moderationPlayground.nav",
          icon: MockIcon,
          order: 2
        }
      }
    ]
  }
})

describe("settings nav moderation visibility", () => {
  it("includes moderation playground in settings navigation", () => {
    const paths = getSettingsNavGroups(undefined).flatMap((group) =>
      group.items.map((item) => item.to)
    )

    expect(paths).toContain("/moderation-playground")
  })
})
