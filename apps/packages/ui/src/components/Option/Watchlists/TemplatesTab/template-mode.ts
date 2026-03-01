import type { WatchlistTemplateCreate } from "@/types/watchlists"

export type TemplateAuthoringMode = "basic" | "advanced"
export type TemplateEditorActiveTab = "visual" | "editor" | "preview" | "docs"

interface TemplateAdvancedContextInput {
  isEditing: boolean
  selectedVersion?: number
  activeTab: TemplateEditorActiveTab
  hasVersionDrift: boolean
  validationErrorCount: number
}

interface TemplateModeChangeInput {
  currentMode: TemplateAuthoringMode
  nextMode: TemplateAuthoringMode
  hasAdvancedContext: boolean
}

interface TemplateFormSaveValues {
  name: string
  description?: string | null
  content: string
  format: "md" | "html"
}

export const hasTemplateAdvancedContext = ({
  isEditing,
  selectedVersion,
  activeTab,
  hasVersionDrift,
  validationErrorCount
}: TemplateAdvancedContextInput): boolean => {
  if (!isEditing) return false
  return (
    selectedVersion !== undefined ||
    activeTab === "docs" ||
    hasVersionDrift ||
    validationErrorCount > 0
  )
}

export const shouldWarnOnTemplateModeChange = ({
  currentMode,
  nextMode,
  hasAdvancedContext
}: TemplateModeChangeInput): boolean => {
  if (currentMode === nextMode) return false
  return currentMode === "advanced" && nextMode === "basic" && hasAdvancedContext
}

export const buildTemplateSavePayload = (
  values: TemplateFormSaveValues,
  isEditing: boolean
): WatchlistTemplateCreate => {
  return {
    name: values.name,
    description: values.description || null,
    content: values.content,
    format: values.format,
    overwrite: isEditing
  }
}
