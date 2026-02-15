import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Button,
  Form,
  Input,
  Modal,
  Skeleton,
  Table,
  Tag,
  Tooltip,
  Select,
  Alert,
  Checkbox,
  Segmented,
  Pagination,
  Upload,
  Dropdown,
  InputNumber
} from "antd"
import type { InputRef, FormInstance } from "antd"
import React from "react"
import { tldwClient, type ServerChatSummary } from "@/services/tldw/TldwApiClient"
import { fetchChatModels } from "@/services/tldw-server"
import { History, Pen, Trash2, UserCircle2, MessageCircle, Copy, ChevronDown, ChevronUp, LayoutGrid, List, Keyboard, Download, CheckSquare, Square, Tags, X, MoreHorizontal } from "lucide-react"
import { CharacterPreview } from "./CharacterPreview"
import { CharacterGalleryCard } from "./CharacterGalleryCard"
import { CharacterPreviewPopup } from "./CharacterPreviewPopup"
import { AvatarField, extractAvatarValues, createAvatarValue } from "./AvatarField"
import { GenerateCharacterPanel, GenerationPreviewModal } from "./GenerateCharacterPanel"
import { GenerateFieldButton } from "./GenerateFieldButton"
import { useCharacterGeneration } from "@/hooks/useCharacterGeneration"
import { useFormDraft, formatDraftAge } from "@/hooks/useFormDraft"
import { useCharacterShortcuts } from "@/hooks/useCharacterShortcuts"
import { CHARACTER_TEMPLATES, type CharacterTemplate } from "@/data/character-templates"
import {
  CHARACTER_PROMPT_PRESETS,
  DEFAULT_CHARACTER_PROMPT_PRESET,
  isCharacterPromptPresetId,
  type CharacterPromptPresetId
} from "@/data/character-prompt-presets"
import type { GeneratedCharacter, CharacterField } from "@/services/character-generation"
import { useStorage } from "@plasmohq/storage/hook"
import { validateAndCreateImageDataUrl } from "@/utils/image-utils"
import { exportCharacterToJSON, exportCharacterToPNG, exportCharactersToJSON } from "@/utils/character-export"
import { useTranslation } from "react-i18next"
import { useConfirmDanger } from "@/components/Common/confirm-danger"
import { useNavigate } from "react-router-dom"
import { useSelectedCharacter } from "@/hooks/useSelectedCharacter"
import FeatureEmptyState from "@/components/Common/FeatureEmptyState"
import { useAntdNotification } from "@/hooks/useAntdNotification"
import { focusComposer } from "@/hooks/useComposerFocus"
import { useStoreMessageOption } from "@/store/option"
import { shallow } from "zustand/shallow"
import { updatePageTitle } from "@/utils/update-page-title"
import { normalizeChatRole } from "@/utils/normalize-chat-role"

const MAX_NAME_LENGTH = 75
const MAX_DESCRIPTION_LENGTH = 65
const MAX_TAG_LENGTH = 20
const MAX_TAGS_DISPLAYED = 6
const DEFAULT_PAGE_SIZE = 10

const truncateText = (value?: string, max?: number) => {
  if (!value) return ""
  if (!max || value.length <= max) return value
  return `${value.slice(0, max)}...`
}

const normalizeAlternateGreetings = (value: any): string[] => {
  if (!value) return []
  if (Array.isArray(value)) {
    return value.map((v) => String(v)).filter((v) => v.trim().length > 0)
  }
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value)
      if (Array.isArray(parsed)) {
        return parsed.map((v) => String(v)).filter((v) => v.trim().length > 0)
      }
    } catch {
      // fall through to newline splitting
    }
    return value
      .split(/\r?\n|;/)
      .map((v) => v.trim())
      .filter((v) => v.length > 0)
  }
  return []
}

const isPlainObject = (value: unknown): value is Record<string, any> =>
  !!value && typeof value === "object" && !Array.isArray(value)

const parseExtensionsObject = (
  value: unknown
): Record<string, any> | null => {
  if (!value) return {}
  if (isPlainObject(value)) return { ...value }
  if (typeof value === "string") {
    if (!value.trim()) return {}
    try {
      const parsed = JSON.parse(value)
      return isPlainObject(parsed) ? { ...parsed } : {}
    } catch {
      return null
    }
  }
  return {}
}

const normalizePromptPresetId = (
  value: unknown
): CharacterPromptPresetId =>
  isCharacterPromptPresetId(value)
    ? value
    : DEFAULT_CHARACTER_PROMPT_PRESET

const readPromptPresetFromExtensions = (
  extensions: unknown
): CharacterPromptPresetId => {
  const parsed = parseExtensionsObject(extensions)
  if (!parsed) return DEFAULT_CHARACTER_PROMPT_PRESET
  const tldw = parsed.tldw
  const nestedPreset = isPlainObject(tldw)
    ? tldw.prompt_preset || tldw.promptPreset
    : undefined
  const topPreset = parsed.prompt_preset || parsed.promptPreset
  return normalizePromptPresetId(nestedPreset || topPreset)
}

const readDefaultAuthorNoteFromExtensions = (extensions: unknown): string => {
  const parsed = parseExtensionsObject(extensions)
  if (!parsed) return ""

  const tldw = isPlainObject(parsed.tldw) ? parsed.tldw : undefined
  const candidates: unknown[] = [
    parsed.default_author_note,
    parsed.defaultAuthorNote,
    parsed.author_note,
    parsed.authorNote,
    parsed.memory_note,
    parsed.memoryNote,
    tldw?.default_author_note,
    tldw?.defaultAuthorNote,
    tldw?.author_note,
    tldw?.authorNote,
    tldw?.memory_note,
    tldw?.memoryNote
  ]

  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim().length > 0) {
      return candidate.trim()
    }
  }
  return ""
}

const readDefaultAuthorNoteFromRecord = (record: any): string => {
  const directCandidates: unknown[] = [
    record?.default_author_note,
    record?.defaultAuthorNote,
    record?.author_note,
    record?.authorNote,
    record?.memory_note,
    record?.memoryNote
  ]
  for (const candidate of directCandidates) {
    if (typeof candidate === "string" && candidate.trim().length > 0) {
      return candidate.trim()
    }
  }
  return readDefaultAuthorNoteFromExtensions(record?.extensions)
}

type CharacterGenerationSettings = {
  temperature?: number
  top_p?: number
  repetition_penalty?: number
  stop?: string[]
}

const parseGenerationNumber = (
  value: unknown,
  minimum: number,
  maximum: number
): number | undefined => {
  if (typeof value === "boolean" || value === null || value === undefined) {
    return undefined
  }
  const parsed =
    typeof value === "number"
      ? value
      : typeof value === "string"
        ? Number.parseFloat(value)
        : Number.NaN
  if (!Number.isFinite(parsed)) return undefined
  if (parsed < minimum || parsed > maximum) return undefined
  return parsed
}

const normalizeGenerationStopStrings = (value: unknown): string[] | undefined => {
  if (value === null || value === undefined) return undefined
  if (Array.isArray(value)) {
    const normalized = value
      .map((entry) => (typeof entry === "string" ? entry.trim() : ""))
      .filter((entry) => entry.length > 0)
    return normalized.length > 0 ? normalized : undefined
  }
  if (typeof value === "string") {
    const trimmed = value.trim()
    if (!trimmed) return undefined
    try {
      const parsed = JSON.parse(trimmed)
      if (Array.isArray(parsed)) {
        const normalized = parsed
          .map((entry) => (typeof entry === "string" ? entry.trim() : ""))
          .filter((entry) => entry.length > 0)
        if (normalized.length > 0) return normalized
      }
    } catch {
      // fall back to simple splitting
    }
    const normalized = trimmed
      .split(/\r?\n|;/)
      .map((entry) => entry.trim())
      .filter((entry) => entry.length > 0)
    return normalized.length > 0 ? normalized : undefined
  }
  return undefined
}

const resolveGenerationSetting = <T,>(
  containers: Record<string, any>[],
  keys: string[],
  parser: (value: unknown) => T | undefined
): T | undefined => {
  for (const container of containers) {
    for (const key of keys) {
      if (!(key in container)) continue
      const parsed = parser(container[key])
      if (typeof parsed !== "undefined") {
        return parsed
      }
    }
  }
  return undefined
}

const readGenerationSettingsFromRecord = (
  record: any
): CharacterGenerationSettings => {
  const parsed = parseExtensionsObject(record?.extensions)
  const parsedObject = parsed && isPlainObject(parsed) ? parsed : undefined
  const tldw = parsedObject && isPlainObject(parsedObject.tldw)
    ? parsedObject.tldw
    : undefined
  const generation = tldw && isPlainObject(tldw.generation)
    ? tldw.generation
    : undefined

  const containers: Record<string, any>[] = []
  if (generation) containers.push(generation)
  if (parsedObject) containers.push(parsedObject)
  if (isPlainObject(record)) containers.push(record)

  const temperature = resolveGenerationSetting(
    containers,
    ["temperature", "generation_temperature"],
    (value) => parseGenerationNumber(value, 0, 2)
  )
  const topP = resolveGenerationSetting(
    containers,
    ["top_p", "topP", "generation_top_p"],
    (value) => parseGenerationNumber(value, 0, 1)
  )
  const repetitionPenalty = resolveGenerationSetting(
    containers,
    ["repetition_penalty", "repetitionPenalty", "generation_repetition_penalty"],
    (value) => parseGenerationNumber(value, 0, 3)
  )
  const stop = resolveGenerationSetting(
    containers,
    [
      "stop",
      "stop_strings",
      "stopStrings",
      "stop_sequences",
      "stopSequences",
      "generation_stop_strings"
    ],
    normalizeGenerationStopStrings
  )

  const settings: CharacterGenerationSettings = {}
  if (typeof temperature !== "undefined") settings.temperature = temperature
  if (typeof topP !== "undefined") settings.top_p = topP
  if (typeof repetitionPenalty !== "undefined") {
    settings.repetition_penalty = repetitionPenalty
  }
  if (stop && stop.length > 0) settings.stop = stop
  return settings
}

const readGenerationSettingsFromFormValues = (
  values: Record<string, any>
): CharacterGenerationSettings => {
  const settings: CharacterGenerationSettings = {}
  const temperature = parseGenerationNumber(values.generation_temperature, 0, 2)
  const topP = parseGenerationNumber(values.generation_top_p, 0, 1)
  const repetitionPenalty = parseGenerationNumber(
    values.generation_repetition_penalty,
    0,
    3
  )
  const stop = normalizeGenerationStopStrings(values.generation_stop_strings)

  if (typeof temperature !== "undefined") settings.temperature = temperature
  if (typeof topP !== "undefined") settings.top_p = topP
  if (typeof repetitionPenalty !== "undefined") {
    settings.repetition_penalty = repetitionPenalty
  }
  if (stop && stop.length > 0) settings.stop = stop
  return settings
}

const removeLegacyGenerationKeys = (target: Record<string, any>) => {
  delete target.generation
  delete target.top_p
  delete target.topP
  delete target.repetition_penalty
  delete target.repetitionPenalty
  delete target.stop_strings
  delete target.stopStrings
  delete target.stop_sequences
  delete target.stopSequences
}

const applyCharacterMetadataToExtensions = (
  rawExtensions: unknown,
  params: {
    preset: CharacterPromptPresetId
    defaultAuthorNote?: unknown
    generation?: CharacterGenerationSettings
  }
): Record<string, any> | string | undefined => {
  const parsed = parseExtensionsObject(rawExtensions)
  const hadRawString =
    typeof rawExtensions === "string" &&
    rawExtensions.trim().length > 0 &&
    parsed === null

  if (hadRawString) {
    return rawExtensions as string
  }

  let next: Record<string, any> = parsed && parsed !== null ? { ...parsed } : {}

  const tldw = isPlainObject(next.tldw) ? { ...next.tldw } : {}

  if (params.preset === DEFAULT_CHARACTER_PROMPT_PRESET) {
    delete tldw.prompt_preset
    delete tldw.promptPreset
    delete next.prompt_preset
    delete next.promptPreset
  } else {
    tldw.prompt_preset = params.preset
    delete next.prompt_preset
    delete next.promptPreset
  }

  const defaultAuthorNote =
    typeof params.defaultAuthorNote === "string"
      ? params.defaultAuthorNote.trim()
      : ""
  if (defaultAuthorNote) {
    next.default_author_note = defaultAuthorNote
    delete next.defaultAuthorNote
  } else {
    delete next.default_author_note
    delete next.defaultAuthorNote
  }

  const generation = params.generation || {}
  const normalizedGeneration: Record<string, any> = {}
  const normalizedTemp = parseGenerationNumber(generation.temperature, 0, 2)
  const normalizedTopP = parseGenerationNumber(generation.top_p, 0, 1)
  const normalizedRepetition = parseGenerationNumber(
    generation.repetition_penalty,
    0,
    3
  )
  const normalizedStop = normalizeGenerationStopStrings(generation.stop)

  if (typeof normalizedTemp !== "undefined") {
    normalizedGeneration.temperature = normalizedTemp
  }
  if (typeof normalizedTopP !== "undefined") {
    normalizedGeneration.top_p = normalizedTopP
  }
  if (typeof normalizedRepetition !== "undefined") {
    normalizedGeneration.repetition_penalty = normalizedRepetition
  }
  if (normalizedStop && normalizedStop.length > 0) {
    normalizedGeneration.stop = normalizedStop
  }

  removeLegacyGenerationKeys(next)
  if (Object.keys(normalizedGeneration).length > 0) {
    tldw.generation = normalizedGeneration
  } else {
    delete tldw.generation
  }

  if (Object.keys(tldw).length > 0) {
    next.tldw = tldw
  } else {
    delete next.tldw
  }

  if (Object.keys(next).length > 0) {
    return next
  }

  return undefined
}

const hasAdvancedData = (record: any, extensionsValue: string): boolean => {
  const normalizedRecord = {
    ...record,
    extensions: record?.extensions ?? extensionsValue
  }
  const defaultAuthorNote = readDefaultAuthorNoteFromRecord(normalizedRecord)
  const generationSettings = readGenerationSettingsFromRecord(normalizedRecord)
  const hasGenerationSettings =
    typeof generationSettings.temperature !== "undefined" ||
    typeof generationSettings.top_p !== "undefined" ||
    typeof generationSettings.repetition_penalty !== "undefined" ||
    (Array.isArray(generationSettings.stop) &&
      generationSettings.stop.length > 0)
  return !!(
    record.personality ||
    record.scenario ||
    record.post_history_instructions ||
    record.message_example ||
    record.creator_notes ||
    (record.alternate_greetings && record.alternate_greetings.length > 0) ||
    record.creator ||
    record.character_version ||
    hasGenerationSettings ||
    defaultAuthorNote ||
    extensionsValue
  )
}

const buildCharacterPayload = (values: any): Record<string, any> => {
  const payload: Record<string, any> = {
    name: values.name,
    description: values.description,
    personality: values.personality,
    scenario: values.scenario,
    system_prompt: values.system_prompt,
    post_history_instructions: values.post_history_instructions,
    first_message: values.greeting || values.first_message,
    message_example: values.message_example,
    creator_notes: values.creator_notes,
    tags: Array.isArray(values.tags)
      ? values.tags.filter((tag: string) => tag && tag.trim().length > 0)
      : values.tags,
    alternate_greetings: Array.isArray(values.alternate_greetings)
      ? values.alternate_greetings.filter((g: string) => g && g.trim().length > 0)
      : values.alternate_greetings,
    creator: values.creator,
    character_version: values.character_version
  }

  // Extract avatar values from unified avatar field
  if (values.avatar) {
    const avatarValues = extractAvatarValues(values.avatar)
    if (avatarValues.avatar_url) {
      payload.avatar_url = avatarValues.avatar_url
    }
    if (avatarValues.image_base64) {
      payload.image_base64 = avatarValues.image_base64
    }
  } else {
    // Fallback for legacy form structure
    if (values.avatar_url) {
      payload.avatar_url = values.avatar_url
    }
    if (values.image_base64) {
      payload.image_base64 = values.image_base64
    }
  }

  // Keep compatibility with mock server / older deployments
  if (values.greeting) {
    payload.greeting = values.greeting
  }

  Object.keys(payload).forEach((key) => {
    if (key === "extensions") return
    const v = payload[key]
    if (
      typeof v === "undefined" ||
      v === null ||
      (typeof v === "string" && v.trim().length === 0) ||
      (Array.isArray(v) && v.length === 0)
    ) {
      delete payload[key]
    }
  })

  const resolvedPreset = normalizePromptPresetId(values.prompt_preset)
  const generationSettings = readGenerationSettingsFromFormValues(values)
  const mergedExtensions = applyCharacterMetadataToExtensions(values.extensions, {
    preset: resolvedPreset,
    defaultAuthorNote: values.default_author_note,
    generation: generationSettings
  })
  if (typeof mergedExtensions !== "undefined") {
    payload.extensions = mergedExtensions
  }

  return payload
}

type CharactersManagerProps = {
  forwardedNewButtonRef?: React.RefObject<HTMLButtonElement | null>
  autoOpenCreate?: boolean
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
  const [open, setOpen] = React.useState(false)
  const [openEdit, setOpenEdit] = React.useState(false)
  const [editId, setEditId] = React.useState<string | null>(null)
  const [editVersion, setEditVersion] = React.useState<number | null>(null)
  const [createForm] = Form.useForm()
  const [editForm] = Form.useForm()
  const [, setSelectedCharacter] = useSelectedCharacter<any>(null)
  const newButtonRef = React.useRef<HTMLButtonElement | null>(null)
  const lastEditTriggerRef = React.useRef<HTMLButtonElement | null>(null)
  const createNameRef = React.useRef<InputRef>(null)
  const editNameRef = React.useRef<InputRef>(null)
  const searchInputRef = React.useRef<InputRef>(null)
  const [searchTerm, setSearchTerm] = React.useState("")
  const [filterTags, setFilterTags] = React.useState<string[]>([])
  const [matchAllTags, setMatchAllTags] = React.useState(false)
  const [showEditAdvanced, setShowEditAdvanced] = React.useState(false)
  const [showCreateAdvanced, setShowCreateAdvanced] = React.useState(false)
  const [conversationsOpen, setConversationsOpen] = React.useState(false)
  const [conversationCharacter, setConversationCharacter] = React.useState<any | null>(null)
  const [characterChats, setCharacterChats] = React.useState<ServerChatSummary[]>([])
  const [chatsError, setChatsError] = React.useState<string | null>(null)
  const [loadingChats, setLoadingChats] = React.useState(false)
  const [resumingChatId, setResumingChatId] = React.useState<string | null>(null)
  const [createFormDirty, setCreateFormDirty] = React.useState(false)
  const [editFormDirty, setEditFormDirty] = React.useState(false)
  const [debouncedSearchTerm, setDebouncedSearchTerm] = React.useState("")
  const searchDebounceRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)
  const [showCreatePreview, setShowCreatePreview] = React.useState(true)
  const [showEditPreview, setShowEditPreview] = React.useState(true)
  const autoOpenCreateHandledRef = React.useRef(false)
  const [viewMode, setViewMode] = React.useState<'table' | 'gallery'>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('characters-view-mode')
      return saved === 'gallery' ? 'gallery' : 'table'
    }
    return 'table'
  })
  const [sortColumn, setSortColumn] = React.useState<string | null>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('characters-sort-column')
    }
    return null
  })
  const [sortOrder, setSortOrder] = React.useState<'ascend' | 'descend' | null>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('characters-sort-order')
      return saved === 'ascend' || saved === 'descend' ? saved : null
    }
    return null
  })
  const [currentPage, setCurrentPage] = React.useState(1)
  const [importing, setImporting] = React.useState(false)
  const [previewCharacter, setPreviewCharacter] = React.useState<any | null>(null)

  // Inline editing state (M1)
  const [inlineEdit, setInlineEdit] = React.useState<{
    id: string
    field: 'name' | 'description'
    value: string
    originalValue: string
  } | null>(null)
  const inlineEditInputRef = React.useRef<InputRef>(null)

  // Bulk operations state (M5)
  const [selectedCharacterIds, setSelectedCharacterIds] = React.useState<Set<string>>(new Set())
  const [bulkTagModalOpen, setBulkTagModalOpen] = React.useState(false)
  const [bulkTagsToAdd, setBulkTagsToAdd] = React.useState<string[]>([])
  const [bulkOperationLoading, setBulkOperationLoading] = React.useState(false)

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

  const [generationPreviewData, setGenerationPreviewData] = React.useState<GeneratedCharacter | null>(null)
  const [generationPreviewField, setGenerationPreviewField] = React.useState<string | null>(null)
  const [generationPreviewOpen, setGenerationPreviewOpen] = React.useState(false)
  const [generationTargetForm, setGenerationTargetForm] = React.useState<'create' | 'edit'>('create')

  // Template selection state
  const [showTemplates, setShowTemplates] = React.useState(false)

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

  // Keyboard shortcuts (H1)
  const modalOpen = open || openEdit || conversationsOpen || generationPreviewOpen
  useCharacterShortcuts({
    modalOpen,
    onNewCharacter: () => {
      if (!modalOpen) setOpen(true)
    },
    onFocusSearch: () => {
      searchInputRef.current?.focus()
    },
    onCloseModal: () => {
      if (generationPreviewOpen) {
        setGenerationPreviewOpen(false)
      } else if (conversationsOpen) {
        setConversationsOpen(false)
      } else if (openEdit) {
        setOpenEdit(false)
      } else if (open) {
        setOpen(false)
      }
    },
    onTableView: () => setViewMode('table'),
    onGalleryView: () => setViewMode('gallery'),
    enabled: true
  })

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
      // Expose the "New character" button to parent workspaces that may
      // want to focus it (e.g., when coming from a persistence error).
      // The ref object itself is stable; assign its current value once.
      // eslint-disable-next-line no-param-reassign
      ;(forwardedNewButtonRef as any).current = newButtonRef.current
    }
  }, [forwardedNewButtonRef])

  React.useEffect(() => {
    if (!autoOpenCreate) return
    if (autoOpenCreateHandledRef.current) return
    autoOpenCreateHandledRef.current = true
    if (!openEdit && !conversationsOpen) {
      setOpen(true)
    }
  }, [autoOpenCreate, conversationsOpen, openEdit])

  // C8: Debounce search input to reduce API calls
  React.useEffect(() => {
    if (searchDebounceRef.current) {
      clearTimeout(searchDebounceRef.current)
    }
    searchDebounceRef.current = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm)
    }, 300)
    return () => {
      if (searchDebounceRef.current) {
        clearTimeout(searchDebounceRef.current)
        searchDebounceRef.current = null
      }
    }
  }, [searchTerm])

  // Persist view mode preference
  React.useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('characters-view-mode', viewMode)
    }
  }, [viewMode])

  // Persist sort preference
  React.useEffect(() => {
    if (typeof window !== 'undefined') {
      if (sortColumn) {
        localStorage.setItem('characters-sort-column', sortColumn)
      } else {
        localStorage.removeItem('characters-sort-column')
      }
      if (sortOrder) {
        localStorage.setItem('characters-sort-order', sortOrder)
      } else {
        localStorage.removeItem('characters-sort-order')
      }
    }
  }, [sortColumn, sortOrder])

  // Keyboard shortcut: "/" to focus search
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Skip if user is typing in an input/textarea or a modal is open
      const target = e.target as HTMLElement
      const isTyping = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable
      const modalOpen = open || openEdit || conversationsOpen

      if (isTyping || modalOpen) return

      if (e.key === '/') {
        e.preventDefault()
        searchInputRef.current?.focus()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, openEdit, conversationsOpen])

  React.useEffect(() => {
    setCurrentPage(1)
  }, [debouncedSearchTerm, filterTags, matchAllTags])

  // Cleanup pending delete timeout on unmount
  React.useEffect(() => {
    return () => {
      if (undoDeleteRef.current) {
        clearTimeout(undoDeleteRef.current)
      }
    }
  }, [])

  const resolveImportDetail = (error: unknown) => {
    const details = (error as any)?.details
    if (details && typeof details === "object") {
      return (details as any).detail ?? details
    }
    return null
  }

  const importCharacterFile = React.useCallback(
    async (file: File, allowImageOnly = false) => {
      setImporting(true)
      try {
        const response = await tldwClient.importCharacterFile(file, {
          allowImageOnly
        })
        qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
        const message =
          response?.message ||
          t("settings:manageCharacters.import.success", {
            defaultValue: "Character imported successfully"
          })
        notification.success({
          message: t("settings:manageCharacters.import.title", {
            defaultValue: "Import complete"
          }),
          description: message
        })
      } catch (err: any) {
        const detail = resolveImportDetail(err)
        if (
          detail?.code === "missing_character_data" &&
          detail?.can_import_image_only &&
          !allowImageOnly
        ) {
          Modal.confirm({
            title: t("settings:manageCharacters.import.imageOnlyTitle", {
              defaultValue: "No character data detected"
            }),
            content: detail?.message || t("settings:manageCharacters.import.imageOnlyDesc", {
              defaultValue:
                "No character data detected in the image metadata. Import as an image-only character?"
            }),
            okText: t("settings:manageCharacters.import.imageOnlyConfirm", {
              defaultValue: "Import image only"
            }),
            cancelText: t("common:cancel", { defaultValue: "Cancel" }),
            onOk: () => importCharacterFile(file, true)
          })
          return
        }
        notification.error({
          message: t("settings:manageCharacters.import.errorTitle", {
            defaultValue: "Import failed"
          }),
          description:
            err?.message ||
            t("settings:manageCharacters.import.errorDesc", {
              defaultValue: "Unable to import character. Please try again."
            })
        })
      } finally {
        setImporting(false)
      }
    },
    [notification, qc, t]
  )

  const handleImportUpload = React.useCallback(
    async (file: File) => {
      await importCharacterFile(file)
      return false
    },
    [importCharacterFile]
  )

  const hasFilters =
    searchTerm.trim().length > 0 || (filterTags && filterTags.length > 0)

  const {
    setHistory,
    setMessages,
    setHistoryId,
    setServerChatId,
    setServerChatState,
    setServerChatTopic,
    setServerChatClusterId,
    setServerChatSource,
    setServerChatExternalRef
  } = useStoreMessageOption(
    (state) => ({
      setHistory: state.setHistory,
      setMessages: state.setMessages,
      setHistoryId: state.setHistoryId,
      setServerChatId: state.setServerChatId,
      setServerChatState: state.setServerChatState,
      setServerChatTopic: state.setServerChatTopic,
      setServerChatClusterId: state.setServerChatClusterId,
      setServerChatSource: state.setServerChatSource,
      setServerChatExternalRef: state.setServerChatExternalRef
    }),
    shallow
  )

  const characterIdentifier = (record: any): string =>
    String(record?.id ?? record?.slug ?? record?.name ?? "")

  const formatUpdatedLabel = (value?: string | null) => {
    const fallback = t("settings:manageCharacters.conversations.unknownTime", {
      defaultValue: "Unknown"
    })
    let formatted = fallback
    if (value) {
      try {
        formatted = new Date(value).toLocaleString()
      } catch {
        formatted = String(value)
      }
    }
    return t("settings:manageCharacters.conversations.updated", {
      defaultValue: "Updated {{time}}",
      time: formatted
    })
  }

  const {
    data,
    status,
    error,
    refetch
  } = useQuery({
    queryKey: [
      "tldw:listCharacters",
      {
        search: debouncedSearchTerm.trim() || "",
        tags: filterTags.slice().sort(),
        matchAll: matchAllTags
      }
    ],
    queryFn: async () => {
      try {
        await tldwClient.initialize()
        const query = debouncedSearchTerm.trim()
        const tags = filterTags.filter((t) => t.trim().length > 0)
        const hasSearch = query.length > 0
        const hasTags = tags.length > 0

        if (!hasSearch && !hasTags) {
          const list = await tldwClient.listCharacters()
          return Array.isArray(list) ? list : []
        }

        if (hasSearch && !hasTags) {
          const list = await tldwClient.searchCharacters(query)
          return Array.isArray(list) ? list : []
        }

        if (!hasSearch && hasTags) {
          const list = await tldwClient.filterCharactersByTags(tags, {
            match_all: matchAllTags
          })
          return Array.isArray(list) ? list : []
        }

        // When both search and tags are active, use server search then filter client-side by tags
        const searched = await tldwClient.searchCharacters(query)
        const normalized = Array.isArray(searched) ? searched : []
        const filtered = normalized.filter((c: any) => {
          const ct: string[] = Array.isArray(c?.tags)
            ? c.tags
            : typeof c?.tags === "string"
              ? [c.tags]
              : []
          if (ct.length === 0) return false
          if (matchAllTags) {
            return tags.every((tag) => ct.includes(tag))
          }
          return tags.some((tag) => ct.includes(tag))
        })
        return filtered
      } catch (e: any) {
        notification.error({
          message: t("settings:manageCharacters.notification.error", {
            defaultValue: "Error"
          }),
          description:
            e?.message ||
            t("settings:manageCharacters.notification.someError", {
              defaultValue: "Something went wrong. Please try again later"
            })
        })
        throw e
      }
    }
  })

  React.useEffect(() => {
    if (!Array.isArray(data)) return
    const maxPage = Math.max(1, Math.ceil(data.length / DEFAULT_PAGE_SIZE))
    if (currentPage > maxPage) {
      setCurrentPage(maxPage)
    }
  }, [data, currentPage])

  const pagedGalleryData = React.useMemo(() => {
    if (!Array.isArray(data)) return []
    const start = (currentPage - 1) * DEFAULT_PAGE_SIZE
    return data.slice(start, start + DEFAULT_PAGE_SIZE)
  }, [data, currentPage])

  // Tag usage data with counts for M3 improvements
  const tagUsageData = React.useMemo(() => {
    const counts: Record<string, number> = {}
    ;(data || []).forEach((c: any) =>
      (c?.tags || []).forEach((tag: string) => {
        counts[tag] = (counts[tag] || 0) + 1
      })
    )
    // Convert to array and sort by count descending
    return Object.entries(counts)
      .map(([tag, count]) => ({ tag, count }))
      .sort((a, b) => b.count - a.count)
  }, [data])

  const allTags = React.useMemo(() => {
    return tagUsageData.map(({ tag }) => tag)
  }, [tagUsageData])

  // Popular tags (top 5 most used)
  const popularTags = React.useMemo(() => {
    return tagUsageData.slice(0, 5)
  }, [tagUsageData])

  // Tag options with usage counts for Select dropdown
  const tagOptionsWithCounts = React.useMemo(() => {
    return tagUsageData.map(({ tag, count }) => ({
      label: (
        <span className="flex items-center justify-between w-full">
          <span>{tag}</span>
          <span className="text-xs text-text-subtle ml-2">({count})</span>
        </span>
      ),
      value: tag
    }))
  }, [tagUsageData])

  const tagFilterOptions = React.useMemo(
    () =>
      Array.from(
        new Set([...(allTags || []), ...(filterTags || [])].filter(Boolean))
      ).map((tag) => ({ label: tag, value: tag })),
    [allTags, filterTags]
  )

  // Fetch conversation counts for all characters (H3)
  const characterIds = React.useMemo(() => {
    if (!Array.isArray(data)) return []
    return data.map((c: any) => String(c.id || c.slug || c.name)).filter(Boolean)
  }, [data])

  const { data: conversationCounts } = useQuery<Record<string, number>>({
    queryKey: ["tldw:characterConversationCounts", characterIds],
    queryFn: async () => {
      if (characterIds.length === 0) return {}
      await tldwClient.initialize()
      // Fetch all chats once and count by character_id
      const chats = await tldwClient.listChats({ limit: 1000 })
      const counts: Record<string, number> = {}
      for (const chat of chats) {
        const charId = String(chat.character_id ?? "")
        if (charId && characterIds.includes(charId)) {
          counts[charId] = (counts[charId] || 0) + 1
        }
      }
      return counts
    },
    enabled: characterIds.length > 0,
    staleTime: 60 * 1000 // Cache for 1 minute
  })

  const { mutate: createCharacter, isPending: creating } = useMutation({
    mutationFn: async (values: any) =>
      tldwClient.createCharacter(buildCharacterPayload(values)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
      setOpen(false)
      createForm.resetFields()
      clearCreateDraft()
      setShowTemplates(false)
      notification.success({
        message: t("settings:manageCharacters.notification.addSuccess", {
          defaultValue: "Character created"
        })
      })
      setTimeout(() => {
        newButtonRef.current?.focus()
      }, 0)
    },
    onError: (e: any) =>
      notification.error({
        message: t("settings:manageCharacters.notification.error", {
          defaultValue: "Error"
        }),
        description:
          e?.message ||
          t("settings:manageCharacters.notification.someError", {
            defaultValue: "Something went wrong. Please try again later"
          })
      })
  })
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

  React.useEffect(() => {
    if (!conversationsOpen || !conversationCharacter) return
    let cancelled = false
    const load = async () => {
      setLoadingChats(true)
      setChatsError(null)
      setCharacterChats([])
      try {
        await tldwClient.initialize()
        const characterId = characterIdentifier(conversationCharacter)
        const chats = await tldwClient.listChats({
          character_id: characterId || undefined,
          limit: 100,
          ordering: "-updated_at"
        })
        if (!cancelled) {
          const filtered = Array.isArray(chats)
            ? chats.filter(
                (c) =>
                  characterId &&
                  String(c.character_id ?? "") === String(characterId)
              )
            : []
          setCharacterChats(filtered)
        }
      } catch {
        if (!cancelled) {
          setChatsError(
            t("settings:manageCharacters.conversations.error", {
              defaultValue:
                "Unable to load conversations for this character."
            })
          )
        }
      } finally {
        if (!cancelled) {
          setLoadingChats(false)
        }
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [conversationsOpen, conversationCharacter, t])

  const { mutate: updateCharacter, isPending: updating } = useMutation({
    mutationFn: async (values: any) => {
      if (!editId) {
        throw new Error("No character selected for editing")
      }
      return await tldwClient.updateCharacter(
        editId,
        buildCharacterPayload(values),
        editVersion ?? undefined
      )
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
      setOpenEdit(false)
      editForm.resetFields()
      setEditId(null)
      clearEditDraft()
      notification.success({
        message: t("settings:manageCharacters.notification.updatedSuccess", {
          defaultValue: "Character updated"
        })
      })
      setTimeout(() => {
        lastEditTriggerRef.current?.focus()
      }, 0)
    },
    onError: (e: any) =>
      notification.error({
        message: t("settings:manageCharacters.notification.error", {
          defaultValue: "Error"
        }),
        description:
          e?.message ||
          t("settings:manageCharacters.notification.someError", {
            defaultValue: "Something went wrong. Please try again later"
          })
      })
  })

  // Inline edit mutation (M1)
  const { mutate: inlineUpdateCharacter, isPending: inlineUpdating } = useMutation({
    mutationFn: async ({ id, field, value, version }: { id: string; field: 'name' | 'description'; value: string; version?: number }) => {
      return await tldwClient.updateCharacter(id, { [field]: value }, version)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
      setInlineEdit(null)
    },
    onError: (e: any) => {
      notification.error({
        message: t("settings:manageCharacters.notification.error", { defaultValue: "Error" }),
        description: e?.message || t("settings:manageCharacters.notification.someError", { defaultValue: "Something went wrong" })
      })
    }
  })

  // Inline edit handlers (M1)
  const startInlineEdit = React.useCallback((record: any, field: 'name' | 'description') => {
    const id = String(record.id || record.slug || record.name)
    const value = record[field] || ''
    setInlineEdit({ id, field, value, originalValue: value })
    setTimeout(() => inlineEditInputRef.current?.focus(), 0)
  }, [])

  const saveInlineEdit = React.useCallback(() => {
    if (!inlineEdit) return
    const trimmedValue = inlineEdit.value.trim()

    // Validate name field
    if (inlineEdit.field === 'name' && !trimmedValue) {
      notification.warning({
        message: t("settings:manageCharacters.form.name.required", { defaultValue: "Please enter a name" })
      })
      return
    }

    // Skip if unchanged
    if (trimmedValue === inlineEdit.originalValue) {
      setInlineEdit(null)
      return
    }

    // Find the record to get version
    const record = (data || []).find((c: any) =>
      String(c.id || c.slug || c.name) === inlineEdit.id
    )

    inlineUpdateCharacter({
      id: inlineEdit.id,
      field: inlineEdit.field,
      value: trimmedValue,
      version: record?.version
    })
  }, [inlineEdit, inlineUpdateCharacter, data, notification, t])

  const cancelInlineEdit = React.useCallback(() => {
    setInlineEdit(null)
  }, [])

  // Bulk selection helpers (M5)
  const toggleCharacterSelection = React.useCallback((id: string) => {
    setSelectedCharacterIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }, [])

  const selectAllOnPage = React.useCallback(() => {
    if (!Array.isArray(data)) return
    const pageStart = (currentPage - 1) * DEFAULT_PAGE_SIZE
    const pageEnd = pageStart + DEFAULT_PAGE_SIZE
    const pageIds = data.slice(pageStart, pageEnd).map((c: any) => String(c.id || c.slug || c.name))
    setSelectedCharacterIds((prev) => new Set([...prev, ...pageIds]))
  }, [data, currentPage])

  const clearSelection = React.useCallback(() => {
    setSelectedCharacterIds(new Set())
  }, [])

  const selectedCount = selectedCharacterIds.size
  const hasSelection = selectedCount > 0

  // Check if all items on current page are selected
  const allOnPageSelected = React.useMemo(() => {
    if (!Array.isArray(data) || data.length === 0) return false
    const pageStart = (currentPage - 1) * DEFAULT_PAGE_SIZE
    const pageEnd = pageStart + DEFAULT_PAGE_SIZE
    const pageIds = data.slice(pageStart, pageEnd).map((c: any) => String(c.id || c.slug || c.name))
    return pageIds.length > 0 && pageIds.every((id) => selectedCharacterIds.has(id))
  }, [data, currentPage, selectedCharacterIds])

  const someOnPageSelected = React.useMemo(() => {
    if (!Array.isArray(data) || data.length === 0) return false
    const pageStart = (currentPage - 1) * DEFAULT_PAGE_SIZE
    const pageEnd = pageStart + DEFAULT_PAGE_SIZE
    const pageIds = data.slice(pageStart, pageEnd).map((c: any) => String(c.id || c.slug || c.name))
    const selectedOnPage = pageIds.filter((id) => selectedCharacterIds.has(id)).length
    return selectedOnPage > 0 && selectedOnPage < pageIds.length
  }, [data, currentPage, selectedCharacterIds])

  // Clear selection when filters change
  React.useEffect(() => {
    setSelectedCharacterIds(new Set())
  }, [debouncedSearchTerm, filterTags, matchAllTags])

  // Bulk delete handler
  const handleBulkDelete = React.useCallback(async () => {
    if (selectedCharacterIds.size === 0) return

    const selectedChars = (data || []).filter((c: any) =>
      selectedCharacterIds.has(String(c.id || c.slug || c.name))
    )

    const ok = await confirmDanger({
      title: t("settings:manageCharacters.bulk.deleteTitle", {
        defaultValue: "Delete {{count}} characters?",
        count: selectedChars.length
      }),
      content: t("settings:manageCharacters.bulk.deleteContent", {
        defaultValue: "This will delete {{count}} characters. This action cannot be undone.",
        count: selectedChars.length
      }),
      okText: t("common:delete", { defaultValue: "Delete" }),
      cancelText: t("common:cancel", { defaultValue: "Cancel" })
    })

    if (!ok) return

    setBulkOperationLoading(true)
    let successCount = 0
    let failCount = 0

    for (const char of selectedChars) {
      try {
        await tldwClient.deleteCharacter(
          String(char.id || char.slug || char.name),
          char.version
        )
        successCount++
      } catch {
        failCount++
      }
    }

    setBulkOperationLoading(false)
    setSelectedCharacterIds(new Set())
    qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })

    if (failCount === 0) {
      notification.success({
        message: t("settings:manageCharacters.bulk.deleteSuccess", {
          defaultValue: "Deleted {{count}} characters",
          count: successCount
        })
      })
    } else {
      notification.warning({
        message: t("settings:manageCharacters.bulk.deletePartial", {
          defaultValue: "Deleted {{success}} characters, {{fail}} failed",
          success: successCount,
          fail: failCount
        })
      })
    }
  }, [selectedCharacterIds, data, confirmDanger, t, notification, qc])

  // Bulk export handler
  const handleBulkExport = React.useCallback(async () => {
    if (selectedCharacterIds.size === 0) return

    setBulkOperationLoading(true)
    const selectedChars = (data || []).filter((c: any) =>
      selectedCharacterIds.has(String(c.id || c.slug || c.name))
    )

    const exportedCharacters: any[] = []
    let failCount = 0

    for (const char of selectedChars) {
      try {
        const exported = await tldwClient.exportCharacter(
          String(char.id || char.slug || char.name),
          { format: 'v3' }
        )
        exportedCharacters.push(exported)
      } catch {
        failCount++
      }
    }

    if (exportedCharacters.length > 0) {
      // Use the new export utility
      exportCharactersToJSON(exportedCharacters)
    }

    setBulkOperationLoading(false)

    if (failCount === 0) {
      notification.success({
        message: t("settings:manageCharacters.bulk.exportSuccess", {
          defaultValue: "Exported {{count}} characters",
          count: exportedCharacters.length
        })
      })
    } else {
      notification.warning({
        message: t("settings:manageCharacters.bulk.exportPartial", {
          defaultValue: "Exported {{success}} characters, {{fail}} failed",
          success: exportedCharacters.length,
          fail: failCount
        })
      })
    }
  }, [selectedCharacterIds, data, notification, t])

  // Bulk add tags handler
  const handleBulkAddTags = React.useCallback(async () => {
    if (selectedCharacterIds.size === 0 || bulkTagsToAdd.length === 0) return

    setBulkOperationLoading(true)
    const selectedChars = (data || []).filter((c: any) =>
      selectedCharacterIds.has(String(c.id || c.slug || c.name))
    )

    let successCount = 0
    let failCount = 0

    for (const char of selectedChars) {
      try {
        const existingTags: string[] = Array.isArray(char.tags) ? char.tags : []
        const newTags = [...new Set([...existingTags, ...bulkTagsToAdd])]
        await tldwClient.updateCharacter(
          String(char.id || char.slug || char.name),
          { tags: newTags },
          char.version
        )
        successCount++
      } catch {
        failCount++
      }
    }

    setBulkOperationLoading(false)
    setBulkTagModalOpen(false)
    setBulkTagsToAdd([])
    qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })

    if (failCount === 0) {
      notification.success({
        message: t("settings:manageCharacters.bulk.tagSuccess", {
          defaultValue: "Added tags to {{count}} characters",
          count: successCount
        })
      })
    } else {
      notification.warning({
        message: t("settings:manageCharacters.bulk.tagPartial", {
          defaultValue: "Added tags to {{success}} characters, {{fail}} failed",
          success: successCount,
          fail: failCount
        })
      })
    }
  }, [selectedCharacterIds, data, bulkTagsToAdd, notification, t, qc])

  // State for undo delete functionality
  const [pendingDelete, setPendingDelete] = React.useState<{
    character: any
    timeoutId: ReturnType<typeof setTimeout>
  } | null>(null)
  const undoDeleteRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)

  const { mutate: deleteCharacter, isPending: deleting } = useMutation({
    mutationFn: async ({ id, expectedVersion }: { id: string; expectedVersion?: number }) =>
      tldwClient.deleteCharacter(id, expectedVersion),
    onSuccess: (_data, _variables, context: any) => {
      // Don't invalidate immediately - wait for undo timeout
      // The character is already removed from UI optimistically
    },
    onError: (e: any, _variables, context: any) => {
      // Restore character to list on error
      if (context?.character) {
        qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
      }
      notification.error({
        message: t("settings:manageCharacters.notification.error", {
          defaultValue: "Error"
        }),
        description:
          e?.message ||
          t("settings:manageCharacters.notification.someError", {
            defaultValue: "Something went wrong. Please try again later"
          })
      })
    }
  })

  const { mutate: restoreCharacter } = useMutation({
    mutationFn: async ({ id, version }: { id: string; version: number }) =>
      tldwClient.restoreCharacter(id, version),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
      notification.success({
        message: t("settings:manageCharacters.notification.restored", {
          defaultValue: "Character restored"
        })
      })
    },
    onError: (e: any) => {
      qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
      notification.error({
        message: t("settings:manageCharacters.notification.restoreError", {
          defaultValue: "Failed to restore character"
        }),
        description: e?.message
      })
    }
  })

  const [exporting, setExporting] = React.useState<string | null>(null)
  const handleExport = React.useCallback(async (record: any, format: 'json' | 'png' = 'json') => {
    const id = record.id || record.slug || record.name
    const name = record.name || record.title || record.slug || "character"
    try {
      setExporting(id)
      const data = await tldwClient.exportCharacter(id, { format: 'v3' })

      if (format === 'png') {
        // Export as PNG with embedded metadata
        await exportCharacterToPNG(data, {
          avatarUrl: record.avatar_url,
          avatarBase64: record.image_base64,
          filename: `${name.replace(/[^a-z0-9]/gi, '_')}_character.png`
        })
      } else {
        // Export as JSON
        exportCharacterToJSON(data, `${name.replace(/[^a-z0-9]/gi, '_')}_character.json`)
      }

      notification.success({
        message: t("settings:manageCharacters.notification.exported", {
          defaultValue: "Character exported"
        })
      })
    } catch (e: any) {
      notification.error({
        message: t("settings:manageCharacters.notification.exportError", {
          defaultValue: "Failed to export character"
        }),
        description: e?.message
      })
    } finally {
      setExporting(null)
    }
  }, [notification, t])

  // Extracted action handlers for reuse between table and gallery views
  const handleChat = React.useCallback((record: any) => {
    const id = record.id || record.slug || record.name
    setSelectedCharacter({
      id,
      name: record.name || record.title || record.slug,
      system_prompt:
        record.system_prompt ||
        record.systemPrompt ||
        record.instructions ||
        "",
      greeting:
        record.greeting ||
        record.first_message ||
        record.greet ||
        "",
      avatar_url:
        record.avatar_url ||
        validateAndCreateImageDataUrl(record.image_base64) ||
        ""
    })
    navigate("/")
    setTimeout(() => {
      focusComposer()
    }, 0)
  }, [setSelectedCharacter, navigate])

  const handleEdit = React.useCallback((record: any, triggerRef?: HTMLButtonElement | null) => {
    if (triggerRef) {
      lastEditTriggerRef.current = triggerRef
    }
    setEditId(record.id || record.slug || record.name)
    setEditVersion(record?.version ?? null)
    const ex = record.extensions
    const extensionsValue =
      ex && typeof ex === "object" && !Array.isArray(ex)
        ? JSON.stringify(ex, null, 2)
        : typeof ex === "string"
          ? ex
          : ""
    const promptPreset = readPromptPresetFromExtensions(record.extensions)
    const defaultAuthorNote = readDefaultAuthorNoteFromRecord(record)
    const generationSettings = readGenerationSettingsFromRecord(record)
    editForm.setFieldsValue({
      name: record.name,
      description: record.description,
      avatar: createAvatarValue(record.avatar_url, record.image_base64),
      tags: record.tags,
      greeting:
        record.greeting ||
        record.first_message ||
        record.greet,
      system_prompt: record.system_prompt,
      personality: record.personality,
      scenario: record.scenario,
      post_history_instructions:
        record.post_history_instructions,
      message_example: record.message_example,
      creator_notes: record.creator_notes,
      alternate_greetings: normalizeAlternateGreetings(
        record.alternate_greetings
      ),
      creator: record.creator,
      character_version: record.character_version,
      prompt_preset: promptPreset,
      default_author_note: defaultAuthorNote,
      generation_temperature: generationSettings.temperature,
      generation_top_p: generationSettings.top_p,
      generation_repetition_penalty: generationSettings.repetition_penalty,
      generation_stop_strings: generationSettings.stop?.join("\n") || "",
      extensions: extensionsValue
    })
    setShowEditAdvanced(hasAdvancedData(record, extensionsValue))
    setOpenEdit(true)
  }, [editForm])

  const handleDuplicate = React.useCallback((record: any) => {
    const ex = record.extensions
    const extensionsValue =
      ex && typeof ex === "object" && !Array.isArray(ex)
        ? JSON.stringify(ex, null, 2)
        : typeof ex === "string"
          ? ex
          : ""
    const promptPreset = readPromptPresetFromExtensions(record.extensions)
    const defaultAuthorNote = readDefaultAuthorNoteFromRecord(record)
    const generationSettings = readGenerationSettingsFromRecord(record)
    createForm.setFieldsValue({
      name: `${record.name || ""} (copy)`,
      description: record.description,
      avatar: createAvatarValue(record.avatar_url, record.image_base64),
      tags: record.tags,
      greeting:
        record.greeting ||
        record.first_message ||
        record.greet,
      system_prompt: record.system_prompt,
      personality: record.personality,
      scenario: record.scenario,
      post_history_instructions:
        record.post_history_instructions,
      message_example: record.message_example,
      creator_notes: record.creator_notes,
      alternate_greetings: normalizeAlternateGreetings(
        record.alternate_greetings
      ),
      creator: record.creator,
      character_version: record.character_version,
      prompt_preset: promptPreset,
      default_author_note: defaultAuthorNote,
      generation_temperature: generationSettings.temperature,
      generation_top_p: generationSettings.top_p,
      generation_repetition_penalty: generationSettings.repetition_penalty,
      generation_stop_strings: generationSettings.stop?.join("\n") || "",
      extensions: extensionsValue
    })
    setShowCreateAdvanced(hasAdvancedData(record, extensionsValue))
    setOpen(true)

    // Show duplicate notification
    const name = record.name || record.title || record.slug || ""
    notification.info({
      message: t("settings:manageCharacters.notification.duplicated", {
        defaultValue: "Duplicated '{{name}}'. Editing copy.",
        name
      })
    })
  }, [createForm, notification, t])

  const handleDelete = React.useCallback(async (record: any) => {
    const name = record?.name || record?.title || record?.slug || ""
    const characterId = String(record.id || record.slug || record.name)
    const characterVersion = record.version

    // Clear any existing undo timeout
    if (undoDeleteRef.current) {
      clearTimeout(undoDeleteRef.current)
      undoDeleteRef.current = null
    }
    if (pendingDelete?.timeoutId) {
      clearTimeout(pendingDelete.timeoutId)
    }

    // Delete the character (soft delete on backend)
    deleteCharacter({ id: characterId, expectedVersion: characterVersion }, {
      onSuccess: () => {
        // Optimistically remove from UI
        qc.setQueryData(
          ["tldw:listCharacters", { search: debouncedSearchTerm.trim() || "", tags: filterTags.slice().sort(), matchAll: matchAllTags }],
          (old: any[] | undefined) =>
            old?.filter((c: any) => String(c.id || c.slug || c.name) !== characterId) ?? []
        )

        // Create undo timeout - after 10 seconds, finalize delete
        const timeoutId = setTimeout(() => {
          setPendingDelete(null)
          undoDeleteRef.current = null
          // Refresh list to ensure consistency
          qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
        }, 10000)

        undoDeleteRef.current = timeoutId
        setPendingDelete({ character: record, timeoutId })

        // Show undo notification
        notification.info({
          message: t("settings:manageCharacters.notification.deletedWithUndo", {
            defaultValue: "Character '{{name}}' deleted",
            name
          }),
          description: (
            <button
              type="button"
              className="mt-1 text-sm font-medium text-primary hover:underline"
              onClick={() => {
                // Cancel the timeout
                if (undoDeleteRef.current) {
                  clearTimeout(undoDeleteRef.current)
                  undoDeleteRef.current = null
                }
                setPendingDelete(null)

                // Restore the character
                // Version incremented by 1 after soft delete
                restoreCharacter({ id: characterId, version: (characterVersion ?? 0) + 1 })
              }}>
              {t("common:undo", { defaultValue: "Undo" })}
            </button>
          ),
          duration: 10
        })
      }
    })
  }, [deleteCharacter, notification, t, qc, debouncedSearchTerm, filterTags, matchAllTags, pendingDelete, restoreCharacter])

  const handleViewConversations = React.useCallback((record: any) => {
    setConversationCharacter(record)
    setCharacterChats([])
    setChatsError(null)
    setConversationsOpen(true)
  }, [])

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="primary"
            ref={newButtonRef}
            onClick={() => setOpen(true)}>
            {t("settings:manageCharacters.addBtn", {
              defaultValue: "New character"
            })}
          </Button>
          <Upload
            accept=".png,.webp,.json,.md,.txt"
            showUploadList={false}
            beforeUpload={handleImportUpload}
            disabled={importing}>
            <Button loading={importing}>
              {t("settings:manageCharacters.import.button", {
                defaultValue: "Upload character"
              })}
            </Button>
          </Upload>
        </div>
        <div className="flex flex-1 flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
          <Tooltip title={t("settings:manageCharacters.search.shortcut", { defaultValue: "Press / to search" })}>
            <Input
              ref={searchInputRef}
              allowClear
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder={t(
                "settings:manageCharacters.search.placeholder",
                {
                  defaultValue: "Search characters"
                }
              )}
              aria-label={t("settings:manageCharacters.search.label", {
                defaultValue: "Search characters"
              })}
              className="sm:max-w-xs"
              suffix={<span className="text-xs text-text-subtle hidden sm:inline">/</span>}
            />
          </Tooltip>
          <div className="flex flex-col gap-1 sm:flex-row sm:items-center">
            <Select
              mode="multiple"
              allowClear
              className="min-w-[12rem]"
              placeholder={t(
                "settings:manageCharacters.filter.tagsPlaceholder",
                {
                  defaultValue: "Filter by tags"
                }
              )}
              aria-label={t(
                "settings:manageCharacters.filter.tagsAriaLabel",
                {
                  defaultValue: "Filter characters by tags"
                }
              )}
              value={filterTags}
              options={tagFilterOptions}
              onChange={(value) =>
                setFilterTags(
                  (value as string[]).filter((v) => v && v.trim().length > 0)
                )
              }
            />
            <Checkbox
              checked={matchAllTags}
              onChange={(e) => setMatchAllTags(e.target.checked)}>
              {t("settings:manageCharacters.filter.matchAll", {
                defaultValue: "Match all tags"
              })}
            </Checkbox>
            {hasFilters && (
              <Button
                size="small"
                onClick={() => {
                  setSearchTerm("")
                  setFilterTags([])
                  setMatchAllTags(false)
                }}>
                {t("settings:manageCharacters.filter.clear", {
                  defaultValue: "Clear filters"
                })}
              </Button>
            )}
            <Segmented
              value={viewMode}
              onChange={(v) => setViewMode(v as 'table' | 'gallery')}
              options={[
                {
                  value: 'table',
                  icon: <List className="w-4 h-4" />,
                  title: t("settings:manageCharacters.viewMode.table", {
                    defaultValue: "Table view"
                  })
                },
                {
                  value: 'gallery',
                  icon: <LayoutGrid className="w-4 h-4" />,
                  title: t("settings:manageCharacters.viewMode.gallery", {
                    defaultValue: "Gallery view"
                  })
                }
              ]}
              aria-label={t("settings:manageCharacters.viewMode.label", {
                defaultValue: "View mode"
              })}
            />
            {/* Keyboard shortcuts help (H1) */}
            <Tooltip
              title={
                <div className="text-xs space-y-1">
                  <div className="font-medium mb-1">{t("settings:manageCharacters.shortcuts.title", { defaultValue: "Keyboard shortcuts" })}</div>
                  <div><kbd className="px-1 bg-white/20 rounded">N</kbd> {t("settings:manageCharacters.shortcuts.new", { defaultValue: "New character" })}</div>
                  <div><kbd className="px-1 bg-white/20 rounded">/</kbd> {t("settings:manageCharacters.shortcuts.search", { defaultValue: "Focus search" })}</div>
                  <div><kbd className="px-1 bg-white/20 rounded">G</kbd> <kbd className="px-1 bg-white/20 rounded">T</kbd> {t("settings:manageCharacters.shortcuts.tableView", { defaultValue: "Table view" })}</div>
                  <div><kbd className="px-1 bg-white/20 rounded">G</kbd> <kbd className="px-1 bg-white/20 rounded">G</kbd> {t("settings:manageCharacters.shortcuts.galleryView", { defaultValue: "Gallery view" })}</div>
                  <div><kbd className="px-1 bg-white/20 rounded">Esc</kbd> {t("settings:manageCharacters.shortcuts.close", { defaultValue: "Close modal" })}</div>
                </div>
              }
              placement="bottomRight">
              <Button
                type="text"
                size="small"
                icon={<Keyboard className="w-4 h-4" />}
                aria-label={t("settings:manageCharacters.shortcuts.ariaLabel", { defaultValue: "Keyboard shortcuts" })}
              />
            </Tooltip>
          </div>
        </div>
      </div>
      {/* Accessible live region for search results */}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
        role="status"
      >
        {status === "success" &&
          t("settings:manageCharacters.aria.searchResults", {
            defaultValue: "{{count}} characters found",
            count: data?.length ?? 0
          })}
      </div>
      {status === "error" && (
        <div className="rounded-lg border border-danger/30 bg-danger/10 p-4">
          <Alert
            type="error"
            message={t("settings:manageCharacters.loadError.title", {
              defaultValue: "Couldn't load characters"
            })}
            description={
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm text-danger">
                  {(error as any)?.message ||
                    t("settings:manageCharacters.loadError.description", {
                      defaultValue: "Check your connection and try again."
                    })}
                </span>
                <Button size="small" onClick={() => refetch()}>
                  {t("common:retry", { defaultValue: "Retry" })}
                </Button>
              </div>
            }
            showIcon
            className="border-0 bg-transparent p-0"
          />
        </div>
      )}
      {status === "pending" && <Skeleton active paragraph={{ rows: 6 }} />}
      {status === "success" &&
        Array.isArray(data) &&
        data.length === 0 &&
        !hasFilters && (
          <FeatureEmptyState
            title={t("settings:manageCharacters.emptyTitle", {
              defaultValue: "No characters yet"
            })}
            description={t("settings:manageCharacters.emptyDescription", {
              defaultValue:
                "Create a reusable character with a name, description, and system prompt you can chat with."
            })}
            primaryActionLabel={t(
              "settings:manageCharacters.emptyPrimaryCta",
              {
                defaultValue: "Create character"
              }
            )}
            onPrimaryAction={() => setOpen(true)}
          />
        )}
      {status === "success" &&
        Array.isArray(data) &&
        data.length === 0 &&
        hasFilters && (
          <div className="rounded-lg border border-dashed border-border bg-surface p-4 text-sm text-text">
            <div className="flex flex-col gap-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  {t("settings:manageCharacters.filteredEmptyTitle", {
                    defaultValue: "No characters match your filters"
                  })}
                </span>
                <Button
                  size="small"
                  onClick={() => {
                    setSearchTerm("")
                    setFilterTags([])
                    setMatchAllTags(false)
                    refetch()
                  }}>
                  {t("settings:manageCharacters.filter.clear", {
                    defaultValue: "Clear filters"
                  })}
                </Button>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs text-text-subtle">
                {searchTerm.trim() && (
                  <span className="inline-flex items-center gap-1 rounded bg-surface2 px-2 py-0.5">
                    {t("settings:manageCharacters.filter.activeSearch", {
                      defaultValue: "Search: \"{{term}}\"",
                      term: searchTerm.trim()
                    })}
                  </span>
                )}
                {filterTags.length > 0 && (
                  <span className="inline-flex items-center gap-1 rounded bg-surface2 px-2 py-0.5">
                    {t("settings:manageCharacters.filter.activeTags", {
                      defaultValue: "Tags: {{tags}}",
                      tags: filterTags.join(", ")
                    })}
                    {matchAllTags && (
                      <span className="text-text-subtle">
                        ({t("settings:manageCharacters.filter.matchAllLabel", { defaultValue: "all" })})
                      </span>
                    )}
                  </span>
                )}
              </div>
            </div>
          </div>
        )}
      {status === "success" && Array.isArray(data) && data.length > 0 && viewMode === 'table' && (
        <div className="space-y-3">
          {/* Bulk Actions Toolbar (M5) */}
          {hasSelection && (
            <div className="flex items-center gap-3 p-2 bg-surface rounded-lg border border-border">
              <div className="flex items-center gap-2">
                <CheckSquare className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium">
                  {t("settings:manageCharacters.bulk.selected", {
                    defaultValue: "{{count}} selected",
                    count: selectedCount
                  })}
                </span>
              </div>
              <div className="flex items-center gap-2 ml-auto">
                <Tooltip title={t("settings:manageCharacters.bulk.addTags", { defaultValue: "Add tags" })}>
                  <Button
                    size="small"
                    icon={<Tags className="w-4 h-4" />}
                    onClick={() => setBulkTagModalOpen(true)}
                    loading={bulkOperationLoading}>
                    {t("settings:manageCharacters.bulk.addTags", { defaultValue: "Add tags" })}
                  </Button>
                </Tooltip>
                <Tooltip title={t("settings:manageCharacters.bulk.export", { defaultValue: "Export" })}>
                  <Button
                    size="small"
                    icon={<Download className="w-4 h-4" />}
                    onClick={handleBulkExport}
                    loading={bulkOperationLoading}>
                    {t("settings:manageCharacters.bulk.export", { defaultValue: "Export" })}
                  </Button>
                </Tooltip>
                <Tooltip title={t("settings:manageCharacters.bulk.delete", { defaultValue: "Delete" })}>
                  <Button
                    size="small"
                    danger
                    icon={<Trash2 className="w-4 h-4" />}
                    onClick={handleBulkDelete}
                    loading={bulkOperationLoading}>
                    {t("settings:manageCharacters.bulk.delete", { defaultValue: "Delete" })}
                  </Button>
                </Tooltip>
                <Tooltip title={t("settings:manageCharacters.bulk.clearSelection", { defaultValue: "Clear selection" })}>
                  <Button
                    size="small"
                    type="text"
                    icon={<X className="w-4 h-4" />}
                    onClick={clearSelection}
                    aria-label={t("settings:manageCharacters.bulk.clearSelection", { defaultValue: "Clear selection" })}
                  />
                </Tooltip>
              </div>
            </div>
          )}
          <div className="overflow-x-auto">
            <Table
              rowKey={(r: any) => r.id || r.slug || r.name}
              dataSource={data}
              pagination={{
                current: currentPage,
                pageSize: DEFAULT_PAGE_SIZE,
                onChange: (page) => setCurrentPage(page)
              }}
              onChange={(_pagination, _filters, sorter) => {
                // Handle sort state for persistence
                if (!Array.isArray(sorter)) {
                  setSortColumn(sorter.columnKey as string || null)
                  setSortOrder(sorter.order || null)
                }
              }}
              columns={[
              {
                // Bulk selection checkbox column (M5)
                title: (
                  <Checkbox
                    checked={allOnPageSelected}
                    indeterminate={someOnPageSelected}
                    onChange={(e) => {
                      if (e.target.checked) {
                        selectAllOnPage()
                      } else {
                        // Deselect all on current page
                        if (!Array.isArray(data)) return
                        const pageStart = (currentPage - 1) * DEFAULT_PAGE_SIZE
                        const pageEnd = pageStart + DEFAULT_PAGE_SIZE
                        const pageIds = data.slice(pageStart, pageEnd).map((c: any) => String(c.id || c.slug || c.name))
                        setSelectedCharacterIds((prev) => {
                          const next = new Set(prev)
                          pageIds.forEach((id) => next.delete(id))
                          return next
                        })
                      }
                    }}
                    aria-label={t("settings:manageCharacters.bulk.selectAll", { defaultValue: "Select all on page" })}
                  />
                ),
                key: "selection",
                width: 48,
                render: (_: any, record: any) => {
                  const recordId = String(record.id || record.slug || record.name)
                  return (
                    <Checkbox
                      checked={selectedCharacterIds.has(recordId)}
                      onChange={(e) => {
                        e.stopPropagation()
                        toggleCharacterSelection(recordId)
                      }}
                      aria-label={t("settings:manageCharacters.bulk.selectOne", {
                        defaultValue: "Select {{name}}",
                        name: record.name || recordId
                      })}
                    />
                  )
                }
              },
              {
                title: (
                  <span className="sr-only">
                    {t("settings:manageCharacters.columns.avatar", {
                      defaultValue: "Avatar"
                    })}
                  </span>
                ),
              key: "avatar",
              width: 48,
              render: (_: any, record: any) =>
                record?.avatar_url ? (
                  <img
                    src={record.avatar_url}
                    className="w-6 h-6 rounded-full"
                    alt={
                      record?.name
                        ? t("settings:manageCharacters.avatarAltWithName", {
                            defaultValue: "Avatar of {{name}}",
                            name: record.name
                          })
                        : t("settings:manageCharacters.avatarAlt", {
                            defaultValue: "User avatar"
                          })
                    }
                  />
                ) : (
                  <UserCircle2 className="w-5 h-5" />
                )
            },
            {
              title: t("settings:manageCharacters.columns.name", {
                defaultValue: "Name"
              }),
              dataIndex: "name",
              key: "name",
              sorter: (a: any, b: any) => (a.name || "").localeCompare(b.name || ""),
              sortDirections: ["ascend", "descend"] as const,
              sortOrder: sortColumn === "name" ? sortOrder : undefined,
              defaultSortOrder: sortColumn === "name" ? sortOrder ?? undefined : undefined,
              render: (v: string, record: any) => {
                const recordId = String(record.id || record.slug || record.name)
                const isEditing = inlineEdit?.id === recordId && inlineEdit?.field === 'name'

                if (isEditing) {
                  return (
                    <Input
                      ref={inlineEditInputRef}
                      size="small"
                      value={inlineEdit.value}
                      onChange={(e) => setInlineEdit({ ...inlineEdit, value: e.target.value })}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault()
                          saveInlineEdit()
                        } else if (e.key === 'Escape') {
                          cancelInlineEdit()
                        }
                      }}
                      onBlur={saveInlineEdit}
                      disabled={inlineUpdating}
                      className="max-w-[200px]"
                    />
                  )
                }

                return (
                  <Tooltip title={t("settings:manageCharacters.table.doubleClickEdit", { defaultValue: "Double-click to edit" })}>
                    <span
                      className="line-clamp-1 cursor-text hover:bg-surface-hover rounded px-1 -mx-1"
                      title={v || undefined}
                      onDoubleClick={() => startInlineEdit(record, 'name')}
                    >
                      {truncateText(v, MAX_NAME_LENGTH)}
                    </span>
                  </Tooltip>
                )
              }
            },
            {
              title: t("settings:manageCharacters.columns.description", {
                defaultValue: "Description"
              }),
              dataIndex: "description",
              key: "description",
              render: (v: string, record: any) => {
                const recordId = String(record.id || record.slug || record.name)
                const isEditing = inlineEdit?.id === recordId && inlineEdit?.field === 'description'

                if (isEditing) {
                  return (
                    <Input
                      ref={inlineEditInputRef}
                      size="small"
                      value={inlineEdit.value}
                      onChange={(e) => setInlineEdit({ ...inlineEdit, value: e.target.value })}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault()
                          saveInlineEdit()
                        } else if (e.key === 'Escape') {
                          cancelInlineEdit()
                        }
                      }}
                      onBlur={saveInlineEdit}
                      disabled={inlineUpdating}
                      className="max-w-[250px]"
                    />
                  )
                }

                return (
                  <Tooltip title={t("settings:manageCharacters.table.doubleClickEdit", { defaultValue: "Double-click to edit" })}>
                    <span
                      className="line-clamp-1 cursor-text hover:bg-surface-hover rounded px-1 -mx-1"
                      title={v || undefined}
                      onDoubleClick={() => startInlineEdit(record, 'description')}
                    >
                      {v ? (
                        truncateText(v, MAX_DESCRIPTION_LENGTH)
                      ) : (
                        <span className="text-text-subtle">
                          {t("settings:manageCharacters.table.noDescription", {
                            defaultValue: "—"
                          })}
                        </span>
                      )}
                    </span>
                  </Tooltip>
                )
              }
            },
            {
              title: t("settings:manageCharacters.tags.label", {
                defaultValue: "Tags"
              }),
              dataIndex: "tags",
              key: "tags",
              render: (tags: string[]) => {
                const all = tags || []
                const visible = all.slice(0, MAX_TAGS_DISPLAYED)
                const hasMore = all.length > MAX_TAGS_DISPLAYED
                const hiddenCount = all.length - MAX_TAGS_DISPLAYED
                const hiddenTags = all.slice(MAX_TAGS_DISPLAYED)
                return (
                  <div className="flex flex-wrap gap-1">
                    {visible.map((tag: string, index: number) => (
                      <Tag key={`${tag}-${index}`}>
                        {truncateText(tag, MAX_TAG_LENGTH)}
                      </Tag>
                    ))}
                    {hasMore && (
                      <Tooltip
                        title={
                          <div>
                            <div className="font-medium mb-1">
                              {t("settings:manageCharacters.tags.moreCount", {
                                defaultValue: "+{{count}} more tags",
                                count: hiddenCount
                              })}
                            </div>
                            <div className="text-xs">
                              {hiddenTags.join(", ")}
                            </div>
                          </div>
                        }
                      >
                        <span className="text-xs text-text-subtle cursor-help">
                          +{hiddenCount}
                        </span>
                      </Tooltip>
                    )}
                  </div>
                )
              }
            },
            {
              title: t("settings:manageCharacters.columns.conversations", {
                defaultValue: "Chats"
              }),
              key: "conversations",
              width: 70,
              align: "center" as const,
              sorter: (a: any, b: any) => {
                const aId = String(a.id || a.slug || a.name)
                const bId = String(b.id || b.slug || b.name)
                const aCount = conversationCounts?.[aId] || 0
                const bCount = conversationCounts?.[bId] || 0
                return aCount - bCount
              },
              render: (_: any, record: any) => {
                const charId = String(record.id || record.slug || record.name)
                const count = conversationCounts?.[charId] || 0
                return count > 0 ? (
                  <Tooltip
                    title={t("settings:manageCharacters.gallery.conversationCount", {
                      defaultValue: "{{count}} conversation(s)",
                      count
                    })}
                  >
                    <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                      <MessageCircle className="h-3 w-3" />
                      {count > 99 ? '99+' : count}
                    </span>
                  </Tooltip>
                ) : (
                  <span className="text-text-subtle">—</span>
                )
              }
            },
            {
              title: t("settings:manageCharacters.columns.actions", {
                defaultValue: "Actions"
              }),
              key: "actions",
              render: (_: any, record: any) => {
                const chatLabel = t("settings:manageCharacters.actions.chat", {
                  defaultValue: "Chat"
                })
                const editLabel = t(
                  "settings:manageCharacters.actions.edit",
                  {
                    defaultValue: "Edit"
                  }
                )
                const deleteLabel = t(
                  "settings:manageCharacters.actions.delete",
                  {
                    defaultValue: "Delete"
                  }
                )
                const duplicateLabel = t(
                  "settings:manageCharacters.actions.duplicate",
                  {
                    defaultValue: "Duplicate"
                  }
                )
                const exportLabel = t(
                  "settings:manageCharacters.actions.export",
                  {
                    defaultValue: "Export"
                  }
                )
                const name = record?.name || record?.title || record?.slug || ""
                return (
                  <div className="flex flex-wrap items-center gap-2">
                    {/* Primary: Chat */}
                    <Tooltip
                      title={chatLabel}>
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 rounded-md border border-transparent px-2 py-1 text-primary transition hover:border-primary/30 hover:bg-primary/10 focus:outline-none focus:ring-2 focus:ring-focus focus:ring-offset-1 focus:ring-offset-bg"
                        aria-label={t("settings:manageCharacters.aria.chatWith", {
                          defaultValue: "Chat as {{name}}",
                          name
                        })}
                        onClick={() => {
                          const id = record.id || record.slug || record.name
                          setSelectedCharacter({
                            id,
                            name: record.name || record.title || record.slug,
                            system_prompt:
                              record.system_prompt ||
                              record.systemPrompt ||
                              record.instructions ||
                              "",
                            greeting:
                              record.greeting ||
                              record.first_message ||
                              record.greet ||
                              "",
                            avatar_url:
                              record.avatar_url ||
                              validateAndCreateImageDataUrl(record.image_base64) ||
                              ""
                          })
                          navigate("/")
                          setTimeout(() => {
                            focusComposer()
                          }, 0)
                        }}>
                        <MessageCircle className="w-4 h-4" />
                        <span className="hidden sm:inline text-xs font-medium">
                          {chatLabel}
                        </span>
                      </button>
                    </Tooltip>
                    {/* Primary: Edit */}
                    <Tooltip
                      title={editLabel}>
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 rounded-md border border-transparent px-2 py-1 text-text-muted transition hover:border-border hover:bg-surface2 focus:outline-none focus:ring-2 focus:ring-focus focus:ring-offset-1 focus:ring-offset-bg"
                        aria-label={t("settings:manageCharacters.aria.edit", {
                          defaultValue: "Edit character {{name}}",
                          name
                        })}
                        onClick={(e) => {
                          handleEdit(record, e.currentTarget)
                        }}>
                        <Pen className="w-4 h-4" />
                        <span className="hidden sm:inline text-xs font-medium">
                          {editLabel}
                        </span>
                      </button>
                    </Tooltip>
                    {/* Primary: Delete */}
                    <Tooltip
                      title={deleteLabel}>
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 rounded-md border border-transparent px-2 py-1 text-danger transition hover:border-danger/30 hover:bg-danger/10 focus:outline-none focus:ring-2 focus:ring-danger focus:ring-offset-1 focus:ring-offset-bg disabled:cursor-not-allowed disabled:opacity-60"
                        aria-label={t("settings:manageCharacters.aria.delete", {
                          defaultValue: "Delete character {{name}}",
                          name
                        })}
                        disabled={deleting}
                        onClick={async () => {
                          const ok = await confirmDanger({
                            title: t("common:confirmTitle", {
                              defaultValue: "Please confirm"
                            }),
                            content: t(
                              "settings:manageCharacters.confirm.delete",
                              {
                                defaultValue:
                                  "Are you sure you want to delete this character? This action cannot be undone."
                              }
                            ),
                            okText: t("common:delete", { defaultValue: "Delete" }),
                            cancelText: t("common:cancel", {
                              defaultValue: "Cancel"
                            })
                          })
                          if (ok) {
                            handleDelete(record)
                          }
                        }}>
                        <Trash2 className="w-4 h-4" />
                        <span className="hidden sm:inline text-xs font-medium">
                          {deleteLabel}
                        </span>
                      </button>
                    </Tooltip>
                    {/* Overflow: View Conversations, Duplicate, Export */}
                    <Dropdown
                      menu={{
                        items: [
                          {
                            key: 'conversations',
                            icon: <History className="w-4 h-4" />,
                            label: t("settings:manageCharacters.actions.viewConversations", {
                              defaultValue: "View conversations"
                            }),
                            onClick: () => {
                              setConversationCharacter(record)
                              setCharacterChats([])
                              setChatsError(null)
                              setConversationsOpen(true)
                            }
                          },
                          {
                            key: 'duplicate',
                            icon: <Copy className="w-4 h-4" />,
                            label: duplicateLabel,
                            onClick: () => handleDuplicate(record)
                          },
                          { type: 'divider' as const },
                          {
                            key: 'export-json',
                            icon: <Download className="w-4 h-4" />,
                            label: t("settings:manageCharacters.export.json", { defaultValue: "Export as JSON" }),
                            disabled: exporting === (record.id || record.slug || record.name),
                            onClick: () => handleExport(record, 'json')
                          },
                          {
                            key: 'export-png',
                            icon: <Download className="w-4 h-4" />,
                            label: t("settings:manageCharacters.export.png", { defaultValue: "Export as PNG (with metadata)" }),
                            disabled: exporting === (record.id || record.slug || record.name),
                            onClick: () => handleExport(record, 'png')
                          }
                        ]
                      }}
                      trigger={['click']}
                      placement="bottomRight">
                      <Tooltip title={t("settings:manageCharacters.actions.more", { defaultValue: "More actions" })}>
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 rounded-md border border-transparent px-2 py-1 text-text-muted transition hover:border-border hover:bg-surface2 focus:outline-none focus:ring-2 focus:ring-focus focus:ring-offset-1 focus:ring-offset-bg"
                          aria-label={t("settings:manageCharacters.aria.moreActions", {
                            defaultValue: "More actions for {{name}}",
                            name
                          })}>
                          <MoreHorizontal className="w-4 h-4" />
                        </button>
                      </Tooltip>
                    </Dropdown>
                  </div>
                )
              }
            }
          ]}
          />
          </div>
        </div>
      )}

      {/* Gallery View */}
      {status === "success" && Array.isArray(data) && data.length > 0 && viewMode === 'gallery' && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
            {pagedGalleryData.map((character: any) => {
              const charId = String(character.id || character.slug || character.name)
              return (
                <CharacterGalleryCard
                  key={charId}
                  character={character}
                  onClick={() => setPreviewCharacter(character)}
                  conversationCount={conversationCounts?.[charId]}
                />
              )
            })}
          </div>
          {data.length > DEFAULT_PAGE_SIZE && (
            <div className="flex justify-end">
              <Pagination
                current={currentPage}
                pageSize={DEFAULT_PAGE_SIZE}
                total={data.length}
                onChange={(page) => setCurrentPage(page)}
                showSizeChanger={false}
              />
            </div>
          )}
        </div>
      )}

      {/* Character Preview Popup for Gallery View */}
      <CharacterPreviewPopup
        character={previewCharacter}
        open={!!previewCharacter}
        onClose={() => setPreviewCharacter(null)}
        onChat={() => {
          if (previewCharacter) {
            handleChat(previewCharacter)
            setPreviewCharacter(null)
          }
        }}
        onEdit={() => {
          if (previewCharacter) {
            handleEdit(previewCharacter)
            setPreviewCharacter(null)
          }
        }}
        onDuplicate={() => {
          if (previewCharacter) {
            handleDuplicate(previewCharacter)
            setPreviewCharacter(null)
          }
        }}
        onExport={async (format?: 'json' | 'png') => {
          if (previewCharacter) {
            await handleExport(previewCharacter, format || 'json')
          }
        }}
        onDelete={async () => {
          if (previewCharacter) {
            await handleDelete(previewCharacter)
            setPreviewCharacter(null)
          }
        }}
        onViewConversations={() => {
          if (previewCharacter) {
            handleViewConversations(previewCharacter)
            setPreviewCharacter(null)
          }
        }}
        deleting={deleting}
        exporting={!!exporting && exporting === (previewCharacter?.id || previewCharacter?.slug || previewCharacter?.name)}
      />

      <Modal
        title={
          conversationCharacter
            ? t("settings:manageCharacters.conversations.title", {
                defaultValue: "Conversations for {{name}}",
                name:
                  conversationCharacter.name ||
                  conversationCharacter.title ||
                  conversationCharacter.slug ||
                  ""
              })
            : t("settings:manageCharacters.conversations.titleGeneric", {
                defaultValue: "Character conversations"
              })
        }
        open={conversationsOpen}
        onCancel={() => {
          setConversationsOpen(false)
          setConversationCharacter(null)
          setCharacterChats([])
          setChatsError(null)
          setResumingChatId(null)
        }}
        footer={null}
        destroyOnHidden>
        <div className="space-y-3">
          <p className="text-sm text-text-muted">
            {t("settings:manageCharacters.conversations.subtitle", {
              defaultValue:
                "Select a conversation to continue as this character."
            })}
          </p>
          {chatsError && (
            <Alert
              type="error"
              showIcon
              message={chatsError}
              action={
                <Button
                  size="small"
                  onClick={async () => {
                    if (!conversationCharacter) return
                    setChatsError(null)
                    setLoadingChats(true)
                    setCharacterChats([])
                    try {
                      await tldwClient.initialize()
                      const characterId = characterIdentifier(conversationCharacter)
                      const chats = await tldwClient.listChats({
                        character_id: characterId || undefined,
                        limit: 100,
                        ordering: "-updated_at"
                      })
                      const filtered = Array.isArray(chats)
                        ? chats.filter(
                            (c) =>
                              characterId &&
                              String(c.character_id ?? "") === String(characterId)
                          )
                        : []
                      setCharacterChats(filtered)
                    } catch {
                      setChatsError(
                        t("settings:manageCharacters.conversations.error", {
                          defaultValue:
                            "Unable to load conversations for this character."
                        })
                      )
                    } finally {
                      setLoadingChats(false)
                    }
                  }}>
                  {t("common:retry", { defaultValue: "Retry" })}
                </Button>
              }
            />
          )}
          {loadingChats && <Skeleton active title paragraph={{ rows: 4 }} />}
          {!loadingChats && !chatsError && (
            <>
              {characterChats.length === 0 ? (
                <div className="rounded-md border border-dashed border-border bg-surface2 p-3 text-sm text-text-muted">
                  {t("settings:manageCharacters.conversations.empty", {
                    defaultValue: "No conversations found for this character yet."
                  })}
                </div>
              ) : (
                <div className="space-y-2">
                  {characterChats.map((chat, index) => (
                    <div
                      key={chat.id}
                      className={`flex items-start justify-between gap-3 rounded-md border p-3 shadow-sm ${
                        index === 0
                          ? "border-primary/30 bg-primary/10"
                          : "border-border bg-surface"
                      }`}>
                      <div className="min-w-0 space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-text truncate">
                            {chat.title ||
                              t("settings:manageCharacters.conversations.untitled", {
                                defaultValue: "Untitled"
                              })}
                          </span>
                          {index === 0 && (
                            <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                              {t("settings:manageCharacters.conversations.mostRecent", {
                                defaultValue: "Most recent"
                              })}
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-text-subtle">
                          {formatUpdatedLabel(chat.updated_at || chat.created_at)}
                        </div>
                        <div className="flex flex-wrap items-center gap-2 text-xs text-text-subtle">
                          <span className="inline-flex items-center rounded-full bg-surface2 px-2 py-0.5 lowercase text-text-muted">
                            {(chat.state as string) || "in-progress"}
                          </span>
                          {chat.topic_label && (
                            <span
                              className="truncate max-w-[14rem]"
                              title={String(chat.topic_label)}
                            >
                              {String(chat.topic_label)}
                            </span>
                          )}
                        </div>
                      </div>
                      <Tooltip
                        title={t("settings:manageCharacters.conversations.resumeTooltip", {
                          defaultValue: "Load chat history and continue this conversation"
                        })}>
                        <Button
                          type="primary"
                          size="small"
                          loading={resumingChatId === chat.id}
                          onClick={async () => {
                          if (!conversationCharacter) return
                          setResumingChatId(chat.id)
                          try {
                            await tldwClient.initialize()

                            const assistantName =
                              conversationCharacter.name ||
                              conversationCharacter.title ||
                              conversationCharacter.slug ||
                              t("common:assistant", {
                                defaultValue: "Assistant"
                              })

                            const messages = await tldwClient.listChatMessages(
                              chat.id,
                              { include_deleted: "false" } as any
                            )
                            const history = messages.map((m) => ({
                              role: normalizeChatRole(m.role),
                              content: m.content
                            }))
                            const mappedMessages = messages.map((m) => {
                              const createdAt = Date.parse(m.created_at)
                              const normalized = normalizeChatRole(m.role)
                              return {
                                createdAt: Number.isNaN(createdAt)
                                  ? undefined
                                  : createdAt,
                                isBot: normalized === "assistant",
                                role: normalized,
                                name:
                                  normalized === "assistant"
                                    ? assistantName
                                    : normalized === "system"
                                      ? t("common:system", {
                                          defaultValue: "System"
                                        })
                                      : t("common:you", { defaultValue: "You" }),
                                message: m.content,
                                sources: [],
                                images: [],
                                serverMessageId: m.id,
                                serverMessageVersion: m.version
                              }
                            })

                            const id = characterIdentifier(conversationCharacter)
                            setSelectedCharacter({
                              id,
                              name:
                                conversationCharacter.name ||
                                conversationCharacter.title ||
                                conversationCharacter.slug,
                              system_prompt:
                                conversationCharacter.system_prompt ||
                                conversationCharacter.systemPrompt ||
                                conversationCharacter.instructions ||
                                "",
                              greeting:
                                conversationCharacter.greeting ||
                                conversationCharacter.first_message ||
                                conversationCharacter.greet ||
                                "",
                              avatar_url:
                                conversationCharacter.avatar_url ||
                                validateAndCreateImageDataUrl(
                                  conversationCharacter.image_base64
                                ) ||
                                ""
                            })

                            setHistoryId(null)
                            setServerChatId(chat.id)
                            setServerChatState(
                              (chat as any)?.state ??
                                (chat as any)?.conversation_state ??
                                "in-progress"
                            )
                            setServerChatTopic(
                              (chat as any)?.topic_label ?? null
                            )
                            setServerChatClusterId(
                              (chat as any)?.cluster_id ?? null
                            )
                            setServerChatSource(
                              (chat as any)?.source ?? null
                            )
                            setServerChatExternalRef(
                              (chat as any)?.external_ref ?? null
                            )
                            setHistory(history)
                            setMessages(mappedMessages)
                            updatePageTitle(chat.title)
                            setConversationsOpen(false)
                            setConversationCharacter(null)
                            navigate("/")
                            setTimeout(() => {
                              focusComposer()
                            }, 0)
                          } catch (e) {
                            setChatsError(
                              t("settings:manageCharacters.conversations.error", {
                                defaultValue:
                                  "Unable to load conversations for this character."
                              })
                            )
                          } finally {
                            setResumingChatId(null)
                          }
                        }}>
                          {t("settings:manageCharacters.conversations.resume", {
                            defaultValue: "Continue chat"
                          })}
                        </Button>
                      </Tooltip>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </Modal>

      <Modal
        title={t("settings:manageCharacters.modal.addTitle", {
          defaultValue: "New character"
        })}
        open={open}
        onCancel={() => {
          if (createFormDirty) {
            Modal.confirm({
              title: t("settings:manageCharacters.modal.unsavedTitle", {
                defaultValue: "Discard changes?"
              }),
              content: t("settings:manageCharacters.modal.unsavedContent", {
                defaultValue: "You have unsaved changes. Are you sure you want to close?"
              }),
              okText: t("common:discard", { defaultValue: "Discard" }),
              cancelText: t("common:cancel", { defaultValue: "Cancel" }),
              onOk: () => {
                setOpen(false)
                createForm.resetFields()
                setCreateFormDirty(false)
                setShowCreateAdvanced(false)
                setTimeout(() => {
                  newButtonRef.current?.focus()
                }, 0)
              }
            })
          } else {
            setOpen(false)
            createForm.resetFields()
            setShowCreateAdvanced(false)
            setTimeout(() => {
              newButtonRef.current?.focus()
            }, 0)
          }
        }}
        footer={null}>
        <p className="text-sm text-text-muted mb-4">
          {t("settings:manageCharacters.modal.description", {
            defaultValue: "Define a reusable character you can chat with in the sidebar."
          })}
        </p>

        {/* Draft Recovery Banner (H4) */}
        {hasCreateDraft && createDraftData && (
          <Alert
            type="info"
            showIcon
            className="mb-4"
            message={
              <span>
                {t("settings:manageCharacters.draft.found", {
                  defaultValue: "Resume unsaved character?"
                })}
                {createDraftData.formData?.name && (
                  <strong className="ml-1">"{createDraftData.formData.name}"</strong>
                )}
                <span className="text-text-muted ml-1">
                  ({formatDraftAge(createDraftData.savedAt)})
                </span>
              </span>
            }
            action={
              <div className="flex gap-2">
                <Button
                  size="small"
                  type="primary"
                  onClick={() => {
                    const draft = applyCreateDraft()
                    if (draft) {
                      createForm.setFieldsValue(draft)
                      setCreateFormDirty(true)
                      if (hasAdvancedData(draft, draft.extensions || '')) {
                        setShowCreateAdvanced(true)
                      }
                    }
                  }}>
                  {t("settings:manageCharacters.draft.restore", { defaultValue: "Restore" })}
                </Button>
                <Button
                  size="small"
                  onClick={dismissCreateDraft}>
                  {t("settings:manageCharacters.draft.discard", { defaultValue: "Discard" })}
                </Button>
              </div>
            }
          />
        )}

        {/* Template Selection (M4) */}
        {!showTemplates ? (
          <div className="mb-4">
            <Button
              type="link"
              size="small"
              className="p-0"
              onClick={() => setShowTemplates(true)}>
              {t("settings:manageCharacters.templates.startFrom", {
                defaultValue: "Start from a template..."
              })}
            </Button>
          </div>
        ) : (
          <div className="mb-4 p-3 bg-surface rounded-lg border border-border">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm font-medium">
                {t("settings:manageCharacters.templates.title", {
                  defaultValue: "Choose a template"
                })}
              </span>
              <Button
                type="link"
                size="small"
                onClick={() => setShowTemplates(false)}>
                {t("common:cancel", { defaultValue: "Cancel" })}
              </Button>
            </div>
            <div className="grid grid-cols-1 gap-2">
              {CHARACTER_TEMPLATES.map((template) => (
                <button
                  key={template.id}
                  type="button"
                  className="text-left p-2 rounded border border-border hover:border-primary hover:bg-surface-hover transition-colors"
                  onClick={() => {
                    createForm.setFieldsValue({
                      name: template.name,
                      description: template.description,
                      system_prompt: template.system_prompt,
                      greeting: template.greeting,
                      tags: template.tags
                    })
                    setCreateFormDirty(true)
                    setShowTemplates(false)
                    notification.info({
                      message: t("settings:manageCharacters.templates.applied", {
                        defaultValue: "Template applied"
                      }),
                      description: t("settings:manageCharacters.templates.appliedDesc", {
                        defaultValue: "You can customize all fields before saving."
                      })
                    })
                  }}>
                  <div className="font-medium text-sm">{template.name}</div>
                  <div className="text-xs text-text-muted">{template.description}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* AI Character Generation Panel */}
        <GenerateCharacterPanel
          isGenerating={isGenerating && generatingField === 'all'}
          error={generationError}
          onGenerate={handleGenerateFullCharacter}
          onCancel={cancelGeneration}
          onClearError={clearGenerationError}
        />

        <Form
          layout="vertical"
          form={createForm}
          initialValues={{ prompt_preset: DEFAULT_CHARACTER_PROMPT_PRESET }}
          className="space-y-3"
          onValuesChange={(_, allValues) => {
            setCreateFormDirty(true)
            saveCreateDraft(allValues)
          }}
          onFinish={(v) => {
            createCharacter(v)
            clearCreateDraft()
            setCreateFormDirty(false)
            setShowCreateAdvanced(false)
          }}>
          {/* Field order: Name → System Prompt (required) → Greeting → Description → Tags → Avatar */}
          <Form.Item
            name="name"
            label={
              <span>
                {t("settings:manageCharacters.form.name.label", {
                  defaultValue: "Name"
                })}
                <span className="text-danger ml-0.5">*</span>
                <GenerateFieldButton
                  isGenerating={generatingField === 'name'}
                  disabled={isGenerating}
                  onClick={() => handleGenerateField('name', createForm, 'create')}
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
              }
            ]}>
            <Input
              ref={createNameRef}
              placeholder={t(
                "settings:manageCharacters.form.name.placeholder",
                { defaultValue: "e.g. Writing coach" }
              )}
            />
          </Form.Item>
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
                  isGenerating={generatingField === 'system_prompt'}
                  disabled={isGenerating}
                  onClick={() => handleGenerateField('system_prompt', createForm, 'create')}
                />
              </span>
            }
            help={t(
              "settings:manageCharacters.form.systemPrompt.help",
              {
                defaultValue:
                  "Describe how this character should respond, including role, tone, and constraints. (max 2000 characters)"
              }
            )}
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
            name="greeting"
            label={
              <span>
                {t("settings:manageCharacters.form.greeting.label", {
                  defaultValue: "Greeting message (optional)"
                })}
                <GenerateFieldButton
                  isGenerating={generatingField === 'first_message'}
                  disabled={isGenerating}
                  onClick={() => handleGenerateField('first_message', createForm, 'create')}
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
          <Form.Item
            name="description"
            label={
              <span>
                {t("settings:manageCharacters.form.description.label", {
                  defaultValue: "Description"
                })}
                <GenerateFieldButton
                  isGenerating={generatingField === 'description'}
                  disabled={isGenerating}
                  onClick={() => handleGenerateField('description', createForm, 'create')}
                />
              </span>
            }>
            <Input
              placeholder={t(
                "settings:manageCharacters.form.description.placeholder",
                { defaultValue: "Short description" }
              )}
            />
          </Form.Item>
          <Form.Item
            name="tags"
            label={
              <span>
                {t("settings:manageCharacters.tags.label", {
                  defaultValue: "Tags"
                })}
                <GenerateFieldButton
                  isGenerating={generatingField === 'tags'}
                  disabled={isGenerating}
                  onClick={() => handleGenerateField('tags', createForm, 'create')}
                />
              </span>
            }
            help={t("settings:manageCharacters.tags.help", {
              defaultValue:
                "Use tags to group characters by use case (e.g., 'writing', 'teaching')."
            })}>
            <div className="space-y-2">
              {/* Popular tags suggestion chips (M3) */}
              {popularTags.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  <span className="text-xs text-text-subtle mr-1">
                    {t("settings:manageCharacters.tags.popular", { defaultValue: "Popular:" })}
                  </span>
                  {popularTags.map(({ tag, count }) => {
                    const currentTags = createForm.getFieldValue('tags') || []
                    const isSelected = currentTags.includes(tag)
                    return (
                      <button
                        key={tag}
                        type="button"
                        className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full border transition-colors ${
                          isSelected
                            ? 'bg-primary/10 border-primary text-primary'
                            : 'bg-surface border-border text-text-muted hover:border-primary/50 hover:text-primary'
                        }`}
                        onClick={() => {
                          const current = createForm.getFieldValue('tags') || []
                          if (isSelected) {
                            createForm.setFieldValue('tags', current.filter((t: string) => t !== tag))
                          } else {
                            createForm.setFieldValue('tags', [...current, tag])
                          }
                          setCreateFormDirty(true)
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
                  filterOption={(input, option) =>
                    option?.value?.toString().toLowerCase().includes(input.toLowerCase()) ?? false
                  }
                />
              </Form.Item>
            </div>
          </Form.Item>
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
          <button
            type="button"
            className="mb-2 text-xs font-medium text-primary underline-offset-2 hover:underline"
            onClick={() => setShowCreateAdvanced((v) => !v)}>
            {showCreateAdvanced
              ? t("settings:manageCharacters.advanced.hide", {
                  defaultValue: "Hide advanced fields"
                })
              : t("settings:manageCharacters.advanced.show", {
                  defaultValue: "Show advanced fields"
                })}
          </button>
          {showCreateAdvanced && (
            <div className="space-y-3 rounded-md border border-dashed border-border p-3">
              <Form.Item
                name="personality"
                label={
                  <span>
                    {t("settings:manageCharacters.form.personality.label", {
                      defaultValue: "Personality"
                    })}
                    <GenerateFieldButton
                      isGenerating={generatingField === 'personality'}
                      disabled={isGenerating}
                      onClick={() => handleGenerateField('personality', createForm, 'create')}
                    />
                  </span>
                }>
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
                      isGenerating={generatingField === 'scenario'}
                      disabled={isGenerating}
                      onClick={() => handleGenerateField('scenario', createForm, 'create')}
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
                      isGenerating={generatingField === 'message_example'}
                      disabled={isGenerating}
                      onClick={() => handleGenerateField('message_example', createForm, 'create')}
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
                      isGenerating={generatingField === 'creator_notes'}
                      disabled={isGenerating}
                      onClick={() => handleGenerateField('creator_notes', createForm, 'create')}
                    />
                  </span>
                }>
                <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
              </Form.Item>
              <Form.Item
                name="alternate_greetings"
                label={
                  <span>
                    {t(
                      "settings:manageCharacters.form.alternateGreetings.label",
                      {
                        defaultValue: "Alternate greetings"
                      }
                    )}
                    <GenerateFieldButton
                      isGenerating={generatingField === 'alternate_greetings'}
                      disabled={isGenerating}
                      onClick={() => handleGenerateField('alternate_greetings', createForm, 'create')}
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
                <Select
                  mode="tags"
                  allowClear
                  placeholder={t(
                    "settings:manageCharacters.form.alternateGreetings.placeholder",
                    {
                      defaultValue: "Add alternate greetings"
                    }
                  )}
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
            </div>
          )}

          {/* Preview toggle */}
          <button
            type="button"
            className="mt-4 mb-2 flex items-center gap-1 text-xs font-medium text-text-muted hover:text-text"
            onClick={() => setShowCreatePreview((v) => !v)}>
            {showCreatePreview ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
            {showCreatePreview
              ? t("settings:manageCharacters.preview.hide", {
                  defaultValue: "Hide preview"
                })
              : t("settings:manageCharacters.preview.show", {
                  defaultValue: "Show preview"
                })}
          </button>

          {/* Character Preview */}
          {showCreatePreview && (
            <Form.Item noStyle shouldUpdate>
              {() => {
                const avatar = createForm.getFieldValue("avatar")
                const avatarValues = avatar ? extractAvatarValues(avatar) : {}
                return (
                  <CharacterPreview
                    name={createForm.getFieldValue("name")}
                    description={createForm.getFieldValue("description")}
                    avatar_url={avatarValues.avatar_url}
                    image_base64={avatarValues.image_base64}
                    system_prompt={createForm.getFieldValue("system_prompt")}
                    greeting={createForm.getFieldValue("greeting")}
                    tags={createForm.getFieldValue("tags")}
                  />
                )
              }}
            </Form.Item>
          )}

          <Button
            type="primary"
            htmlType="submit"
            loading={creating}
            className="mt-4">
            {creating
              ? t("settings:manageCharacters.form.btnSave.saving", {
                  defaultValue: "Creating character..."
                })
              : t("settings:manageCharacters.form.btnSave.save", {
                  defaultValue: "Create character"
                })}
          </Button>
        </Form>
      </Modal>

      <Modal
        title={t("settings:manageCharacters.modal.editTitle", {
          defaultValue: "Edit character"
        })}
        open={openEdit}
        onCancel={() => {
          if (editFormDirty) {
            Modal.confirm({
              title: t("settings:manageCharacters.modal.unsavedTitle", {
                defaultValue: "Discard changes?"
              }),
              content: t("settings:manageCharacters.modal.unsavedContent", {
                defaultValue: "You have unsaved changes. Are you sure you want to close?"
              }),
              okText: t("common:discard", { defaultValue: "Discard" }),
              cancelText: t("common:cancel", { defaultValue: "Cancel" }),
              onOk: () => {
                setOpenEdit(false)
                editForm.resetFields()
                setEditId(null)
                setEditVersion(null)
                setEditFormDirty(false)
                setTimeout(() => {
                  lastEditTriggerRef.current?.focus()
                }, 0)
              }
            })
          } else {
            setOpenEdit(false)
            editForm.resetFields()
            setEditId(null)
            setEditVersion(null)
            setTimeout(() => {
              lastEditTriggerRef.current?.focus()
            }, 0)
          }
        }}
        footer={null}>
        <p className="text-sm text-text-muted mb-4">
          {t("settings:manageCharacters.modal.editDescription", {
            defaultValue: "Update the character's name, behavior, and other settings."
          })}
        </p>

        {/* Draft Recovery Banner for Edit Form (H4) */}
        {hasEditDraft && editDraftData && (
          <Alert
            type="info"
            showIcon
            className="mb-4"
            message={
              <span>
                {t("settings:manageCharacters.draft.resumeEdit", {
                  defaultValue: "Resume unsaved changes?"
                })}
                <span className="text-text-muted ml-1">
                  ({formatDraftAge(editDraftData.savedAt)})
                </span>
              </span>
            }
            action={
              <div className="flex gap-2">
                <Button
                  size="small"
                  type="primary"
                  onClick={() => {
                    const draft = applyEditDraft()
                    if (draft) {
                      editForm.setFieldsValue(draft)
                      setEditFormDirty(true)
                      if (hasAdvancedData(draft, draft.extensions || '')) {
                        setShowEditAdvanced(true)
                      }
                    }
                  }}>
                  {t("settings:manageCharacters.draft.restore", { defaultValue: "Restore" })}
                </Button>
                <Button
                  size="small"
                  onClick={dismissEditDraft}>
                  {t("settings:manageCharacters.draft.discard", { defaultValue: "Discard" })}
                </Button>
              </div>
            }
          />
        )}

        <Form
          layout="vertical"
          form={editForm}
          className="space-y-3"
          onValuesChange={(_, allValues) => {
            setEditFormDirty(true)
            saveEditDraft(allValues)
          }}
          onFinish={(v) => {
            updateCharacter(v)
            clearEditDraft()
            setEditFormDirty(false)
          }}>
          {/* Field order: Name → System Prompt (required) → Greeting → Description → Tags → Avatar */}
          <Form.Item
            name="name"
            label={
              <span>
                {t("settings:manageCharacters.form.name.label", {
                  defaultValue: "Name"
                })}
                <span className="text-danger ml-0.5">*</span>
                <GenerateFieldButton
                  isGenerating={generatingField === 'name'}
                  disabled={isGenerating}
                  onClick={() => handleGenerateField('name', editForm, 'edit')}
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
              }
            ]}>
            <Input
              ref={editNameRef}
              placeholder={t(
                "settings:manageCharacters.form.name.placeholder",
                { defaultValue: "e.g. Writing coach" }
              )}
            />
          </Form.Item>
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
                  isGenerating={generatingField === 'system_prompt'}
                  disabled={isGenerating}
                  onClick={() => handleGenerateField('system_prompt', editForm, 'edit')}
                />
              </span>
            }
            help={t(
              "settings:manageCharacters.form.systemPrompt.help",
              {
                defaultValue:
                  "Describe how this character should respond, including role, tone, and constraints. (max 2000 characters)"
              }
            )}
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
            name="greeting"
            label={
              <span>
                {t("settings:manageCharacters.form.greeting.label", {
                  defaultValue: "Greeting message (optional)"
                })}
                <GenerateFieldButton
                  isGenerating={generatingField === 'first_message'}
                  disabled={isGenerating}
                  onClick={() => handleGenerateField('first_message', editForm, 'edit')}
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
          <Form.Item
            name="description"
            label={
              <span>
                {t("settings:manageCharacters.form.description.label", {
                  defaultValue: "Description"
                })}
                <GenerateFieldButton
                  isGenerating={generatingField === 'description'}
                  disabled={isGenerating}
                  onClick={() => handleGenerateField('description', editForm, 'edit')}
                />
              </span>
            }>
            <Input
              placeholder={t(
                "settings:manageCharacters.form.description.placeholder",
                { defaultValue: "Short description" }
              )}
            />
          </Form.Item>
          <Form.Item
            name="tags"
            label={
              <span>
                {t("settings:manageCharacters.tags.label", {
                  defaultValue: "Tags"
                })}
                <GenerateFieldButton
                  isGenerating={generatingField === 'tags'}
                  disabled={isGenerating}
                  onClick={() => handleGenerateField('tags', editForm, 'edit')}
                />
              </span>
            }
            help={t("settings:manageCharacters.tags.help", {
              defaultValue:
                "Use tags to group characters by use case (e.g., 'writing', 'teaching')."
            })}>
            <div className="space-y-2">
              {/* Popular tags suggestion chips (M3) */}
              {popularTags.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  <span className="text-xs text-text-subtle mr-1">
                    {t("settings:manageCharacters.tags.popular", { defaultValue: "Popular:" })}
                  </span>
                  {popularTags.map(({ tag, count }) => {
                    const currentTags = editForm.getFieldValue('tags') || []
                    const isSelected = currentTags.includes(tag)
                    return (
                      <button
                        key={tag}
                        type="button"
                        className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full border transition-colors ${
                          isSelected
                            ? 'bg-primary/10 border-primary text-primary'
                            : 'bg-surface border-border text-text-muted hover:border-primary/50 hover:text-primary'
                        }`}
                        onClick={() => {
                          const current = editForm.getFieldValue('tags') || []
                          if (isSelected) {
                            editForm.setFieldValue('tags', current.filter((t: string) => t !== tag))
                          } else {
                            editForm.setFieldValue('tags', [...current, tag])
                          }
                          setEditFormDirty(true)
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
                  filterOption={(input, option) =>
                    option?.value?.toString().toLowerCase().includes(input.toLowerCase()) ?? false
                  }
                />
              </Form.Item>
            </div>
          </Form.Item>
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
          <button
            type="button"
            className="mb-2 text-xs font-medium text-primary underline-offset-2 hover:underline"
            onClick={() => setShowEditAdvanced((v) => !v)}>
            {showEditAdvanced
              ? t("settings:manageCharacters.advanced.hide", {
                  defaultValue: "Hide advanced fields"
                })
              : t("settings:manageCharacters.advanced.show", {
                  defaultValue: "Show advanced fields"
                })}
          </button>
          {showEditAdvanced && (
            <div className="space-y-3 rounded-md border border-dashed border-border p-3">
              <Form.Item
                name="personality"
                label={
                  <span>
                    {t("settings:manageCharacters.form.personality.label", {
                      defaultValue: "Personality"
                    })}
                    <GenerateFieldButton
                      isGenerating={generatingField === 'personality'}
                      disabled={isGenerating}
                      onClick={() => handleGenerateField('personality', editForm, 'edit')}
                    />
                  </span>
                }>
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
                      isGenerating={generatingField === 'scenario'}
                      disabled={isGenerating}
                      onClick={() => handleGenerateField('scenario', editForm, 'edit')}
                    />
                  </span>
                }>
                <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
              </Form.Item>
              <Form.Item
                name="post_history_instructions"
                label={t(
                  "settings:manageCharacters.form.postHistory.label",
                  {
                    defaultValue: "Post-history instructions"
                  }
                )}>
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
                      isGenerating={generatingField === 'message_example'}
                      disabled={isGenerating}
                      onClick={() => handleGenerateField('message_example', editForm, 'edit')}
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
                      isGenerating={generatingField === 'creator_notes'}
                      disabled={isGenerating}
                      onClick={() => handleGenerateField('creator_notes', editForm, 'edit')}
                    />
                  </span>
                }>
                <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
              </Form.Item>
              <Form.Item
                name="alternate_greetings"
                label={
                  <span>
                    {t(
                      "settings:manageCharacters.form.alternateGreetings.label",
                      {
                        defaultValue: "Alternate greetings"
                      }
                    )}
                    <GenerateFieldButton
                      isGenerating={generatingField === 'alternate_greetings'}
                      disabled={isGenerating}
                      onClick={() => handleGenerateField('alternate_greetings', editForm, 'edit')}
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
                <Select
                  mode="tags"
                  allowClear
                  placeholder={t(
                    "settings:manageCharacters.form.alternateGreetings.placeholder",
                    {
                      defaultValue: "Add alternate greetings"
                    }
                  )}
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
            </div>
          )}

          {/* Preview toggle */}
          <button
            type="button"
            className="mt-4 mb-2 flex items-center gap-1 text-xs font-medium text-text-muted hover:text-text"
            onClick={() => setShowEditPreview((v) => !v)}>
            {showEditPreview ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
            {showEditPreview
              ? t("settings:manageCharacters.preview.hide", {
                  defaultValue: "Hide preview"
                })
              : t("settings:manageCharacters.preview.show", {
                  defaultValue: "Show preview"
                })}
          </button>

          {/* Character Preview */}
          {showEditPreview && (
            <Form.Item noStyle shouldUpdate>
              {() => {
                const avatar = editForm.getFieldValue("avatar")
                const avatarValues = avatar ? extractAvatarValues(avatar) : {}
                return (
                  <CharacterPreview
                    name={editForm.getFieldValue("name")}
                    description={editForm.getFieldValue("description")}
                    avatar_url={avatarValues.avatar_url}
                    image_base64={avatarValues.image_base64}
                    system_prompt={editForm.getFieldValue("system_prompt")}
                    greeting={editForm.getFieldValue("greeting")}
                    tags={editForm.getFieldValue("tags")}
                  />
                )
              }}
            </Form.Item>
          )}

          <Button
            type="primary"
            htmlType="submit"
            loading={updating}
            className="w-full">
            {updating
              ? t("settings:manageCharacters.form.btnEdit.saving", {
                  defaultValue: "Saving changes..."
                })
              : t("settings:manageCharacters.form.btnEdit.save", {
                  defaultValue: "Save changes"
                })}
          </Button>
        </Form>
      </Modal>

      {/* Generation Preview Modal */}
      <GenerationPreviewModal
        open={generationPreviewOpen}
        generatedData={generationPreviewData}
        fieldName={generationPreviewField}
        onApply={applyGenerationPreview}
        onCancel={() => {
          setGenerationPreviewOpen(false)
          setGenerationPreviewData(null)
          setGenerationPreviewField(null)
        }}
      />

      {/* Bulk Add Tags Modal (M5) */}
      <Modal
        title={t("settings:manageCharacters.bulk.addTagsTitle", {
          defaultValue: "Add tags to {{count}} characters",
          count: selectedCount
        })}
        open={bulkTagModalOpen}
        onCancel={() => {
          setBulkTagModalOpen(false)
          setBulkTagsToAdd([])
        }}
        onOk={handleBulkAddTags}
        okText={t("settings:manageCharacters.bulk.addTagsConfirm", { defaultValue: "Add tags" })}
        cancelText={t("common:cancel", { defaultValue: "Cancel" })}
        confirmLoading={bulkOperationLoading}
        okButtonProps={{ disabled: bulkTagsToAdd.length === 0 }}>
        <div className="space-y-4">
          <p className="text-sm text-text-muted">
            {t("settings:manageCharacters.bulk.addTagsDescription", {
              defaultValue: "Select tags to add to all selected characters. Existing tags will be preserved."
            })}
          </p>
          {/* Popular tags suggestion chips */}
          {popularTags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              <span className="text-xs text-text-subtle mr-1">
                {t("settings:manageCharacters.tags.popular", { defaultValue: "Popular:" })}
              </span>
              {popularTags.map(({ tag, count }) => {
                const isSelected = bulkTagsToAdd.includes(tag)
                return (
                  <button
                    key={tag}
                    type="button"
                    className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full border transition-colors ${
                      isSelected
                        ? 'bg-primary/10 border-primary text-primary'
                        : 'bg-surface border-border text-text-muted hover:border-primary/50 hover:text-primary'
                    }`}
                    onClick={() => {
                      if (isSelected) {
                        setBulkTagsToAdd(bulkTagsToAdd.filter((t) => t !== tag))
                      } else {
                        setBulkTagsToAdd([...bulkTagsToAdd, tag])
                      }
                    }}>
                    {tag}
                    <span className="text-text-subtle">({count})</span>
                  </button>
                )
              })}
            </div>
          )}
          <Select
            mode="tags"
            allowClear
            className="w-full"
            placeholder={t("settings:manageCharacters.bulk.selectTags", {
              defaultValue: "Select or type tags to add"
            })}
            value={bulkTagsToAdd}
            onChange={(values) => setBulkTagsToAdd(values)}
            options={tagOptionsWithCounts}
            filterOption={(input, option) =>
              option?.value?.toString().toLowerCase().includes(input.toLowerCase()) ?? false
            }
          />
        </div>
      </Modal>
    </div>
  )
}
