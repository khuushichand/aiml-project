import React from "react"
import { Button, Checkbox, Input, Select, Typography } from "antd"
import { useTranslation } from "react-i18next"

import type { DeckSchedulerDraftState } from "../hooks/useDeckSchedulerDraft"
import type { SchedulerPresetId } from "../utils/scheduler-settings"
import { getSchedulerPresets } from "../utils/scheduler-settings"

const { Text } = Typography

type DeckSchedulerSettingsEditorProps = {
  schedulerDraft: DeckSchedulerDraftState
  advancedDefaultOpen?: boolean
}

type Sm2FieldConfig = {
  key: Exclude<keyof DeckSchedulerDraftState["draft"]["sm2_plus"], "enable_fuzz">
  label: string
  placeholder?: string
  testId: string
}

const SM2_ADVANCED_FIELDS: Sm2FieldConfig[] = [
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

type FsrsFieldConfig = {
  key: Exclude<keyof DeckSchedulerDraftState["draft"]["fsrs"], "enable_fuzz">
  label: string
  placeholder?: string
  testId: string
}

const FSRS_FIELDS: FsrsFieldConfig[] = [
  {
    key: "target_retention",
    label: "Target retention",
    placeholder: "0.90",
    testId: "deck-scheduler-editor-field-target-retention"
  },
  {
    key: "maximum_interval_days",
    label: "Maximum interval (days)",
    placeholder: "36500",
    testId: "deck-scheduler-editor-field-maximum-interval"
  }
]

export const DeckSchedulerSettingsEditor: React.FC<DeckSchedulerSettingsEditorProps> = ({
  schedulerDraft,
  advancedDefaultOpen = false
}) => {
  const { t } = useTranslation(["option", "common"])
  const [advancedOpen, setAdvancedOpen] = React.useState(advancedDefaultOpen)
  const schedulerType = schedulerDraft.draft.scheduler_type
  const presets = React.useMemo(() => getSchedulerPresets(schedulerType), [schedulerType])

  const renderFieldError = React.useCallback(
    (field: string) => {
      const error =
        schedulerType === "fsrs"
          ? schedulerDraft.errors.fsrs[field as keyof typeof schedulerDraft.errors.fsrs]
          : schedulerDraft.errors.sm2_plus[field as keyof typeof schedulerDraft.errors.sm2_plus]
      if (!error) return null
      return (
        <Text type="danger" className="text-xs">
          {error}
        </Text>
      )
    },
    [schedulerDraft.errors.fsrs, schedulerDraft.errors.sm2_plus, schedulerType]
  )

  const renderPresetButtons = () => (
    <div className="space-y-2">
      <Text strong>
        {t("option:flashcards.schedulerPresets", { defaultValue: "Presets" })}
      </Text>
      <div className="flex flex-wrap gap-2">
        {presets.map((preset) => (
          <Button
            key={preset.id}
            size="small"
            onClick={() => schedulerDraft.applyPreset(preset.id as SchedulerPresetId)}
            data-testid={`deck-scheduler-editor-preset-${preset.id}`}
          >
            {preset.label}
          </Button>
        ))}
        <Button
          size="small"
          onClick={schedulerDraft.resetToDefaults}
          data-testid="deck-scheduler-editor-reset"
        >
          {t("option:flashcards.schedulerResetAction", {
            defaultValue: "Reset to defaults"
          })}
        </Button>
      </div>
    </div>
  )

  return (
    <div className="space-y-4">
      <label className="flex flex-col gap-1">
        <Text strong>
          {t("option:flashcards.schedulerTypeLabel", {
            defaultValue: "Scheduler type"
          })}
        </Text>
        <Select
          value={schedulerType}
          onChange={(value) => schedulerDraft.updateSchedulerType(value)}
          options={[
            { value: "sm2_plus", label: "SM-2+" },
            { value: "fsrs", label: "FSRS" }
          ]}
          data-testid="deck-scheduler-editor-field-scheduler-type"
        />
      </label>

      {renderPresetButtons()}

      <div className="rounded border border-border bg-muted/20 p-3">
        <Text
          type={schedulerDraft.summary ? "secondary" : "danger"}
          data-testid="deck-scheduler-editor-summary"
        >
          {schedulerDraft.summary ??
            t("option:flashcards.schedulerDraftInvalid", {
              defaultValue: "Draft has validation errors."
            })}
        </Text>
      </div>

      {schedulerType === "sm2_plus" ? (
        <>
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
              {SM2_ADVANCED_FIELDS.map((field) => (
                <label key={field.key} className="flex flex-col gap-1">
                  <Text strong>{field.label}</Text>
                  <Input
                    value={schedulerDraft.draft.sm2_plus[field.key]}
                    onChange={(event) =>
                      schedulerDraft.updateSm2Field(field.key, event.target.value)
                    }
                    placeholder={field.placeholder}
                    data-testid={field.testId}
                  />
                  {renderFieldError(field.key)}
                </label>
              ))}

              <div className="md:col-span-2">
                <Checkbox
                  checked={schedulerDraft.draft.sm2_plus.enable_fuzz}
                  onChange={(event) =>
                    schedulerDraft.updateSm2Field("enable_fuzz", event.target.checked)
                  }
                  data-testid="deck-scheduler-editor-field-enable-fuzz"
                >
                  {t("option:flashcards.schedulerEnableFuzz", {
                    defaultValue: "Enable review fuzz"
                  })}
                </Checkbox>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {FSRS_FIELDS.map((field) => (
            <label key={field.key} className="flex flex-col gap-1">
              <Text strong>{field.label}</Text>
              <Input
                value={schedulerDraft.draft.fsrs[field.key]}
                onChange={(event) =>
                  schedulerDraft.updateFsrsField(field.key, event.target.value)
                }
                placeholder={field.placeholder}
                data-testid={field.testId}
              />
              {renderFieldError(field.key)}
            </label>
          ))}

          <div className="md:col-span-2">
            <Checkbox
              checked={schedulerDraft.draft.fsrs.enable_fuzz}
              onChange={(event) =>
                schedulerDraft.updateFsrsField("enable_fuzz", event.target.checked)
              }
              data-testid="deck-scheduler-editor-field-fsrs-enable-fuzz"
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
