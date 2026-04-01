import { describe, expect, it } from "vitest"

import { buildApiProxyRequestOptions } from "../cdp-examine-workflows"

describe("buildApiProxyRequestOptions", () => {
  it("pins proxy requests to the configured backend connection fields", () => {
    const options = buildApiProxyRequestOptions(
      "https://evil.example/api/v1/admin?steal=1",
      "https://127.0.0.1:8443",
      "POST",
      {
        authorization: "Bearer token",
        "content-type": "application/json",
        host: "evil.example",
        "x-forwarded-host": "evil.example",
        "x-forwarded-proto": "http",
      }
    )

    expect(options.protocol).toBe("https:")
    expect(options.hostname).toBe("127.0.0.1")
    expect(options.port).toBe("8443")
    expect(options.method).toBe("POST")
    expect(options.path).toBe("/api/v1/admin?steal=1")
    expect(options.headers.authorization).toBe("Bearer token")
    expect(options.headers["content-type"]).toBe("application/json")
    expect(options.headers.host).toBeUndefined()
    expect(options.headers["x-forwarded-host"]).toBeUndefined()
    expect(options.headers["x-forwarded-proto"]).toBeUndefined()
  })

  it("keeps API request paths pinned to the backend origin for relative URLs", () => {
    const options = buildApiProxyRequestOptions(
      "/api/v1/health?verbose=1",
      "http://127.0.0.1:8000",
      "GET",
      {}
    )

    expect(options.protocol).toBe("http:")
    expect(options.hostname).toBe("127.0.0.1")
    expect(options.port).toBe("8000")
    expect(options.method).toBe("GET")
    expect(options.path).toBe("/api/v1/health?verbose=1")
  })

  it("rejects non-api requests", () => {
    expect(() =>
      buildApiProxyRequestOptions(
        "/static/index.html",
        "http://127.0.0.1:8000",
        "GET",
        {}
      )
    ).toThrow("Only /api/* requests may be proxied")
  })
})
