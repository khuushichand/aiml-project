import { describe, expect, it } from "vitest"

import { classifyBackendUnreachableError } from "@/services/backend-unreachable"

describe("classifyBackendUnreachableError", () => {
  it("classifies status 0 network-style errors as backend unreachable", () => {
    const result = classifyBackendUnreachableError(
      Object.assign(
        new Error("Network request failed while fetching server metadata."),
        {
          status: 0
        }
      )
    )

    expect(result).toMatchObject({
      kind: "backend_unreachable"
    })
  })

  it("classifies NetworkError when attempting to fetch resource", () => {
    const result = classifyBackendUnreachableError(
      new Error("NetworkError when attempting to fetch resource.")
    )

    expect(result).toMatchObject({
      kind: "backend_unreachable"
    })
  })

  it("classifies Failed to fetch", () => {
    const result = classifyBackendUnreachableError(new Error("Failed to fetch"))

    expect(result).toMatchObject({
      kind: "backend_unreachable"
    })
  })

  it("does not classify feature-specific failed-to-fetch HTTP errors", () => {
    const cases = [
      new Error("Failed to fetch file report.pdf: HTTP 404"),
      Object.assign(new Error("Failed to fetch media count: HTTP 500"), {
        status: 500
      })
    ]

    for (const error of cases) {
      expect(classifyBackendUnreachableError(error)).toMatchObject({
        kind: "other"
      })
    }
  })

  it("does not classify abort-style transport errors", () => {
    const cases = [
      Object.assign(new Error("AbortError"), { status: 0, code: "REQUEST_ABORTED" }),
      Object.assign(new Error("REQUEST_ABORTED"), { status: 0 }),
      new Error("The operation was aborted.")
    ]

    for (const error of cases) {
      expect(classifyBackendUnreachableError(error)).toMatchObject({
        kind: "other"
      })
    }
  })

  it("does not classify unrelated runtime errors", () => {
    const result = classifyBackendUnreachableError(new Error("Unexpected state transition"))

    expect(result).toMatchObject({
      kind: "other"
    })
  })

  it("enriches diagnostics from a recent __tldwLastRequestError payload", () => {
    const result = classifyBackendUnreachableError(
      Object.assign(new Error("Failed to fetch"), {
        status: 0
      }),
      {
        nowMs: Date.parse("2026-03-27T12:00:10.000Z"),
        recentRequestError: {
          method: "GET",
          path: "/api/v1/health",
          status: 0,
          error: "NetworkError when attempting to fetch resource.",
          source: "direct",
          at: "2026-03-27T12:00:00.000Z"
        },
        recentRequestErrorFreshnessMs: 60_000
      }
    )

    expect(result).toMatchObject({
      kind: "backend_unreachable",
      method: "GET",
      path: "/api/v1/health",
      recentRequestError: {
        method: "GET",
        path: "/api/v1/health",
        status: 0,
        error: "NetworkError when attempting to fetch resource.",
        source: "direct"
      }
    })
  })
})
