import { describe, expect, it } from "vitest"

import {
  getHostedAllowedRoutes,
  isHostedAllowedRoute
} from "@web/lib/hosted-route-allowlist"

describe("hosted route allowlist", () => {
  it("allows signup, login, account, billing, and core product routes", () => {
    const routes = getHostedAllowedRoutes()

    expect(routes).toContain("/signup")
    expect(routes).toContain("/login")
    expect(routes).toContain("/account")
    expect(routes).toContain("/billing")
    expect(isHostedAllowedRoute("/chat")).toBe(true)
  })

  it("blocks operator and placeholder routes", () => {
    expect(isHostedAllowedRoute("/admin/server")).toBe(false)
    expect(isHostedAllowedRoute("/settings/tldw")).toBe(false)
    expect(isHostedAllowedRoute("/config")).toBe(false)
  })
})
