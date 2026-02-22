import { describe, expect, it } from "vitest"
import { mapWatchlistsError } from "../watchlists-error"

const t = (key: string, defaultValue?: string, options?: Record<string, unknown>) => {
  if (!defaultValue) return key
  return defaultValue.replace(/\{\{(\w+)\}\}/g, (_, token) => String(options?.[token] ?? ""))
}

describe("mapWatchlistsError", () => {
  it("classifies network failures and includes retry guidance", () => {
    const mapped = mapWatchlistsError(new Error("Failed to fetch"), {
      t,
      context: "feeds",
      fallbackMessage: "Failed to load feeds"
    })

    expect(mapped.kind).toBe("network")
    expect(mapped.severity).toBe("error")
    expect(mapped.description).toContain("Check server connection")
  })

  it("classifies auth failures from status-bearing payloads", () => {
    const mapped = mapWatchlistsError(
      {
        status: 403,
        details: { detail: "forbidden" }
      },
      {
        t,
        context: "monitors",
        fallbackMessage: "Failed to load monitors"
      }
    )

    expect(mapped.kind).toBe("auth")
    expect(mapped.severity).toBe("warning")
    expect(mapped.description).toContain("Verify your login/API key permissions")
  })

  it("extracts status from nested response payloads", () => {
    const mapped = mapWatchlistsError(
      {
        response: {
          status: 429,
          data: { detail: "too many requests" }
        }
      },
      {
        t,
        context: "activity"
      }
    )

    expect(mapped.status).toBe(429)
    expect(mapped.kind).toBe("rate_limit")
    expect(mapped.description).toContain("Reduce monitor frequency")
  })
})

