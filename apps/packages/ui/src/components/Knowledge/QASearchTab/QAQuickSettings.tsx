import React from "react"
import { Select } from "antd"
import { useTranslation } from "react-i18next"
import type { RagPresetName, RagSource } from "@/services/rag/unified-rag"
import { SourceChips } from "../SearchTab/SourceChips"

type QAQuickSettingsProps = {
  preset: RagPresetName
  onPresetChange: (preset: RagPresetName) => void
  strategy: "standard" | "agentic"
  onStrategyChange: (strategy: "standard" | "agentic") => void
  selectedSources: RagSource[]
  onSourcesChange: (sources: RagSource[]) => void
  disabled?: boolean
}

/**
 * Quick settings row for QA Search tab.
 * Shows preset dropdown, strategy selector, and source chips inline.
 */
export const QAQuickSettings: React.FC<QAQuickSettingsProps> = ({
  preset,
  onPresetChange,
  strategy,
  onStrategyChange,
  selectedSources,
  onSourcesChange,
  disabled = false
}) => {
  const { t } = useTranslation(["sidepanel"])

  const presetOptions = React.useMemo(
    () => [
      { label: t("sidepanel:rag.presets.fast", "Fast"), value: "fast" as const },
      {
        label: t("sidepanel:rag.presets.balanced", "Balanced"),
        value: "balanced" as const
      },
      {
        label: t("sidepanel:rag.presets.thorough", "Thorough"),
        value: "thorough" as const
      },
      {
        label: t("sidepanel:rag.presets.custom", "Custom"),
        value: "custom" as const
      }
    ],
    [t]
  )

  const strategyOptions = React.useMemo(
    () => [
      {
        label: t("sidepanel:qaSearch.strategy.standard", "Standard"),
        value: "standard" as const
      },
      {
        label: t("sidepanel:qaSearch.strategy.agentic", "Agentic"),
        value: "agentic" as const
      }
    ],
    [t]
  )

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <Select
          value={preset}
          onChange={onPresetChange}
          options={presetOptions}
          size="small"
          className="w-28 flex-shrink-0"
          disabled={disabled}
        />
        <Select
          value={strategy}
          onChange={onStrategyChange}
          options={strategyOptions}
          size="small"
          className="w-28 flex-shrink-0"
          disabled={disabled}
        />
      </div>
      <SourceChips
        selectedSources={selectedSources}
        onSourcesChange={onSourcesChange}
        disabled={disabled}
      />
    </div>
  )
}
