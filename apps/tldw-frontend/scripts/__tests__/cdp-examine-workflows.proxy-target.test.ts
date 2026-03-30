import { describe, expect, it } from "vitest"

import { buildApiProxyTarget } from "../cdp-examine-workflows"

describe("buildApiProxyTarget", () => {
  it("keeps API requests pinned to the configured backend origin", () => {
    const target = buildApiProxyTarget(
      "/api/v1/health?verbose=1",
      "http://127.0.0.1:8000"
    )

    expect(target.origin).toBe("http://127.0.0.1:8000")
    expect(target.pathname).toBe("/api/v1/health")
    expect(target.search).toBe("?verbose=1")
  })

  it("strips attacker-controlled origins from absolute request URLs", () => {
    const target = buildApiProxyTarget(
      "https://evil.example/api/v1/admin?steal=1",
      "http://127.0.0.1:8000"
    )

    expect(target.origin).toBe("http://127.0.0.1:8000")
    expect(target.pathname).toBe("/api/v1/admin")
    expect(target.search).toBe("?steal=1")
  })

  it("rejects non-api requests", () => {
    expect(() =>
      buildApiProxyTarget("/static/index.html", "http://127.0.0.1:8000")
    ).toThrow("Only /api/* requests may be proxied")
  })
})
