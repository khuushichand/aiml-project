import watchlistsLocale from "../../../../../assets/locale/en/watchlists.json"
import { describe, expect, it } from "vitest"

type JsonObject = Record<string, unknown>

const getNestedValue = (source: JsonObject, keyPath: string): unknown =>
  keyPath.split(".").reduce<unknown>((acc, segment) => {
    if (!acc || typeof acc !== "object") return undefined
    return (acc as JsonObject)[segment]
  }, source)

const REQUIRED_WATCHLISTS_ERROR_KEYS = [
  "errors.retry",
  "errors.operation.load",
  "errors.operation.save",
  "errors.operation.test",
  "errors.operation.retry",
  "errors.title",
  "errors.details",
  "errors.next.auth",
  "errors.next.rateLimit",
  "errors.next.timeout",
  "errors.next.validation",
  "errors.next.dns",
  "errors.next.tls",
  "errors.next.network",
  "errors.next.server",
  "errors.next.notFound",
  "errors.next.generic"
] as const

describe("Watchlists error locale contract", () => {
  it("keeps all error taxonomy and remediation copy keys present", () => {
    const labels = watchlistsLocale as JsonObject

    for (const keyPath of REQUIRED_WATCHLISTS_ERROR_KEYS) {
      const value = getNestedValue(labels, keyPath)
      expect(typeof value, `Missing or non-string locale key: ${keyPath}`).toBe("string")
      expect(String(value).trim().length).toBeGreaterThan(0)
    }
  })
})
