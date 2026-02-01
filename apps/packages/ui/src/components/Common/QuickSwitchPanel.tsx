import React from "react"
import { Skeleton, Empty } from "antd"
import { Book, Check } from "lucide-react"
import { cn } from "@/libs/utils"

export interface QuickSwitchOption {
  value: string
  label: string
  description?: string
}

export interface QuickSwitchPanelProps {
  /** Available options to switch between */
  options: QuickSwitchOption[]
  /** Currently selected value(s) - can be single or multiple */
  value: string | string[]
  /** Callback when selection changes */
  onChange: (value: string | string[]) => void
  /** Whether multiple selection is allowed */
  multiple?: boolean
  /** Whether the panel is loading */
  loading?: boolean
  /** Whether the panel is disabled */
  disabled?: boolean
  /** Placeholder text when no options */
  emptyText?: string
  /** Additional class names */
  className?: string
  /** Maximum height before scrolling */
  maxHeight?: number
}

/**
 * A quick-switch panel component for rapidly changing between options.
 * Designed for one-click activation with visual feedback.
 */
export function QuickSwitchPanel({
  options,
  value,
  onChange,
  multiple = false,
  loading = false,
  disabled = false,
  emptyText = "No options available",
  className,
  maxHeight = 200,
}: QuickSwitchPanelProps) {
  const selectedValues = Array.isArray(value) ? value : value ? [value] : []

  const handleSelect = (optionValue: string) => {
    if (disabled) return

    if (multiple) {
      const newValues = selectedValues.includes(optionValue)
        ? selectedValues.filter((v) => v !== optionValue)
        : [...selectedValues, optionValue]
      onChange(newValues)
    } else {
      onChange(optionValue)
    }
  }

  if (loading) {
    return (
      <div className={cn("space-y-2", className)}>
        <Skeleton.Button active block style={{ height: 44 }} />
        <Skeleton.Button active block style={{ height: 44 }} />
      </div>
    )
  }

  if (options.length === 0) {
    return (
      <div className={cn("py-4", className)}>
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={emptyText}
        />
      </div>
    )
  }

  return (
    <div
      className={cn("space-y-1 overflow-y-auto", className)}
      style={{ maxHeight }}
      role="listbox"
      aria-multiselectable={multiple}
    >
      {options.map((option) => {
        const isSelected = selectedValues.includes(option.value)
        return (
          <button
            key={option.value}
            type="button"
            role="option"
            aria-selected={isSelected}
            disabled={disabled}
            onClick={() => handleSelect(option.value)}
            className={cn(
              "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all",
              "hover:bg-surface2 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-1",
              "min-h-[44px]", // WCAG touch target
              isSelected
                ? "bg-primary/10 border border-primary/30 text-text"
                : "bg-surface border border-border text-text-muted hover:text-text",
              disabled && "opacity-50 cursor-not-allowed"
            )}
          >
            {/* Selection indicator */}
            <div
              className={cn(
                "w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0",
                isSelected
                  ? "border-primary bg-primary"
                  : "border-border bg-transparent"
              )}
            >
              {isSelected && <Check className="w-3 h-3 text-white" />}
            </div>

            {/* Icon */}
            <Book
              className={cn(
                "w-4 h-4 shrink-0",
                isSelected ? "text-primary" : "text-text-muted"
              )}
              aria-hidden="true"
            />

            {/* Label and description */}
            <div className="flex-1 min-w-0">
              <div
                className={cn(
                  "text-sm font-medium truncate",
                  isSelected ? "text-text" : "text-text"
                )}
              >
                {option.label}
              </div>
              {option.description && (
                <div className="text-xs text-text-muted truncate">
                  {option.description}
                </div>
              )}
            </div>
          </button>
        )
      })}
    </div>
  )
}

export default QuickSwitchPanel
