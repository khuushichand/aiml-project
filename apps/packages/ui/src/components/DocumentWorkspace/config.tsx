import React from "react"
import {
  Target,
  HelpCircle,
  Lightbulb,
  Wrench,
  Star,
  AlertTriangle,
  ArrowRight,
  FileText,
} from "lucide-react"
import type { AnnotationColor } from "./types"
import type { InsightCategory } from "@/hooks/document-workspace"

// theme-exempt: user annotation colors
export const HIGHLIGHT_COLORS: Array<{ key: AnnotationColor; label: string; color: string }> = [
  { key: "yellow", label: "Yellow", color: "#fef08a" },
  { key: "green", label: "Green", color: "#bbf7d0" },
  { key: "blue", label: "Blue", color: "#bfdbfe" },
  { key: "pink", label: "Pink", color: "#fbcfe8" }
]

export const TARGET_LANGUAGES = [
  { value: "English", label: "English" },
  { value: "Spanish", label: "Spanish" },
  { value: "French", label: "French" },
  { value: "German", label: "German" },
  { value: "Chinese", label: "Chinese" },
  { value: "Japanese", label: "Japanese" },
  { value: "Korean", label: "Korean" },
  { value: "Portuguese", label: "Portuguese" },
  { value: "Russian", label: "Russian" },
  { value: "Arabic", label: "Arabic" }
]

// theme-exempt: user annotation colors
export const COLOR_BADGES: Record<AnnotationColor, { bg: string; border: string; label: string }> = {
  yellow: { bg: "bg-yellow-100 dark:bg-yellow-900/30", border: "border-yellow-300 dark:border-yellow-700", label: "Yellow" },
  green: { bg: "bg-green-100 dark:bg-green-900/30", border: "border-green-300 dark:border-green-700", label: "Green" },
  blue: { bg: "bg-blue-100 dark:bg-blue-900/30", border: "border-blue-300 dark:border-blue-700", label: "Blue" },
  pink: { bg: "bg-pink-100 dark:bg-pink-900/30", border: "border-pink-300 dark:border-pink-700", label: "Pink" }
}

/**
 * Icon mapping for each insight category.
 */
export const CATEGORY_ICONS: Record<InsightCategory, React.ReactNode> = {
  research_gap: <Target className="h-4 w-4" />,
  research_question: <HelpCircle className="h-4 w-4" />,
  motivation: <Lightbulb className="h-4 w-4" />,
  methods: <Wrench className="h-4 w-4" />,
  key_findings: <Star className="h-4 w-4" />,
  limitations: <AlertTriangle className="h-4 w-4" />,
  future_work: <ArrowRight className="h-4 w-4" />,
  summary: <FileText className="h-4 w-4" />,
}
