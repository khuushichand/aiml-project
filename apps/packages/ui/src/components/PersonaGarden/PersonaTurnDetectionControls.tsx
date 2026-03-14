import React from "react"
import { Button, Checkbox } from "antd"

export type PersonaTurnDetectionPreset =
  | "conservative"
  | "balanced"
  | "fast"
  | "custom"

export type PersonaTurnDetectionValues = {
  autoCommitEnabled: boolean
  vadThreshold: number
  minSilenceMs: number
  turnStopSecs: number
  minUtteranceSecs: number
}

export const PERSONA_TURN_DETECTION_PRESETS: Record<
  Exclude<PersonaTurnDetectionPreset, "custom">,
  PersonaTurnDetectionValues
> = {
  conservative: {
    autoCommitEnabled: true,
    vadThreshold: 0.65,
    minSilenceMs: 450,
    turnStopSecs: 0.35,
    minUtteranceSecs: 0.6
  },
  balanced: {
    autoCommitEnabled: true,
    vadThreshold: 0.5,
    minSilenceMs: 250,
    turnStopSecs: 0.2,
    minUtteranceSecs: 0.4
  },
  fast: {
    autoCommitEnabled: true,
    vadThreshold: 0.35,
    minSilenceMs: 150,
    turnStopSecs: 0.1,
    minUtteranceSecs: 0.25
  }
}

const TURN_DETECTION_PRESETS = Object.keys(
  PERSONA_TURN_DETECTION_PRESETS
) as Array<Exclude<PersonaTurnDetectionPreset, "custom">>

const formatPresetLabel = (preset: PersonaTurnDetectionPreset): string =>
  preset === "custom"
    ? "Custom"
    : preset.slice(0, 1).toUpperCase() + preset.slice(1)

const formatNumericInput = (value: number): string => String(value)

const useNumericInputDraft = (value: number) => {
  const [draft, setDraft] = React.useState(() => formatNumericInput(value))

  React.useEffect(() => {
    setDraft(formatNumericInput(value))
  }, [value])

  return [draft, setDraft] as const
}

const isMatchingPreset = (
  candidate: PersonaTurnDetectionValues,
  preset: PersonaTurnDetectionValues
): boolean =>
  candidate.autoCommitEnabled === preset.autoCommitEnabled &&
  candidate.vadThreshold === preset.vadThreshold &&
  candidate.minSilenceMs === preset.minSilenceMs &&
  candidate.turnStopSecs === preset.turnStopSecs &&
  candidate.minUtteranceSecs === preset.minUtteranceSecs

export const derivePersonaTurnDetectionPreset = (
  candidate: PersonaTurnDetectionValues
): PersonaTurnDetectionPreset => {
  for (const preset of TURN_DETECTION_PRESETS) {
    if (isMatchingPreset(candidate, PERSONA_TURN_DETECTION_PRESETS[preset])) {
      return preset
    }
  }
  return "custom"
}

type PersonaTurnDetectionControlsProps = {
  title: string
  helperText: string
  testIdPrefix: string
  autoCommitLabel: string
  currentPreset: PersonaTurnDetectionPreset
  values: PersonaTurnDetectionValues
  disabled?: boolean
  advancedInputsDisabled?: boolean
  className?: string
  advancedFooterText?: string
  onAutoCommitEnabledChange: (next: boolean) => void
  onPresetChange: (next: Exclude<PersonaTurnDetectionPreset, "custom">) => void
  onVadThresholdChange: (next: number) => void
  onMinSilenceMsChange: (next: number) => void
  onTurnStopSecsChange: (next: number) => void
  onMinUtteranceSecsChange: (next: number) => void
}

export const PersonaTurnDetectionControls: React.FC<
  PersonaTurnDetectionControlsProps
> = ({
  title,
  helperText,
  testIdPrefix,
  autoCommitLabel,
  currentPreset,
  values,
  disabled = false,
  advancedInputsDisabled,
  className,
  advancedFooterText,
  onAutoCommitEnabledChange,
  onPresetChange,
  onVadThresholdChange,
  onMinSilenceMsChange,
  onTurnStopSecsChange,
  onMinUtteranceSecsChange
}) => {
  const [advancedOpen, setAdvancedOpen] = React.useState(false)
  const [vadThresholdDraft, setVadThresholdDraft] = useNumericInputDraft(values.vadThreshold)
  const [minSilenceMsDraft, setMinSilenceMsDraft] = useNumericInputDraft(values.minSilenceMs)
  const [turnStopSecsDraft, setTurnStopSecsDraft] = useNumericInputDraft(values.turnStopSecs)
  const [minUtteranceSecsDraft, setMinUtteranceSecsDraft] = useNumericInputDraft(
    values.minUtteranceSecs
  )
  const numericInputsDisabled =
    advancedInputsDisabled ?? (disabled || !values.autoCommitEnabled)

  const commitNumericDraft = React.useCallback(
    (
      draft: string,
      currentValue: number,
      setDraft: React.Dispatch<React.SetStateAction<string>>,
      onCommit: (next: number) => void
    ) => {
      const normalized = String(draft || "").trim()
      if (!normalized) {
        setDraft(formatNumericInput(currentValue))
        return
      }

      const parsed = Number(normalized)
      if (!Number.isFinite(parsed)) {
        setDraft(formatNumericInput(currentValue))
        return
      }

      setDraft(formatNumericInput(parsed))
      if (parsed !== currentValue) {
        onCommit(parsed)
      }
    },
    []
  )

  return (
    <div
      data-testid={`${testIdPrefix}-section`}
      className={className || "rounded-md border border-border bg-surface2 p-3 text-xs text-text"}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="font-medium text-text">{title}</div>
          <div className="mt-1 text-text-muted">{helperText}</div>
        </div>
        <Button
          data-testid={`${testIdPrefix}-advanced-toggle`}
          size="small"
          onClick={() => setAdvancedOpen((current) => !current)}
        >
          {advancedOpen ? "Hide advanced" : "Advanced"}
        </Button>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-4">
        <Checkbox
          data-testid={`${testIdPrefix}-auto-commit`}
          checked={values.autoCommitEnabled}
          disabled={disabled}
          onChange={(event) => onAutoCommitEnabledChange(event.target.checked)}
        >
          {autoCommitLabel}
        </Checkbox>
        <div className="flex flex-wrap items-center gap-2">
          {TURN_DETECTION_PRESETS.map((preset) => {
            const isActive = currentPreset === preset
            return (
              <Button
                key={preset}
                data-testid={`${testIdPrefix}-preset-${preset}`}
                data-active={isActive ? "true" : "false"}
                size="small"
                type={isActive ? "primary" : "default"}
                disabled={numericInputsDisabled}
                onClick={() => onPresetChange(preset)}
              >
                {formatPresetLabel(preset)}
              </Button>
            )
          })}
          {currentPreset === "custom" ? (
            <Button
              data-testid={`${testIdPrefix}-preset-custom`}
              data-active="true"
              size="small"
              type="primary"
              disabled={numericInputsDisabled}
            >
              Custom
            </Button>
          ) : null}
        </div>
      </div>

      {advancedOpen ? (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1">
            <span className="text-text-muted">Speech threshold</span>
            <input
              data-testid={`${testIdPrefix}-threshold`}
              className="rounded border border-border bg-bg px-2 py-1 text-text"
              type="text"
              inputMode="decimal"
              disabled={numericInputsDisabled}
              value={vadThresholdDraft}
              onChange={(event) => setVadThresholdDraft(event.target.value)}
              onBlur={() =>
                commitNumericDraft(
                  vadThresholdDraft,
                  values.vadThreshold,
                  setVadThresholdDraft,
                  onVadThresholdChange
                )
              }
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-text-muted">Silence before commit</span>
            <input
              data-testid={`${testIdPrefix}-min-silence-ms`}
              className="rounded border border-border bg-bg px-2 py-1 text-text"
              type="text"
              inputMode="numeric"
              disabled={numericInputsDisabled}
              value={minSilenceMsDraft}
              onChange={(event) => setMinSilenceMsDraft(event.target.value)}
              onBlur={() =>
                commitNumericDraft(
                  minSilenceMsDraft,
                  values.minSilenceMs,
                  setMinSilenceMsDraft,
                  onMinSilenceMsChange
                )
              }
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-text-muted">Minimum utterance</span>
            <input
              data-testid={`${testIdPrefix}-min-utterance-secs`}
              className="rounded border border-border bg-bg px-2 py-1 text-text"
              type="text"
              inputMode="decimal"
              disabled={numericInputsDisabled}
              value={minUtteranceSecsDraft}
              onChange={(event) => setMinUtteranceSecsDraft(event.target.value)}
              onBlur={() =>
                commitNumericDraft(
                  minUtteranceSecsDraft,
                  values.minUtteranceSecs,
                  setMinUtteranceSecsDraft,
                  onMinUtteranceSecsChange
                )
              }
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-text-muted">Turn tail</span>
            <input
              data-testid={`${testIdPrefix}-turn-stop-secs`}
              className="rounded border border-border bg-bg px-2 py-1 text-text"
              type="text"
              inputMode="decimal"
              disabled={numericInputsDisabled}
              value={turnStopSecsDraft}
              onChange={(event) => setTurnStopSecsDraft(event.target.value)}
              onBlur={() =>
                commitNumericDraft(
                  turnStopSecsDraft,
                  values.turnStopSecs,
                  setTurnStopSecsDraft,
                  onTurnStopSecsChange
                )
              }
            />
          </label>
          {advancedFooterText ? (
            <div className="sm:col-span-2 text-text-muted">{advancedFooterText}</div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
