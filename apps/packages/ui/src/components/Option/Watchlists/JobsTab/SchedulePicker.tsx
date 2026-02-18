import React, { useEffect, useMemo, useState } from "react"
import { Button, Input, InputNumber, Select, Switch } from "antd"
import { Clock } from "lucide-react"
import { useTranslation } from "react-i18next"
import { CronDisplay } from "../shared"
import {
  buildCronFromPreset,
  createDefaultPresetState,
  parsePresetFromCron,
  type PresetScheduleState,
  type SchedulePresetKey,
  type WeekdayToken
} from "./schedule-utils"

interface SchedulePickerProps {
  value: string | null | undefined
  onChange: (schedule: string | null) => void
  timezone?: string
  onTimezoneChange?: (tz: string) => void
}

const TIMEZONES = [
  { value: "UTC", label: "UTC" },
  { value: "America/New_York", label: "US Eastern" },
  { value: "America/Chicago", label: "US Central" },
  { value: "America/Denver", label: "US Mountain" },
  { value: "America/Los_Angeles", label: "US Pacific" },
  { value: "Europe/London", label: "London" },
  { value: "Europe/Paris", label: "Paris" },
  { value: "Europe/Berlin", label: "Berlin" },
  { value: "Asia/Tokyo", label: "Tokyo" },
  { value: "Asia/Shanghai", label: "Shanghai" },
  { value: "Asia/Singapore", label: "Singapore" },
  { value: "Australia/Sydney", label: "Sydney" }
]

const WEEKDAY_OPTIONS: Array<{ value: WeekdayToken; label: string }> = [
  { value: "MON", label: "Monday" },
  { value: "TUE", label: "Tuesday" },
  { value: "WED", label: "Wednesday" },
  { value: "THU", label: "Thursday" },
  { value: "FRI", label: "Friday" },
  { value: "SAT", label: "Saturday" },
  { value: "SUN", label: "Sunday" }
]

export const SchedulePicker: React.FC<SchedulePickerProps> = ({
  value,
  onChange,
  timezone = "UTC",
  onTimezoneChange
}) => {
  const { t } = useTranslation(["watchlists"])
  const [customCron, setCustomCron] = useState(value || "")
  const [advancedMode, setAdvancedMode] = useState(false)
  const [presetState, setPresetState] = useState<PresetScheduleState>(createDefaultPresetState())

  useEffect(() => {
    setCustomCron(value || "")
    const parsed = parsePresetFromCron(value)
    if (parsed) {
      setPresetState(parsed)
      setAdvancedMode(false)
      return
    }
    if (!value) {
      setPresetState(createDefaultPresetState())
      setAdvancedMode(false)
      return
    }
    setAdvancedMode(true)
  }, [value])

  const presetOptions = useMemo(
    () =>
      [
        {
          value: "hourly",
          label: t("watchlists:schedule.preset.hourly.label", "Every hour"),
          description: t(
            "watchlists:schedule.preset.hourly.description",
            "Runs once each hour at the selected minute."
          )
        },
        {
          value: "every6hours",
          label: t("watchlists:schedule.preset.every6hours.label", "Every 6 hours"),
          description: t(
            "watchlists:schedule.preset.every6hours.description",
            "Runs four times each day at the selected minute."
          )
        },
        {
          value: "daily",
          label: t("watchlists:schedule.preset.daily.label", "Daily"),
          description: t(
            "watchlists:schedule.preset.daily.description",
            "Runs every day at the selected time."
          )
        },
        {
          value: "weekly",
          label: t("watchlists:schedule.preset.weekly.label", "Weekly"),
          description: t(
            "watchlists:schedule.preset.weekly.description",
            "Runs once a week on the selected weekday and time."
          )
        }
      ] as Array<{ value: SchedulePresetKey; label: string; description: string }>,
    [t]
  )

  const selectedPreset = presetOptions.find((item) => item.value === presetState.preset)

  const applyPreset = (nextState: PresetScheduleState) => {
    onChange(buildCronFromPreset(nextState))
  }

  const updatePresetState = (updater: (previous: PresetScheduleState) => PresetScheduleState) => {
    setPresetState((previous) => {
      const next = updater(previous)
      if (!advancedMode) {
        applyPreset(next)
      }
      return next
    })
  }

  const handlePresetChange = (preset: SchedulePresetKey) => {
    updatePresetState((previous) => ({ ...previous, preset }))
  }

  const handleMinuteChange = (value: number | null) => {
    updatePresetState((previous) => ({
      ...previous,
      minute: typeof value === "number" && value >= 0 ? Math.min(59, Math.floor(value)) : 0
    }))
  }

  const handleHourChange = (value: number | null) => {
    updatePresetState((previous) => ({
      ...previous,
      hour: typeof value === "number" && value >= 0 ? Math.min(23, Math.floor(value)) : 0
    }))
  }

  const handleWeekdayChange = (weekday: WeekdayToken) => {
    updatePresetState((previous) => ({ ...previous, weekday }))
  }

  const handleAdvancedToggle = (checked: boolean) => {
    setAdvancedMode(checked)
    if (!checked) {
      applyPreset(presetState)
    } else {
      setCustomCron(value || buildCronFromPreset(presetState))
    }
  }

  const handleCustomApply = () => {
    const normalized = customCron.trim()
    if (!normalized) return
    onChange(normalized)
  }

  const handleClear = () => {
    setCustomCron("")
    setPresetState(createDefaultPresetState())
    setAdvancedMode(false)
    onChange(null)
  }

  return (
    <div className="space-y-4">
      {value && (
        <div className="flex items-center justify-between rounded-lg border border-primary/30 bg-primary/10 p-3">
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-primary" />
            <CronDisplay expression={value} showIcon={false} />
          </div>
          <Button size="small" onClick={handleClear}>
            {t("watchlists:schedule.clear", "Clear")}
          </Button>
        </div>
      )}

      <div className="rounded-lg border border-border p-3">
        <div className="mb-3 text-sm font-medium">
          {t("watchlists:schedule.presets", "Schedule presets")}
        </div>
        <Select
          value={presetState.preset}
          onChange={(value) => handlePresetChange(value as SchedulePresetKey)}
          options={presetOptions}
          className="w-full"
        />
        <div className="mt-2 text-xs text-text-muted">
          {selectedPreset?.description}
        </div>

        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
          {(presetState.preset === "daily" || presetState.preset === "weekly") && (
            <div>
              <div className="mb-1 text-xs text-text-muted">
                {t("watchlists:schedule.hour", "Hour")}
              </div>
              <InputNumber
                min={0}
                max={23}
                precision={0}
                value={presetState.hour}
                onChange={handleHourChange}
                className="w-full"
              />
            </div>
          )}
          <div>
            <div className="mb-1 text-xs text-text-muted">
              {t("watchlists:schedule.minute", "Minute")}
            </div>
            <InputNumber
              min={0}
              max={59}
              precision={0}
              value={presetState.minute}
              onChange={handleMinuteChange}
              className="w-full"
            />
          </div>
          {presetState.preset === "weekly" && (
            <div>
              <div className="mb-1 text-xs text-text-muted">
                {t("watchlists:schedule.weekday", "Weekday")}
              </div>
              <Select
                value={presetState.weekday}
                onChange={(value) => handleWeekdayChange(value as WeekdayToken)}
                options={WEEKDAY_OPTIONS.map((item) => ({
                  value: item.value,
                  label: t(`watchlists:schedule.weekdayOption.${item.value}`, item.label)
                }))}
              />
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
        <div>
          <div className="text-sm font-medium">
            {t("watchlists:schedule.advancedLabel", "Advanced cron expression")}
          </div>
          <div className="text-xs text-text-muted">
            {t(
              "watchlists:schedule.advancedHint",
              "Enable only if presets cannot express the cadence you need."
            )}
          </div>
        </div>
        <Switch checked={advancedMode} onChange={handleAdvancedToggle} />
      </div>

      {advancedMode && (
        <div>
          <div className="mb-2 text-sm font-medium">
            {t("watchlists:schedule.custom", "Custom schedule")}
          </div>
          <div className="flex gap-2">
            <Input
              placeholder={t("watchlists:schedule.cronPlaceholder", "Cron expression (e.g., 0 9 * * MON)")}
              value={customCron}
              onChange={(event) => setCustomCron(event.target.value)}
              className="flex-1"
              onPressEnter={handleCustomApply}
            />
            <Button type="primary" onClick={handleCustomApply} disabled={!customCron.trim()}>
              {t("watchlists:schedule.apply", "Apply")}
            </Button>
          </div>
          {customCron.trim().length > 0 && (
            <div className="mt-2 text-sm text-text-muted">
              <span className="font-medium">{t("watchlists:schedule.preview", "Preview")}:</span>{" "}
              <CronDisplay expression={customCron} showIcon={false} />
            </div>
          )}
        </div>
      )}

      {onTimezoneChange && (
        <div>
          <div className="mb-2 text-sm font-medium">
            {t("watchlists:schedule.timezone", "Timezone")}
          </div>
          <Select
            value={timezone}
            onChange={onTimezoneChange}
            className="w-56"
            options={TIMEZONES}
            showSearch
            optionFilterProp="label"
          />
        </div>
      )}

      <div className="text-xs text-text-muted">
        {advancedMode
          ? t(
              "watchlists:schedule.helpAdvanced",
              "Cron format: minute hour day-of-month month day-of-week. Example: 0 9 * * MON runs every Monday at 09:00."
            )
          : t(
              "watchlists:schedule.helpSimple",
              "Pick a schedule preset above. You can switch to Advanced cron for uncommon timing patterns."
            )}
      </div>
    </div>
  )
}
