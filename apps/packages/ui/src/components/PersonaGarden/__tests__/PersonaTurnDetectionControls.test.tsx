import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import {
  PersonaTurnDetectionControls,
  type PersonaTurnDetectionValues
} from "../PersonaTurnDetectionControls"

const defaultValues = (): PersonaTurnDetectionValues => ({
  autoCommitEnabled: true,
  vadThreshold: 0.5,
  minSilenceMs: 250,
  turnStopSecs: 0.2,
  minUtteranceSecs: 0.4
})

describe("PersonaTurnDetectionControls", () => {
  it("preserves incomplete decimal edits until blur and then commits parsed values", () => {
    const onVadThresholdChange = vi.fn()
    const onTurnStopSecsChange = vi.fn()

    const TestHarness: React.FC = () => {
      const [values, setValues] = React.useState(defaultValues)
      return (
        <PersonaTurnDetectionControls
          title="Turn detection"
          helperText="Tune auto-commit behavior"
          testIdPrefix="test-vad"
          autoCommitLabel="Enable auto-commit"
          currentPreset="balanced"
          values={values}
          onAutoCommitEnabledChange={(next) =>
            setValues((current) => ({ ...current, autoCommitEnabled: next }))
          }
          onPresetChange={vi.fn()}
          onVadThresholdChange={(next) => {
            onVadThresholdChange(next)
            setValues((current) => ({ ...current, vadThreshold: next }))
          }}
          onMinSilenceMsChange={(next) =>
            setValues((current) => ({ ...current, minSilenceMs: next }))
          }
          onTurnStopSecsChange={(next) => {
            onTurnStopSecsChange(next)
            setValues((current) => ({ ...current, turnStopSecs: next }))
          }}
          onMinUtteranceSecsChange={(next) =>
            setValues((current) => ({ ...current, minUtteranceSecs: next }))
          }
        />
      )
    }

    render(<TestHarness />)

    fireEvent.click(screen.getByTestId("test-vad-advanced-toggle"))

    const thresholdInput = screen.getByTestId("test-vad-threshold")
    fireEvent.change(thresholdInput, { target: { value: "0." } })

    expect(onVadThresholdChange).not.toHaveBeenCalled()
    expect(thresholdInput).toHaveDisplayValue("0.")

    fireEvent.blur(thresholdInput)

    expect(onVadThresholdChange).toHaveBeenCalledWith(0)
    expect(thresholdInput).toHaveDisplayValue("0")

    const turnStopInput = screen.getByTestId("test-vad-turn-stop-secs")
    fireEvent.change(turnStopInput, { target: { value: "0." } })

    expect(onTurnStopSecsChange).not.toHaveBeenCalled()
    expect(turnStopInput).toHaveDisplayValue("0.")

    fireEvent.blur(turnStopInput)

    expect(onTurnStopSecsChange).toHaveBeenCalledWith(0)
    expect(turnStopInput).toHaveDisplayValue("0")
  })
})
