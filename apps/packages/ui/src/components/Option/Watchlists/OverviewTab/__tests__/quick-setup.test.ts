import { describe, expect, it, vi } from "vitest"
import {
  getLocalTimezone,
  QUICK_SETUP_DEFAULT_VALUES,
  resolveQuickSetupSchedule,
  toQuickSetupJobPayload,
  toQuickSetupSourcePayload
} from "../quick-setup"

describe("watchlists overview quick setup helpers", () => {
  it("provides sensible defaults", () => {
    expect(QUICK_SETUP_DEFAULT_VALUES).toEqual({
      sourceName: "",
      sourceUrl: "",
      sourceType: "rss",
      monitorName: "",
      schedulePreset: "daily",
      runNow: true
    })
  })

  it("resolves preset schedules into cron/timezone", () => {
    const timezoneSpy = vi
      .spyOn(Intl, "DateTimeFormat")
      .mockImplementation(() => ({
        resolvedOptions: () => ({ timeZone: "America/New_York" })
      }) as Intl.DateTimeFormat)

    expect(resolveQuickSetupSchedule("none")).toEqual({})
    expect(resolveQuickSetupSchedule("hourly")).toEqual({
      schedule_expr: "0 * * * *",
      timezone: "America/New_York"
    })
    expect(resolveQuickSetupSchedule("daily")).toEqual({
      schedule_expr: "0 8 * * *",
      timezone: "America/New_York"
    })
    expect(resolveQuickSetupSchedule("weekdays")).toEqual({
      schedule_expr: "0 8 * * MON-FRI",
      timezone: "America/New_York"
    })

    timezoneSpy.mockRestore()
  })

  it("falls back to UTC when timezone is unavailable", () => {
    const timezoneSpy = vi
      .spyOn(Intl, "DateTimeFormat")
      .mockImplementation(() => ({
        resolvedOptions: () => ({ timeZone: "" })
      }) as Intl.DateTimeFormat)

    expect(getLocalTimezone()).toBe("UTC")
    timezoneSpy.mockRestore()
  })

  it("builds trimmed source and monitor payloads", () => {
    expect(
      toQuickSetupSourcePayload({
        sourceName: " My Feed ",
        sourceUrl: " https://example.com/rss.xml ",
        sourceType: "rss"
      })
    ).toEqual({
      name: "My Feed",
      url: "https://example.com/rss.xml",
      source_type: "rss",
      active: true
    })

    const timezoneSpy = vi
      .spyOn(Intl, "DateTimeFormat")
      .mockImplementation(() => ({
        resolvedOptions: () => ({ timeZone: "UTC" })
      }) as Intl.DateTimeFormat)

    expect(
      toQuickSetupJobPayload(
        {
          monitorName: " Morning Monitor ",
          schedulePreset: "daily"
        },
        42
      )
    ).toEqual({
      name: "Morning Monitor",
      scope: { sources: [42] },
      active: true,
      schedule_expr: "0 8 * * *",
      timezone: "UTC"
    })

    timezoneSpy.mockRestore()
  })
})

