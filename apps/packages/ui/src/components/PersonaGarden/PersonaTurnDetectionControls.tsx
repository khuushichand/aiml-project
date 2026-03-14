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
  const numericInputsDisabled =
    advancedInputsDisabled ?? (disabled || !values.autoCommitEnabled)

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
              type="number"
              min={0}
              max={1}
              step={0.01}
              disabled={numericInputsDisabled}
              value={values.vadThreshold}
              onChange={(event) => onVadThresholdChange(Number(event.target.value))}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-text-muted">Silence before commit</span>
            <input
              data-testid={`${testIdPrefix}-min-silence-ms`}
              className="rounded border border-border bg-bg px-2 py-1 text-text"
              type="number"
              min={50}
              max={10000}
              step={10}
              disabled={numericInputsDisabled}
              value={values.minSilenceMs}
              onChange={(event) => onMinSilenceMsChange(Number(event.target.value))}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-text-muted">Minimum utterance</span>
            <input
              data-testid={`${testIdPrefix}-min-utterance-secs`}
              className="rounded border border-border bg-bg px-2 py-1 text-text"
              type="number"
              min={0}
              max={10}
              step={0.01}
              disabled={numericInputsDisabled}
              value={values.minUtteranceSecs}
              onChange={(event) => onMinUtteranceSecsChange(Number(event.target.value))}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-text-muted">Turn tail</span>
            <input
              data-testid={`${testIdPrefix}-turn-stop-secs`}
              className="rounded border border-border bg-bg px-2 py-1 text-text"
              type="number"
              min={0.05}
              max={10}
              step={0.01}
              disabled={numericInputsDisabled}
              value={values.turnStopSecs}
              onChange={(event) => onTurnStopSecsChange(Number(event.target.value))}
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
