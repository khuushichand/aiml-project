import React, { useState } from "react"
import { X } from "lucide-react"
import { useTranslation } from "react-i18next"
import type { DiscoSkillComment } from "@/types/disco-skills"
import { DISCO_CATEGORY_COLORS } from "@/constants/disco-skills"

interface DiscoSkillAnnotationProps {
  /** The skill comment to display */
  comment: DiscoSkillComment
  /** Optional callback when dismiss button is clicked */
  onDismiss?: () => void
  /** Whether to show the dismiss button */
  showDismiss?: boolean
  /** Whether to animate the appearance */
  animate?: boolean
}

/**
 * Displays a Disco Elysium-style skill annotation below a chat message.
 *
 * Visual design inspired by the game's skill check notifications:
 * - Left border in skill category color
 * - Skill name in small-caps
 * - Passive/Active badge
 * - Italic comment text
 */
export const DiscoSkillAnnotation: React.FC<DiscoSkillAnnotationProps> = ({
  comment,
  onDismiss,
  showDismiss = true,
  animate = true
}) => {
  const { t } = useTranslation("playground")
  const [isVisible, setIsVisible] = useState(true)

  if (!isVisible) return null

  const handleDismiss = () => {
    setIsVisible(false)
    onDismiss?.()
  }

  // Get the category color for styling
  const categoryColor =
    DISCO_CATEGORY_COLORS[comment.category] || comment.color

  // Background color with low opacity based on category
  const bgColorMap: Record<string, string> = {
    intellect: "bg-blue-50 dark:bg-blue-950/30",
    psyche: "bg-purple-50 dark:bg-purple-950/30",
    physique: "bg-red-50 dark:bg-red-950/30",
    motorics: "bg-yellow-50 dark:bg-yellow-950/30"
  }
  const bgColor = bgColorMap[comment.category] || "bg-surface2/50"

  const badgeLabel = t("discoSkills.passive", "Passive")

  return (
    <div
      className={`
        relative mt-3 rounded-lg overflow-hidden
        ${bgColor}
        border border-border/50
        ${animate ? "animate-in fade-in slide-in-from-bottom-2 duration-300" : ""}
      `}
      style={{
        borderLeftWidth: "4px",
        borderLeftColor: categoryColor
      }}
      role="complementary"
      aria-label={t("discoSkills.annotation", "Skill annotation from {{skill}}", {
        skill: comment.skillName
      })}
    >
      <div className="px-3 py-2">
        {/* Header row with skill name and badge */}
        <div className="flex items-center justify-between gap-2 mb-1">
          <div className="flex items-center gap-2">
            <span
              className="text-xs font-semibold tracking-wide uppercase"
              style={{ color: categoryColor }}
            >
              {comment.skillName}
            </span>
            <span
              className="
                inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium
                bg-surface2/80 text-text-muted
              "
            >
              {badgeLabel}
            </span>
          </div>

          {showDismiss && (
            <button
              type="button"
              onClick={handleDismiss}
              className="
                p-0.5 rounded-sm text-text-subtle
                hover:text-text hover:bg-surface2
                transition-colors
              "
              aria-label={t("discoSkills.dismiss", "Dismiss")}
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Comment text */}
        <p className="text-sm text-text italic leading-relaxed">
          {comment.comment}
        </p>
      </div>
    </div>
  )
}

export default DiscoSkillAnnotation
