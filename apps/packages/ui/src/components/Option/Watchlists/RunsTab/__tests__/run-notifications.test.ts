import { describe, expect, it } from "vitest"
import {
  getRunFailureHint,
  resolveRunTransitionNotification,
  shouldNotifyNewTerminalRun
} from "../run-notifications"

describe("run notification helpers", () => {
  const translatedHints: Record<string, string> = {
    "watchlists:notifications.failureHints.timeout": "Localized timeout hint",
    "watchlists:notifications.failureHints.auth": "Localized auth hint"
  }
  const t = (key: string, defaultValue?: string) =>
    translatedHints[key] ?? defaultValue ?? key

  it("returns completed notification when run transitions from running", () => {
    const result = resolveRunTransitionNotification("running", {
      status: "completed",
      error_msg: null
    })
    expect(result).toEqual({ kind: "completed" })
  })

  it("returns failed notification and remediation hint for failed transitions", () => {
    const result = resolveRunTransitionNotification(
      "pending",
      {
        status: "failed",
        error_msg: "timeout while fetching"
      },
      t
    )
    expect(result).toEqual({
      kind: "failed",
      hint: "Localized timeout hint"
    })
  })

  it("does not notify without a previous status transition", () => {
    const result = resolveRunTransitionNotification(null, {
      status: "failed",
      error_msg: "403 forbidden"
    })
    expect(result).toBeNull()
  })

  it("notifies for newly observed terminal runs that finished after session start", () => {
    const sessionStart = Date.parse("2026-02-18T09:00:00Z")
    expect(
      shouldNotifyNewTerminalRun(
        {
          status: "completed",
          finished_at: "2026-02-18T09:01:00Z"
        },
        sessionStart
      )
    ).toBe(true)
  })

  it("skips notifications for old runs or cancelled runs", () => {
    const sessionStart = Date.parse("2026-02-18T09:00:00Z")
    expect(
      shouldNotifyNewTerminalRun(
        {
          status: "failed",
          finished_at: "2026-02-18T08:59:00Z"
        },
        sessionStart
      )
    ).toBe(false)
    expect(
      shouldNotifyNewTerminalRun(
        {
          status: "cancelled",
          finished_at: "2026-02-18T09:05:00Z"
        },
        sessionStart
      )
    ).toBe(false)
  })

  it("maps common failure modes to actionable hints", () => {
    expect(getRunFailureHint("403 Forbidden")).toContain("authentication")
    expect(getRunFailureHint("rate limit exceeded")).toContain("rate-limiting")
    expect(getRunFailureHint("dns lookup failed")).toContain("resolved")
    expect(getRunFailureHint("")).toContain("inspect logs")
  })

  it("resolves localized hint keys when translator is provided", () => {
    expect(getRunFailureHint("403 Forbidden", t)).toBe("Localized auth hint")
    expect(getRunFailureHint("timeout while fetching", t)).toBe("Localized timeout hint")
  })

  it("falls back to default copy when translator is missing key", () => {
    const missingTranslator = (key: string) => key
    expect(getRunFailureHint("timeout while fetching", missingTranslator)).toBe(
      "The source request timed out. Retry, or lower concurrency for this source."
    )
  })
})
