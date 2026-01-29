import React from "react"
import { Card } from "antd"
import { cn } from "@/libs/utils"

interface LandingCardProps {
  icon: React.ReactNode
  title: string
  description: string
  onClick: () => void
}

/**
 * LandingCard
 *
 * A clickable card for the landing hub that presents a primary action.
 * Used in the 2x2 grid layout on the landing page.
 */
export const LandingCard: React.FC<LandingCardProps> = ({
  icon,
  title,
  description,
  onClick
}) => {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault()
      onClick()
    }
  }

  return (
    <Card
      hoverable
      className={cn(
        "group cursor-pointer transition-all",
        "hover:border-primary hover:shadow-md"
      )}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="button"
      aria-label={title}
    >
      <div className="flex flex-col items-start text-left gap-3">
        <div
          className={cn(
            "p-3 rounded-lg",
            "bg-primary/10 text-primary",
            "group-hover:bg-primary group-hover:text-white transition-colors"
          )}
        >
          {icon}
        </div>
        <h3 className="text-lg font-semibold text-text">{title}</h3>
        <p className="text-sm text-textMuted">{description}</p>
      </div>
    </Card>
  )
}
