import type {
  WatchlistJobCreate,
  WatchlistSourceCreate,
  SourceType
} from "@/types/watchlists"

export type QuickSetupSchedulePreset = "none" | "hourly" | "daily" | "weekdays"
export type QuickSetupGoal = "briefing" | "triage"

export interface QuickSetupValues {
  sourceName: string
  sourceUrl: string
  sourceType: SourceType
  monitorName: string
  schedulePreset: QuickSetupSchedulePreset
  audioBriefing: boolean
  runNow: boolean
  setupGoal: QuickSetupGoal
}

export const QUICK_SETUP_DEFAULT_VALUES: QuickSetupValues = {
  sourceName: "",
  sourceUrl: "",
  sourceType: "rss",
  monitorName: "",
  schedulePreset: "daily",
  audioBriefing: false,
  runNow: true,
  setupGoal: "briefing"
}

const presetToCron: Record<Exclude<QuickSetupSchedulePreset, "none">, string> = {
  hourly: "0 * * * *",
  daily: "0 8 * * *",
  weekdays: "0 8 * * MON-FRI"
}

export const getLocalTimezone = (): string => {
  const resolved = Intl.DateTimeFormat().resolvedOptions().timeZone
  return resolved || "UTC"
}

export const resolveQuickSetupSchedule = (
  preset: QuickSetupSchedulePreset
): { schedule_expr?: string; timezone?: string } => {
  if (preset === "none") return {}
  return {
    schedule_expr: presetToCron[preset],
    timezone: getLocalTimezone()
  }
}

export const toQuickSetupSourcePayload = (
  values: Pick<QuickSetupValues, "sourceName" | "sourceUrl" | "sourceType">
): WatchlistSourceCreate => ({
  name: String(values.sourceName || "").trim(),
  url: String(values.sourceUrl || "").trim(),
  source_type: values.sourceType || "rss",
  active: true
})

export const toQuickSetupJobPayload = (
  values: Pick<QuickSetupValues, "monitorName" | "schedulePreset" | "setupGoal" | "audioBriefing">,
  sourceId: number
): WatchlistJobCreate => {
  const payload: WatchlistJobCreate = {
    name: String(values.monitorName || "").trim(),
    scope: { sources: [sourceId] },
    active: true,
    ...resolveQuickSetupSchedule(values.schedulePreset || "daily")
  }

  if ((values.setupGoal || "briefing") === "briefing") {
    payload.output_prefs = {
      template_name: "briefing_md",
      ...(values.audioBriefing ? { generate_audio: true } : {})
    }
  }

  return payload
}
