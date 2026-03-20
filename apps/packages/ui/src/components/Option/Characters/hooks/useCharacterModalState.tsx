import React from "react"
import type { FormInstance } from "antd"
import type { GalleryCardDensity } from "../CharacterGalleryCard"

type TableDensity = "comfortable" | "compact" | "dense"
type AdvancedSectionKey = "promptControl" | "generationSettings" | "metadata"
type AdvancedSectionState = Record<AdvancedSectionKey, boolean>

const GALLERY_DENSITY_KEY = "characters-gallery-density"
const TABLE_DENSITY_KEY = "characters-table-density"

const DEFAULT_ADVANCED_SECTION_STATE: AdvancedSectionState = {
  promptControl: true,
  generationSettings: false,
  metadata: false
}

export interface UseCharacterModalStateDeps {
  /** i18n translator */
  t: (key: string, opts?: Record<string, any>) => string
  /** Current character list scope (active/deleted) */
  characterListScope?: "active" | "deleted"
}

export function useCharacterModalState(deps: UseCharacterModalStateDeps) {
  const { t } = deps

  // Create/edit drawer state
  const [open, setOpen] = React.useState(false)
  const [openEdit, setOpenEdit] = React.useState(false)
  const [editId, setEditId] = React.useState<string | null>(null)
  const [editVersion, setEditVersion] = React.useState<number | null>(null)

  // Conversations drawer state
  const [conversationsOpen, setConversationsOpen] = React.useState(false)
  const [conversationCharacter, setConversationCharacter] = React.useState<any | null>(null)

  // Preview popup state
  const [previewCharacter, setPreviewCharacter] = React.useState<any | null>(null)

  // Compare modal state
  const [compareModalOpen, setCompareModalOpen] = React.useState(false)
  const [compareCharacters, setCompareCharacters] = React.useState<[any, any] | null>(null)

  // Form dirty state
  const [createFormDirty, setCreateFormDirty] = React.useState(false)
  const [editFormDirty, setEditFormDirty] = React.useState(false)

  // System prompt example state
  const [showCreateSystemPromptExample, setShowCreateSystemPromptExample] = React.useState(false)
  const [showEditSystemPromptExample, setShowEditSystemPromptExample] = React.useState(false)

  // Preview toggle state
  const [showCreatePreview, setShowCreatePreview] = React.useState(true)
  const [showEditPreview, setShowEditPreview] = React.useState(true)

  // Advanced fields state
  const [showEditAdvanced, setShowEditAdvanced] = React.useState(false)
  const [showCreateAdvanced, setShowCreateAdvanced] = React.useState(false)
  const [createAdvancedSections, setCreateAdvancedSections] =
    React.useState<AdvancedSectionState>(() => ({
      ...DEFAULT_ADVANCED_SECTION_STATE
    }))
  const [editAdvancedSections, setEditAdvancedSections] =
    React.useState<AdvancedSectionState>(() => ({
      ...DEFAULT_ADVANCED_SECTION_STATE
    }))

  // View mode state
  const [viewMode, setViewMode] = React.useState<"table" | "gallery">(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("characters-view-mode")
      return saved === "gallery" ? "gallery" : "table"
    }
    return "table"
  })

  const [galleryDensity, setGalleryDensity] = React.useState<GalleryCardDensity>(
    () => {
      if (typeof window !== "undefined") {
        const saved = localStorage.getItem(GALLERY_DENSITY_KEY)
        return saved === "compact" ? "compact" : "rich"
      }
      return "rich"
    }
  )

  const [tableDensity, setTableDensity] = React.useState<TableDensity>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem(TABLE_DENSITY_KEY)
      if (
        saved === "dense" ||
        saved === "compact" ||
        saved === "comfortable"
      ) {
        return saved
      }
    }
    return "dense"
  })

  // Generation preview state
  const [generationPreviewOpen, setGenerationPreviewOpen] = React.useState(false)
  const [generationTargetForm, setGenerationTargetForm] = React.useState<
    "create" | "edit"
  >("create")

  // Export state
  const [exporting, setExporting] = React.useState<string | null>(null)

  // Refs
  const newButtonRef = React.useRef<HTMLButtonElement | null>(null)
  const lastEditTriggerRef = React.useRef<HTMLButtonElement | null>(null)
  const editWorldBooksInitializedRef = React.useRef(false)
  const autoOpenCreateHandledRef = React.useRef(false)

  // Persist view mode
  React.useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("characters-view-mode", viewMode)
    }
  }, [viewMode])

  // Force table view in deleted scope
  React.useEffect(() => {
    if (
      deps.characterListScope === "deleted" &&
      viewMode !== "table"
    ) {
      setViewMode("table")
    }
  }, [deps.characterListScope, viewMode])

  // Persist gallery density
  React.useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem(GALLERY_DENSITY_KEY, galleryDensity)
    }
  }, [galleryDensity])

  // Persist table density
  React.useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem(TABLE_DENSITY_KEY, tableDensity)
    }
  }, [tableDensity])

  const editCharacterNumericId = React.useMemo(() => {
    const parsed = Number(editId)
    return Number.isFinite(parsed) && parsed > 0 ? Math.trunc(parsed) : null
  }, [editId])

  const closeCompareModal = React.useCallback(() => {
    setCompareModalOpen(false)
    setCompareCharacters(null)
  }, [])

  const markModeDirty = React.useCallback((mode: "create" | "edit") => {
    if (mode === "create") {
      setCreateFormDirty(true)
    } else {
      setEditFormDirty(true)
    }
  }, [])

  return {
    // create/edit drawer
    open,
    setOpen,
    openEdit,
    setOpenEdit,
    editId,
    setEditId,
    editVersion,
    setEditVersion,
    editCharacterNumericId,
    // conversations drawer
    conversationsOpen,
    setConversationsOpen,
    conversationCharacter,
    setConversationCharacter,
    // preview popup
    previewCharacter,
    setPreviewCharacter,
    // compare modal
    compareModalOpen,
    setCompareModalOpen,
    compareCharacters,
    setCompareCharacters,
    closeCompareModal,
    // form dirty
    createFormDirty,
    setCreateFormDirty,
    editFormDirty,
    setEditFormDirty,
    markModeDirty,
    // system prompt examples
    showCreateSystemPromptExample,
    setShowCreateSystemPromptExample,
    showEditSystemPromptExample,
    setShowEditSystemPromptExample,
    // preview toggles
    showCreatePreview,
    setShowCreatePreview,
    showEditPreview,
    setShowEditPreview,
    // advanced fields
    showEditAdvanced,
    setShowEditAdvanced,
    showCreateAdvanced,
    setShowCreateAdvanced,
    createAdvancedSections,
    setCreateAdvancedSections,
    editAdvancedSections,
    setEditAdvancedSections,
    // view mode
    viewMode,
    setViewMode,
    galleryDensity,
    setGalleryDensity,
    tableDensity,
    setTableDensity,
    // generation preview
    generationPreviewOpen,
    setGenerationPreviewOpen,
    generationTargetForm,
    setGenerationTargetForm,
    // export
    exporting,
    setExporting,
    // refs
    newButtonRef,
    lastEditTriggerRef,
    editWorldBooksInitializedRef,
    autoOpenCreateHandledRef
  }
}
