import React from "react"

interface PolicyStatusBadgesProps {
  enabled?: boolean
  inputAction?: string
  outputAction?: string
  ruleCount?: number
  compact?: boolean
}

const badgeColor = (active: boolean) =>
  active
    ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
    : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"

const actionColor = (action: string) => {
  switch (action) {
    case "block": return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
    case "redact": return "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300"
    case "warn": return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300"
    default: return "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300"
  }
}

export const PolicyStatusBadges: React.FC<PolicyStatusBadgesProps> = ({
  enabled = false,
  inputAction = "pass",
  outputAction = "pass",
  ruleCount = 0,
  compact = false
}) => {
  const badgeClass = compact
    ? "inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium"
    : "inline-flex items-center px-2 py-1 rounded-md text-xs font-medium"

  return (
    <div className="flex flex-wrap gap-1.5">
      <span className={`${badgeClass} ${badgeColor(enabled)}`}>
        {enabled ? "Enabled" : "Disabled"}
      </span>
      <span className={`${badgeClass} ${actionColor(inputAction)}`}>
        Input: {inputAction}
      </span>
      <span className={`${badgeClass} ${actionColor(outputAction)}`}>
        Output: {outputAction}
      </span>
      <span className={`${badgeClass} bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300`}>
        {ruleCount} rules
      </span>
    </div>
  )
}
