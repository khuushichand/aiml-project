import { describe, expect, it } from "vitest"
import {
  buildApiBaseUrl,
  detectNetworkingIssue,
  resolveDeploymentMode,
  resolvePublicApiOrigin
} from "@web/lib/api-base"

describe("api-base", () => {
  it("uses a same-origin relative base in quickstart mode", () => {
    expect(resolveDeploymentMode({ NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE: "quickstart" })).toBe("quickstart")
    expect(resolvePublicApiOrigin({ NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE: "quickstart" }, "http://localhost:8080")).toBe("")
    expect(buildApiBaseUrl("", "v1")).toBe("/api/v1")
    expect(buildApiBaseUrl("", "")).toBe("/api/v1")
  })

  it("keeps explicit absolute API origins in advanced mode", () => {
    expect(
      resolvePublicApiOrigin(
        {
          NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE: "advanced",
          NEXT_PUBLIC_API_URL: "https://api.example.test"
        },
        "https://app.example.test"
      )
    ).toBe("https://api.example.test")
  })

  it("flags localhost API URLs when the page origin is not loopback", () => {
    expect(
      detectNetworkingIssue(
        {
          NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE: "advanced",
          NEXT_PUBLIC_API_URL: "http://127.0.0.1:8000"
        },
        "http://192.168.5.184:8080"
      )?.kind
    ).toBe("loopback_api_not_browser_reachable")
  })
})
