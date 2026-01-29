/**
 * Small button for generating a single field with AI
 */

import React from "react"
import { Button, Tooltip, Spin } from "antd"
import { Sparkles } from "lucide-react"
import { useTranslation } from "react-i18next"

interface GenerateFieldButtonProps {
  /** Whether this field is currently being generated */
  isGenerating: boolean
  /** Whether any generation is in progress (to disable all buttons) */
  disabled?: boolean
  /** Callback when user clicks generate */
  onClick: () => void
  /** Tooltip text override */
  tooltip?: string
}

export const GenerateFieldButton: React.FC<GenerateFieldButtonProps> = ({
  isGenerating,
  disabled = false,
  onClick,
  tooltip
}) => {
  const { t } = useTranslation(["settings", "common"])

  const tooltipText =
    tooltip ||
    t("settings:manageCharacters.generate.fieldTooltip", {
      defaultValue: "Generate with AI"
    })

  return (
    <Tooltip title={tooltipText}>
      <Button
        type="text"
        size="small"
        disabled={disabled || isGenerating}
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()
          onClick()
        }}
        className="inline-flex items-center justify-center h-6 w-6 p-0.5 ml-1.5 rounded text-primary/70 hover:text-primary hover:bg-primary/10 disabled:opacity-40 transition-colors"
        aria-label={tooltipText}>
        {isGenerating ? (
          <Spin size="small" className="[&_.ant-spin-dot]:h-3 [&_.ant-spin-dot]:w-3" />
        ) : (
          <Sparkles className="w-4 h-4" />
        )}
      </Button>
    </Tooltip>
  )
}
