import { describe, expect, it } from "vitest"
import { isSidebarShortcutRouteActive } from "../shortcut-active"

describe("isSidebarShortcutRouteActive", () => {
  it("treats root chat route as active for / and /chat", () => {
    expect(isSidebarShortcutRouteActive("/", "/")).toBe(true)
    expect(isSidebarShortcutRouteActive("/", "/chat")).toBe(true)
  })

  it("treats settings as active for nested settings paths", () => {
    expect(isSidebarShortcutRouteActive("/settings", "/settings")).toBe(true)
    expect(isSidebarShortcutRouteActive("/settings", "/settings/tldw")).toBe(true)
  })

  it("matches exact route and nested subpaths", () => {
    expect(isSidebarShortcutRouteActive("/knowledge", "/knowledge")).toBe(true)
    expect(isSidebarShortcutRouteActive("/knowledge", "/knowledge/history")).toBe(true)
  })

  it("does not mark similarly prefixed routes as active", () => {
    expect(isSidebarShortcutRouteActive("/media", "/media-multi")).toBe(false)
    expect(isSidebarShortcutRouteActive("/notes", "/notebook")).toBe(false)
  })

  it("normalizes query/hash and trailing slash input", () => {
    expect(isSidebarShortcutRouteActive("/media/", "/media?tab=all")).toBe(true)
    expect(isSidebarShortcutRouteActive("/media/", "/media/#content")).toBe(true)
  })
})

