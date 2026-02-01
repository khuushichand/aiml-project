import React from "react"
import { Tooltip } from "antd"
import { HelpCircle } from "lucide-react"
import { cn } from "@/libs/utils"

export interface LabelWithHelpProps {
  /** The label text to display */
  label: React.ReactNode
  /** Help text shown in tooltip on hover */
  help?: string
  /** Whether the field is required (shows asterisk) */
  required?: boolean
  /** Additional class names */
  className?: string
  /** ID for aria-describedby linking */
  helpId?: string
}

/**
 * A form label component with an optional help tooltip icon.
 * Improves accessibility and user understanding by providing
 * contextual help without cluttering the UI.
 */
export function LabelWithHelp({
  label,
  help,
  required,
  className,
  helpId,
}: LabelWithHelpProps) {
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <span>
        {label}
        {required && <span className="text-danger ml-0.5">*</span>}
      </span>
      {help && (
        <Tooltip title={help}>
          <button
            type="button"
            className="inline-flex items-center justify-center text-text-muted hover:text-text cursor-help focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-1 rounded-full"
            aria-label="Help"
            id={helpId}
            tabIndex={-1}
          >
            <HelpCircle className="size-3.5" />
          </button>
        </Tooltip>
      )}
    </span>
  )
}

export default LabelWithHelp
