import React from "react"
import { Card } from "antd"
import { CheckCircle } from "lucide-react"
import { useTranslation } from "react-i18next"
import * as LucideIcons from "lucide-react"
import type { WorkflowDefinition, WorkflowId } from "@/types/workflows"
import { cn } from "@/libs/utils"

interface WorkflowCardProps {
  workflow: WorkflowDefinition
  onSelect: (workflowId: WorkflowId) => void
  isCompleted?: boolean
  disabled?: boolean
}

/**
 * WorkflowCard
 *
 * A clickable card that represents a single workflow option.
 * Used in the landing page to let users select what they want to do.
 */
export const WorkflowCard: React.FC<WorkflowCardProps> = ({
  workflow,
  onSelect,
  isCompleted = false,
  disabled = false
}) => {
  const { t } = useTranslation(["workflows"])

  // Dynamically get the icon component
  const IconComponent = (LucideIcons as unknown as Record<string, React.FC<{ className?: string }>>)[
    workflow.icon
  ] || LucideIcons.HelpCircle

  const handleClick = () => {
    if (!disabled) {
      onSelect(workflow.id)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.key === "Enter" || e.key === " ") && !disabled) {
      e.preventDefault()
      onSelect(workflow.id)
    }
  }

  return (
    <Card
      hoverable={!disabled}
      className={cn(
        "group cursor-pointer transition-all relative",
        "border border-border !bg-surface text-text",
        "hover:border-primary hover:shadow-md",
        disabled && "opacity-50 cursor-not-allowed hover:border-border hover:shadow-none",
        isCompleted && "border-success/50"
      )}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      tabIndex={disabled ? -1 : 0}
      role="button"
      aria-disabled={disabled}
      aria-label={t(workflow.labelToken, workflow.id)}
    >
      {/* Completed indicator */}
      {isCompleted && (
        <div className="absolute top-2 right-2">
          <CheckCircle className="h-4 w-4 text-success" />
        </div>
      )}

      <div className="flex flex-col items-start text-left gap-3">
        {/* Icon */}
        <div
          className={cn(
            "p-3 rounded-lg",
            "bg-primary/10 text-primary",
            !disabled &&
              "group-hover:bg-primary group-hover:text-white transition-colors"
          )}
        >
          <IconComponent className="h-6 w-6" />
        </div>

        {/* Title */}
        <h3 className="text-lg font-semibold text-text">
          {t(workflow.labelToken, workflow.id)}
        </h3>

        {/* Description */}
        <p className="text-sm text-textMuted line-clamp-2">
          {t(workflow.descriptionToken, "")}
        </p>
      </div>
    </Card>
  )
}
