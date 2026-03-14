import React from "react"
import { Button, Checkbox, Input, Typography } from "antd"
import { useTranslation } from "react-i18next"

import type {
  SchedulerPresetId,
  SchedulerSettingsDraft,
  SchedulerValidationErrors
} from "../utils/scheduler-settings"
import { SCHEDULER_PRESETS } from "../utils/scheduler-settings"

const { Text } = Typography

type DeckSchedulerSettingsEditorProps = {
  draft: SchedulerSettingsDraft
  errors: SchedulerValidationErrors
  summary: string | null
  onFieldChange: <K extends keyof SchedulerSettingsDraft>(
    field: K,
    value: SchedulerSettingsDraft[K]
  ) => void
  onApplyPreset: (presetId: SchedulerPresetId) => void
  onResetDefaults: () => void
  advancedDefaultOpen?: boolean
}

type SchedulerFieldConfig = {
  key: Exclude<keyof SchedulerSettingsDraft, "enable_fuzz">
  label: string
  placeholder?: string
  testId: string
}

const ADVANCED_FIELDS: SchedulerFieldConfig[] = [
  {
    key: "new_steps_minutes",
    label: "New steps (minutes)",
    placeholder: "1, 10",
    testId: "deck-scheduler-editor-field-new-steps"
  },
  {
    key: "relearn_steps_minutes",
    label: "Relearn steps (minutes)",
    placeholder: "10",
    testId: "deck-scheduler-editor-field-relearn-steps"
  },
  {
    key: "graduating_interval_days",
    label: "Graduating interval (days)",
    testId: "deck-scheduler-editor-field-graduating-interval"
  },
  {
    key: "easy_interval_days",
    label: "Easy interval (days)",
    testId: "deck-scheduler-editor-field-easy-interval"
  },
  {
    key: "easy_bonus",
    label: "Easy bonus",
    testId: "deck-scheduler-editor-field-easy-bonus"
  },
  {
    key: "interval_modifier",
    label: "Interval modifier",
    testId: "deck-scheduler-editor-field-interval-modifier"
  },
  {
    key: "max_interval_days",
    label: "Max interval (days)",
    testId: "deck-scheduler-editor-field-max-interval"
  },
  {
    key: "leech_threshold",
    label: "Leech threshold",
    testId: "deck-scheduler-editor-field-leech-threshold"
  }
]

export const DeckSchedulerSettingsEditor: React.FC<DeckSchedulerSettingsEditorProps> = ({
  draft,
  errors,
  summary,
  onFieldChange,
  onApplyPreset,
  onResetDefaults,
  advancedDefaultOpen = false
}) => {
  const { t } = useTranslation(["option", "common"])
  const [advancedOpen, setAdvancedOpen] = React.useState(advancedDefaultOpen)

  const renderFieldError = (field: keyof SchedulerValidationErrors) => {
    const error = errors[field]
    if (!error) return null
    return (
      <Text type="danger" className="text-xs">
        {error}
      </Text>
    )
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Text strong>
          {t("option:flashcards.schedulerPresets", { defaultValue: "Presets" })}
        </Text>
        <div className="flex flex-wrap gap-2">
          {SCHEDULER_PRESETS.map((preset) => (
            <Button
              key={preset.id}
              size="small"
              onClick={() => onApplyPreset(preset.id)}
              data-testid={`deck-scheduler-editor-preset-${preset.id}`}
            >
              {preset.label}
            </Button>
          ))}
          <Button
            size="small"
            onClick={onResetDefaults}
            data-testid="deck-scheduler-editor-reset"
          >
            {t("option:flashcards.schedulerResetAction", {
              defaultValue: "Reset to defaults"
            })}
          </Button>
        </div>
      </div>

      <div className="rounded border border-border bg-muted/20 p-3">
        <Text
          type={summary ? "secondary" : "danger"}
          data-testid="deck-scheduler-editor-summary"
        >
          {summary ??
            t("option:flashcards.schedulerDraftInvalid", {
              defaultValue: "Draft has validation errors."
            })}
        </Text>
      </div>

      <div>
        <Button
          type="text"
          size="small"
          onClick={() => setAdvancedOpen((current) => !current)}
          data-testid="deck-scheduler-editor-toggle-advanced"
        >
          {advancedOpen
            ? t("option:flashcards.hideAdvancedScheduler", {
                defaultValue: "Hide advanced settings"
              })
            : t("option:flashcards.showAdvancedScheduler", {
                defaultValue: "Customize scheduler"
              })}
        </Button>
      </div>

      {advancedOpen && (
        <div className="grid gap-4 md:grid-cols-2">
          {ADVANCED_FIELDS.map((field) => (
            <label key={field.key} className="flex flex-col gap-1">
              <Text strong>{field.label}</Text>
              <Input
                value={draft[field.key]}
                onChange={(event) => onFieldChange(field.key, event.target.value)}
                placeholder={field.placeholder}
                data-testid={field.testId}
              />
              {renderFieldError(field.key as keyof SchedulerValidationErrors)}
            </label>
          ))}

          <div className="md:col-span-2">
            <Checkbox
              checked={draft.enable_fuzz}
              onChange={(event) => onFieldChange("enable_fuzz", event.target.checked)}
              data-testid="deck-scheduler-editor-field-enable-fuzz"
            >
              {t("option:flashcards.schedulerEnableFuzz", {
                defaultValue: "Enable review fuzz"
              })}
            </Checkbox>
          </div>
        </div>
      )}
    </div>
  )
}

export default DeckSchedulerSettingsEditor
