import { useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Button,
  Form,
  Input,
  Modal,
  Select,
  InputNumber
} from "antd"
import type { InputRef, FormInstance } from "antd"
import React from "react"
import { fetchChatModels } from "@/services/tldw-server"
import { ChevronDown, ChevronUp } from "lucide-react"
import { CharacterPreview } from "./CharacterPreview"
import { AvatarField, extractAvatarValues } from "./AvatarField"
import {
  useCharacterFiltering,
  useCharacterInlineEdit,
  useCharacterQuickChat,
  useCharacterVersionHistory,
  useCharacterImportQueue,
  useCharacterTagManagement,
  useCharacterModalState,
  useCharacterData,
  useCharacterCrud,
  useCharacterBulkOps
} from "./hooks"
import { GenerateFieldButton } from "./GenerateFieldButton"
import { useCharacterGeneration } from "@/hooks/useCharacterGeneration"
import { useFormDraft } from "@/hooks/useFormDraft"
import { useCharacterShortcuts } from "@/hooks/useCharacterShortcuts"
import { CHARACTER_TEMPLATES, type CharacterTemplate } from "@/data/character-templates"
import {
  CHARACTER_PROMPT_PRESETS,
  DEFAULT_CHARACTER_PROMPT_PRESET
} from "@/data/character-prompt-presets"
import type { GeneratedCharacter, CharacterField } from "@/services/character-generation"
import { useStorage } from "@plasmohq/storage/hook"
import { useTranslation } from "react-i18next"
import { useConfirmDanger } from "@/components/Common/confirm-danger"
import { useNavigate } from "react-router-dom"
import { useSelectedCharacter } from "@/hooks/useSelectedCharacter"
import { useAntdNotification } from "@/hooks/useAntdNotification"
import {
  DEFAULT_CHARACTER_STORAGE_KEY,
  defaultCharacterStorage,
  resolveCharacterSelectionId
} from "@/utils/default-character-preference"
import {
  MAX_NAME_LENGTH,
  TEMPLATE_CHOOSER_SEEN_KEY,
  SYSTEM_PROMPT_EXAMPLE,
  getCharacterVisibleTags,
  normalizeCharacterFolderId,
  hasAdvancedData,
  parseCharacterImportPreview,
  type AdvancedSectionKey,
  type CharacterWorldBookOption,
  type CharacterFolderOption,
} from "./utils"
export { withCharacterNameInLabel } from "./utils"

// --- Extracted sub-components ---
import { CharacterListToolbar } from "./CharacterListToolbar"
import { CharacterListContent } from "./CharacterListContent"
import { CharacterDialogs } from "./CharacterDialogs"

type CharactersManagerProps = {
  forwardedNewButtonRef?: React.RefObject<HTMLButtonElement | null>
  autoOpenCreate?: boolean
}

type SharedCharacterFormProps = {
  form: FormInstance
  mode: "create" | "edit"
  initialValues?: Record<string, any>
  worldBookFieldContext: {
    options: CharacterWorldBookOption[]
    loading: boolean
    editCharacterNumericId: number | null
  }
  isSubmitting: boolean
  submitButtonClassName?: string
  submitPendingLabel: string
  submitIdleLabel: string
  showPreview: boolean
  onTogglePreview: () => void
  onValuesChange: (allValues: Record<string, any>) => void
  onFinish: (values: Record<string, any>) => void
}

export const CharactersManager: React.FC<CharactersManagerProps> = ({
  forwardedNewButtonRef,
  autoOpenCreate = false
}) => {
  const { t } = useTranslation(["settings", "common"])
  const promptPresetOptions = React.useMemo(
    () =>
      CHARACTER_PROMPT_PRESETS.map((preset) => ({
        value: preset.id,
        label: t(
          `settings:manageCharacters.promptPresets.${preset.id}.label`,
          { defaultValue: preset.label }
        )
      })),
    [t]
  )
  const qc = useQueryClient()
  const navigate = useNavigate()
  const notification = useAntdNotification()
  const confirmDanger = useConfirmDanger()
  const [createForm] = Form.useForm()
  const [editForm] = Form.useForm()
  const [, setSelectedCharacter] = useSelectedCharacter<any>(null)
  const [defaultCharacterSelection, setDefaultCharacterSelection] =
    useStorage<any | null>(
      {
        key: DEFAULT_CHARACTER_STORAGE_KEY,
        instance: defaultCharacterStorage
      },
      null
    )
  const createNameRef = React.useRef<InputRef>(null)
  const editNameRef = React.useRef<InputRef>(null)

  // --- Extracted hooks ---
  const filtering = useCharacterFiltering({ t })
  const {
    searchInputRef,
    searchTerm, setSearchTerm,
    debouncedSearchTerm,
    filterTags, setFilterTags,
    folderFilterId, setFolderFilterId,
    matchAllTags, setMatchAllTags,
    creatorFilter, setCreatorFilter,
    createdFromDate, setCreatedFromDate,
    createdToDate, setCreatedToDate,
    updatedFromDate, setUpdatedFromDate,
    updatedToDate, setUpdatedToDate,
    hasConversationsOnly, setHasConversationsOnly,
    favoritesOnly, setFavoritesOnly,
    advancedFiltersOpen, setAdvancedFiltersOpen,
    characterListScope, setCharacterListScope,
    sortColumn, setSortColumn,
    sortOrder, setSortOrder,
    currentPage, setCurrentPage,
    pageSize, setPageSize,
    hasFilters,
    activeAdvancedFilterCount,
    clearFilters
  } = filtering

  const modalState = useCharacterModalState({ t, characterListScope })
  const {
    open, setOpen,
    openEdit, setOpenEdit,
    editId, setEditId,
    editVersion, setEditVersion,
    editCharacterNumericId,
    conversationsOpen, setConversationsOpen,
    conversationCharacter, setConversationCharacter,
    previewCharacter, setPreviewCharacter,
    compareModalOpen, setCompareModalOpen,
    compareCharacters, setCompareCharacters,
    closeCompareModal,
    createFormDirty, setCreateFormDirty,
    editFormDirty, setEditFormDirty,
    markModeDirty,
    showCreateSystemPromptExample, setShowCreateSystemPromptExample,
    showEditSystemPromptExample, setShowEditSystemPromptExample,
    showCreatePreview, setShowCreatePreview,
    showEditPreview, setShowEditPreview,
    showEditAdvanced, setShowEditAdvanced,
    showCreateAdvanced, setShowCreateAdvanced,
    createAdvancedSections, setCreateAdvancedSections,
    editAdvancedSections, setEditAdvancedSections,
    viewMode, setViewMode,
    galleryDensity, setGalleryDensity,
    tableDensity, setTableDensity,
    generationPreviewOpen, setGenerationPreviewOpen,
    generationTargetForm, setGenerationTargetForm,
    exporting, setExporting,
    newButtonRef, lastEditTriggerRef,
    editWorldBooksInitializedRef, autoOpenCreateHandledRef
  } = modalState

  const importQueue = useCharacterImportQueue({
    t,
    notification,
    qc,
    parseCharacterImportPreview
  })
  const {
    importButtonContainerRef,
    importing,
    importPreviewOpen, setImportPreviewOpen,
    importPreviewLoading,
    importPreviewItems,
    importPreviewProcessing,
    importQueueState, dispatchImportQueue,
    importablePreviewItems,
    importQueueItemsById,
    importQueueSummary,
    retryableFailedPreviewItems,
    importPreviewHasSuccessfulCompletion,
    isImportBusy,
    importCharacterFile,
    runBatchImport,
    openImportPreviewForBatch,
    handleConfirmImportPreview,
    handleRetryFailedImportPreview,
    handleImportUpload,
    handleImportDragEnter,
    handleImportDragLeave,
    handleImportDragOver,
    handleImportDrop,
    triggerImportPicker,
    resetImportPreview,
    getImportQueueStateLabel,
    getImportQueueStateColor
  } = importQueue

  // crossNavigationContext, previewCharacterId, selectedCharacterIds moved to useCharacterData / useCharacterBulkOps

  // Character generation state
  const {
    isGenerating,
    generatingField,
    error: generationError,
    generateFullCharacter,
    generateField,
    cancel: cancelGeneration,
    clearError: clearGenerationError
  } = useCharacterGeneration()
  const [selectedGenModel] = useStorage<string | null>("characterGenModel", null)
  const [selectedChatModel] = useStorage<string | null>("selectedModel", null)
  // serverQueryRolloutFlag moved to useCharacterData

  // Fetch models to get provider for selected model
  const { data: generationModels } = useQuery<Array<{ model: string; provider?: string }>>({
    queryKey: ["getModelsForFieldGeneration"],
    queryFn: () => fetchChatModels({ returnEmpty: true }),
    staleTime: 5 * 60 * 1000 // 5 minutes
  })

  // Get the provider for the selected generation model
  const selectedGenModelProvider = React.useMemo(() => {
    if (!selectedGenModel || !generationModels) return undefined
    const modelData = generationModels.find((m) => m.model === selectedGenModel)
    return modelData?.provider
  }, [selectedGenModel, generationModels])

  const quickChatModelOptions = React.useMemo(
    () =>
      (generationModels || [])
        .filter((model) => typeof model.model === "string" && model.model.trim())
        .map((model) => {
          const modelName = model.model.trim()
          return {
            value: modelName,
            label: model.provider
              ? `${modelName} (${model.provider})`
              : modelName
          }
        }),
    [generationModels]
  )

  // Quick chat model override kept here since activeQuickChatModel depends on it
  const [quickChatModelOverride, setQuickChatModelOverride] = React.useState<string | null>(null)

  const activeQuickChatModel =
    quickChatModelOverride ||
    selectedChatModel ||
    quickChatModelOptions[0]?.value ||
    null

  const quickChat = useCharacterQuickChat({ t, activeQuickChatModel })
  const {
    quickChatCharacter, setQuickChatCharacter,
    quickChatMessages, setQuickChatMessages,
    quickChatDraft, setQuickChatDraft,
    quickChatSessionId, setQuickChatSessionId,
    quickChatSending,
    quickChatError, setQuickChatError,
    openQuickChat,
    closeQuickChat,
    sendQuickChatMessage,
    handlePromoteQuickChat
  } = quickChat

  const versionHistory = useCharacterVersionHistory({ t, notification, qc, confirmDanger })
  const {
    versionHistoryOpen, setVersionHistoryOpen,
    versionHistoryCharacter, setVersionHistoryCharacter,
    versionHistoryCharacterId,
    versionHistoryCharacterName,
    versionFrom, setVersionFrom,
    versionTo, setVersionTo,
    versionRevertTarget, setVersionRevertTarget,
    versionHistoryItems,
    versionHistoryLoading,
    versionHistoryFetching,
    versionSelectOptions,
    versionDiffResponse,
    versionDiffLoading,
    versionDiffFetching,
    revertingCharacterVersion,
    openVersionHistory,
    revertCharacterVersion
  } = versionHistory

  const tagManagement = useCharacterTagManagement({ t, notification, qc, confirmDanger })
  const {
    tagManagerOpen, setTagManagerOpen,
    tagManagerLoading,
    tagManagerSubmitting,
    tagManagerCharacters,
    tagManagerOperation, setTagManagerOperation,
    tagManagerSourceTag, setTagManagerSourceTag,
    tagManagerTargetTag, setTagManagerTargetTag,
    bulkTagModalOpen, setBulkTagModalOpen,
    bulkTagsToAdd, setBulkTagsToAdd,
    bulkOperationLoading, setBulkOperationLoading,
    tagManagerTagUsageData,
    openTagManager,
    closeTagManager,
    handleApplyTagManagerOperation,
    handleBulkAddTags
  } = tagManagement

  const defaultCharacterId = React.useMemo(
    () => resolveCharacterSelectionId(defaultCharacterSelection),
    [defaultCharacterSelection]
  )

  const [generationPreviewData, setGenerationPreviewData] = React.useState<GeneratedCharacter | null>(null)
  const [generationPreviewField, setGenerationPreviewField] = React.useState<string | null>(null)

  // Template selection state
  const [hasSeenTemplateChooser, setHasSeenTemplateChooser] = React.useState(() => {
    if (typeof window === "undefined") return false
    return localStorage.getItem(TEMPLATE_CHOOSER_SEEN_KEY) === "true"
  })
  const [showTemplates, setShowTemplates] = React.useState(() => {
    if (typeof window === "undefined") return true
    return localStorage.getItem(TEMPLATE_CHOOSER_SEEN_KEY) !== "true"
  })

  // Form draft autosave (H4)
  const {
    hasDraft: hasCreateDraft,
    draftData: createDraftData,
    saveDraft: saveCreateDraft,
    clearDraft: clearCreateDraft,
    applyDraft: applyCreateDraft,
    dismissDraft: dismissCreateDraft,
    lastSaved: createLastSaved
  } = useFormDraft<Record<string, any>>({
    storageKey: 'character-form-draft-create',
    formType: 'create',
    autoSaveInterval: 30000
  })

  const {
    hasDraft: hasEditDraft,
    draftData: editDraftData,
    saveDraft: saveEditDraft,
    clearDraft: clearEditDraft,
    applyDraft: applyEditDraft,
    dismissDraft: dismissEditDraft,
    lastSaved: editLastSaved
  } = useFormDraft<Record<string, any>>({
    storageKey: 'character-form-draft-edit',
    formType: 'edit',
    editId: editId ?? undefined,
    autoSaveInterval: 30000
  })

  const markTemplateChooserSeen = React.useCallback(() => {
    setHasSeenTemplateChooser(true)
    if (typeof window !== "undefined") {
      localStorage.setItem(TEMPLATE_CHOOSER_SEEN_KEY, "true")
    }
  }, [])

  const openCreateModal = React.useCallback(() => {
    if (!hasSeenTemplateChooser) {
      setShowTemplates(true)
      markTemplateChooserSeen()
    }
    setOpen(true)
  }, [hasSeenTemplateChooser, markTemplateChooserSeen])

  const applyTemplateToCreateForm = React.useCallback(
    (template: CharacterTemplate) => {
      createForm.setFieldsValue({
        name: template.name,
        description: template.description,
        system_prompt: template.system_prompt,
        greeting: template.greeting,
        tags: template.tags,
        folder_id: undefined
      })
      setCreateFormDirty(true)
      setShowTemplates(false)
      markTemplateChooserSeen()
      setOpen(true)
      notification.info({
        message: t("settings:manageCharacters.templates.applied", {
          defaultValue: "Template applied"
        }),
        description: t("settings:manageCharacters.templates.appliedDesc", {
          defaultValue: "You can customize all fields before saving."
        })
      })
    },
    [createForm, markTemplateChooserSeen, notification, t]
  )

  const applySystemPromptExample = React.useCallback(
    (mode: "create" | "edit") => {
      const targetForm = mode === "create" ? createForm : editForm
      const currentValue = String(targetForm.getFieldValue("system_prompt") ?? "").trim()
      const shouldConfirmOverwrite =
        currentValue.length > 0 && currentValue !== SYSTEM_PROMPT_EXAMPLE

      const apply = () => {
        targetForm.setFieldValue("system_prompt", SYSTEM_PROMPT_EXAMPLE)
        if (mode === "create") {
          setCreateFormDirty(true)
          setShowCreateSystemPromptExample(false)
        } else {
          setEditFormDirty(true)
          setShowEditSystemPromptExample(false)
        }
      }

      if (!shouldConfirmOverwrite) {
        apply()
        return
      }

      Modal.confirm({
        title: t("settings:manageCharacters.form.systemPrompt.exampleOverwrite.title", {
          defaultValue: "Replace current system prompt?"
        }),
        content: t("settings:manageCharacters.form.systemPrompt.exampleOverwrite.content", {
          defaultValue:
            "This will replace your current system prompt with the Writing Assistant example."
        }),
        okText: t("settings:manageCharacters.form.systemPrompt.exampleOverwrite.confirm", {
          defaultValue: "Replace"
        }),
        cancelText: t("common:cancel", { defaultValue: "Cancel" }),
        onOk: apply
      })
    },
    [createForm, editForm, t]
  )

  // Keyboard shortcuts (H1)
  const modalOpen =
    open ||
    openEdit ||
    conversationsOpen ||
    generationPreviewOpen ||
    Boolean(quickChatCharacter)
  useCharacterShortcuts({
    modalOpen,
    onNewCharacter: () => {
      if (!modalOpen) openCreateModal()
    },
    onFocusSearch: () => {
      searchInputRef.current?.focus()
    },
    onCloseModal: () => {
      if (generationPreviewOpen) {
        setGenerationPreviewOpen(false)
      } else if (conversationsOpen) {
        setConversationsOpen(false)
      } else if (quickChatCharacter) {
        void closeQuickChat()
      } else if (openEdit) {
        setOpenEdit(false)
        editWorldBooksInitializedRef.current = false
        setShowEditSystemPromptExample(false)
      } else if (open) {
        setOpen(false)
        setShowCreateSystemPromptExample(false)
      }
    },
    onTableView: () => setViewMode("table"),
    onGalleryView: () => setViewMode("gallery"),
    enabled: true
  })

  const shortcutHelpItems = React.useMemo(
    () => [
      {
        id: "new",
        keys: ["N"],
        label: t("settings:manageCharacters.shortcuts.new", {
          defaultValue: "New character"
        })
      },
      {
        id: "search",
        keys: ["/"],
        label: t("settings:manageCharacters.shortcuts.search", {
          defaultValue: "Focus search"
        })
      },
      {
        id: "table",
        keys: ["G", "T"],
        label: t("settings:manageCharacters.shortcuts.tableView", {
          defaultValue: "Table view"
        })
      },
      {
        id: "gallery",
        keys: ["G", "G"],
        label: t("settings:manageCharacters.shortcuts.galleryView", {
          defaultValue: "Gallery view"
        })
      },
      {
        id: "close",
        keys: ["Esc"],
        label: t("settings:manageCharacters.shortcuts.close", {
          defaultValue: "Close modal"
        })
      }
    ],
    [t]
  )

  const shortcutSummaryText = React.useMemo(
    () =>
      shortcutHelpItems
        .map((item) => `${item.keys.join(" ")} ${item.label}`)
        .join(". "),
    [shortcutHelpItems]
  )

  // Helper to get current form values as GeneratedCharacter
  const getFormFieldsAsCharacter = (form: FormInstance): Partial<GeneratedCharacter> => {
    const values = form.getFieldsValue()
    return {
      name: values.name,
      description: values.description,
      personality: values.personality,
      scenario: values.scenario,
      system_prompt: values.system_prompt,
      first_message: values.greeting || values.first_message,
      message_example: values.message_example,
      creator_notes: values.creator_notes,
      tags: values.tags,
      alternate_greetings: values.alternate_greetings
    }
  }

  // Handle full character generation
  const handleGenerateFullCharacter = async (concept: string, model: string, apiProvider?: string) => {
    const result = await generateFullCharacter(concept, { model, apiProvider })
    if (result) {
      setGenerationPreviewData(result)
      setGenerationPreviewField(null)
      setGenerationTargetForm('create')
      setGenerationPreviewOpen(true)
    }
  }

  // Handle single field generation
  const handleGenerateField = async (
    field: CharacterField,
    form: FormInstance,
    targetForm: 'create' | 'edit'
  ) => {
    if (!selectedGenModel) {
      notification.warning({
        message: t("settings:manageCharacters.generate.noModelSelected", {
          defaultValue: "No model selected"
        }),
        description: t("settings:manageCharacters.generate.noModelSelectedDesc", {
          defaultValue: "Please select a model in the generation panel first."
        })
      })
      return
    }

    const existingFields = getFormFieldsAsCharacter(form)
    const currentValue = (existingFields as any)[field]

    const result = await generateField(field, existingFields, {
      model: selectedGenModel,
      apiProvider: selectedGenModelProvider
    })

    if (result !== null) {
      // If field has existing content, show preview
      if (currentValue && String(currentValue).trim().length > 0) {
        setGenerationPreviewData({ [field]: result } as GeneratedCharacter)
        setGenerationPreviewField(field)
        setGenerationTargetForm(targetForm)
        setGenerationPreviewOpen(true)
      } else {
        // Apply directly if field is empty
        applyGeneratedFieldToForm(field, result, form)
      }
    }
  }

  const renderSystemPromptField = React.useCallback(
    (form: FormInstance, mode: "create" | "edit") => {
      const showExample =
        mode === "create"
          ? showCreateSystemPromptExample
          : showEditSystemPromptExample
      const toggleExample =
        mode === "create"
          ? setShowCreateSystemPromptExample
          : setShowEditSystemPromptExample

      return (
        <>
          <Form.Item
            name="system_prompt"
            label={
              <span>
                {t(
                  "settings:manageCharacters.form.systemPrompt.label",
                  { defaultValue: "Behavior / instructions" }
                )}
                <span className="text-danger ml-0.5" aria-hidden="true">*</span>
                <span className="sr-only"> ({t("common:required", { defaultValue: "required" })})</span>
                <GenerateFieldButton
                  isGenerating={generatingField === "system_prompt"}
                  disabled={isGenerating}
                  onClick={() =>
                    handleGenerateField("system_prompt", form, mode)
                  }
                />
              </span>
            }
          help={t(
            "settings:manageCharacters.form.systemPrompt.help",
            {
              defaultValue:
                "System prompt: full behavioral instructions sent to the model, including role, tone, and constraints. (max 2000 characters)"
            }
          )}
            extra={
              <div className="space-y-2">
                <button
                  type="button"
                  className="text-xs font-medium text-primary underline-offset-2 hover:underline"
                  onClick={() => toggleExample((value) => !value)}>
                  {showExample
                    ? t("settings:manageCharacters.form.systemPrompt.hideExample", {
                        defaultValue: "Hide example"
                      })
                    : t("settings:manageCharacters.form.systemPrompt.showExample", {
                        defaultValue: "Show example"
                      })}
                </button>
                {showExample && (
                  <div className="rounded border border-border bg-surface2 p-2">
                    <p className="mb-2 text-xs font-medium text-text">
                      {t("settings:manageCharacters.form.systemPrompt.exampleLabel", {
                        defaultValue: "Writing Assistant example"
                      })}
                    </p>
                    <p className="whitespace-pre-wrap text-xs text-text-muted">
                      {SYSTEM_PROMPT_EXAMPLE}
                    </p>
                    <Button
                      type="link"
                      size="small"
                      className="mt-2 p-0"
                      onClick={() => applySystemPromptExample(mode)}>
                      {t("settings:manageCharacters.form.systemPrompt.useExample", {
                        defaultValue: "Use this example"
                      })}
                    </Button>
                  </div>
                )}
              </div>
            }
            rules={[
              {
                required: true,
                message: t(
                  "settings:manageCharacters.form.systemPrompt.required",
                  {
                    defaultValue:
                      "Please add instructions for how the character should respond."
                  }
                )
              },
              {
                min: 10,
                message: t(
                  "settings:manageCharacters.form.systemPrompt.min",
                  {
                    defaultValue:
                      "Add a short description so the character knows how to respond."
                  }
                )
              },
              {
                max: 2000,
                message: t(
                  "settings:manageCharacters.form.systemPrompt.max",
                  {
                    defaultValue:
                      "System prompt must be 2000 characters or less."
                  }
                )
              }
            ]}>
            <Input.TextArea
              autoSize={{ minRows: 3, maxRows: 8 }}
              showCount
              maxLength={2000}
              placeholder={t(
                "settings:manageCharacters.form.systemPrompt.placeholder",
                {
                  defaultValue:
                    "E.g., You are a patient math teacher who explains concepts step by step and checks understanding with short examples."
                }
              )}
            />
          </Form.Item>

          <Form.Item
            name="prompt_preset"
            label={t(
              "settings:manageCharacters.form.promptPreset.label",
              { defaultValue: "Prompt preset" }
            )}
            help={t(
              "settings:manageCharacters.form.promptPreset.help",
              {
                defaultValue:
                  "Controls how character fields are formatted in system prompts for character chats."
              }
            )}>
            <Select options={promptPresetOptions} />
          </Form.Item>
        </>
      )
    },
    [
      applySystemPromptExample,
      generatingField,
      handleGenerateField,
      isGenerating,
      promptPresetOptions,
      showCreateSystemPromptExample,
      showEditSystemPromptExample,
      t
    ]
  )

  const renderAlternateGreetingsField = React.useCallback(
    (form: FormInstance, mode: "create" | "edit") => {
      const markDirty =
        mode === "create" ? () => setCreateFormDirty(true) : () => setEditFormDirty(true)

      return (
        <Form.Item
          label={
            <span>
              {t(
                "settings:manageCharacters.form.alternateGreetings.label",
                {
                  defaultValue: "Alternate greetings"
                }
              )}
              <GenerateFieldButton
                isGenerating={generatingField === "alternate_greetings"}
                disabled={isGenerating}
                onClick={() =>
                  handleGenerateField("alternate_greetings", form, mode)
                }
              />
            </span>
          }
          help={t(
            "settings:manageCharacters.form.alternateGreetings.help",
            {
              defaultValue:
                "Optional alternate greetings to rotate between when starting chats."
            }
          )}>
          <Form.List name="alternate_greetings">
            {(fields, { add, remove, move }) => (
              <div className="space-y-2">
                {fields.length === 0 && (
                  <p className="text-xs text-text-subtle">
                    {t(
                      "settings:manageCharacters.form.alternateGreetings.empty",
                      {
                        defaultValue:
                          "No alternate greetings yet. Add one to vary how chats start."
                      }
                    )}
                  </p>
                )}
                {fields.map((field, index) => {
                  const { key, ...fieldProps } = field
                  return (
                    <div
                      key={key}
                      className="rounded-md border border-border bg-surface2 p-2">
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <span className="text-xs font-medium text-text-muted">
                          {t(
                            "settings:manageCharacters.form.alternateGreetings.itemLabel",
                            {
                              defaultValue: "Greeting {{index}}",
                              index: index + 1
                            }
                          )}
                        </span>
                        <div className="flex items-center gap-1">
                          <Button
                            type="text"
                            size="small"
                            icon={<ChevronUp className="h-4 w-4" />}
                            aria-label={t(
                              "settings:manageCharacters.form.alternateGreetings.moveUp",
                              { defaultValue: "Move greeting up" }
                            )}
                            disabled={index === 0}
                            onClick={() => {
                              move(index, index - 1)
                              markDirty()
                            }}
                          />
                          <Button
                            type="text"
                            size="small"
                            icon={<ChevronDown className="h-4 w-4" />}
                            aria-label={t(
                              "settings:manageCharacters.form.alternateGreetings.moveDown",
                              { defaultValue: "Move greeting down" }
                            )}
                            disabled={index === fields.length - 1}
                            onClick={() => {
                              move(index, index + 1)
                              markDirty()
                            }}
                          />
                          <Button
                            type="text"
                            size="small"
                            danger
                            icon={<span className="text-xs font-medium">X</span>}
                            aria-label={t(
                              "settings:manageCharacters.form.alternateGreetings.remove",
                              { defaultValue: "Remove greeting" }
                            )}
                            onClick={() => {
                              remove(field.name)
                              markDirty()
                            }}
                          />
                        </div>
                      </div>
                      <Form.Item
                        {...fieldProps}
                        className="mb-0"
                        rules={[
                          {
                            validator: async (_rule, value) => {
                              if (!value || String(value).trim().length === 0) {
                                return Promise.resolve()
                              }
                              if (String(value).trim().length > 1000) {
                                return Promise.reject(
                                  new Error(
                                    t(
                                      "settings:manageCharacters.form.alternateGreetings.max",
                                      {
                                        defaultValue:
                                          "Alternate greeting must be 1000 characters or less."
                                      }
                                    )
                                  )
                                )
                              }
                              return Promise.resolve()
                            }
                          }
                        ]}>
                        <Input.TextArea
                          autoSize={{ minRows: 2, maxRows: 6 }}
                          showCount
                          maxLength={1000}
                          placeholder={t(
                            "settings:manageCharacters.form.alternateGreetings.itemPlaceholder",
                            {
                              defaultValue:
                                "Enter an alternate greeting message"
                            }
                          )}
                          onChange={() => markDirty()}
                        />
                      </Form.Item>
                    </div>
                  )
                })}
                <Button
                  type="dashed"
                  size="small"
                  onClick={() => {
                    add("")
                    markDirty()
                  }}>
                  {t(
                    "settings:manageCharacters.form.alternateGreetings.add",
                    { defaultValue: "Add alternate greeting" }
                  )}
                </Button>
              </div>
            )}
          </Form.List>
        </Form.Item>
      )
    },
    [generatingField, handleGenerateField, isGenerating, t]
  )

  const renderNameField = React.useCallback(
    (form: FormInstance, mode: "create" | "edit") => (
      <Form.Item
        name="name"
        label={
          <span>
            {t("settings:manageCharacters.form.name.label", {
              defaultValue: "Name"
            })}
            <span className="text-danger ml-0.5">*</span>
            <GenerateFieldButton
              isGenerating={generatingField === "name"}
              disabled={isGenerating}
              onClick={() => handleGenerateField("name", form, mode)}
            />
          </span>
        }
        rules={[
          {
            required: true,
            message: t(
              "settings:manageCharacters.form.name.required",
              { defaultValue: "Please enter a name" }
            )
          },
          {
            max: MAX_NAME_LENGTH,
            message: t(
              "settings:manageCharacters.form.name.maxLength",
              {
                defaultValue: `Name must be ${MAX_NAME_LENGTH} characters or fewer`
              }
            )
          }
        ]}>
        <Input
          ref={mode === "create" ? createNameRef : editNameRef}
          placeholder={t(
            "settings:manageCharacters.form.name.placeholder",
            { defaultValue: "e.g. Writing coach" }
          )}
          maxLength={MAX_NAME_LENGTH}
          showCount
        />
      </Form.Item>
    ),
    [editNameRef, createNameRef, generatingField, handleGenerateField, isGenerating, t]
  )

  const renderGreetingField = React.useCallback(
    (form: FormInstance, mode: "create" | "edit") => (
      <Form.Item
        name="greeting"
        label={
          <span>
            {t("settings:manageCharacters.form.greeting.label", {
              defaultValue: "Greeting message (optional)"
            })}
            <GenerateFieldButton
              isGenerating={generatingField === "first_message"}
              disabled={isGenerating}
              onClick={() => handleGenerateField("first_message", form, mode)}
            />
          </span>
        }
        help={t("settings:manageCharacters.form.greeting.help", {
          defaultValue:
            "Optional first message the character will send when you start a chat."
        })}>
        <Input.TextArea
          autoSize={{ minRows: 2, maxRows: 6 }}
          placeholder={t(
            "settings:manageCharacters.form.greeting.placeholder",
            {
              defaultValue:
                "Hi there! I'm your writing coach. Paste your draft and I'll help you tighten it up."
            }
          )}
          showCount
          maxLength={1000}
        />
      </Form.Item>
    ),
    [generatingField, handleGenerateField, isGenerating, t]
  )

  const renderDescriptionField = React.useCallback(
    (form: FormInstance, mode: "create" | "edit") => (
      <Form.Item
        name="description"
        label={
          <span>
            {t("settings:manageCharacters.form.description.label", {
              defaultValue: "Description"
            })}
            <GenerateFieldButton
              isGenerating={generatingField === "description"}
              disabled={isGenerating}
              onClick={() => handleGenerateField("description", form, mode)}
            />
          </span>
        }
        help={t("settings:manageCharacters.form.description.help", {
          defaultValue: "Description: brief blurb shown in character lists and cards."
        })}>
        <Input
          placeholder={t(
            "settings:manageCharacters.form.description.placeholder",
            { defaultValue: "Short description" }
          )}
        />
      </Form.Item>
    ),
    [generatingField, handleGenerateField, isGenerating, t]
  )

  const renderTagsField = (form: FormInstance, mode: "create" | "edit") => (
    <Form.Item
      name="tags"
      label={
        <span>
          {t("settings:manageCharacters.tags.label", {
            defaultValue: "Tags"
          })}
          <GenerateFieldButton
            isGenerating={generatingField === "tags"}
            disabled={isGenerating}
            onClick={() => handleGenerateField("tags", form, mode)}
          />
        </span>
      }
      help={t("settings:manageCharacters.tags.help", {
        defaultValue:
          "Use tags to group characters by use case (e.g., 'writing', 'teaching')."
      })}>
      <div className="space-y-2">
        {popularTags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            <span className="text-xs text-text-subtle mr-1">
              {t("settings:manageCharacters.tags.popular", { defaultValue: "Popular:" })}
            </span>
            {popularTags.map(({ tag, count }) => {
              const currentTags = form.getFieldValue("tags") || []
              const isSelected = currentTags.includes(tag)
              return (
                <button
                  key={tag}
                  type="button"
                  className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full border transition-colors motion-reduce:transition-none ${
                    isSelected
                      ? "bg-primary/10 border-primary text-primary"
                      : "bg-surface border-border text-text-muted hover:border-primary/50 hover:text-primary"
                  }`}
                  onClick={() => {
                    const current = form.getFieldValue("tags") || []
                    if (isSelected) {
                      form.setFieldValue(
                        "tags",
                        current.filter((t: string) => t !== tag)
                      )
                    } else {
                      form.setFieldValue("tags", [...current, tag])
                    }
                    markModeDirty(mode)
                  }}>
                  {tag}
                  <span className="text-text-subtle">({count})</span>
                </button>
              )
            })}
          </div>
        )}
        <Form.Item name="tags" noStyle>
          <Select
            mode="tags"
            allowClear
            placeholder={t(
              "settings:manageCharacters.tags.placeholder",
              {
                defaultValue: "Add tags"
              }
            )}
            options={tagOptionsWithCounts}
            onChange={(value) => {
              form.setFieldValue("tags", getCharacterVisibleTags(value))
              markModeDirty(mode)
            }}
            filterOption={(input, option) =>
              option?.value?.toString().toLowerCase().includes(input.toLowerCase()) ?? false
            }
          />
        </Form.Item>
      </div>
    </Form.Item>
  )

  const renderAvatarField = React.useCallback(
    (form: FormInstance) => (
      <Form.Item
        noStyle
        shouldUpdate={(prev, cur) =>
          prev?.name !== cur?.name || prev?.description !== cur?.description
        }>
        {({ getFieldValue }) => (
          <Form.Item
            name="avatar"
            label={t("settings:manageCharacters.avatar.label", {
              defaultValue: "Avatar (optional)"
            })}>
            <AvatarField
              characterName={getFieldValue("name")}
              characterDescription={getFieldValue("description")}
            />
          </Form.Item>
        )}
      </Form.Item>
    ),
    [t]
  )

  const renderAdvancedFields = (
    form: FormInstance,
    mode: "create" | "edit",
    worldBookFieldContext: SharedCharacterFormProps["worldBookFieldContext"]
  ) => {
      const worldBookOptions_local = worldBookFieldContext.options
      const worldBookOptionsLoading_local = worldBookFieldContext.loading
      const worldBookEditCharacterNumericId =
        worldBookFieldContext.editCharacterNumericId
      const showAdvanced = mode === "create" ? showCreateAdvanced : showEditAdvanced
      const setShowAdvanced =
        mode === "create" ? setShowCreateAdvanced : setShowEditAdvanced
      const sectionState =
        mode === "create" ? createAdvancedSections : editAdvancedSections
      const setSectionState =
        mode === "create" ? setCreateAdvancedSections : setEditAdvancedSections
      const toggleSection = (section: AdvancedSectionKey) => {
        setSectionState((prev) => ({ ...prev, [section]: !prev[section] }))
      }
      const renderSection = (
        section: AdvancedSectionKey,
        title: string,
        children: React.ReactNode
      ) => (
        <div className="rounded-md border border-border/70 bg-bg/40">
          <button
            type="button"
            className="flex w-full items-center justify-between px-3 py-2 text-left"
            aria-expanded={sectionState[section]}
            onClick={() => toggleSection(section)}>
            <span className="text-sm font-medium text-text">{title}</span>
            {sectionState[section] ? (
              <ChevronUp className="h-4 w-4 text-text-subtle" />
            ) : (
              <ChevronDown className="h-4 w-4 text-text-subtle" />
            )}
          </button>
          {sectionState[section] && (
            <div className="space-y-3 border-t border-border/60 p-3">
              {children}
            </div>
          )}
        </div>
      )

      return (
        <>
          <button
            type="button"
            className="mb-2 text-xs font-medium text-primary underline-offset-2 hover:underline"
            onClick={() => setShowAdvanced((v) => !v)}>
            {showAdvanced
              ? t("settings:manageCharacters.advanced.hide", {
                  defaultValue: "Hide advanced fields"
                })
              : t("settings:manageCharacters.advanced.show", {
                  defaultValue: "Show advanced fields"
                })}
          </button>
          {showAdvanced && (
            <div className="space-y-3 rounded-md border border-dashed border-border p-3">
              {renderSection(
                "promptControl",
                t("settings:manageCharacters.advanced.section.promptControl", {
                  defaultValue: "Prompt control"
                }),
                <>
                  <Form.Item
                    name="personality"
                    label={
                      <span>
                        {t("settings:manageCharacters.form.personality.label", {
                          defaultValue: "Personality"
                        })}
                        <GenerateFieldButton
                          isGenerating={generatingField === "personality"}
                          disabled={isGenerating}
                          onClick={() => handleGenerateField("personality", form, mode)}
                        />
                      </span>
                    }
                    help={t("settings:manageCharacters.form.personality.help", {
                      defaultValue:
                        "Personality: adjectives and traits injected into context to shape voice and behavior."
                    })}>
                    <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
                  </Form.Item>
                  <Form.Item
                    name="scenario"
                    label={
                      <span>
                        {t("settings:manageCharacters.form.scenario.label", {
                          defaultValue: "Scenario"
                        })}
                        <GenerateFieldButton
                          isGenerating={generatingField === "scenario"}
                          disabled={isGenerating}
                          onClick={() => handleGenerateField("scenario", form, mode)}
                        />
                      </span>
                    }>
                    <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
                  </Form.Item>
                  <Form.Item
                    name="post_history_instructions"
                    label={t("settings:manageCharacters.form.postHistory.label", {
                      defaultValue: "Post-history instructions"
                    })}>
                    <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
                  </Form.Item>
                  <Form.Item
                    name="message_example"
                    label={
                      <span>
                        {t(
                          "settings:manageCharacters.form.messageExample.label",
                          {
                            defaultValue: "Message example"
                          }
                        )}
                        <GenerateFieldButton
                          isGenerating={generatingField === "message_example"}
                          disabled={isGenerating}
                          onClick={() => handleGenerateField("message_example", form, mode)}
                        />
                      </span>
                    }>
                    <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
                  </Form.Item>
                  <Form.Item
                    name="creator_notes"
                    label={
                      <span>
                        {t(
                          "settings:manageCharacters.form.creatorNotes.label",
                          {
                            defaultValue: "Creator notes"
                          }
                        )}
                        <GenerateFieldButton
                          isGenerating={generatingField === "creator_notes"}
                          disabled={isGenerating}
                          onClick={() => handleGenerateField("creator_notes", form, mode)}
                        />
                      </span>
                    }>
                    <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
                  </Form.Item>
                  {renderAlternateGreetingsField(form, mode)}
                  <Form.Item
                    name="default_author_note"
                    label={t(
                      "settings:manageCharacters.form.defaultAuthorNote.label",
                      { defaultValue: "Default author note" }
                    )}
                    help={t(
                      "settings:manageCharacters.form.defaultAuthorNote.help",
                      {
                        defaultValue:
                          "Optional default note used by character chats when the chat-level author note is empty."
                      }
                    )}>
                    <Input.TextArea
                      autoSize={{ minRows: 2, maxRows: 6 }}
                      showCount
                      maxLength={2000}
                      placeholder={t(
                        "settings:manageCharacters.form.defaultAuthorNote.placeholder",
                        {
                          defaultValue:
                            "E.g., Keep replies concise, grounded, and in first-person voice."
                        }
                      )}
                    />
                  </Form.Item>
                </>
              )}

              {renderSection(
                "generationSettings",
                t("settings:manageCharacters.advanced.section.generationSettings", {
                  defaultValue: "Generation settings"
                }),
                <>
                  <Form.Item
                    name="generation_temperature"
                    label={t(
                      "settings:manageCharacters.form.generationTemperature.label",
                      { defaultValue: "Generation temperature" }
                    )}
                    help={t(
                      "settings:manageCharacters.form.generationTemperature.help",
                      {
                        defaultValue:
                          "Optional per-character sampling temperature for character chat completions."
                      }
                    )}>
                    <InputNumber min={0} max={2} step={0.01} className="w-full" />
                  </Form.Item>
                  <Form.Item
                    name="generation_top_p"
                    label={t(
                      "settings:manageCharacters.form.generationTopP.label",
                      { defaultValue: "Generation top_p" }
                    )}
                    help={t(
                      "settings:manageCharacters.form.generationTopP.help",
                      {
                        defaultValue:
                          "Optional per-character nucleus sampling value (0.0 to 1.0)."
                      }
                    )}>
                    <InputNumber min={0} max={1} step={0.01} className="w-full" />
                  </Form.Item>
                  <Form.Item
                    name="generation_repetition_penalty"
                    label={t(
                      "settings:manageCharacters.form.generationRepetitionPenalty.label",
                      { defaultValue: "Repetition penalty" }
                    )}
                    help={t(
                      "settings:manageCharacters.form.generationRepetitionPenalty.help",
                      {
                        defaultValue:
                          "Optional per-character repetition penalty used for character chat completions."
                      }
                    )}>
                    <InputNumber min={0} max={3} step={0.01} className="w-full" />
                  </Form.Item>
                  <Form.Item
                    name="generation_stop_strings"
                    label={t(
                      "settings:manageCharacters.form.generationStopStrings.label",
                      { defaultValue: "Stop strings" }
                    )}
                    help={t(
                      "settings:manageCharacters.form.generationStopStrings.help",
                      {
                        defaultValue:
                          "Optional stop sequences for this character. Use one per line."
                      }
                    )}>
                    <Input.TextArea
                      autoSize={{ minRows: 2, maxRows: 6 }}
                      placeholder={t(
                        "settings:manageCharacters.form.generationStopStrings.placeholder",
                        {
                          defaultValue:
                            "Example:\n###\nEND"
                        }
                      )}
                    />
                  </Form.Item>
                </>
              )}

              {renderSection(
                "metadata",
                t("settings:manageCharacters.advanced.section.metadata", {
                  defaultValue: "Metadata"
                }),
                <>
                  <Form.Item
                    name="folder_id"
                    label={t("settings:manageCharacters.folder.label", {
                      defaultValue: "Folder"
                    })}
                    help={t("settings:manageCharacters.folder.help", {
                      defaultValue:
                        "Assign a single folder for organization. This does not change your visible tags."
                    })}
                  >
                    <Select
                      allowClear
                      showSearch
                      optionFilterProp="label"
                      placeholder={t(
                        "settings:manageCharacters.folder.placeholder",
                        {
                          defaultValue: "Select folder"
                        }
                      )}
                      options={characterFolderOptions.map((folder) => ({
                        value: String(folder.id),
                        label: folder.name
                      }))}
                      loading={characterFolderOptionsLoading}
                    />
                  </Form.Item>
                  <Form.Item
                    name="creator"
                    label={t("settings:manageCharacters.form.creator.label", {
                      defaultValue: "Creator"
                    })}>
                    <Input />
                  </Form.Item>
                  <Form.Item
                    name="character_version"
                    label={t(
                      "settings:manageCharacters.form.characterVersion.label",
                      {
                        defaultValue: "Character version"
                      }
                    )}
                    help={t(
                      "settings:manageCharacters.form.characterVersion.help",
                      {
                        defaultValue: "Free text, e.g. \"1.0\" or \"2024-01\""
                      }
                    )}>
                    <Input />
                  </Form.Item>
                  <Form.Item
                    name="extensions"
                    label={t("settings:manageCharacters.form.extensions.label", {
                      defaultValue: "Extensions (JSON)"
                    })}
                    help={t(
                      "settings:manageCharacters.form.extensions.help",
                      {
                        defaultValue:
                          "Optional JSON object with additional metadata; invalid JSON will be sent as raw text."
                      }
                    )}>
                    <Input.TextArea autoSize={{ minRows: 2, maxRows: 8 }} />
                  </Form.Item>
                  <Form.Item
                    name="world_book_ids"
                    label={t("settings:manageCharacters.worldBooks.editorTitle", {
                      defaultValue: "World book attachments"
                    })}
                    help={t("settings:manageCharacters.worldBooks.editorDescription", {
                      defaultValue:
                        "Attach or detach world books used for character context injection."
                    })}
                  >
                    <Select
                      mode="multiple"
                      allowClear
                      optionFilterProp="label"
                      placeholder={t(
                        "settings:manageCharacters.worldBooks.attachPlaceholder",
                        {
                          defaultValue: "Select world book to attach"
                        }
                      )}
                      options={worldBookOptions_local.map((worldBook) => ({
                        value: worldBook.id,
                        label: worldBook.name
                      }))}
                      loading={worldBookOptionsLoading_local}
                    />
                  </Form.Item>
                  {mode === "edit" && worldBookEditCharacterNumericId == null && (
                    <div className="-mt-2 text-xs text-text-muted">
                      {t("settings:manageCharacters.worldBooks.unsyncedCharacter", {
                        defaultValue:
                          "Save this character to the server before attaching world books."
                      })}
                    </div>
                  )}
                  <div className="rounded-md border border-dashed border-border px-3 py-2">
                    <p className="text-xs font-medium text-text">
                      {t("settings:manageCharacters.form.moodImages.placeholderTitle", {
                        defaultValue: "Mood images (coming soon)"
                      })}
                    </p>
                    <p className="mt-1 text-xs text-text-muted">
                      {t("settings:manageCharacters.form.moodImages.placeholderBody", {
                        defaultValue:
                          "Per-mood image variants are planned but not yet available in the character editor."
                      })}
                    </p>
                  </div>
                </>
              )}
            </div>
          )}
        </>
      )
    }

  const renderSharedCharacterForm = ({
    form,
    mode,
    initialValues,
    worldBookFieldContext,
    isSubmitting,
    submitButtonClassName,
    submitPendingLabel,
    submitIdleLabel,
    showPreview,
    onTogglePreview,
    onValuesChange,
    onFinish
  }: SharedCharacterFormProps) => (
    <Form
      layout="vertical"
      form={form}
      initialValues={initialValues}
      className="space-y-3"
      onValuesChange={(_, allValues) => {
        onValuesChange(allValues)
      }}
      onFinish={onFinish}>
      {/* Field order: Name -> System Prompt (required) -> Greeting -> Description -> Tags -> Avatar */}
      {renderNameField(form, mode)}
      {renderSystemPromptField(form, mode)}
      {renderGreetingField(form, mode)}
      {renderDescriptionField(form, mode)}
      {renderTagsField(form, mode)}
      {renderAvatarField(form)}
      {renderAdvancedFields(form, mode, worldBookFieldContext)}

      {/* Preview toggle */}
      <button
        type="button"
        className="mt-4 mb-2 flex items-center gap-1 text-xs font-medium text-text-muted hover:text-text"
        onClick={onTogglePreview}>
        {showPreview ? (
          <ChevronUp className="w-4 h-4" />
        ) : (
          <ChevronDown className="w-4 h-4" />
        )}
        {showPreview
          ? t("settings:manageCharacters.preview.hide", {
              defaultValue: "Hide preview"
            })
          : t("settings:manageCharacters.preview.show", {
              defaultValue: "Show preview"
            })}
      </button>

      {/* Character Preview */}
      {showPreview && (
        <Form.Item noStyle shouldUpdate>
          {() => {
            const avatar = form.getFieldValue("avatar")
            const avatarValues = avatar ? extractAvatarValues(avatar) : {}
            return (
              <CharacterPreview
                name={form.getFieldValue("name")}
                description={form.getFieldValue("description")}
                avatar_url={avatarValues.avatar_url}
                image_base64={avatarValues.image_base64}
                system_prompt={form.getFieldValue("system_prompt")}
                greeting={form.getFieldValue("greeting")}
                tags={form.getFieldValue("tags")}
              />
            )
          }}
        </Form.Item>
      )}

      <Button
        type="primary"
        htmlType="submit"
        loading={isSubmitting}
        className={submitButtonClassName}>
        {isSubmitting ? submitPendingLabel : submitIdleLabel}
      </Button>
    </Form>
  )

  // Apply generated data to form
  const applyGeneratedFieldToForm = (
    field: string,
    value: any,
    form: FormInstance
  ) => {
    // Map field names to form field names
    const fieldMap: Record<string, string> = {
      first_message: 'greeting'
    }
    const formField = fieldMap[field] || field
    form.setFieldValue(formField, value)
    if (generationTargetForm === 'create') {
      setCreateFormDirty(true)
    } else {
      setEditFormDirty(true)
    }
  }

  // Apply full character generation preview
  const applyGenerationPreview = () => {
    if (!generationPreviewData) return

    const form = generationTargetForm === 'create' ? createForm : editForm

    if (generationPreviewField) {
      // Single field
      const value = (generationPreviewData as any)[generationPreviewField]
      if (value !== undefined) {
        applyGeneratedFieldToForm(generationPreviewField, value, form)
      }
    } else {
      // Full character - apply all non-empty fields
      const fieldMap: Record<string, string> = {
        first_message: 'greeting'
      }

      Object.entries(generationPreviewData).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          const formField = fieldMap[key] || key
          form.setFieldValue(formField, value)
        }
      })

      // Auto-expand advanced section if advanced fields were generated
      const hasAdvanced = generationPreviewData.personality ||
        generationPreviewData.scenario ||
        generationPreviewData.message_example ||
        generationPreviewData.creator_notes ||
        (generationPreviewData.alternate_greetings && generationPreviewData.alternate_greetings.length > 0)

      if (hasAdvanced) {
        if (generationTargetForm === 'create') {
          setShowCreateAdvanced(true)
        } else {
          setShowEditAdvanced(true)
        }
      }

      if (generationTargetForm === 'create') {
        setCreateFormDirty(true)
      } else {
        setEditFormDirty(true)
      }
    }

    setGenerationPreviewOpen(false)
    setGenerationPreviewData(null)
    setGenerationPreviewField(null)
  }

  React.useEffect(() => {
    if (forwardedNewButtonRef && newButtonRef.current) {
      ;(forwardedNewButtonRef as any).current = newButtonRef.current
    }
  }, [forwardedNewButtonRef])

  React.useEffect(() => {
    if (!autoOpenCreate) return
    if (autoOpenCreateHandledRef.current) return
    autoOpenCreateHandledRef.current = true
    if (!openEdit && !conversationsOpen) {
      openCreateModal()
    }
  }, [autoOpenCreate, conversationsOpen, openCreateModal, openEdit])

  // Cleanup pending delete timeout on unmount
  React.useEffect(() => {
    return () => {
      if (undoDeleteRef.current) {
        clearTimeout(undoDeleteRef.current)
      }
      if (bulkUndoDeleteRef.current) {
        clearTimeout(bulkUndoDeleteRef.current)
      }
    }
  }, [])

  // --- useCharacterData hook ---
  const characterData = useCharacterData({
    t,
    notification,
    qc,
    searchTerm,
    debouncedSearchTerm,
    filterTags,
    folderFilterId,
    matchAllTags,
    creatorFilter,
    createdFromDate,
    createdToDate,
    updatedFromDate,
    updatedToDate,
    hasConversationsOnly,
    favoritesOnly,
    characterListScope,
    sortColumn,
    sortOrder,
    currentPage,
    pageSize,
    setCurrentPage,
    previewCharacter,
    setPreviewCharacter,
    editCharacterNumericId,
    editWorldBooksInitializedRef,
    open,
    openEdit,
    editForm,
    defaultCharacterSelection,
    setDefaultCharacterSelection,
    defaultCharacterId
  })
  const {
    status,
    error,
    refetch,
    data,
    totalCharacters,
    pagedGalleryData,
    effectiveDefaultCharacterId,
    conversationCounts,
    previewCharacterWorldBooks,
    previewCharacterWorldBooksLoading,
    worldBookOptionsLoading,
    worldBookOptions,
    tagUsageData,
    allTags,
    popularTags,
    tagOptionsWithCounts,
    tagFilterOptions,
    creatorFilterOptions,
    characterFolderOptions,
    characterFolderOptionsLoading,
    selectedFolderFilterLabel,
    crossNavigationContext
  } = characterData

  // --- useCharacterCrud hook ---
  const crud = useCharacterCrud({
    t,
    notification,
    qc,
    createForm,
    editForm,
    editId,
    setEditId,
    editVersion,
    editCharacterNumericId,
    setOpen,
    setOpenEdit,
    setConversationsOpen,
    setConversationCharacter,
    setPreviewCharacter,
    setShowTemplates: (v: boolean) => setShowTemplates(v),
    setShowCreateSystemPromptExample,
    setShowEditSystemPromptExample,
    setShowCreateAdvanced,
    setShowEditAdvanced,
    setCreateFormDirty,
    setEditFormDirty,
    setExporting,
    newButtonRef,
    lastEditTriggerRef,
    editWorldBooksInitializedRef,
    clearCreateDraft,
    clearEditDraft,
    data,
    effectiveDefaultCharacterId,
    defaultCharacterSelection,
    setDefaultCharacterSelection
  })
  const {
    createCharacter,
    creating,
    updateCharacter,
    updating,
    deleting,
    handleExport,
    handleChat,
    handleChatInNewTab,
    handleEdit,
    handleDuplicate,
    handleDelete,
    handleViewConversations,
    handleRestoreFromTrash,
    isDefaultCharacterRecord,
    handleSetDefaultCharacter,
    handleClearDefaultCharacter,
    isCharacterFavoriteRecord,
    handleToggleFavorite,
    isPersonaCreatePending,
    getCreatePersonaActionLabel,
    openPersonaGardenForCharacter,
    createPersonaFromCharacter,
    characterChats,
    setCharacterChats,
    chatsError,
    setChatsError,
    loadingChats,
    setLoadingChats,
    resumingChatId,
    setResumingChatId,
    setHistory,
    setMessages,
    setHistoryId,
    setServerChatId,
    setServerChatState,
    setServerChatTopic,
    setServerChatClusterId,
    setServerChatSource,
    setServerChatExternalRef,
    pendingDelete,
    undoDeleteRef,
    bulkUndoDeleteRef,
    conversationsLoadErrorMessageRef,
    restoreCharacter
  } = crud

  React.useEffect(() => {
    if (open) {
      setTimeout(() => {
        createNameRef.current?.focus()
      }, 0)
    }
  }, [open])

  React.useEffect(() => {
    if (openEdit) {
      setTimeout(() => {
        editNameRef.current?.focus()
      }, 0)
    }
  }, [openEdit])

  // Inline edit state, mutation, and handlers (M1) - now from hook
  const {
    inlineEdit,
    setInlineEdit,
    inlineUpdating,
    inlineEditInputRef,
    inlineEditTriggerRef,
    inlineEditFocusKeyRef,
    startInlineEdit,
    saveInlineEdit,
    cancelInlineEdit,
    restoreInlineEditFocus
  } = useCharacterInlineEdit({ t, notification, qc, data })

  // --- useCharacterBulkOps hook ---
  const bulkOps = useCharacterBulkOps({
    t,
    notification,
    qc,
    data,
    characterListScope,
    creatorFilter,
    currentPage,
    debouncedSearchTerm,
    filterTags,
    folderFilterId,
    favoritesOnly,
    hasConversationsOnly,
    matchAllTags,
    pageSize,
    sortColumn,
    sortOrder,
    bulkUndoDeleteRef,
    setBulkOperationLoading,
    compareModalOpen,
    setCompareModalOpen,
    compareCharacters,
    setCompareCharacters,
    closeCompareModal,
    handleBulkAddTags
  })
  const {
    selectedCharacterIds,
    setSelectedCharacterIds,
    toggleCharacterSelection,
    selectAllOnPage,
    clearSelection,
    selectedCount,
    hasSelection,
    selectedCharacters,
    allOnPageSelected,
    someOnPageSelected,
    handleBulkDelete,
    handleBulkExport,
    handleBulkAddTagsForSelection,
    comparisonRows,
    changedComparisonRows,
    handleOpenCompareModal,
    handleCopyComparisonSummary,
    handleExportComparisonSummary
  } = bulkOps

  return (
    <div className="characters-page" data-testid="characters-page">
      <a
        href="#characters-main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:border focus:border-border focus:bg-surface focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-text focus:shadow">
        {t("settings:manageCharacters.skipToContent", {
          defaultValue: "Skip to characters content"
        })}
      </a>
      <div
        id="characters-main-content"
        role="main"
        tabIndex={-1}
        aria-describedby="characters-shortcuts-summary"
        className="space-y-4"
        onDragEnter={handleImportDragEnter}
        onDragOver={handleImportDragOver}
        onDragLeave={handleImportDragLeave}
        onDrop={(event) => {
          void handleImportDrop(event)
        }}>

      <CharacterListToolbar
        t={t}
        searchInputRef={searchInputRef}
        searchTerm={searchTerm}
        setSearchTerm={setSearchTerm}
        viewMode={viewMode}
        setViewMode={setViewMode}
        characterListScope={characterListScope}
        setCharacterListScope={setCharacterListScope}
        advancedFiltersOpen={advancedFiltersOpen}
        setAdvancedFiltersOpen={setAdvancedFiltersOpen}
        activeAdvancedFilterCount={activeAdvancedFilterCount}
        hasFilters={hasFilters}
        clearFilters={clearFilters}
        filterTags={filterTags}
        setFilterTags={setFilterTags}
        folderFilterId={folderFilterId}
        setFolderFilterId={setFolderFilterId}
        creatorFilter={creatorFilter}
        setCreatorFilter={setCreatorFilter}
        createdFromDate={createdFromDate}
        setCreatedFromDate={setCreatedFromDate}
        createdToDate={createdToDate}
        setCreatedToDate={setCreatedToDate}
        updatedFromDate={updatedFromDate}
        setUpdatedFromDate={setUpdatedFromDate}
        updatedToDate={updatedToDate}
        setUpdatedToDate={setUpdatedToDate}
        matchAllTags={matchAllTags}
        setMatchAllTags={setMatchAllTags}
        hasConversationsOnly={hasConversationsOnly}
        setHasConversationsOnly={setHasConversationsOnly}
        favoritesOnly={favoritesOnly}
        setFavoritesOnly={setFavoritesOnly}
        tagFilterOptions={tagFilterOptions}
        creatorFilterOptions={creatorFilterOptions}
        characterFolderOptions={characterFolderOptions}
        characterFolderOptionsLoading={characterFolderOptionsLoading}
        selectedFolderFilterLabel={selectedFolderFilterLabel}
        galleryDensity={galleryDensity}
        setGalleryDensity={setGalleryDensity}
        tableDensity={tableDensity}
        setTableDensity={setTableDensity}
        shortcutHelpItems={shortcutHelpItems}
        shortcutSummaryText={shortcutSummaryText}
        isImportBusy={isImportBusy}
        triggerImportPicker={triggerImportPicker}
        newButtonRef={newButtonRef}
        openCreateModal={openCreateModal}
        openTagManager={openTagManager}
      />

      <CharacterListContent
        t={t}
        status={status}
        error={error}
        refetch={refetch}
        data={data}
        totalCharacters={totalCharacters}
        pagedGalleryData={pagedGalleryData}
        conversationCounts={conversationCounts}
        viewMode={viewMode}
        characterListScope={characterListScope}
        setCharacterListScope={setCharacterListScope}
        galleryDensity={galleryDensity}
        tableDensity={tableDensity}
        currentPage={currentPage}
        setCurrentPage={setCurrentPage}
        pageSize={pageSize}
        setPageSize={setPageSize}
        sortColumn={sortColumn}
        setSortColumn={setSortColumn}
        sortOrder={sortOrder}
        setSortOrder={setSortOrder}
        hasFilters={hasFilters}
        searchTerm={searchTerm}
        filterTags={filterTags}
        setFilterTags={setFilterTags}
        matchAllTags={matchAllTags}
        folderFilterId={folderFilterId}
        selectedFolderFilterLabel={selectedFolderFilterLabel}
        creatorFilter={creatorFilter}
        createdFromDate={createdFromDate}
        createdToDate={createdToDate}
        updatedFromDate={updatedFromDate}
        updatedToDate={updatedToDate}
        hasConversationsOnly={hasConversationsOnly}
        favoritesOnly={favoritesOnly}
        clearFilters={clearFilters}
        previewCharacter={previewCharacter}
        setPreviewCharacter={setPreviewCharacter}
        previewCharacterWorldBooks={previewCharacterWorldBooks}
        previewCharacterWorldBooksLoading={previewCharacterWorldBooksLoading}
        crossNavigationContext={crossNavigationContext}
        inlineEdit={inlineEdit}
        setInlineEdit={setInlineEdit}
        inlineUpdating={inlineUpdating}
        inlineEditInputRef={inlineEditInputRef}
        startInlineEdit={startInlineEdit}
        saveInlineEdit={saveInlineEdit}
        cancelInlineEdit={cancelInlineEdit}
        selectedCharacterIds={selectedCharacterIds}
        setSelectedCharacterIds={setSelectedCharacterIds}
        toggleCharacterSelection={toggleCharacterSelection}
        selectAllOnPage={selectAllOnPage}
        clearSelection={clearSelection}
        selectedCount={selectedCount}
        hasSelection={hasSelection}
        allOnPageSelected={allOnPageSelected}
        someOnPageSelected={someOnPageSelected}
        handleBulkDelete={handleBulkDelete}
        handleBulkExport={handleBulkExport}
        handleOpenCompareModal={handleOpenCompareModal}
        bulkOperationLoading={bulkOperationLoading}
        setBulkTagModalOpen={setBulkTagModalOpen}
        handleChat={handleChat}
        handleChatInNewTab={handleChatInNewTab}
        handleEdit={handleEdit}
        handleDuplicate={handleDuplicate}
        handleDelete={handleDelete}
        handleExport={handleExport}
        handleViewConversations={handleViewConversations}
        handleRestoreFromTrash={handleRestoreFromTrash}
        handleToggleFavorite={handleToggleFavorite}
        handleSetDefaultCharacter={handleSetDefaultCharacter}
        handleClearDefaultCharacter={handleClearDefaultCharacter}
        isDefaultCharacterRecord={isDefaultCharacterRecord}
        isCharacterFavoriteRecord={isCharacterFavoriteRecord}
        isPersonaCreatePending={isPersonaCreatePending}
        getCreatePersonaActionLabel={getCreatePersonaActionLabel}
        openPersonaGardenForCharacter={openPersonaGardenForCharacter}
        createPersonaFromCharacter={createPersonaFromCharacter}
        openVersionHistory={openVersionHistory}
        openQuickChat={openQuickChat}
        deleting={deleting}
        exporting={exporting}
        setConversationCharacter={setConversationCharacter}
        setCharacterChats={setCharacterChats}
        setChatsError={setChatsError}
        setConversationsOpen={setConversationsOpen}
        openCreateModal={openCreateModal}
        setShowTemplates={setShowTemplates}
        markTemplateChooserSeen={markTemplateChooserSeen}
        isImportBusy={isImportBusy}
        triggerImportPicker={triggerImportPicker}
        confirmDanger={confirmDanger}
      />

      <CharacterDialogs
        t={t}
        navigate={navigate}
        // import
        importPreviewOpen={importPreviewOpen}
        resetImportPreview={resetImportPreview}
        importPreviewHasSuccessfulCompletion={importPreviewHasSuccessfulCompletion}
        retryableFailedPreviewItems={retryableFailedPreviewItems}
        importPreviewProcessing={importPreviewProcessing}
        handleRetryFailedImportPreview={handleRetryFailedImportPreview}
        importPreviewLoading={importPreviewLoading}
        importablePreviewItems={importablePreviewItems}
        importQueueSummary={importQueueSummary}
        importPreviewItems={importPreviewItems}
        importQueueItemsById={importQueueItemsById}
        importing={importing}
        handleConfirmImportPreview={handleConfirmImportPreview}
        getImportQueueStateLabel={getImportQueueStateLabel}
        getImportQueueStateColor={getImportQueueStateColor}
        importButtonContainerRef={importButtonContainerRef}
        isImportBusy={isImportBusy}
        handleImportUpload={handleImportUpload}
        handleImportDragEnter={handleImportDragEnter}
        handleImportDragLeave={handleImportDragLeave}
        handleImportDragOver={handleImportDragOver}
        handleImportDrop={handleImportDrop}
        // quick chat
        quickChatCharacter={quickChatCharacter}
        closeQuickChat={closeQuickChat}
        quickChatModelOptions={quickChatModelOptions}
        activeQuickChatModel={activeQuickChatModel}
        setQuickChatModelOverride={setQuickChatModelOverride}
        quickChatError={quickChatError}
        quickChatMessages={quickChatMessages}
        quickChatDraft={quickChatDraft}
        setQuickChatDraft={setQuickChatDraft}
        quickChatSending={quickChatSending}
        sendQuickChatMessage={sendQuickChatMessage}
        handlePromoteQuickChat={handlePromoteQuickChat}
        // conversations
        conversationsOpen={conversationsOpen}
        setConversationsOpen={setConversationsOpen}
        conversationCharacter={conversationCharacter}
        setConversationCharacter={setConversationCharacter}
        characterChats={characterChats}
        setCharacterChats={setCharacterChats}
        chatsError={chatsError}
        setChatsError={setChatsError}
        loadingChats={loadingChats}
        setLoadingChats={setLoadingChats}
        resumingChatId={resumingChatId}
        setResumingChatId={setResumingChatId}
        setSelectedCharacter={setSelectedCharacter}
        setHistory={setHistory}
        setMessages={setMessages}
        setHistoryId={setHistoryId}
        setServerChatId={setServerChatId}
        setServerChatState={setServerChatState}
        setServerChatTopic={setServerChatTopic}
        setServerChatClusterId={setServerChatClusterId}
        setServerChatSource={setServerChatSource}
        setServerChatExternalRef={setServerChatExternalRef}
        // create
        open={open}
        setOpen={setOpen}
        createForm={createForm}
        createFormDirty={createFormDirty}
        setCreateFormDirty={setCreateFormDirty}
        creating={creating}
        createCharacter={createCharacter}
        showCreatePreview={showCreatePreview}
        setShowCreatePreview={setShowCreatePreview}
        setShowCreateAdvanced={setShowCreateAdvanced}
        setShowCreateSystemPromptExample={setShowCreateSystemPromptExample}
        setShowTemplates={setShowTemplates}
        showTemplates={showTemplates}
        markTemplateChooserSeen={markTemplateChooserSeen}
        applyTemplateToCreateForm={applyTemplateToCreateForm}
        newButtonRef={newButtonRef}
        hasCreateDraft={hasCreateDraft}
        createDraftData={createDraftData}
        saveCreateDraft={saveCreateDraft}
        clearCreateDraft={clearCreateDraft}
        applyCreateDraft={applyCreateDraft}
        dismissCreateDraft={dismissCreateDraft}
        // edit
        openEdit={openEdit}
        setOpenEdit={setOpenEdit}
        editForm={editForm}
        editFormDirty={editFormDirty}
        setEditFormDirty={setEditFormDirty}
        editId={editId}
        setEditId={setEditId}
        editVersion={editVersion}
        setEditVersion={setEditVersion}
        editCharacterNumericId={editCharacterNumericId}
        updating={updating}
        updateCharacter={updateCharacter}
        showEditPreview={showEditPreview}
        setShowEditPreview={setShowEditPreview}
        setShowEditAdvanced={setShowEditAdvanced}
        setShowEditSystemPromptExample={setShowEditSystemPromptExample}
        lastEditTriggerRef={lastEditTriggerRef}
        editWorldBooksInitializedRef={editWorldBooksInitializedRef}
        hasEditDraft={hasEditDraft}
        editDraftData={editDraftData}
        saveEditDraft={saveEditDraft}
        clearEditDraft={clearEditDraft}
        applyEditDraft={applyEditDraft}
        dismissEditDraft={dismissEditDraft}
        worldBookOptions={worldBookOptions}
        worldBookOptionsLoading={worldBookOptionsLoading}
        // generation
        isGenerating={isGenerating}
        generatingField={generatingField}
        generationError={generationError}
        handleGenerateFullCharacter={handleGenerateFullCharacter}
        cancelGeneration={cancelGeneration}
        clearGenerationError={clearGenerationError}
        generationPreviewOpen={generationPreviewOpen}
        setGenerationPreviewOpen={setGenerationPreviewOpen}
        generationPreviewData={generationPreviewData}
        setGenerationPreviewData={setGenerationPreviewData}
        generationPreviewField={generationPreviewField}
        setGenerationPreviewField={setGenerationPreviewField}
        applyGenerationPreview={applyGenerationPreview}
        // version history
        versionHistoryOpen={versionHistoryOpen}
        setVersionHistoryOpen={setVersionHistoryOpen}
        versionHistoryCharacter={versionHistoryCharacter}
        setVersionHistoryCharacter={setVersionHistoryCharacter}
        versionHistoryCharacterId={versionHistoryCharacterId}
        versionHistoryCharacterName={versionHistoryCharacterName}
        versionFrom={versionFrom}
        setVersionFrom={setVersionFrom}
        versionTo={versionTo}
        setVersionTo={setVersionTo}
        versionRevertTarget={versionRevertTarget}
        setVersionRevertTarget={setVersionRevertTarget}
        versionHistoryItems={versionHistoryItems}
        versionHistoryLoading={versionHistoryLoading}
        versionHistoryFetching={versionHistoryFetching}
        versionSelectOptions={versionSelectOptions}
        versionDiffResponse={versionDiffResponse}
        versionDiffLoading={versionDiffLoading}
        versionDiffFetching={versionDiffFetching}
        revertingCharacterVersion={revertingCharacterVersion}
        openVersionHistory={openVersionHistory}
        revertCharacterVersion={revertCharacterVersion}
        // compare
        compareModalOpen={compareModalOpen}
        closeCompareModal={closeCompareModal}
        compareCharacters={compareCharacters}
        comparisonRows={comparisonRows}
        changedComparisonRows={changedComparisonRows}
        handleCopyComparisonSummary={handleCopyComparisonSummary}
        handleExportComparisonSummary={handleExportComparisonSummary}
        // tag manager
        tagManagerOpen={tagManagerOpen}
        closeTagManager={closeTagManager}
        tagManagerLoading={tagManagerLoading}
        tagManagerSubmitting={tagManagerSubmitting}
        tagManagerOperation={tagManagerOperation}
        setTagManagerOperation={setTagManagerOperation}
        tagManagerSourceTag={tagManagerSourceTag}
        setTagManagerSourceTag={setTagManagerSourceTag}
        tagManagerTargetTag={tagManagerTargetTag}
        setTagManagerTargetTag={setTagManagerTargetTag}
        tagManagerTagUsageData={tagManagerTagUsageData}
        handleApplyTagManagerOperation={handleApplyTagManagerOperation}
        // bulk tags
        bulkTagModalOpen={bulkTagModalOpen}
        setBulkTagModalOpen={setBulkTagModalOpen}
        bulkTagsToAdd={bulkTagsToAdd}
        setBulkTagsToAdd={setBulkTagsToAdd}
        bulkOperationLoading={bulkOperationLoading}
        handleBulkAddTagsForSelection={handleBulkAddTagsForSelection}
        selectedCount={selectedCount}
        popularTags={popularTags}
        tagOptionsWithCounts={tagOptionsWithCounts}
        // confirm
        confirmDanger={confirmDanger}
        // shared form
        renderSharedCharacterForm={renderSharedCharacterForm}
        data={data}
      />
      </div>
    </div>
  )
}
