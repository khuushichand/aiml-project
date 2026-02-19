import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Skeleton,
  Table,
  Tooltip,
  notification,
  Modal,
  Input,
  Form,
  Segmented,
  Tag,
  Select,
  Alert,
  type InputRef
} from "antd"
import { Computer, Zap, Star, StarOff, UploadCloud, Download, Trash2, Pen, Undo2, AlertTriangle, Layers, Cloud, Clipboard, Copy, Keyboard, FolderPlus, Play } from "lucide-react"
import { PromptActionsMenu } from "./PromptActionsMenu"
import { PromptDrawer } from "./PromptDrawer"
import { SyncStatusBadge } from "./SyncStatusBadge"
import { ConflictResolutionModal } from "./ConflictResolutionModal"
import { PromptBulkActionBar } from "./PromptBulkActionBar"
import { PromptInspectorPanel } from "./PromptInspectorPanel"
import { PromptListTable } from "./PromptListTable"
import { PromptListToolbar } from "./PromptListToolbar"
import type { PromptListQueryState, PromptRowVM } from "./prompt-workspace-types"
import {
  buildSyncBatchPlan,
  type SyncBatchTask
} from "./sync-batch-utils"
import { ProjectSelector } from "./ProjectSelector"
import React, { useMemo, useRef, useState, useEffect } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate, useSearchParams } from "react-router-dom"
import {
  deletePromptById,
  getAllPrompts,
  savePrompt,
  updatePrompt,
  exportPrompts,
  importPromptsV2,
  getDeletedPrompts,
  restorePrompt,
  permanentlyDeletePrompt,
  emptyTrash,
  incrementPromptUsage
} from "@/db/dexie/helpers"
import {
  getAllCopilotPrompts,
  upsertCopilotPrompts
} from "@/services/application"
import { tagColors } from "@/utils/color"
import { isFireFoxPrivateMode } from "@/utils/is-private-mode"
import { useConfirmDanger } from "@/components/Common/confirm-danger"
import { useServerOnline } from "@/hooks/useServerOnline"
import FeatureEmptyState from "@/components/Common/FeatureEmptyState"
import ConnectFeatureBanner from "@/components/Common/ConnectFeatureBanner"
import { useMessageOption } from "@/hooks/useMessageOption"
import { useDebounce } from "@/hooks/useDebounce"
import {
  autoSyncPrompt,
  pushToStudio,
  pullFromStudio,
  shouldAutoSyncWorkspacePrompts,
  unlinkPrompt as unlinkPromptFromServer,
  getConflictInfo,
  resolveConflict,
  getAllPromptsWithSyncStatus,
  type ConflictInfo,
  type ConflictResolution
} from "@/services/prompt-sync"
import {
  exportPromptsServer,
  searchPromptsServer,
  listPromptCollectionsServer,
  createPromptCollectionServer,
  updatePromptCollectionServer,
  type PromptCollection
} from "@/services/prompts-api"
import {
  hasPromptStudio,
  getPrompt as getStudioPromptById,
  getLlmProviders
} from "@/services/prompt-studio"
import { StudioTabContainer } from "./Studio/StudioTabContainer"
import {
  getExecuteDefaultModel,
  getExecuteDefaultProvider,
  normalizeExecuteProvidersCatalog
} from "./Studio/Prompts/execute-playground-provider-utils"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { usePromptStudioStore } from "@/store/prompt-studio"
import {
  mapServerSearchItemsToLocalPrompts,
  matchesPromptSearchText,
  matchesTagFilter,
  PROMPT_SEARCH_FIELDS,
  type TagMatchMode
} from "./custom-prompts-utils"
import { filterCopilotPrompts } from "./copilot-prompts-utils"
import {
  getPromptImportNotificationCopy,
  normalizePromptImportCounts
} from "./prompt-import-utils"
import {
  getPromptImportErrorNotice,
  parseImportPromptsPayload
} from "./prompt-import-error-utils"
import { buildBulkCountSummary, collectFailedIds } from "./bulk-result-utils"
import {
  filterTrashPromptsByName,
  getTrashDaysRemaining,
  getTrashRemainingSeverity
} from "./trash-prompts-utils"
import {
  isPromptInCollection,
  mergePromptIdsForCollection
} from "./prompt-collections-utils"

type SegmentType = "custom" | "copilot" | "studio" | "trash"

const VALID_SEGMENTS: SegmentType[] = ["custom", "copilot", "studio", "trash"]

const getSegmentFromParam = (param: string | null): SegmentType => {
  if (param && VALID_SEGMENTS.includes(param as SegmentType)) {
    return param as SegmentType
  }
  return "custom"
}

type BatchSyncFailure = {
  task: SyncBatchTask
  error: string
}

type BatchSyncState = {
  running: boolean
  completed: number
  total: number
  succeeded: number
  failed: BatchSyncFailure[]
  skippedConflicts: number
  skippedCopilotPending: number
  cancelled: boolean
}

const INITIAL_BATCH_SYNC_STATE: BatchSyncState = {
  running: false,
  completed: 0,
  total: 0,
  succeeded: 0,
  failed: [],
  skippedConflicts: 0,
  skippedCopilotPending: 0,
  cancelled: false
}

type PromptSortKey = "title" | "modifiedAt" | null
type PromptSortOrder = "ascend" | "descend" | null
type PromptSortState = {
  key: PromptSortKey
  order: PromptSortOrder
}

type LocalQuickTestPrompt = {
  id: string
  name: string
  systemText?: string
  userText?: string
}

const PROMPTS_CUSTOM_SORT_STORAGE_KEY = "tldw-prompts-custom-sort-v1"
const PROMPTS_MOBILE_BREAKPOINT_PX = 768

const readPromptSortState = (): PromptSortState => {
  if (typeof window === "undefined") {
    return { key: null, order: null }
  }
  try {
    const raw = window.sessionStorage.getItem(PROMPTS_CUSTOM_SORT_STORAGE_KEY)
    if (!raw) {
      return { key: null, order: null }
    }
    const parsed = JSON.parse(raw) as PromptSortState
    const allowedKeys: PromptSortKey[] = ["title", "modifiedAt", null]
    const allowedOrders: PromptSortOrder[] = ["ascend", "descend", null]
    if (!allowedKeys.includes(parsed?.key) || !allowedOrders.includes(parsed?.order)) {
      return { key: null, order: null }
    }
    return parsed
  } catch {
    return { key: null, order: null }
  }
}

export const PromptBody = () => {
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerMode, setDrawerMode] = useState<"create" | "edit">("create")
  const [editId, setEditId] = useState("")
  const [drawerInitialValues, setDrawerInitialValues] = useState<any>(null)
  const { t } = useTranslation(["settings", "common", "option"])
  const navigate = useNavigate()
  const isOnline = useServerOnline()
  const setStudioActiveSubTab = usePromptStudioStore((s) => s.setActiveSubTab)
  const setStudioSelectedProjectId = usePromptStudioStore(
    (s) => s.setSelectedProjectId
  )
  const setStudioSelectedPromptId = usePromptStudioStore(
    (s) => s.setSelectedPromptId
  )
  const setStudioExecutePlaygroundOpen = usePromptStudioStore(
    (s) => s.setExecutePlaygroundOpen
  )

  // Get initial segment from URL param
  const initialSegment = getSegmentFromParam(searchParams.get("tab"))
  const [selectedSegment, setSelectedSegment] = useState<SegmentType>(initialSegment)

  // Sync URL params with selected segment
  useEffect(() => {
    const currentTab = searchParams.get("tab")
    const expectedTab = selectedSegment === "custom" ? null : selectedSegment

    if (currentTab !== expectedTab) {
      if (expectedTab) {
        setSearchParams({ tab: expectedTab }, { replace: true })
      } else {
        // Remove tab param when on default (custom) tab
        const newParams = new URLSearchParams(searchParams)
        newParams.delete("tab")
        setSearchParams(newParams, { replace: true })
      }
    }
  }, [selectedSegment, searchParams, setSearchParams])

  // Track if we've processed the initial prompt deep-link
  const deepLinkProcessedRef = useRef(false)

  // Handle ?project= filter for showing prompts from a specific project
  const projectFilter = searchParams.get("project")

  const [searchText, setSearchText] = useState("")
  const [typeFilter, setTypeFilter] = useState<"all" | "system" | "quick">(
    "all"
  )
  const [usageFilter, setUsageFilter] = useState<"all" | "used" | "unused">(
    "all"
  )
  const [collectionFilter, setCollectionFilter] = useState<number | "all">("all")
  const [createCollectionModalOpen, setCreateCollectionModalOpen] = useState(false)
  const [newCollectionName, setNewCollectionName] = useState("")
  const [newCollectionDescription, setNewCollectionDescription] = useState("")
  const [tagFilter, setTagFilter] = useState<string[]>([])
  const [tagMatchMode, setTagMatchMode] = useState<TagMatchMode>("any")
  const [currentPage, setCurrentPage] = useState(1)
  const [resultsPerPage, setResultsPerPage] = useState(20)
  const [promptSort, setPromptSort] = useState<PromptSortState>(() =>
    readPromptSortState()
  )
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const searchInputRef = useRef<InputRef | null>(null)
  const [importMode, setImportMode] = useState<"merge" | "replace">("merge")
  const [exportFormat, setExportFormat] = useState<"json" | "csv" | "markdown">("json")
  const [bulkKeywordModalOpen, setBulkKeywordModalOpen] = useState(false)
  const [bulkKeywordValue, setBulkKeywordValue] = useState("")
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [inspectorPromptId, setInspectorPromptId] = useState<string | null>(null)
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const [isCompactViewport, setIsCompactViewport] = useState(() =>
    typeof window !== "undefined"
      ? window.innerWidth < PROMPTS_MOBILE_BREAKPOINT_PX
      : false
  )
  const [trashSearchText, setTrashSearchText] = useState("")
  const [trashSelectedRowKeys, setTrashSelectedRowKeys] = useState<React.Key[]>([])
  const [insertPrompt, setInsertPrompt] = useState<{
    id: string
    systemText?: string
    userText?: string
  } | null>(null)
  const [localQuickTestPrompt, setLocalQuickTestPrompt] =
    useState<LocalQuickTestPrompt | null>(null)
  const [localQuickTestInput, setLocalQuickTestInput] = useState("")
  const [localQuickTestOutput, setLocalQuickTestOutput] = useState<string | null>(
    null
  )
  const [isRunningLocalQuickTest, setIsRunningLocalQuickTest] = useState(false)
  const [localQuickTestRunInfo, setLocalQuickTestRunInfo] = useState<{
    provider?: string
    model: string
  } | null>(null)
  const confirmDanger = useConfirmDanger()

  // Sync state
  const [projectSelectorOpen, setProjectSelectorOpen] = useState(false)
  const [promptToSync, setPromptToSync] = useState<string | null>(null)
  const [conflictModalOpen, setConflictModalOpen] = useState(false)
  const [conflictPromptId, setConflictPromptId] = useState<string | null>(null)
  const [conflictInfo, setConflictInfo] = useState<ConflictInfo | null>(null)
  const [batchSyncState, setBatchSyncState] = useState<BatchSyncState>(
    INITIAL_BATCH_SYNC_STATE
  )
  const batchSyncCancelRef = useRef(false)

  const [openCopilotEdit, setOpenCopilotEdit] = useState(false)
  const [editCopilotId, setEditCopilotId] = useState("")
  const [editCopilotForm] = Form.useForm()
  const [copilotSearchText, setCopilotSearchText] = useState("")
  const [copilotKeyFilter, setCopilotKeyFilter] = useState<string>("all")
  const [shortcutsHelpOpen, setShortcutsHelpOpen] = useState(false)
  const copilotEditPromptValue = Form.useWatch("prompt", editCopilotForm)

  const { setSelectedQuickPrompt, setSelectedSystemPrompt } = useMessageOption()
  const debouncedSearchText = useDebounce(searchText, 300)
  const normalizedSearchText = debouncedSearchText.trim()
  const shouldUseServerSearch = isOnline && normalizedSearchText.length > 0

  const { data, status } = useQuery({
    queryKey: ["fetchAllPrompts"],
    queryFn: getAllPrompts
  })

  const {
    data: serverSearchData,
    status: serverSearchStatus
  } = useQuery({
    queryKey: [
      "searchPrompts",
      normalizedSearchText,
      currentPage,
      resultsPerPage
    ],
    queryFn: () =>
      searchPromptsServer({
        searchQuery: normalizedSearchText,
        searchFields: PROMPT_SEARCH_FIELDS,
        page: currentPage,
        resultsPerPage,
        includeDeleted: false
      }),
    enabled: shouldUseServerSearch
  })

  const { data: copilotData, status: copilotStatus } = useQuery({
    queryKey: ["fetchCopilotPrompts"],
    queryFn: getAllCopilotPrompts,
    enabled: isOnline
  })

  const { data: trashData, status: trashStatus } = useQuery({
    queryKey: ["fetchDeletedPrompts"],
    queryFn: getDeletedPrompts
  })

  const { data: promptCollectionsData, status: promptCollectionsStatus } = useQuery({
    queryKey: ["promptCollections"],
    queryFn: listPromptCollectionsServer,
    enabled: isOnline
  })

  // Prompt Studio capability check
  const { data: hasStudio } = useQuery({
    queryKey: ["prompt-studio", "capability"],
    queryFn: hasPromptStudio,
    enabled: isOnline
  })

  useEffect(() => {
    setCurrentPage(1)
  }, [normalizedSearchText, projectFilter, typeFilter, collectionFilter, tagFilter, tagMatchMode])

  useEffect(() => {
    if (typeof window === "undefined") return
    try {
      window.sessionStorage.setItem(
        PROMPTS_CUSTOM_SORT_STORAGE_KEY,
        JSON.stringify(promptSort)
      )
    } catch {
      // Ignore session storage failures in restricted browser modes.
    }
  }, [promptSort])

  useEffect(() => {
    if (typeof window === "undefined") return
    const handleResize = () => {
      setIsCompactViewport(window.innerWidth < PROMPTS_MOBILE_BREAKPOINT_PX)
    }
    window.addEventListener("resize", handleResize)
    return () => {
      window.removeEventListener("resize", handleResize)
    }
  }, [])

  useEffect(() => {
    if (!shouldUseServerSearch || serverSearchStatus !== "error") return
    notification.warning({
      message: t("managePrompts.searchServerFallback", {
        defaultValue: "Server search unavailable"
      }),
      description: t("managePrompts.searchServerFallbackDesc", {
        defaultValue:
          "Falling back to local search results for this query."
      })
    })
  }, [serverSearchStatus, shouldUseServerSearch, t])

  // Handle ?prompt= deep-link for opening a specific prompt
  useEffect(() => {
    const promptId = searchParams.get("prompt")
    if (!promptId || deepLinkProcessedRef.current) return
    if (status !== "success" || !Array.isArray(data)) return

    const clearPromptParam = () => {
      const newParams = new URLSearchParams(searchParams)
      newParams.delete("prompt")
      newParams.delete("source")
      setSearchParams(newParams, { replace: true })
    }

    const openPromptDrawer = (promptRecord: any) => {
      clearPromptParam()
      setEditId(promptRecord.id)
      setDrawerMode("edit")
      setDrawerInitialValues({
        id: promptRecord?.id,
        name: promptRecord?.name || promptRecord?.title,
        author: promptRecord?.author,
        details: promptRecord?.details,
        system_prompt:
          promptRecord?.system_prompt ||
          (promptRecord?.is_system ? promptRecord?.content : undefined),
        user_prompt:
          promptRecord?.user_prompt ||
          (!promptRecord?.is_system ? promptRecord?.content : undefined),
        keywords: promptRecord?.keywords ?? promptRecord?.tags ?? [],
        serverId: promptRecord?.serverId,
        syncStatus: promptRecord?.syncStatus,
        sourceSystem: promptRecord?.sourceSystem,
        studioProjectId: promptRecord?.studioProjectId,
        lastSyncedAt: promptRecord?.lastSyncedAt,
        fewShotExamples: promptRecord?.fewShotExamples,
        modulesConfig: promptRecord?.modulesConfig,
        changeDescription: promptRecord?.changeDescription,
        versionNumber: promptRecord?.versionNumber
      })
      setDrawerOpen(true)
    }

    deepLinkProcessedRef.current = true

    // First try local prompt IDs.
    const localPromptRecord = data.find((p: any) => p.id === promptId)
    if (localPromptRecord) {
      openPromptDrawer(localPromptRecord)
      return
    }

    const source = searchParams.get("source")
    const parsedServerPromptId = Number(promptId)
    const isServerPromptLink =
      Number.isInteger(parsedServerPromptId) &&
      parsedServerPromptId > 0 &&
      (source === "studio" || source === null)

    const getSharedPromptFailureDescription = (errorMessage?: string) => {
      const normalized = String(errorMessage || "").toLowerCase()
      const isAccessDenied =
        normalized.includes("401") ||
        normalized.includes("403") ||
        normalized.includes("forbidden") ||
        normalized.includes("unauthor") ||
        normalized.includes("not authenticated") ||
        normalized.includes("api key")
      if (isAccessDenied) {
        return t("managePrompts.notification.sharedPromptAccessDeniedDesc", {
          defaultValue:
            "You don't have permission to open this shared prompt. Check your server login and project access."
        })
      }
      return t("managePrompts.notification.sharedPromptNotFoundDesc", {
        defaultValue:
          "The shared prompt could not be pulled from the server. It may not exist or you may not have access."
      })
    }

    if (isOnline && isServerPromptLink) {
      clearPromptParam()
      void (async () => {
        const syncResult = await pullFromStudio(parsedServerPromptId)
        if (!syncResult.success) {
          notification.warning({
            message: t("managePrompts.notification.promptNotFound", {
              defaultValue: "Prompt not found"
            }),
            description: getSharedPromptFailureDescription(syncResult.error)
          })
          return
        }
        try {
          const refreshedPrompts = await queryClient.fetchQuery({
            queryKey: ["fetchAllPrompts"],
            queryFn: getAllPrompts
          })
          const importedPrompt = (Array.isArray(refreshedPrompts)
            ? refreshedPrompts
            : []
          ).find(
            (item: any) =>
              item?.id === syncResult.localId ||
              item?.serverId === parsedServerPromptId
          )
          if (!importedPrompt) {
            notification.warning({
              message: t("managePrompts.notification.promptNotFound", {
                defaultValue: "Prompt not found"
              }),
              description: t("managePrompts.notification.sharedPromptImportMissing", {
                defaultValue:
                  "The shared prompt was fetched, but could not be loaded locally."
              })
            })
            return
          }
          notification.success({
            message: t("managePrompts.notification.sharedPromptImported", {
              defaultValue: "Shared prompt imported"
            }),
            description: t("managePrompts.notification.sharedPromptImportedDesc", {
              defaultValue:
                "The prompt was pulled from the server and opened in your workspace."
            })
          })
          openPromptDrawer(importedPrompt)
        } catch {
          notification.warning({
            message: t("managePrompts.notification.promptNotFound", {
              defaultValue: "Prompt not found"
            }),
            description: t("managePrompts.notification.sharedPromptImportMissing", {
              defaultValue:
                "The shared prompt was fetched, but could not be loaded locally."
            })
          })
        }
      })()
      return
    }

    clearPromptParam()
    if (!isOnline && isServerPromptLink) {
      deepLinkProcessedRef.current = true
      notification.warning({
        message: t("managePrompts.notification.promptNotFound", {
          defaultValue: "Prompt not found"
        }),
        description: t("managePrompts.notification.sharedPromptOfflineDesc", {
          defaultValue:
            "This shared prompt link requires an online server connection."
        })
      })
      return
    }

    notification.warning({
      message: t("managePrompts.notification.promptNotFound", {
        defaultValue: "Prompt not found"
      }),
      description: t("managePrompts.notification.promptNotFoundDesc", {
        defaultValue: "The requested prompt could not be found. It may have been deleted."
      })
    })
  }, [searchParams, data, status, setSearchParams, isOnline, queryClient, t])

  const promptLoadFailed = status === "error"
  const copilotLoadFailed = isOnline && copilotStatus === "error"
  const loadErrorDescription = [
    promptLoadFailed
      ? t(
          "managePrompts.loadErrorDetail",
          "Custom prompts couldn’t be retrieved from local storage."
        )
      : null,
    copilotLoadFailed
      ? t(
          "managePrompts.copilotLoadErrorDetail",
          "Copilot prompts couldn’t be retrieved."
        )
      : null
  ]
    .filter(Boolean)
    .join(" ")

  const guardPrivateMode = React.useCallback(() => {
    if (!isFireFoxPrivateMode) return false
    notification.error({
      message: t(
        "common:privateModeSaveErrorTitle",
        "tldw Assistant can't save data"
      ),
      description: t(
        "settings:prompts.privateModeDescription",
        "Firefox Private Mode does not support saving data to IndexedDB. Please add prompts from a normal window."
      )
    })
    return true
  }, [isFireFoxPrivateMode, t])

  React.useEffect(() => {
    // Only redirect from copilot/studio tab when offline (trash is local-only so always available)
    if (!isOnline && (selectedSegment === "copilot" || selectedSegment === "studio")) {
      setSelectedSegment("custom")
    }
  }, [isOnline, selectedSegment])

  const getPromptKeywords = React.useCallback(
    (prompt: any) => prompt?.keywords ?? prompt?.tags ?? [],
    []
  )

  const getPromptTexts = React.useCallback((prompt: any) => {
    const systemText =
      prompt?.system_prompt ||
      (prompt?.is_system ? prompt?.content : undefined)
    const userText =
      prompt?.user_prompt ||
      (!prompt?.is_system ? prompt?.content : undefined)
    return { systemText, userText }
  }, [])

  const getPromptType = React.useCallback((prompt: any) => {
    const { systemText, userText } = getPromptTexts(prompt)
    const hasSystem = typeof systemText === "string" && systemText.trim().length > 0
    const hasUser = typeof userText === "string" && userText.trim().length > 0
    if (hasSystem && hasUser) return "mixed"
    if (hasSystem) return "system"
    if (hasUser) return "quick"
    return prompt?.is_system ? "system" : "quick"
  }, []) // getPromptTexts has stable identity (empty deps), safe to omit

  const getPromptModifiedAt = React.useCallback((prompt: any) => {
    return prompt?.updatedAt || prompt?.createdAt || 0
  }, [])

  const getPromptUsageCount = React.useCallback((prompt: any) => {
    const value = prompt?.usageCount
    if (typeof value !== "number" || Number.isNaN(value)) return 0
    return Math.max(0, Math.floor(value))
  }, [])

  const getPromptLastUsedAt = React.useCallback((prompt: any) => {
    const value = prompt?.lastUsedAt
    if (typeof value !== "number" || Number.isNaN(value)) return null
    return value
  }, [])

  const formatRelativePromptTime = React.useCallback(
    (timestamp: number | null | undefined) => {
      if (!timestamp) {
        return t("common:unknown", { defaultValue: "Unknown" })
      }
      const now = Date.now()
      const diffMs = Math.max(0, now - timestamp)
      const diffMins = Math.floor(diffMs / (1000 * 60))
      const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

      if (diffMins < 1) {
        return t("common:justNow", { defaultValue: "Just now" })
      }
      if (diffMins < 60) {
        return t("common:minutesAgo", {
          defaultValue: "{{count}}m ago",
          count: diffMins
        })
      }
      if (diffHours < 24) {
        return t("common:hoursAgo", {
          defaultValue: "{{count}}h ago",
          count: diffHours
        })
      }
      if (diffDays < 30) {
        return t("common:daysAgo", {
          defaultValue: "{{count}}d ago",
          count: diffDays
        })
      }
      return new Date(timestamp).toLocaleDateString()
    },
    [t]
  )

  const normalizePromptPayload = React.useCallback((values: any) => {
    const keywords = values?.keywords ?? values?.tags ?? []
    const promptName = values?.name || values?.title
    const hasSystemPrompt = !!(values?.system_prompt?.trim())
    const resolvedContent =
      values?.content ??
      (hasSystemPrompt ? values?.system_prompt : values?.user_prompt) ??
      values?.system_prompt ??
      values?.user_prompt

    return {
      ...values,
      title: promptName,
      name: promptName,
      tags: keywords,
      keywords,
      content: resolvedContent,
      system_prompt: values?.system_prompt,
      user_prompt: values?.user_prompt,
      author: values?.author,
      details: values?.details,
      is_system: hasSystemPrompt
    }
  }, [])

  const markPromptAsUsed = React.useCallback(
    async (promptId: string) => {
      if (!promptId) return
      try {
        await incrementPromptUsage(promptId)
        await queryClient.invalidateQueries({
          queryKey: ["fetchAllPrompts"]
        })
      } catch {
        // Usage tracking should not block prompt insertion into chat.
      }
    },
    [queryClient]
  )

  const buildPromptUpdatePayload = React.useCallback(
    (prompt: any, overrides: Partial<any> = {}) => {
      const { systemText, userText } = getPromptTexts(prompt)
      const promptName = prompt?.name || prompt?.title || "Untitled Prompt"
      const hasSystemPrompt =
        typeof systemText === "string" && systemText.trim().length > 0
      const resolvedContent =
        prompt?.content ??
        (hasSystemPrompt ? systemText : userText) ??
        systemText ??
        userText ??
        ""

      const nextKeywords =
        overrides?.keywords ??
        overrides?.tags ??
        getPromptKeywords(prompt) ??
        []

      return {
        id: prompt.id,
        title: promptName,
        name: promptName,
        content: resolvedContent,
        is_system: hasSystemPrompt,
        keywords: nextKeywords,
        tags: nextKeywords,
        favorite:
          typeof overrides?.favorite === "boolean"
            ? overrides.favorite
            : !!prompt?.favorite,
        author: prompt?.author,
        details: prompt?.details,
        system_prompt: systemText,
        user_prompt: userText,
        ...overrides
      }
    },
    [getPromptKeywords, getPromptTexts]
  )

  const syncPromptAfterLocalSave = React.useCallback(async (localId: string) => {
    try {
      const autoSyncEnabled = await shouldAutoSyncWorkspacePrompts()
      if (!autoSyncEnabled) {
        return {
          attempted: false,
          success: true,
          error: undefined
        }
      }

      const result = await autoSyncPrompt(localId)
      if (!result.success) {
        notification.warning({
          message: t("managePrompts.sync.syncFailed", {
            defaultValue: "Sync failed"
          }),
          description: t("managePrompts.sync.syncFailedWithLocalSave", {
            defaultValue: "{{error}} Your changes are saved locally.",
            error: result.error || t("managePrompts.sync.pendingTooltip", {
              defaultValue: "Local changes not yet synced."
            })
          })
        })
      }
      return {
        attempted: true,
        success: result.success,
        error: result.error
      }
    } catch (error: unknown) {
      const fallbackError =
        error instanceof Error
          ? error.message
          : t("managePrompts.sync.pendingTooltip", {
              defaultValue: "Local changes not yet synced"
            })
      notification.warning({
        message: t("managePrompts.sync.syncFailed", {
          defaultValue: "Sync failed"
        }),
        description: t("managePrompts.sync.syncFailedWithLocalSave", {
          defaultValue: "{{error}} Your changes are saved locally.",
          error: fallbackError
        })
      })
      return {
        attempted: true,
        success: false,
        error: fallbackError
      }
    }
  }, [t])

  const { mutate: deletePrompt } = useMutation({
    mutationFn: deletePromptById,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["fetchAllPrompts"]
      })
      queryClient.invalidateQueries({
        queryKey: ["fetchDeletedPrompts"]
      })
      notification.success({
        message: t("managePrompts.notification.deletedSuccess"),
        description: t("managePrompts.notification.movedToTrash", {
          defaultValue: "The prompt has been moved to trash. You can restore it within 30 days."
        })
      })
    },
    onError: (error) => {
      notification.error({
        message: t("managePrompts.notification.error"),
        description: error?.message || t("managePrompts.notification.someError")
      })
    }
  })

  const { mutate: restorePromptMutation } = useMutation({
    mutationFn: restorePrompt,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["fetchAllPrompts"]
      })
      queryClient.invalidateQueries({
        queryKey: ["fetchDeletedPrompts"]
      })
      notification.success({
        message: t("managePrompts.notification.restoredSuccess", { defaultValue: "Prompt restored" }),
        description: t("managePrompts.notification.restoredSuccessDesc", { defaultValue: "The prompt has been restored from trash." })
      })
    },
    onError: (error) => {
      notification.error({
        message: t("managePrompts.notification.error"),
        description: error?.message || t("managePrompts.notification.someError")
      })
    }
  })

  const { mutate: bulkRestorePrompts, isPending: isBulkRestoring } = useMutation({
    mutationFn: async (ids: string[]) => {
      const results = await Promise.allSettled(ids.map((id) => restorePrompt(id)))
      const failedIds = collectFailedIds(ids, results)
      const counts = buildBulkCountSummary(ids.length, failedIds.length)
      return {
        total: counts.total,
        restored: counts.succeeded,
        failedIds
      }
    },
    onSuccess: ({ total, restored, failedIds }) => {
      queryClient.invalidateQueries({
        queryKey: ["fetchAllPrompts"]
      })
      queryClient.invalidateQueries({
        queryKey: ["fetchDeletedPrompts"]
      })

      if (failedIds.length > 0) {
        setTrashSelectedRowKeys(failedIds)
        notification.warning({
          message: t("managePrompts.trash.bulkRestorePartial", {
            defaultValue: "Bulk restore completed with issues"
          }),
          description: t("managePrompts.trash.bulkRestorePartialDesc", {
            defaultValue: "Restored {{restored}} of {{total}} prompts. {{failed}} failed.",
            restored,
            total,
            failed: failedIds.length
          })
        })
        return
      }

      setTrashSelectedRowKeys([])
      notification.success({
        message: t("managePrompts.trash.bulkRestoreSuccess", {
          defaultValue: "Prompts restored"
        }),
        description: t("managePrompts.trash.bulkRestoreSuccessDesc", {
          defaultValue: "Restored {{count}} prompts from trash.",
          count: restored
        })
      })
    },
    onError: (error) => {
      notification.error({
        message: t("managePrompts.notification.error"),
        description: error?.message || t("managePrompts.notification.someError")
      })
    }
  })

  const { mutate: permanentDeletePromptMutation } = useMutation({
    mutationFn: permanentlyDeletePrompt,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["fetchDeletedPrompts"]
      })
      notification.success({
        message: t("managePrompts.notification.permanentDeleteSuccess", { defaultValue: "Prompt permanently deleted" }),
        description: t("managePrompts.notification.permanentDeleteSuccessDesc", { defaultValue: "The prompt has been permanently removed." })
      })
    },
    onError: (error) => {
      notification.error({
        message: t("managePrompts.notification.error"),
        description: error?.message || t("managePrompts.notification.someError")
      })
    }
  })

  const { mutate: emptyTrashMutation, isPending: isEmptyingTrash } = useMutation({
    mutationFn: emptyTrash,
    onSuccess: (count) => {
      queryClient.invalidateQueries({
        queryKey: ["fetchDeletedPrompts"]
      })
      setTrashSelectedRowKeys([])
      notification.success({
        message: t("managePrompts.notification.trashEmptied", { defaultValue: "Trash emptied" }),
        description: t("managePrompts.notification.trashEmptiedDesc", {
          defaultValue: "{{count}} prompts permanently deleted.",
          count
        })
      })
    },
    onError: (error) => {
      notification.error({
        message: t("managePrompts.notification.error"),
        description: error?.message || t("managePrompts.notification.someError")
      })
    }
  })

  // Sync mutations
  const { mutate: pushToStudioMutation, isPending: isPushing } = useMutation({
    mutationFn: async ({ localId, projectId }: { localId: string; projectId: number }) => {
      return await pushToStudio(localId, projectId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fetchAllPrompts"] })
      setProjectSelectorOpen(false)
      setPromptToSync(null)
      notification.success({
        message: t("managePrompts.sync.pushSuccess", { defaultValue: "Pushed to server" }),
        description: t("managePrompts.sync.pushSuccessDesc", { defaultValue: "Prompt has been synced to Prompt Studio." })
      })
    },
    onError: (error) => {
      notification.error({
        message: t("managePrompts.sync.pushError", { defaultValue: "Failed to push" }),
        description: error?.message || t("managePrompts.notification.someError")
      })
    }
  })

  const { mutate: pullFromStudioMutation, isPending: isPulling } = useMutation({
    mutationFn: async ({ serverId, localId }: { serverId: number; localId?: string }) => {
      return await pullFromStudio(serverId, localId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fetchAllPrompts"] })
      notification.success({
        message: t("managePrompts.sync.pullSuccess", { defaultValue: "Pulled from server" }),
        description: t("managePrompts.sync.pullSuccessDesc", { defaultValue: "Prompt has been updated from Prompt Studio." })
      })
    },
    onError: (error) => {
      notification.error({
        message: t("managePrompts.sync.pullError", { defaultValue: "Failed to pull" }),
        description: error?.message || t("managePrompts.notification.someError")
      })
    }
  })

  const { mutate: unlinkPromptMutation } = useMutation({
    mutationFn: unlinkPromptFromServer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fetchAllPrompts"] })
      notification.success({
        message: t("managePrompts.sync.unlinkSuccess", { defaultValue: "Unlinked from server" }),
        description: t("managePrompts.sync.unlinkSuccessDesc", { defaultValue: "Prompt is now local-only." })
      })
    },
    onError: (error) => {
      notification.error({
        message: t("managePrompts.sync.unlinkError", { defaultValue: "Failed to unlink" }),
        description: error?.message || t("managePrompts.notification.someError")
      })
    }
  })

  const {
    mutate: loadConflictInfoMutation,
    isPending: isLoadingConflictInfo
  } = useMutation({
    mutationFn: async (localId: string) => {
      return await getConflictInfo(localId)
    },
    onSuccess: (info) => {
      if (!info) {
        notification.warning({
          message: t("managePrompts.sync.conflictUnavailable", {
            defaultValue: "Conflict details unavailable"
          }),
          description: t("managePrompts.sync.conflictUnavailableDesc", {
            defaultValue:
              "We couldn't retrieve local and server versions for comparison."
          })
        })
        setConflictModalOpen(false)
        setConflictPromptId(null)
        setConflictInfo(null)
        return
      }
      setConflictInfo(info)
    },
    onError: (error) => {
      notification.error({
        message: t("managePrompts.sync.pullError", {
          defaultValue: "Failed to load conflict details"
        }),
        description: error?.message || t("managePrompts.notification.someError")
      })
      setConflictModalOpen(false)
      setConflictPromptId(null)
      setConflictInfo(null)
    }
  })

  const {
    mutate: resolveConflictMutation,
    isPending: isResolvingConflict
  } = useMutation({
    mutationFn: async ({
      localId,
      resolution
    }: {
      localId: string
      resolution: ConflictResolution
    }) => {
      return await resolveConflict(localId, resolution)
    },
    onSuccess: (result, variables) => {
      if (!result.success) {
        notification.error({
          message: t("managePrompts.sync.resolveError", {
            defaultValue: "Failed to resolve conflict"
          }),
          description: result.error || t("managePrompts.notification.someError")
        })
        return
      }

      queryClient.invalidateQueries({ queryKey: ["fetchAllPrompts"] })
      setConflictModalOpen(false)
      setConflictPromptId(null)
      setConflictInfo(null)

      const description =
        variables.resolution === "keep_local"
          ? t("managePrompts.sync.keepMineSuccessDesc", {
              defaultValue: "Your local prompt has been pushed to the server."
            })
          : variables.resolution === "keep_server"
            ? t("managePrompts.sync.keepServerSuccessDesc", {
                defaultValue:
                  "Your local prompt has been replaced with the server version."
              })
            : t("managePrompts.sync.keepBothSuccessDesc", {
                defaultValue:
                  "The prompt was unlinked and resynced so both versions are preserved."
              })

      notification.success({
        message: t("managePrompts.sync.resolveSuccess", {
          defaultValue: "Conflict resolved"
        }),
        description
      })
    },
    onError: (error) => {
      notification.error({
        message: t("managePrompts.sync.resolveError", {
          defaultValue: "Failed to resolve conflict"
        }),
        description: error?.message || t("managePrompts.notification.someError")
      })
    }
  })

  // Import a server prompt to local (from Studio tab)
  const { mutate: importFromStudioMutation, isPending: isImporting } = useMutation({
    mutationFn: async ({ serverId }: { serverId: number }) => {
      return await pullFromStudio(serverId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fetchAllPrompts"] })
      notification.success({
        message: t("managePrompts.studio.importSuccess", { defaultValue: "Prompt imported" }),
        description: t("managePrompts.studio.importSuccessDesc", { defaultValue: "The prompt has been saved to your local prompts." })
      })
    },
    onError: (error) => {
      notification.error({
        message: t("managePrompts.studio.importError", { defaultValue: "Failed to import" }),
        description: error?.message || t("managePrompts.notification.someError")
      })
    }
  })

  const { mutate: bulkDeletePrompts, isPending: isBulkDeleting } = useMutation({
    mutationFn: async (ids: string[]) => {
      const results = await Promise.allSettled(ids.map((id) => deletePromptById(id)))
      const failedIds = collectFailedIds(ids, results)
      const counts = buildBulkCountSummary(ids.length, failedIds.length)
      return {
        total: counts.total,
        deleted: counts.succeeded,
        failedIds
      }
    },
    onSuccess: ({ total, deleted, failedIds }) => {
      queryClient.invalidateQueries({
        queryKey: ["fetchAllPrompts"]
      })
      queryClient.invalidateQueries({
        queryKey: ["fetchDeletedPrompts"]
      })
      if (failedIds.length > 0) {
        setSelectedRowKeys(failedIds)
        notification.warning({
          message: t("managePrompts.notification.bulkDeletePartial", {
            defaultValue: "Bulk delete completed with issues"
          }),
          description: t("managePrompts.notification.bulkDeletePartialDesc", {
            defaultValue: "Deleted {{deleted}} of {{total}} prompts. {{failed}} failed.",
            deleted,
            total,
            failed: failedIds.length
          })
        })
      } else {
        setSelectedRowKeys([])
        notification.success({
          message: t("managePrompts.notification.bulkDeletedSuccess", { defaultValue: "Prompts deleted" }),
          description: t("managePrompts.notification.bulkDeletedSuccessDesc", { defaultValue: "Selected prompts have been deleted." })
        })
      }
    },
    onError: (error) => {
      notification.error({
        message: t("managePrompts.notification.error"),
        description: error?.message || t("managePrompts.notification.someError")
      })
    }
  })

  const { mutate: bulkToggleFavorite, isPending: isBulkFavoriting } = useMutation({
    mutationFn: async ({
      ids,
      favorite
    }: {
      ids: string[]
      favorite: boolean
    }) => {
      const promptById = new Map(
        (data || []).map((prompt: any) => [String(prompt.id), prompt])
      )
      const results = await Promise.allSettled(
        ids.map(async (id) => {
          const prompt = promptById.get(id)
          if (!prompt) {
            throw new Error("Prompt not found")
          }
          await updatePrompt(
            buildPromptUpdatePayload(prompt, {
              favorite
            })
          )
        })
      )
      const failedIds: string[] = []
      for (let index = 0; index < results.length; index += 1) {
        if (results[index]?.status === "rejected") {
          failedIds.push(ids[index]!)
        }
      }
      return {
        total: ids.length,
        updated: ids.length - failedIds.length,
        failedIds
      }
    },
    onSuccess: ({ total, updated, failedIds }, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["fetchAllPrompts"]
      })
      if (failedIds.length > 0) {
        setSelectedRowKeys(failedIds)
        notification.warning({
          message: t("managePrompts.bulk.favoritePartial", {
            defaultValue: "Bulk favorite update completed with issues"
          }),
          description: t("managePrompts.bulk.favoritePartialDesc", {
            defaultValue:
              "Updated {{updated}} of {{total}} prompts. {{failed}} failed.",
            updated,
            total,
            failed: failedIds.length
          })
        })
        return
      }
      notification.success({
        message: variables.favorite
          ? t("managePrompts.bulk.favoriteSuccess", {
              defaultValue: "Selected prompts favorited"
            })
          : t("managePrompts.bulk.unfavoriteSuccess", {
              defaultValue: "Selected prompts unfavorited"
            }),
        description: t("managePrompts.bulk.favoriteSuccessDesc", {
          defaultValue: "Updated {{count}} prompts.",
          count: updated
        })
      })
    },
    onError: (error) => {
      notification.error({
        message: t("managePrompts.notification.error"),
        description: error?.message || t("managePrompts.notification.someError")
      })
    }
  })

  const { mutate: bulkAddKeyword, isPending: isBulkAddingKeyword } = useMutation({
    mutationFn: async ({
      ids,
      keyword
    }: {
      ids: string[]
      keyword: string
    }) => {
      const trimmedKeyword = keyword.trim()
      if (!trimmedKeyword) {
        throw new Error(
          t("managePrompts.tags.keywordRequired", {
            defaultValue: "Keyword is required."
          })
        )
      }

      const promptById = new Map(
        (data || []).map((prompt: any) => [String(prompt.id), prompt])
      )
      const results = await Promise.allSettled(
        ids.map(async (id) => {
          const prompt = promptById.get(id)
          if (!prompt) {
            throw new Error("Prompt not found")
          }
          const existingKeywords = getPromptKeywords(prompt) || []
          if (existingKeywords.includes(trimmedKeyword)) {
            return { skipped: true }
          }
          const nextKeywords = [...existingKeywords, trimmedKeyword]
          await updatePrompt(
            buildPromptUpdatePayload(prompt, {
              keywords: nextKeywords,
              tags: nextKeywords
            })
          )
          return { skipped: false }
        })
      )

      let updated = 0
      let skipped = 0
      const failedIds: string[] = []
      for (let index = 0; index < results.length; index += 1) {
        const result = results[index]
        if (result?.status === "rejected") {
          failedIds.push(ids[index]!)
          continue
        }
        if (result.value?.skipped) {
          skipped += 1
        } else {
          updated += 1
        }
      }
      return {
        total: ids.length,
        updated,
        skipped,
        failedIds,
        keyword: trimmedKeyword
      }
    },
    onSuccess: ({ total, updated, skipped, failedIds, keyword }) => {
      queryClient.invalidateQueries({
        queryKey: ["fetchAllPrompts"]
      })
      setBulkKeywordModalOpen(false)
      setBulkKeywordValue("")

      if (failedIds.length > 0) {
        setSelectedRowKeys(failedIds)
        notification.warning({
          message: t("managePrompts.bulk.keywordPartial", {
            defaultValue: "Bulk keyword update completed with issues"
          }),
          description: t("managePrompts.bulk.keywordPartialDesc", {
            defaultValue:
              "Updated {{updated}}, skipped {{skipped}}, failed {{failed}} of {{total}} prompts.",
            updated,
            skipped,
            failed: failedIds.length,
            total
          })
        })
        return
      }

      notification.success({
        message: t("managePrompts.bulk.keywordSuccess", {
          defaultValue: "Keyword added to selected prompts"
        }),
        description: t("managePrompts.bulk.keywordSuccessDesc", {
          defaultValue:
            "Added '{{keyword}}' to {{updated}} prompts ({{skipped}} already had it).",
          keyword,
          updated,
          skipped
        })
      })
    },
    onError: (error) => {
      notification.error({
        message: t("managePrompts.notification.error"),
        description: error?.message || t("managePrompts.notification.someError")
      })
    }
  })

  const { mutate: bulkPushToServer, isPending: isBulkPushing } = useMutation({
    mutationFn: async (ids: string[]) => {
      const results = await Promise.allSettled(
        ids.map(async (id) => {
          const result = await autoSyncPrompt(id)
          if (!result.success) {
            throw new Error(
              result.error ||
                t("managePrompts.sync.pendingTooltip", {
                  defaultValue: "Local changes not yet synced"
                })
            )
          }
        })
      )

      const failedIds: string[] = []
      for (let index = 0; index < results.length; index += 1) {
        if (results[index]?.status === "rejected") {
          failedIds.push(ids[index]!)
        }
      }
      return {
        total: ids.length,
        synced: ids.length - failedIds.length,
        failedIds
      }
    },
    onSuccess: ({ total, synced, failedIds }) => {
      queryClient.invalidateQueries({ queryKey: ["fetchAllPrompts"] })
      if (failedIds.length > 0) {
        setSelectedRowKeys(failedIds)
        notification.warning({
          message: t("managePrompts.sync.bulkPushPartial", {
            defaultValue: "Bulk sync completed with issues"
          }),
          description: t("managePrompts.sync.bulkPushPartialDesc", {
            defaultValue:
              "Synced {{synced}} of {{total}} prompts. {{failed}} failed.",
            synced,
            total,
            failed: failedIds.length
          })
        })
        return
      }
      notification.success({
        message: t("managePrompts.sync.bulkPushSuccess", {
          defaultValue: "Selected prompts synced"
        }),
        description: t("managePrompts.sync.bulkPushSuccessDesc", {
          defaultValue: "Synced {{count}} prompts to the server.",
          count: synced
        })
      })
    },
    onError: (error) => {
      notification.error({
        message: t("managePrompts.notification.error"),
        description: error?.message || t("managePrompts.notification.someError")
      })
    }
  })

  const {
    mutate: createPromptCollectionMutation,
    isPending: isCreatingPromptCollection
  } = useMutation({
    mutationFn: async ({
      name,
      description
    }: {
      name: string
      description?: string
    }) =>
      createPromptCollectionServer({
        name: name.trim(),
        description: description?.trim() || undefined
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["promptCollections"] })
      setCreateCollectionModalOpen(false)
      setNewCollectionName("")
      setNewCollectionDescription("")
      notification.success({
        message: t("managePrompts.collections.createSuccess", {
          defaultValue: "Collection created"
        }),
        description: t("managePrompts.collections.createSuccessDesc", {
          defaultValue: "Prompt collection created successfully."
        })
      })
    },
    onError: (error: any) => {
      notification.error({
        message: t("managePrompts.notification.error"),
        description:
          error?.message || t("managePrompts.notification.someError")
      })
    }
  })

  const {
    mutate: addPromptsToCollectionMutation,
    isPending: isAssigningPromptCollection
  } = useMutation({
    mutationFn: async ({
      collection,
      prompts
    }: {
      collection: PromptCollection
      prompts: any[]
    }) => {
      const merged = mergePromptIdsForCollection(
        collection.prompt_ids || [],
        prompts
      )
      if (merged.added === 0) {
        return {
          added: 0,
          skipped: merged.skipped,
          updatedCollection: null
        }
      }
      const updatedCollection = await updatePromptCollectionServer(
        collection.collection_id,
        { prompt_ids: merged.promptIds }
      )
      return {
        added: merged.added,
        skipped: merged.skipped,
        updatedCollection
      }
    },
    onSuccess: ({ added, skipped }, variables) => {
      queryClient.invalidateQueries({ queryKey: ["promptCollections"] })
      if (added === 0) {
        notification.info({
          message: t("managePrompts.collections.assignNoChanges", {
            defaultValue: "No prompts were added"
          }),
          description:
            skipped > 0
              ? t("managePrompts.collections.assignNoChangesSkipped", {
                  defaultValue:
                    "Selected prompts are already in this collection or not synced yet."
                })
              : t("managePrompts.collections.assignNoChangesDefault", {
                  defaultValue:
                    "Selected prompts are already in this collection."
                })
        })
        return
      }
      setSelectedRowKeys([])
      notification.success({
        message: t("managePrompts.collections.assignSuccess", {
          defaultValue: "Prompts added to collection"
        }),
        description: t("managePrompts.collections.assignSuccessDesc", {
          defaultValue:
            "Added {{added}} prompt(s) to {{name}}{{skippedLabel}}.",
          added,
          name: variables.collection.name,
          skippedLabel:
            skipped > 0
              ? t("managePrompts.collections.assignSkippedSuffix", {
                  defaultValue: " ({{count}} skipped)",
                  count: skipped
                })
              : ""
        })
      })
    },
    onError: (error: any) => {
      notification.error({
        message: t("managePrompts.notification.error"),
        description:
          error?.message || t("managePrompts.notification.someError")
      })
    }
  })

  const { mutate: savePromptMutation, isPending: savePromptLoading } =
    useMutation({
      mutationFn: async (payload: any) => {
        const savedPrompt = await savePrompt(payload)
        const syncState = await syncPromptAfterLocalSave(savedPrompt.id)
        return {
          id: savedPrompt.id,
          syncState
        }
      },
      onSuccess: ({ syncState }) => {
        queryClient.invalidateQueries({
          queryKey: ["fetchAllPrompts"]
        })
        setDrawerOpen(false)
        setDrawerInitialValues(null)
        notification.success({
          message: t("managePrompts.notification.addSuccess"),
          description: t("managePrompts.notification.addSuccessDesc")
        })
        void syncState
      },
      onError: (error) => {
        notification.error({
          message: t("managePrompts.notification.error"),
          description:
            error?.message || t("managePrompts.notification.someError")
        })
      }
    })

  const { mutate: updatePromptDirect } = useMutation({
    mutationFn: async (payload: any) => {
      const id = await updatePrompt(payload)
      await syncPromptAfterLocalSave(id)
      return id
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["fetchAllPrompts"]
      })
    },
    onError: (error) => {
      notification.error({
        message: t("managePrompts.notification.error"),
        description:
          error?.message || t("managePrompts.notification.someError")
      })
    }
  })

  const { mutate: updatePromptMutation, isPending: isUpdatingPrompt } =
    useMutation({
      mutationFn: async (data: any) => {
        const id = await updatePrompt({
          ...data,
          id: editId
        })
        const syncState = await syncPromptAfterLocalSave(id)
        return {
          id,
          syncState
        }
      },
      onSuccess: ({ syncState }) => {
        queryClient.invalidateQueries({
          queryKey: ["fetchAllPrompts"]
        })
        setDrawerOpen(false)
        setDrawerInitialValues(null)
        notification.success({
          message: t("managePrompts.notification.updatedSuccess"),
          description: t("managePrompts.notification.updatedSuccessDesc")
        })
        void syncState
      },
      onError: (error) => {
        notification.error({
          message: t("managePrompts.notification.error"),
          description:
            error?.message || t("managePrompts.notification.someError")
        })
      }
    })

  const { mutate: updateCopilotPrompt, isPending: isUpdatingCopilotPrompt } =
    useMutation({
      mutationFn: async (data: any) => {
        return await upsertCopilotPrompts([
          {
            key: data.key,
            prompt: data.prompt
          }
        ])
      },
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["fetchCopilotPrompts"]
        })
        setOpenCopilotEdit(false)
        editCopilotForm.resetFields()
        notification.success({
          message: t("managePrompts.notification.updatedSuccess"),
          description: t("managePrompts.notification.updatedSuccessDesc")
        })
      },
      onError: (error) => {
        notification.error({
          message: t("managePrompts.notification.error"),
          description:
            error?.message || t("managePrompts.notification.someError")
        })
      }
    })

  const allTags = useMemo(() => {
    const set = new Set<string>()
    ;(data || []).forEach((p: any) =>
      (getPromptKeywords(p) || []).forEach((t: string) => set.add(t))
    )
    return Array.from(set.values())
  }, [data, getPromptKeywords])

  const promptCollections = useMemo<PromptCollection[]>(() => {
    if (!Array.isArray(promptCollectionsData)) return []
    return promptCollectionsData
  }, [promptCollectionsData])

  const selectedCollection = useMemo(() => {
    if (collectionFilter === "all") return null
    return (
      promptCollections.find((item) => item.collection_id === collectionFilter) ||
      null
    )
  }, [collectionFilter, promptCollections])

  useEffect(() => {
    if (collectionFilter === "all") return
    if (!selectedCollection) {
      setCollectionFilter("all")
    }
  }, [collectionFilter, selectedCollection])

  const copilotPromptIncludesTextPlaceholder =
    typeof copilotEditPromptValue === "string" &&
    copilotEditPromptValue.includes("{text}")

  const copilotPromptKeyOptions = useMemo(() => {
    if (!Array.isArray(copilotData)) return []
    const keys = Array.from(
      new Set(
        copilotData
          .map((item) => (typeof item?.key === "string" ? item.key : ""))
          .filter((key) => key.length > 0)
      )
    )
    return keys.map((key) => ({
      value: key,
      label: t(`common:copilot.${key}`, { defaultValue: key })
    }))
  }, [copilotData, t])

  const filteredCopilotData = useMemo(() => {
    if (!Array.isArray(copilotData)) return []
    return filterCopilotPrompts(copilotData, {
      keyFilter: copilotKeyFilter,
      queryLower: copilotSearchText.trim().toLowerCase(),
      resolveKeyLabel: (key) => t(`common:copilot.${key}`, { defaultValue: key })
    })
  }, [copilotData, copilotKeyFilter, copilotSearchText, t])

  const filteredTrashData = useMemo(() => {
    if (!Array.isArray(trashData)) return []
    return filterTrashPromptsByName(trashData, trashSearchText)
  }, [trashData, trashSearchText])

  const getPromptRecordById = React.useCallback(
    (promptId: string) => {
      const prompts = Array.isArray(data) ? data : []
      return prompts.find((prompt: any) => String(prompt?.id) === String(promptId))
    },
    [data]
  )

  const inspectorPrompt = useMemo<PromptRowVM | null>(() => {
    if (!inspectorPromptId) return null
    const promptRecord = getPromptRecordById(inspectorPromptId)
    if (!promptRecord) return null
    const { systemText, userText } = getPromptTexts(promptRecord)
    return {
      id: promptRecord.id,
      title:
        promptRecord?.name || promptRecord?.title || t("common:untitled", { defaultValue: "Untitled" }),
      author: promptRecord?.author,
      details: promptRecord?.details,
      previewSystem: systemText || undefined,
      previewUser: userText || undefined,
      keywords: getPromptKeywords(promptRecord) || [],
      favorite: !!promptRecord?.favorite,
      syncStatus: promptRecord?.syncStatus || "local",
      sourceSystem: promptRecord?.sourceSystem || "workspace",
      serverId: promptRecord?.serverId,
      updatedAt: getPromptModifiedAt(promptRecord),
      createdAt:
        typeof promptRecord?.createdAt === "number"
          ? promptRecord.createdAt
          : Date.now(),
      usageCount: getPromptUsageCount(promptRecord),
      lastUsedAt: getPromptLastUsedAt(promptRecord)
    }
  }, [
    inspectorPromptId,
    getPromptRecordById,
    getPromptTexts,
    getPromptKeywords,
    getPromptModifiedAt,
    getPromptUsageCount,
    getPromptLastUsedAt,
    t
  ])

  useEffect(() => {
    if (!inspectorOpen) return
    if (inspectorPrompt) return
    setInspectorOpen(false)
    setInspectorPromptId(null)
  }, [inspectorOpen, inspectorPrompt])

  const selectedPromptRows = useMemo(() => {
    const selectedIds = new Set(selectedRowKeys.map((key) => String(key)))
    return (data || []).filter((prompt: any) => selectedIds.has(prompt.id))
  }, [data, selectedRowKeys])

  const allSelectedAreFavorite = useMemo(() => {
    return (
      selectedPromptRows.length > 0 &&
      selectedPromptRows.every((prompt: any) => !!prompt?.favorite)
    )
  }, [selectedPromptRows])

  const pendingSyncCount = useMemo(() => {
    const prompts = Array.isArray(data) ? data : []
    return prompts.filter((prompt: any) => prompt?.syncStatus === "pending").length
  }, [data])

  const localSyncBatchPlan = useMemo(() => {
    const prompts = Array.isArray(data) ? data : []
    return buildSyncBatchPlan(
      prompts.map((prompt: any) => ({
        prompt,
        syncStatus: prompt?.syncStatus
      }))
    )
  }, [data])

  const baseFilteredData = useMemo(() => {
    let items = (data || []) as any[]
    // Filter by linked project if ?project= query param is present
    if (projectFilter) {
      const projectId = parseInt(projectFilter, 10)
      if (!isNaN(projectId)) {
        items = items.filter((p) => p.studioProjectId === projectId)
      }
    }
    if (typeFilter !== "all") {
      items = items.filter((p) => {
        const promptType = getPromptType(p)
        if (typeFilter === "system") return promptType === "system" || promptType === "mixed"
        if (typeFilter === "quick") return promptType === "quick" || promptType === "mixed"
        return promptType === typeFilter
      })
    }
    if (usageFilter !== "all") {
      items = items.filter((p) =>
        usageFilter === "used"
          ? getPromptUsageCount(p) > 0
          : getPromptUsageCount(p) === 0
      )
    }
    if (selectedCollection) {
      const selectedPromptIds = new Set(selectedCollection.prompt_ids || [])
      items = items.filter((prompt) =>
        isPromptInCollection(prompt, selectedPromptIds)
      )
    }
    if (tagFilter.length > 0) {
      items = items.filter((p) =>
        matchesTagFilter(getPromptKeywords(p), tagFilter, tagMatchMode)
      )
    }
    // favorites first, then newest
    items = items.sort(
      (a, b) =>
        Number(!!b.favorite) - Number(!!a.favorite) ||
        (b.createdAt || 0) - (a.createdAt || 0)
    )
    return items
  }, [
    data,
    projectFilter,
    typeFilter,
    usageFilter,
    selectedCollection,
    tagFilter,
    tagMatchMode,
    getPromptUsageCount,
    getPromptKeywords,
    getPromptType
  ])

  const localSearchFilteredData = useMemo(() => {
    if (normalizedSearchText.length === 0) {
      return baseFilteredData
    }
    const queryLower = normalizedSearchText.toLowerCase()
    return baseFilteredData.filter((prompt) =>
      matchesPromptSearchText(prompt, queryLower, getPromptKeywords)
    )
  }, [baseFilteredData, normalizedSearchText, getPromptKeywords])

  const serverSearchMappedData = useMemo(() => {
    if (!shouldUseServerSearch || serverSearchStatus !== "success" || !serverSearchData) {
      return []
    }
    return mapServerSearchItemsToLocalPrompts(serverSearchData.items, baseFilteredData)
  }, [baseFilteredData, serverSearchData, serverSearchStatus, shouldUseServerSearch])

  const useServerSearchResults =
    shouldUseServerSearch && serverSearchStatus === "success"

  const filteredData = useMemo(() => {
    if (useServerSearchResults) {
      return serverSearchMappedData
    }
    return localSearchFilteredData
  }, [localSearchFilteredData, serverSearchMappedData, useServerSearchResults])

  const sortedFilteredData = useMemo(() => {
    if (!promptSort.key || !promptSort.order) {
      return filteredData
    }

    const direction = promptSort.order === "ascend" ? 1 : -1
    const items = [...filteredData]

    items.sort((a, b) => {
      let compare = 0
      if (promptSort.key === "title") {
        compare = String(a?.name || a?.title || "").localeCompare(
          String(b?.name || b?.title || "")
        )
      } else if (promptSort.key === "modifiedAt") {
        compare = getPromptModifiedAt(a) - getPromptModifiedAt(b)
      }
      if (compare === 0) {
        compare = getPromptModifiedAt(a) - getPromptModifiedAt(b)
      }
      return compare * direction
    })

    return items
  }, [
    filteredData,
    getPromptModifiedAt,
    promptSort.key,
    promptSort.order
  ])

  const paginatedData = useMemo(() => {
    if (useServerSearchResults) {
      return sortedFilteredData
    }
    const start = (currentPage - 1) * resultsPerPage
    return sortedFilteredData.slice(start, start + resultsPerPage)
  }, [currentPage, resultsPerPage, sortedFilteredData, useServerSearchResults])

  const tableTotal = useMemo(() => {
    if (useServerSearchResults) {
      return serverSearchData?.total_matches ?? sortedFilteredData.length
    }
    return sortedFilteredData.length
  }, [serverSearchData?.total_matches, sortedFilteredData.length, useServerSearchResults])

  const customPromptRows = useMemo<PromptRowVM[]>(() => {
    return paginatedData.map((prompt: any) => {
      const { systemText, userText } = getPromptTexts(prompt)
      return {
        id: String(prompt?.id || ""),
        title:
          prompt?.name ||
          prompt?.title ||
          t("common:untitled", { defaultValue: "Untitled" }),
        author: prompt?.author,
        details: prompt?.details,
        previewSystem: systemText || undefined,
        previewUser: userText || undefined,
        keywords: getPromptKeywords(prompt) || [],
        favorite: !!prompt?.favorite,
        syncStatus: prompt?.syncStatus || "local",
        sourceSystem: prompt?.sourceSystem || "workspace",
        serverId: prompt?.serverId,
        updatedAt: getPromptModifiedAt(prompt),
        createdAt:
          typeof prompt?.createdAt === "number" ? prompt.createdAt : Date.now(),
        usageCount: getPromptUsageCount(prompt),
        lastUsedAt: getPromptLastUsedAt(prompt)
      }
    })
  }, [
    paginatedData,
    getPromptTexts,
    t,
    getPromptKeywords,
    getPromptModifiedAt,
    getPromptUsageCount,
    getPromptLastUsedAt
  ])

  const customPromptTableQuery: PromptListQueryState = {
    searchText,
    typeFilter: typeFilter,
    syncFilter: "all",
    usageFilter,
    tagFilter,
    tagMatchMode,
    sort: {
      key: promptSort.key,
      order: promptSort.order
    },
    page: currentPage,
    pageSize: resultsPerPage,
    savedView: "all"
  }

  const hiddenServerResultsOnPage = useMemo(() => {
    if (!useServerSearchResults || !serverSearchData) {
      return 0
    }
    return Math.max(0, serverSearchData.items.length - serverSearchMappedData.length)
  }, [serverSearchData, serverSearchMappedData.length, useServerSearchResults])

  const customPromptsLoading =
    status === "pending" ||
    (shouldUseServerSearch && serverSearchStatus === "pending")

  React.useEffect(() => {
    // Only clear selection for items that are no longer visible
    const visibleIds = new Set(sortedFilteredData.map((p: any) => p.id))
    setSelectedRowKeys((prev) => {
      const stillVisible = prev.filter((key) => visibleIds.has(key as string))
      if (stillVisible.length !== prev.length) {
        if (stillVisible.length < prev.length && prev.length > 0) {
          notification.info({
            message: t("managePrompts.selectionFiltered", {
              defaultValue: "Some selected items were filtered out"
            }),
            duration: 2
          })
        }
        return stillVisible
      }
      return prev
    })
  }, [sortedFilteredData, t])

  const triggerExport = async () => {
    try {
      if (guardPrivateMode()) return
      if (exportFormat === "json") {
        const items = await exportPrompts()
        const blob = new Blob([JSON.stringify(items, null, 2)], {
          type: "application/json"
        })
        const url = URL.createObjectURL(blob)
        const a = document.createElement("a")
        a.href = url
        const safeStamp = new Date().toISOString().replace(/[:]/g, "-")
        a.download = `prompts_${safeStamp}.json`
        a.click()
        URL.revokeObjectURL(url)
        return
      }

      if (!isOnline) {
        notification.warning({
          message: t("managePrompts.exportOffline", {
            defaultValue: "Server export unavailable offline"
          }),
          description: t("managePrompts.exportOfflineDesc", {
            defaultValue: "Reconnect to export CSV or Markdown."
          })
        })
        return
      }

      const response = await exportPromptsServer(exportFormat)
      if (!response?.file_content_b64) {
        notification.info({
          message: t("managePrompts.exportEmpty", {
            defaultValue: "Nothing to export"
          }),
          description:
            response?.message ||
            t("managePrompts.exportEmptyDesc", {
              defaultValue: "No prompts matched the export criteria."
            })
        })
        return
      }

      const binary = atob(response.file_content_b64)
      const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0))
      const fileExtension = exportFormat === "csv" ? "csv" : "md"
      const mimeType = exportFormat === "csv" ? "text/csv" : "text/markdown"
      const blob = new Blob([bytes], {
        type: `${mimeType};charset=utf-8`
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      const safeStamp = new Date().toISOString().replace(/[:]/g, "-")
      a.download = `prompts_${safeStamp}.${fileExtension}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      notification.error({
        message: t("managePrompts.notification.error"),
        description: t("managePrompts.notification.someError")
      })
    }
  }

  const triggerBulkExport = async () => {
    try {
      if (guardPrivateMode()) return
      const selectedItems = (data || []).filter((p: any) => selectedRowKeys.includes(p.id))
      const blob = new Blob([JSON.stringify(selectedItems, null, 2)], {
        type: "application/json"
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `prompts_selected_${new Date().toISOString()}.json`
      a.click()
      URL.revokeObjectURL(url)
      setSelectedRowKeys([])
    } catch (e) {
      notification.error({
        message: t("managePrompts.notification.error"),
        description: t("managePrompts.notification.someError")
      })
    }
  }

  const handleImportFile = async (file: File) => {
    try {
      if (guardPrivateMode()) return
      const text = await file.text()
      const prompts = parseImportPromptsPayload(text)

      if (importMode === "replace") {
        // Get current prompts count for confirmation message
        const currentPrompts = data || []
        const currentCount = currentPrompts.length

        const ok = await confirmDanger({
          title: t("managePrompts.importMode.replaceTitle", { defaultValue: "Replace all prompts?" }),
          content: t("managePrompts.importMode.replaceConfirmWithCount", {
            defaultValue:
              "This will delete {{currentCount}} existing prompts and import {{newCount}} new prompts. A backup will be downloaded automatically before replacing.",
            currentCount,
            newCount: prompts.length
          }),
          okText: t("managePrompts.importMode.replaceAndBackup", { defaultValue: "Backup & Replace" }),
          cancelText: t("common:cancel", { defaultValue: "Cancel" })
        })
        if (!ok) return

        // Auto-backup current prompts before replacing
        if (currentCount > 0) {
          try {
            const backupItems = await exportPrompts()
            const blob = new Blob([JSON.stringify(backupItems, null, 2)], {
              type: "application/json"
            })
            const url = URL.createObjectURL(blob)
            const a = document.createElement("a")
            a.href = url
            const safeStamp = new Date().toISOString().replace(/[:]/g, "-")
            a.download = `prompts_backup_before_replace_${safeStamp}.json`
            a.click()
            URL.revokeObjectURL(url)
            // Small delay to ensure download starts
            await new Promise(resolve => setTimeout(resolve, 100))
          } catch (backupError) {
            // If backup fails, warn user but continue
            notification.warning({
              message: t("managePrompts.notification.backupFailed", { defaultValue: "Backup failed" }),
              description: t("managePrompts.notification.backupFailedDesc", {
                defaultValue: "Could not create backup, but proceeding with import."
              })
            })
          }
        }
      }

      const importResult = await importPromptsV2(prompts, {
        replaceExisting: importMode === "replace",
        mergeData: importMode === "merge"
      })
      const importCounts = normalizePromptImportCounts(importResult, prompts.length)
      const importNotificationCopy = getPromptImportNotificationCopy(
        importMode,
        importCounts
      )
      queryClient.invalidateQueries({ queryKey: ["fetchAllPrompts"] })
      queryClient.invalidateQueries({ queryKey: ["fetchDeletedPrompts"] })
      notification.success({
        message: t("managePrompts.notification.addSuccess"),
        description: t(importNotificationCopy.key, {
          defaultValue: importNotificationCopy.defaultValue,
          ...importNotificationCopy.values
        })
      })
    } catch (e) {
      const importErrorNotice = getPromptImportErrorNotice(e)
      if (importErrorNotice) {
        notification.error({
          message: t(importErrorNotice.titleKey, {
            defaultValue: importErrorNotice.titleDefaultValue
          }),
          description: t(importErrorNotice.descriptionKey, {
            defaultValue: importErrorNotice.descriptionDefaultValue,
            ...(importErrorNotice.values || {})
          })
        })
        return
      }
      notification.error({
        message: t("managePrompts.notification.error"),
        description: t("managePrompts.notification.someError")
      })
    }
  }

  const handleInsertChoice = async (choice: "system" | "quick" | "both") => {
    if (!insertPrompt) return
    await markPromptAsUsed(insertPrompt.id)
    if (choice === "system") {
      setSelectedSystemPrompt(insertPrompt.id)
      setSelectedQuickPrompt(undefined)
      setInsertPrompt(null)
      navigate("/chat")
      return
    }
    if (choice === "both") {
      // Apply both system instruction and insert user template
      setSelectedSystemPrompt(insertPrompt.id)
      if (insertPrompt.userText) {
        setSelectedQuickPrompt(insertPrompt.userText)
      }
      setInsertPrompt(null)
      navigate("/chat")
      return
    }
    const quickContent = insertPrompt.userText ?? insertPrompt.systemText
    if (quickContent) {
      setSelectedQuickPrompt(quickContent)
      setSelectedSystemPrompt(undefined)
      setInsertPrompt(null)
      navigate("/chat")
    }
  }

  const openCreateDrawer = React.useCallback(
    (initialValues: Record<string, unknown> | null = null) => {
      if (guardPrivateMode()) return
      setDrawerMode("create")
      setEditId("")
      setDrawerInitialValues(initialValues)
      setDrawerOpen(true)
    },
    [guardPrivateMode]
  )

  const copyCopilotToCustom = React.useCallback(
    (record: { key?: string; prompt?: string }) => {
      const promptText = typeof record?.prompt === "string" ? record.prompt : ""
      const labelKey = typeof record?.key === "string" ? record.key : "custom"
      const label = t(`common:copilot.${labelKey}`, { defaultValue: labelKey })
      const namePrefix = t("managePrompts.copilot.copyToCustom.namePrefix", {
        defaultValue: "Copilot"
      })
      setSelectedSegment("custom")
      openCreateDrawer({
        name: `${namePrefix}: ${label}`,
        user_prompt: promptText
      })
    },
    [openCreateDrawer, t]
  )

  const copyCopilotPromptToClipboard = React.useCallback(
    async (record: { prompt?: string }) => {
      const promptText = typeof record?.prompt === "string" ? record.prompt : ""
      if (!promptText) {
        notification.warning({
          message: t("managePrompts.copilot.clipboard.emptyTitle", {
            defaultValue: "Nothing to copy"
          }),
          description: t("managePrompts.copilot.clipboard.emptyDesc", {
            defaultValue: "This copilot prompt is empty."
          })
        })
        return
      }

      try {
        if (
          typeof navigator === "undefined" ||
          !navigator.clipboard ||
          typeof navigator.clipboard.writeText !== "function"
        ) {
          throw new Error(
            t("managePrompts.copilot.clipboard.notSupported", {
              defaultValue: "Clipboard is not available in this environment."
            })
          )
        }
        await navigator.clipboard.writeText(promptText)
        notification.success({
          message: t("managePrompts.copilot.clipboard.successTitle", {
            defaultValue: "Copied to clipboard"
          }),
          description: t("managePrompts.copilot.clipboard.successDesc", {
            defaultValue: "Copilot prompt text was copied."
          })
        })
      } catch (error: any) {
        notification.error({
          message: t("managePrompts.copilot.clipboard.errorTitle", {
            defaultValue: "Copy failed"
          }),
          description:
            error?.message ||
            t("managePrompts.copilot.clipboard.errorDesc", {
              defaultValue: "Could not copy prompt text to clipboard."
            })
        })
      }
    },
    [t]
  )

  const copyPromptShareLink = React.useCallback(
    async (record: { serverId?: number | null }) => {
      const serverId = record?.serverId
      if (typeof serverId !== "number" || serverId <= 0) {
        notification.warning({
          message: t("managePrompts.share.missingServerIdTitle", {
            defaultValue: "Share link unavailable"
          }),
          description: t("managePrompts.share.missingServerIdDesc", {
            defaultValue:
              "Only prompts synced to the server can generate a share link."
          })
        })
        return
      }
      if (
        typeof navigator === "undefined" ||
        !navigator.clipboard ||
        typeof navigator.clipboard.writeText !== "function"
      ) {
        notification.error({
          message: t("managePrompts.share.copyUnavailableTitle", {
            defaultValue: "Clipboard unavailable"
          }),
          description: t("managePrompts.share.copyUnavailableDesc", {
            defaultValue:
              "Your browser does not allow copying links automatically."
          })
        })
        return
      }
      const url = new URL(window.location.href)
      url.searchParams.set("prompt", String(serverId))
      url.searchParams.set("source", "studio")
      const shareUrl = `${url.origin}${url.pathname}?${url.searchParams.toString()}`
      try {
        await navigator.clipboard.writeText(shareUrl)
        notification.success({
          message: t("managePrompts.share.copySuccessTitle", {
            defaultValue: "Share link copied"
          }),
          description: t("managePrompts.share.copySuccessDesc", {
            defaultValue:
              "Send this link to another user with access to your prompt server."
          })
        })
      } catch {
        notification.error({
          message: t("managePrompts.share.copyFailedTitle", {
            defaultValue: "Could not copy link"
          }),
          description: t("managePrompts.share.copyFailedDesc", {
            defaultValue:
              "Copy failed. Please try again."
          })
        })
      }
    },
    [t]
  )

  const closeLocalQuickTestModal = React.useCallback(() => {
    setLocalQuickTestPrompt(null)
    setLocalQuickTestInput("")
    setLocalQuickTestOutput(null)
    setLocalQuickTestRunInfo(null)
  }, [])

  const openLocalQuickTestModal = React.useCallback(
    (record: any) => {
      const { systemText, userText } = getPromptTexts(record)
      setLocalQuickTestPrompt({
        id: String(record?.id || ""),
        name: record?.name || record?.title || "Prompt",
        systemText: systemText?.trim() || undefined,
        userText: userText?.trim() || undefined
      })
      setLocalQuickTestInput("")
      setLocalQuickTestOutput(null)
      setLocalQuickTestRunInfo(null)
    },
    [getPromptTexts]
  )

  const openStudioQuickTest = React.useCallback(
    async (record: any) => {
      const serverPromptId = Number(record?.serverId)
      if (!Number.isInteger(serverPromptId) || serverPromptId <= 0) {
        openLocalQuickTestModal(record)
        return
      }

      if (!isOnline || hasStudio === false) {
        notification.warning({
          message: t("managePrompts.quickTest.studioUnavailableTitle", {
            defaultValue: "Studio quick test unavailable"
          }),
          description: t("managePrompts.quickTest.studioUnavailableDesc", {
            defaultValue:
              "Prompt Studio is unavailable right now, so local quick test is opening instead."
          })
        })
        openLocalQuickTestModal(record)
        return
      }

      let projectId =
        typeof record?.studioProjectId === "number" && record.studioProjectId > 0
          ? record.studioProjectId
          : null

      if (!projectId) {
        try {
          const response = await getStudioPromptById(serverPromptId)
          const serverPrompt = (response as any)?.data?.data
          if (
            typeof serverPrompt?.project_id === "number" &&
            serverPrompt.project_id > 0
          ) {
            projectId = serverPrompt.project_id
          }
        } catch {
          projectId = null
        }
      }

      if (!projectId) {
        notification.warning({
          message: t("managePrompts.quickTest.missingProjectTitle", {
            defaultValue: "Quick test unavailable"
          }),
          description: t("managePrompts.quickTest.missingProjectDesc", {
            defaultValue:
              "This prompt is synced, but its Prompt Studio project could not be resolved."
          })
        })
        return
      }

      setStudioSelectedProjectId(projectId)
      setStudioSelectedPromptId(serverPromptId)
      setStudioActiveSubTab("prompts")
      setStudioExecutePlaygroundOpen(true)
      setSelectedSegment("studio")
    },
    [
      hasStudio,
      isOnline,
      openLocalQuickTestModal,
      setStudioActiveSubTab,
      setStudioExecutePlaygroundOpen,
      setStudioSelectedProjectId,
      setStudioSelectedPromptId,
      t
    ]
  )

  const handleQuickTest = React.useCallback(
    async (record: any) => {
      const hasServerPromptId =
        typeof record?.serverId === "number" && record.serverId > 0
      if (hasServerPromptId) {
        await openStudioQuickTest(record)
        return
      }
      openLocalQuickTestModal(record)
    },
    [openLocalQuickTestModal, openStudioQuickTest]
  )

  const runLocalQuickTest = React.useCallback(async () => {
    if (!localQuickTestPrompt || isRunningLocalQuickTest) return

    const userTemplate = localQuickTestPrompt.userText || ""
    const systemTemplate = localQuickTestPrompt.systemText || ""
    const normalizedInput = localQuickTestInput.trim()
    const textTemplateRegex = /\{\{\s*text\s*\}\}/gi
    const hasTextTemplateVar = textTemplateRegex.test(userTemplate)

    if (hasTextTemplateVar && normalizedInput.length === 0) {
      notification.warning({
        message: t("managePrompts.quickTest.inputRequiredTitle", {
          defaultValue: "Input required"
        }),
        description: t("managePrompts.quickTest.inputRequiredDesc", {
          defaultValue:
            "This prompt uses {{text}}. Enter sample input before running quick test."
        })
      })
      return
    }

    let userMessage = userTemplate
    if (hasTextTemplateVar) {
      userMessage = userTemplate.replace(/\{\{\s*text\s*\}\}/gi, normalizedInput)
    } else if (userTemplate && normalizedInput) {
      userMessage = `${userTemplate}\n\n${normalizedInput}`
    } else if (!userTemplate) {
      userMessage = normalizedInput
    }

    if (!userMessage.trim()) {
      notification.warning({
        message: t("managePrompts.quickTest.noMessageTitle", {
          defaultValue: "Nothing to test"
        }),
        description: t("managePrompts.quickTest.noMessageDesc", {
          defaultValue:
            "Add prompt content or input text before running quick test."
        })
      })
      return
    }

    setIsRunningLocalQuickTest(true)
    setLocalQuickTestOutput(null)
    setLocalQuickTestRunInfo(null)

    let provider: string | undefined
    let model = "gpt-4o-mini"

    try {
      const llmProvidersResponse = await getLlmProviders()
      const providersPayload =
        (llmProvidersResponse as any)?.data ?? llmProvidersResponse
      const providersCatalog = normalizeExecuteProvidersCatalog(providersPayload)
      const resolvedProvider = getExecuteDefaultProvider(providersCatalog) || undefined
      const resolvedModel =
        getExecuteDefaultModel(providersCatalog, resolvedProvider) || null
      provider = resolvedProvider
      if (resolvedModel) {
        model = resolvedModel
      }
    } catch {
      // Keep fallback defaults when provider lookup fails.
    }

    try {
      await tldwClient.initialize().catch(() => null)
      const messages: Array<{ role: "system" | "user"; content: string }> = []

      if (systemTemplate.trim()) {
        messages.push({
          role: "system",
          content: systemTemplate.trim()
        })
      }

      messages.push({
        role: "user",
        content: userMessage
      })

      const completionResponse = await tldwClient.createChatCompletion({
        model,
        api_provider: provider,
        messages,
        temperature: 0.2
      })
      const completionPayload = await completionResponse.json()
      const outputCandidate =
        completionPayload?.choices?.[0]?.message?.content ??
        completionPayload?.output ??
        completionPayload?.content
      const output =
        typeof outputCandidate === "string" ? outputCandidate.trim() : ""

      if (!output) {
        throw new Error(
          t("managePrompts.quickTest.emptyResultError", {
            defaultValue: "The model returned an empty result."
          })
        )
      }

      setLocalQuickTestOutput(output)
      setLocalQuickTestRunInfo({ provider, model })
    } catch (error: any) {
      notification.error({
        message: t("managePrompts.quickTest.runFailedTitle", {
          defaultValue: "Quick test failed"
        }),
        description:
          error?.message ||
          t("managePrompts.quickTest.runFailedDesc", {
            defaultValue:
              "The quick test request could not be completed."
          })
      })
    } finally {
      setIsRunningLocalQuickTest(false)
    }
  }, [isRunningLocalQuickTest, localQuickTestInput, localQuickTestPrompt, t])

  // Keyboard shortcuts: N = new prompt, / = focus search, Esc = close drawer, ? = open shortcut help
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      const isInput = target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT" || target.isContentEditable
      if (e.key === "Escape") {
        if (shortcutsHelpOpen) {
          setShortcutsHelpOpen(false)
          return
        }
        if (drawerOpen) {
          setDrawerOpen(false)
        }
        return
      }
      if (isInput) return
      if (
        (e.key === "?" || (e.key === "/" && e.shiftKey)) &&
        !e.metaKey &&
        !e.ctrlKey &&
        !e.altKey
      ) {
        e.preventDefault()
        setShortcutsHelpOpen(true)
        return
      }
      if (e.key === "n" && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault()
        openCreateDrawer()
        return
      }
      if (e.key === "/" && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault()
        searchInputRef.current?.focus()
      }
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [drawerOpen, shortcutsHelpOpen, openCreateDrawer])

  const openEditDrawer = (record: any) => {
    if (guardPrivateMode()) return
    setEditId(record.id)
    setDrawerMode("edit")
    const { systemText, userText } = getPromptTexts(record)
    setDrawerInitialValues({
      id: record?.id,
      name: record?.name || record?.title,
      author: record?.author,
      details: record?.details,
      system_prompt: systemText,
      user_prompt: userText,
      keywords: getPromptKeywords(record),
      // Sync fields for progressive disclosure
      serverId: record?.serverId,
      syncStatus: record?.syncStatus,
      sourceSystem: record?.sourceSystem,
      studioProjectId: record?.studioProjectId,
      lastSyncedAt: record?.lastSyncedAt,
      // Advanced fields
      fewShotExamples: record?.fewShotExamples,
      modulesConfig: record?.modulesConfig,
      changeDescription: record?.changeDescription,
      versionNumber: record?.versionNumber
    })
    setDrawerOpen(true)
  }

  const closeInspector = React.useCallback(() => {
    setInspectorOpen(false)
    setInspectorPromptId(null)
  }, [])

  const openPromptInspector = React.useCallback((promptId: string) => {
    setInspectorPromptId(promptId)
    setInspectorOpen(true)
  }, [])

  const handleUsePromptInChat = React.useCallback(
    async (record: any) => {
      const { systemText, userText } = getPromptTexts(record)
      const hasSystem =
        typeof systemText === "string" && systemText.trim().length > 0
      const hasUser =
        typeof userText === "string" && userText.trim().length > 0

      if (hasSystem) {
        setInsertPrompt({
          id: record.id,
          systemText,
          userText: hasUser ? userText : undefined
        })
        return
      }

      const quickContent = userText ?? record?.content
      if (quickContent) {
        await markPromptAsUsed(record.id)
        setSelectedQuickPrompt(quickContent)
        setSelectedSystemPrompt(undefined)
        navigate("/chat")
      }
    },
    [
      getPromptTexts,
      markPromptAsUsed,
      navigate,
      setSelectedQuickPrompt,
      setSelectedSystemPrompt
    ]
  )

  const handleDuplicatePrompt = React.useCallback(
    (record: any) => {
      savePromptMutation({
        title: `${record.title || record.name} (Copy)`,
        name: `${record.name || record.title} (Copy)`,
        content: record.content,
        is_system: record.is_system,
        keywords: getPromptKeywords(record),
        tags: getPromptKeywords(record),
        favorite: !!record?.favorite,
        author: record?.author,
        details: record?.details,
        system_prompt: record?.system_prompt,
        user_prompt: record?.user_prompt
      })
    },
    [getPromptKeywords, savePromptMutation]
  )

  const handleDeletePrompt = React.useCallback(
    async (record: any) => {
      const ok = await confirmDanger({
        title: t("common:confirmTitle", { defaultValue: "Please confirm" }),
        content: t("managePrompts.confirm.delete"),
        okText: t("common:delete", { defaultValue: "Delete" }),
        cancelText: t("common:cancel", { defaultValue: "Cancel" })
      })
      if (!ok) return
      deletePrompt(record.id)
    },
    [confirmDanger, deletePrompt, t]
  )

  const handleDrawerSubmit = (values: any) => {
    const payload = normalizePromptPayload(values)
    if (drawerMode === "create") {
      savePromptMutation(payload)
    } else {
      updatePromptMutation(payload)
    }
  }

  // Clear project filter
  const clearProjectFilter = () => {
    const newParams = new URLSearchParams(searchParams)
    newParams.delete("project")
    setSearchParams(newParams, { replace: true })
  }

  const openConflictResolution = React.useCallback((localId: string) => {
    setConflictPromptId(localId)
    setConflictInfo(null)
    setConflictModalOpen(true)
    loadConflictInfoMutation(localId)
  }, [loadConflictInfoMutation])

  const closeConflictResolution = React.useCallback(() => {
    setConflictModalOpen(false)
    setConflictPromptId(null)
    setConflictInfo(null)
  }, [])

  const handleResolveConflict = React.useCallback((resolution: ConflictResolution) => {
    if (!conflictPromptId) return
    resolveConflictMutation({ localId: conflictPromptId, resolution })
  }, [conflictPromptId, resolveConflictMutation])

  const cancelBatchSync = React.useCallback(() => {
    batchSyncCancelRef.current = true
  }, [])

  const runBatchSync = React.useCallback(
    async (retryTasks?: SyncBatchTask[]) => {
      if (!isOnline) return

      const plan = retryTasks
        ? {
            tasks: retryTasks,
            skippedConflicts: 0,
            skippedCopilotPending: 0
          }
        : buildSyncBatchPlan(await getAllPromptsWithSyncStatus())

      if (plan.tasks.length === 0) {
        const description = plan.skippedConflicts > 0
          ? t("managePrompts.sync.batchNoActionableWithConflicts", {
              defaultValue:
                "No prompts are ready for batch sync. {{count}} prompt(s) require manual conflict resolution.",
              count: plan.skippedConflicts
            })
          : t("managePrompts.sync.batchNoActionable", {
              defaultValue: "No prompts currently need syncing."
            })
        notification.info({
          message: t("managePrompts.sync.batchNothingToSync", {
            defaultValue: "Nothing to sync"
          }),
          description
        })
        return
      }

      batchSyncCancelRef.current = false
      setBatchSyncState({
        running: true,
        completed: 0,
        total: plan.tasks.length,
        succeeded: 0,
        failed: [],
        skippedConflicts: plan.skippedConflicts,
        skippedCopilotPending: plan.skippedCopilotPending,
        cancelled: false
      })

      let completed = 0
      let succeeded = 0
      const failed: BatchSyncFailure[] = []

      for (const task of plan.tasks) {
        if (batchSyncCancelRef.current) {
          setBatchSyncState({
            running: false,
            completed,
            total: plan.tasks.length,
            succeeded,
            failed: [...failed],
            skippedConflicts: plan.skippedConflicts,
            skippedCopilotPending: plan.skippedCopilotPending,
            cancelled: true
          })
          notification.warning({
            message: t("managePrompts.sync.batchCancelled", {
              defaultValue: "Batch sync cancelled"
            }),
            description: t("managePrompts.sync.batchCancelledDesc", {
              defaultValue:
                "Synced {{completed}} of {{total}} prompts before cancellation.",
              completed,
              total: plan.tasks.length
            })
          })
          await queryClient.invalidateQueries({ queryKey: ["fetchAllPrompts"] })
          return
        }

        try {
          const result =
            task.direction === "pull"
              ? await pullFromStudio(task.serverId!, task.promptId)
              : task.serverId
                ? await pushToStudio(task.promptId, task.preferredProjectId || 1)
                : await autoSyncPrompt(task.promptId, task.preferredProjectId)

          if (result.success) {
            succeeded += 1
          } else {
            failed.push({
              task,
              error:
                result.error ||
                t("managePrompts.notification.someError", {
                  defaultValue: "Something went wrong."
                })
            })
          }
        } catch (error: any) {
          failed.push({
            task,
            error:
              error?.message ||
              t("managePrompts.notification.someError", {
                defaultValue: "Something went wrong."
              })
          })
        }

        completed += 1
        setBatchSyncState((prev) => ({
          ...prev,
          completed,
          succeeded,
          failed: [...failed]
        }))
      }

      await queryClient.invalidateQueries({ queryKey: ["fetchAllPrompts"] })

      setBatchSyncState({
        running: false,
        completed,
        total: plan.tasks.length,
        succeeded,
        failed: [...failed],
        skippedConflicts: plan.skippedConflicts,
        skippedCopilotPending: plan.skippedCopilotPending,
        cancelled: false
      })

      if (failed.length > 0) {
        notification.warning({
          message: t("managePrompts.sync.batchPartialFailure", {
            defaultValue: "Sync completed with issues"
          }),
          description: t("managePrompts.sync.batchPartialFailureDesc", {
            defaultValue:
              "Synced {{succeeded}} of {{total}} prompts. {{failed}} failed.",
            succeeded,
            total: plan.tasks.length,
            failed: failed.length
          })
        })
      } else {
        const extra = plan.skippedConflicts > 0
          ? t("managePrompts.sync.batchConflictReminder", {
              defaultValue:
                " {{count}} conflict prompt(s) still need manual resolution.",
              count: plan.skippedConflicts
            })
          : ""
        notification.success({
          message: t("managePrompts.sync.batchSuccess", {
            defaultValue: "Batch sync complete"
          }),
          description: `${t("managePrompts.sync.batchSuccessDesc", {
            defaultValue: "Synced {{count}} prompt(s).",
            count: succeeded
          })}${extra}`
        })
      }
    },
    [isOnline, queryClient, t]
  )

  const handleBatchSyncAction = React.useCallback(() => {
    if (batchSyncState.running) {
      cancelBatchSync()
      return
    }
    if (batchSyncState.failed.length > 0) {
      void runBatchSync(batchSyncState.failed.map((item) => item.task))
      return
    }
    void runBatchSync()
  }, [batchSyncState.failed, batchSyncState.running, cancelBatchSync, runBatchSync])

  const handleCustomPromptTableQueryChange = React.useCallback(
    (patch: Partial<PromptListQueryState>) => {
      const nextPage =
        typeof patch.page === "number" ? patch.page : currentPage
      const nextPageSize =
        typeof patch.pageSize === "number" ? patch.pageSize : resultsPerPage

      if (nextPageSize !== resultsPerPage) {
        setResultsPerPage(nextPageSize)
        setCurrentPage(1)
      } else if (nextPage !== currentPage) {
        setCurrentPage(nextPage)
      }

      if (patch.sort) {
        const rawNextKey = patch.sort.key
        const nextKey: PromptSortKey =
          rawNextKey === "title" || rawNextKey === "modifiedAt"
            ? rawNextKey
            : null
        const nextOrder = patch.sort.order || null
        setPromptSort({
          key: nextOrder ? nextKey : null,
          order: nextOrder
        })
      }
    },
    [currentPage, resultsPerPage]
  )

  const handleTogglePromptFavorite = React.useCallback(
    (promptId: string, nextFavorite: boolean) => {
      const promptRecord = getPromptRecordById(promptId)
      if (!promptRecord) return
      updatePromptDirect(
        buildPromptUpdatePayload(promptRecord, {
          favorite: nextFavorite
        })
      )
    },
    [buildPromptUpdatePayload, getPromptRecordById, updatePromptDirect]
  )

  const handleEditPromptById = React.useCallback(
    (promptId: string) => {
      const promptRecord = getPromptRecordById(promptId)
      if (!promptRecord) return
      openEditDrawer(promptRecord)
    },
    [getPromptRecordById]
  )

  const renderCustomPromptTitleMeta = React.useCallback(
    (row: PromptRowVM) => {
      if (!isCompactViewport) return null
      return (
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <span className="text-[11px] text-text-muted">
            {formatRelativePromptTime(row.updatedAt)}
          </span>
          <Tooltip
            title={
              !isOnline
                ? t("managePrompts.sync.offlineTooltip", {
                    defaultValue:
                      "Sync unavailable (offline). Showing last known status."
                  })
                : undefined
            }
          >
            <span className={!isOnline ? "opacity-60" : undefined}>
              <SyncStatusBadge
                syncStatus={row.syncStatus}
                sourceSystem={row.sourceSystem}
                serverId={row.serverId}
                compact
                onClick={
                  isOnline && row.syncStatus === "conflict"
                    ? () => openConflictResolution(row.id)
                    : undefined
                }
              />
            </span>
          </Tooltip>
        </div>
      )
    },
    [formatRelativePromptTime, isCompactViewport, isOnline, openConflictResolution, t]
  )

  const renderCustomPromptActions = React.useCallback(
    (row: PromptRowVM) => {
      const promptRecord = getPromptRecordById(row.id)
      const actionDisabled = isFireFoxPrivateMode || !promptRecord
      return (
        <PromptActionsMenu
          promptId={row.id}
          disabled={actionDisabled}
          syncStatus={row.syncStatus}
          serverId={row.serverId}
          inlineUseInChat={false}
          onEdit={() => {
            if (!promptRecord) return
            openEditDrawer(promptRecord)
          }}
          onDuplicate={() => {
            if (!promptRecord) return
            handleDuplicatePrompt(promptRecord)
          }}
          onUseInChat={() => {
            if (!promptRecord) return
            void handleUsePromptInChat(promptRecord)
          }}
          onQuickTest={() => {
            if (!promptRecord) return
            void handleQuickTest(promptRecord)
          }}
          onDelete={() => {
            if (!promptRecord) return
            void handleDeletePrompt(promptRecord)
          }}
          onShareLink={
            row.serverId && promptRecord
              ? () => {
                  void copyPromptShareLink(promptRecord)
                }
              : undefined
          }
          onPushToServer={
            isOnline && promptRecord
              ? () => {
                  setPromptToSync(promptRecord.id)
                  setProjectSelectorOpen(true)
                }
              : undefined
          }
          onPullFromServer={
            isOnline && row.serverId && promptRecord
              ? () => {
                  pullFromStudioMutation({
                    serverId: row.serverId as number,
                    localId: promptRecord.id
                  })
                }
              : undefined
          }
          onUnlink={
            isOnline && row.serverId && promptRecord
              ? () => {
                  unlinkPromptMutation(promptRecord.id)
                }
              : undefined
          }
          onResolveConflict={
            isOnline && row.syncStatus === "conflict"
              ? () => {
                  openConflictResolution(row.id)
                }
              : undefined
          }
        />
      )
    },
    [
      copyPromptShareLink,
      getPromptRecordById,
      handleDeletePrompt,
      handleDuplicatePrompt,
      handleQuickTest,
      handleUsePromptInChat,
      isFireFoxPrivateMode,
      isOnline,
      openConflictResolution,
      pullFromStudioMutation,
      unlinkPromptMutation
    ]
  )

  function customPrompts() {
    const bulkActionTouchClass = isCompactViewport
      ? "min-h-[44px] px-3 py-2"
      : "px-2 py-1"

    return (
      <div data-testid="prompts-custom">
        {/* Project filter banner - shown when filtering by project */}
        {projectFilter && (
          <Alert
            type="info"
            showIcon
            className="mb-4"
            title={t("managePrompts.projectFilter.active", {
              defaultValue: "Filtering by project"
            })}
            description={t("managePrompts.projectFilter.description", {
              defaultValue: "Showing prompts linked to Project #{{projectId}}. Clear the filter to see all prompts.",
              projectId: projectFilter
            })}
            action={
              <button
                onClick={clearProjectFilter}
                className="text-sm text-primary hover:underline"
                data-testid="prompts-clear-project-filter"
              >
                {t("managePrompts.projectFilter.clear", { defaultValue: "Show all prompts" })}
              </button>
            }
          />
        )}
        <div className="mb-6 space-y-3">
          {/* Bulk action bar - shown when rows are selected */}
          {selectedRowKeys.length > 0 && (
            <PromptBulkActionBar mode="legacy">
              <span className="text-sm text-primary">
                {t("managePrompts.bulk.selected", {
                  defaultValue: "{{count}} selected",
                  count: selectedRowKeys.length
                })}
              </span>
              <button
                onClick={() => triggerBulkExport()}
                data-testid="prompts-bulk-export"
                className={`inline-flex items-center gap-1 rounded border border-primary/30 text-sm text-primary hover:bg-primary/10 ${bulkActionTouchClass}`}>
                <Download className="size-3" /> {t("managePrompts.bulk.export", { defaultValue: "Export selected" })}
              </button>
              <button
                onClick={() => setBulkKeywordModalOpen(true)}
                disabled={isBulkAddingKeyword}
                data-testid="prompts-bulk-add-keyword"
                className={`inline-flex items-center gap-1 rounded border border-primary/30 text-sm text-primary hover:bg-primary/10 disabled:opacity-50 ${bulkActionTouchClass}`}>
                {t("managePrompts.bulk.addKeyword", { defaultValue: "Add keyword" })}
              </button>
              <button
                onClick={() =>
                  bulkToggleFavorite({
                    ids: selectedRowKeys.map((key) => String(key)),
                    favorite: !allSelectedAreFavorite
                  })
                }
                disabled={isBulkFavoriting}
                data-testid="prompts-bulk-toggle-favorite"
                className={`inline-flex items-center gap-1 rounded border border-primary/30 text-sm text-primary hover:bg-primary/10 disabled:opacity-50 ${bulkActionTouchClass}`}>
                {allSelectedAreFavorite ? (
                  <StarOff className="size-3" />
                ) : (
                  <Star className="size-3" />
                )}
                {allSelectedAreFavorite
                  ? t("managePrompts.bulk.unfavorite", {
                      defaultValue: "Unfavorite selected"
                    })
                  : t("managePrompts.bulk.favorite", {
                      defaultValue: "Favorite selected"
                    })}
              </button>
              {isOnline && (
                <button
                  onClick={() =>
                    bulkPushToServer(selectedRowKeys.map((key) => String(key)))
                  }
                  disabled={isBulkPushing}
                  data-testid="prompts-bulk-push-server"
                  className={`inline-flex items-center gap-1 rounded border border-primary/30 text-sm text-primary hover:bg-primary/10 disabled:opacity-50 ${bulkActionTouchClass}`}>
                  <Cloud className="size-3" />
                  {t("managePrompts.bulk.pushToServer", {
                    defaultValue: "Push to server"
                  })}
                </button>
              )}
              <button
                onClick={async () => {
                  if (guardPrivateMode()) return
                  const ok = await confirmDanger({
                    title: t("common:confirmTitle", { defaultValue: "Please confirm" }),
                    content: t("managePrompts.bulk.deleteConfirm", {
                      defaultValue: "Are you sure you want to delete {{count}} prompts?",
                      count: selectedRowKeys.length
                    }),
                    okText: t("common:delete", { defaultValue: "Delete" }),
                    cancelText: t("common:cancel", { defaultValue: "Cancel" })
                  })
                  if (!ok) return
                  bulkDeletePrompts(selectedRowKeys as string[])
                }}
                disabled={isBulkDeleting}
                data-testid="prompts-bulk-delete"
                className={`inline-flex items-center gap-1 rounded border border-danger/30 text-sm text-danger hover:bg-danger/10 disabled:opacity-50 ${bulkActionTouchClass}`}>
                <Trash2 className="size-3" /> {t("managePrompts.bulk.delete", { defaultValue: "Delete selected" })}
              </button>
              <button
                onClick={() => setSelectedRowKeys([])}
                data-testid="prompts-clear-selection"
                className={`ml-auto inline-flex items-center rounded text-sm text-text-muted hover:text-text ${isCompactViewport ? "min-h-[44px] px-2" : ""}`}>
                {t("common:clearSelection", { defaultValue: "Clear selection" })}
              </button>
            </PromptBulkActionBar>
          )}
          {isOnline && (batchSyncState.running || batchSyncState.failed.length > 0) && (
            <div
              data-testid="prompts-batch-sync-status"
              className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-surface2 p-2"
            >
              {batchSyncState.running ? (
                <span className="text-sm text-text-muted">
                  {t("managePrompts.sync.batchProgress", {
                    defaultValue: "Syncing {{completed}} of {{total}} prompts...",
                    completed: batchSyncState.completed,
                    total: batchSyncState.total
                  })}
                </span>
              ) : (
                <span className="text-sm text-warn">
                  {t("managePrompts.sync.batchFailedCount", {
                    defaultValue:
                      "{{count}} prompt(s) failed in the last batch run. Retry to continue.",
                    count: batchSyncState.failed.length
                  })}
                </span>
              )}
            </div>
          )}
          {isOnline && (
            <div
              data-testid="prompts-collections-panel"
              className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-surface2 p-2"
            >
              <Select
                value={collectionFilter}
                onChange={(value) =>
                  setCollectionFilter(
                    value === "all" ? "all" : Number(value)
                  )
                }
                loading={promptCollectionsStatus === "pending"}
                style={{ minWidth: isCompactViewport ? "100%" : 260 }}
                data-testid="prompts-collection-filter"
                options={[
                  {
                    label: t("managePrompts.collections.filterAll", {
                      defaultValue: "All collections"
                    }),
                    value: "all"
                  },
                  ...promptCollections.map((collection) => ({
                    label: `${collection.name} (${collection.prompt_ids?.length || 0})`,
                    value: collection.collection_id
                  }))
                ]}
              />
              <button
                type="button"
                onClick={() => setCreateCollectionModalOpen(true)}
                data-testid="prompts-collection-create"
                className="inline-flex items-center gap-2 rounded-md border border-border px-2 py-2 text-sm font-medium text-text hover:bg-surface2 focus:outline-none focus:ring-2 focus:ring-focus focus:ring-offset-2"
              >
                <FolderPlus className="size-4" />
                {t("managePrompts.collections.create", {
                  defaultValue: "New collection"
                })}
              </button>
              {selectedCollection && selectedRowKeys.length > 0 && (
                <button
                  type="button"
                  onClick={() =>
                    addPromptsToCollectionMutation({
                      collection: selectedCollection,
                      prompts: selectedPromptRows
                    })
                  }
                  disabled={isAssigningPromptCollection}
                  data-testid="prompts-collection-add-selected"
                  className="inline-flex items-center gap-2 rounded-md border border-primary/40 px-2 py-2 text-sm font-medium text-primary hover:bg-primary/10 disabled:opacity-50"
                >
                  {t("managePrompts.collections.addSelected", {
                    defaultValue: "Add selected to collection"
                  })}
                </button>
              )}
            </div>
          )}
          <PromptListToolbar
            mode="legacy"
            className="flex flex-wrap items-start justify-between gap-3 sm:items-center"
          >
            {/* Left: Action buttons */}
            <div className="flex flex-wrap items-center gap-2">
              <Tooltip title={t("managePrompts.newPromptHint", { defaultValue: "New prompt (N)" })}>
              <button
                onClick={openCreateDrawer}
                data-testid="prompts-add"
                className="inline-flex items-center rounded-md border border-transparent bg-primary px-2 py-2 text-md font-medium leading-4 text-white shadow-sm hover:bg-primaryStrong focus:outline-none focus:ring-2 focus:ring-focus focus:ring-offset-2 disabled:opacity-50">
                {t("managePrompts.newPromptBtn", { defaultValue: "New prompt" })}
              </button>
              </Tooltip>
              <div className="inline-flex items-center rounded-md border border-border overflow-hidden">
                <button
                  onClick={() => triggerExport()}
                  data-testid="prompts-export"
                  aria-label={t("managePrompts.exportLabel", { defaultValue: "Export prompts" })}
                  className="inline-flex items-center gap-2 px-2 py-2 text-md font-medium leading-4 text-text hover:bg-surface2">
                  <Download className="size-4" /> {t("managePrompts.export", { defaultValue: "Export" })}
                </button>
                <Select
                  value={exportFormat}
                  onChange={(v) => setExportFormat(v as "json" | "csv" | "markdown")}
                  data-testid="prompts-export-format"
                  options={[
                    { label: "JSON", value: "json" },
                    { label: "CSV", value: "csv", disabled: !isOnline },
                    { label: "Markdown", value: "markdown", disabled: !isOnline }
                  ]}
                  variant="borderless"
                  style={{ width: 120 }}
                  popupMatchSelectWidth={false}
                />
              </div>
              {isOnline &&
                (localSyncBatchPlan.tasks.length > 0 ||
                  batchSyncState.failed.length > 0 ||
                  batchSyncState.running) && (
                  <Tooltip
                    title={
                      localSyncBatchPlan.skippedConflicts > 0
                        ? t("managePrompts.sync.batchConflictHint", {
                            defaultValue:
                              "{{count}} conflict prompt(s) require manual resolution.",
                            count: localSyncBatchPlan.skippedConflicts
                          })
                        : undefined
                    }
                  >
                    <button
                      type="button"
                      onClick={handleBatchSyncAction}
                      data-testid="prompts-sync-all"
                      className="inline-flex items-center gap-2 rounded-md border border-border px-2 py-2 text-md font-medium leading-4 text-text hover:bg-surface2 disabled:opacity-50"
                    >
                      <Cloud className="size-4" />
                      {batchSyncState.running
                        ? t("managePrompts.sync.batchCancel", {
                            defaultValue: "Cancel sync"
                          })
                        : batchSyncState.failed.length > 0
                          ? t("managePrompts.sync.batchRetryFailed", {
                              defaultValue: "Retry failed ({{count}})",
                              count: batchSyncState.failed.length
                            })
                          : t("managePrompts.sync.batchSyncAll", {
                              defaultValue: "Sync all"
                            })}
                    </button>
                  </Tooltip>
                )}
              {/* Import controls grouped together */}
              <div className="inline-flex items-center rounded-md border border-border overflow-hidden">
                <button
                  onClick={() => {
                    if (guardPrivateMode()) return
                    fileInputRef.current?.click()
                  }}
                  data-testid="prompts-import"
                  className="inline-flex items-center gap-2 px-2 py-2 text-md font-medium leading-4 text-text hover:bg-surface2">
                  <UploadCloud className="size-4" /> {t("managePrompts.import", { defaultValue: "Import" })}
                </button>
                <Select
                  value={importMode}
                  onChange={(v) => setImportMode(v as any)}
                  data-testid="prompts-import-mode"
                  options={[
                    { label: t("managePrompts.importMode.merge", { defaultValue: "Merge" }), value: "merge" },
                    { label: t("managePrompts.importMode.replaceWithBackup", { defaultValue: "Replace (backup)" }), value: "replace" }
                  ]}
                  variant="borderless"
                  style={{ width: 130 }}
                  popupMatchSelectWidth={false}
                />
              </div>
              <Tooltip
                title={t("managePrompts.shortcuts.openHint", {
                  defaultValue: "Keyboard shortcuts (?)"
                })}
              >
                <button
                  type="button"
                  onClick={() => setShortcutsHelpOpen(true)}
                  data-testid="prompts-shortcuts-help-button"
                  aria-label={t("managePrompts.shortcuts.openLabel", {
                    defaultValue: "Open keyboard shortcuts"
                  })}
                  className="inline-flex items-center gap-2 rounded-md border border-border px-2 py-2 text-md font-medium leading-4 text-text hover:bg-surface2 focus:outline-none focus:ring-2 focus:ring-focus focus:ring-offset-2"
                >
                  <Keyboard className="size-4" aria-hidden="true" />
                  {t("managePrompts.shortcuts.openButton", {
                    defaultValue: "Shortcuts"
                  })}
                </button>
              </Tooltip>
              <input
                ref={fileInputRef}
                type="file"
                accept="application/json"
                className="hidden"
                data-testid="prompts-import-file"
                aria-label={t("managePrompts.importFileLabel", { defaultValue: "Import prompts file" })}
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) handleImportFile(file)
                  e.currentTarget.value = ""
                }}
              />
            </div>
            {/* Right: Filters */}
            <div className="flex w-full flex-wrap items-stretch gap-2 sm:w-auto sm:items-center sm:justify-end">
              <div
                data-testid="prompts-search-control"
                className="w-full sm:w-auto"
              >
                <Input
                  ref={searchInputRef}
                  allowClear
                  placeholder={t("managePrompts.searchWithScope", { defaultValue: "Search name, content, keywords..." })}
                  value={searchText}
                  onChange={(e) => setSearchText(e.target.value)}
                  data-testid="prompts-search"
                  aria-label={t("managePrompts.search", { defaultValue: "Search prompts..." })}
                  suffix={<kbd className="rounded border border-border px-1 text-xs text-text-subtle">/</kbd>}
                  style={{ width: isCompactViewport ? "100%" : 260 }}
                />
              </div>
              <div
                data-testid="prompts-type-filter-control"
                className="w-full sm:w-auto"
              >
                <Select
                  value={typeFilter}
                  onChange={(v) => setTypeFilter(v as any)}
                  data-testid="prompts-type-filter"
                  aria-label={t("managePrompts.filter.typeLabel", { defaultValue: "Filter by type" })}
                  style={{ width: isCompactViewport ? "100%" : 130 }}
                  options={[
                    { label: t("managePrompts.filter.all", { defaultValue: "All types" }), value: "all" },
                    { label: t("managePrompts.filter.system", { defaultValue: "System" }), value: "system" },
                    { label: t("managePrompts.filter.quick", { defaultValue: "Quick" }), value: "quick" }
                  ]}
                />
              </div>
              <div
                data-testid="prompts-usage-filter-control"
                className="w-full sm:w-auto"
              >
                <Select
                  value={usageFilter}
                  onChange={(v) => setUsageFilter(v as "all" | "used" | "unused")}
                  data-testid="prompts-usage-filter"
                  aria-label={t("managePrompts.filter.usageLabel", {
                    defaultValue: "Filter by usage"
                  })}
                  style={{ width: isCompactViewport ? "100%" : 150 }}
                  options={[
                    {
                      label: t("managePrompts.filter.usageAll", {
                        defaultValue: "All usage"
                      }),
                      value: "all"
                    },
                    {
                      label: t("managePrompts.filter.usageUsed", {
                        defaultValue: "Used"
                      }),
                      value: "used"
                    },
                    {
                      label: t("managePrompts.filter.usageUnused", {
                        defaultValue: "Unused"
                      }),
                      value: "unused"
                    }
                  ]}
                />
              </div>
              <div
                data-testid="prompts-tag-filter-control"
                className="w-full sm:w-auto"
              >
                <Select
                  mode="multiple"
                  allowClear
                  placeholder={t("managePrompts.tags.placeholder", { defaultValue: "Filter keywords" })}
                  style={{ width: isCompactViewport ? "100%" : 220 }}
                  value={tagFilter}
                  onChange={(v) => setTagFilter(v)}
                  data-testid="prompts-tag-filter"
                  aria-label={t("managePrompts.tags.filterLabel", { defaultValue: "Filter by keywords" })}
                  options={allTags.map((t) => ({ label: t, value: t }))}
                />
              </div>
              <div
                data-testid="prompts-tag-match-mode-control"
                className="w-full sm:w-auto"
              >
                <Segmented
                  value={tagMatchMode}
                  onChange={(value) => setTagMatchMode(value as TagMatchMode)}
                  size="small"
                  data-testid="prompts-tag-match-mode"
                  style={{ width: isCompactViewport ? "100%" : undefined }}
                  options={[
                    {
                      value: "any",
                      label: t("managePrompts.tags.matchAny", {
                        defaultValue: "Match any"
                      })
                    },
                    {
                      value: "all",
                      label: t("managePrompts.tags.matchAll", {
                        defaultValue: "Match all"
                      })
                    }
                  ]}
                />
              </div>
            </div>
          </PromptListToolbar>
        </div>

        {customPromptsLoading && <Skeleton paragraph={{ rows: 8 }} />}

        {useServerSearchResults && hiddenServerResultsOnPage > 0 && (
          <Alert
            type="info"
            showIcon
            className="mb-3"
            message={t("managePrompts.search.localSubset", {
              defaultValue: "Showing synced local matches only"
            })}
            description={t("managePrompts.search.localSubsetDesc", {
              defaultValue:
                "{{count}} result(s) from this page are not saved locally yet.",
              count: hiddenServerResultsOnPage
            })}
          />
        )}

        {status === "success" && Array.isArray(data) && data.length === 0 && (
          <FeatureEmptyState
            title={t("settings:managePrompts.emptyTitle", {
              defaultValue: "No custom prompts yet"
            })}
            description={t("settings:managePrompts.emptyDescription", {
              defaultValue:
                "Create reusable prompts for recurring tasks, workflows, and team conventions."
            })}
            examples={[
              t("settings:managePrompts.emptyExample1", {
                defaultValue:
                  "Save your favorite system prompt for summaries, explanations, or translations."
              }),
              t("settings:managePrompts.emptyExample2", {
                defaultValue:
                  "Create quick prompts for common actions like drafting emails or refining notes."
              })
            ]}
            primaryActionLabel={t("settings:managePrompts.emptyPrimaryCta", {
              defaultValue: "Create prompt"
            })}
            onPrimaryAction={openCreateDrawer}
          />
        )}

        {status === "success" && Array.isArray(data) && data.length > 0 && (
          <PromptListTable
            rows={customPromptRows}
            total={tableTotal}
            loading={customPromptsLoading}
            isOnline={isOnline}
            isCompactViewport={isCompactViewport}
            query={customPromptTableQuery}
            selectedIds={selectedRowKeys.map((key) => String(key))}
            onQueryChange={handleCustomPromptTableQueryChange}
            onSelectionChange={(ids) => setSelectedRowKeys(ids)}
            onRowOpen={openPromptInspector}
            onEdit={handleEditPromptById}
            onToggleFavorite={handleTogglePromptFavorite}
            onOpenConflictResolution={openConflictResolution}
            renderActions={renderCustomPromptActions}
            renderTitleMeta={renderCustomPromptTitleMeta}
            favoriteButtonTestId={(row) => `prompt-favorite-${row.id}`}
            formatRelativeTime={formatRelativePromptTime}
            selectionDisabled={isFireFoxPrivateMode}
            columnLabels={{
              title: t("managePrompts.columns.title"),
              preview: t("managePrompts.columns.prompt"),
              tags: t("managePrompts.tags.label", {
                defaultValue: "Keywords"
              }),
              updated: t("managePrompts.columns.modified", {
                defaultValue: "Updated"
              }),
              status: t("managePrompts.columns.sync", {
                defaultValue: "Sync"
              }),
              actions: t("managePrompts.columns.actions"),
              author: t("managePrompts.form.author.label", {
                defaultValue: "Author"
              }),
              system: t("managePrompts.form.systemPrompt.shortLabel", {
                defaultValue: "System"
              }),
              user: t("managePrompts.form.userPrompt.shortLabel", {
                defaultValue: "User"
              }),
              unknown: t("common:unknown", {
                defaultValue: "Unknown"
              }),
              offlineStatus: t("managePrompts.sync.offlineTooltip", {
                defaultValue:
                  "Sync unavailable (offline). Showing last known status."
              }),
              edit: t("managePrompts.tooltip.edit")
            }}
            paginationShowTotal={(total, range) =>
              t("managePrompts.pagination.summary", {
                defaultValue: "{{start}}-{{end}} of {{total}} prompts",
                start: range[0],
                end: range[1],
                total
              })
            }
          />
        )}
      </div>
    )
  }

  function copilotPrompts() {
    if (!isOnline) {
      return (
        <ConnectFeatureBanner
          title={t("settings:managePrompts.emptyConnectTitle", {
            defaultValue: "Connect to use Prompts"
          })}
          description={t("settings:managePrompts.emptyConnectDescription", {
            defaultValue:
              "To manage reusable prompts, first connect to your tldw server."
          })}
          examples={[
            t("settings:managePrompts.emptyConnectExample1", {
              defaultValue:
                "Open Settings → tldw server to add your server URL."
            }),
            t("settings:managePrompts.emptyConnectExample2", {
              defaultValue:
                "Once connected, create custom prompts you can reuse across chats."
            })
          ]}
        />
      )
    }
    return (
      <div>
        {copilotStatus === "pending" && <Skeleton paragraph={{ rows: 8 }} />}

        {copilotStatus === "success" && Array.isArray(copilotData) && copilotData.length === 0 && (
          <FeatureEmptyState
            title={t("managePrompts.copilotEmptyTitle", {
              defaultValue: "No Copilot prompts available"
            })}
            description={t("managePrompts.copilotEmptyDescription", {
              defaultValue:
                "Copilot prompts are predefined templates provided by your tldw server."
            })}
            examples={[
              t("managePrompts.copilotEmptyExample1", {
                defaultValue:
                  "Check your server version or configuration if you expect Copilot prompts to be available."
              }),
              t("managePrompts.copilotEmptyExample2", {
                defaultValue:
                  "After updating your server, reload the extension and return to this tab."
              })
            ]}
            primaryActionLabel={t("settings:healthSummary.diagnostics", {
              defaultValue: "Open Diagnostics"
            })}
            onPrimaryAction={() => navigate("/settings/health")}
          />
        )}

        {copilotStatus === "success" && Array.isArray(copilotData) && copilotData.length > 0 && (
          <>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <Input
                value={copilotSearchText}
                onChange={(event) => setCopilotSearchText(event.target.value)}
                allowClear
                placeholder={t("managePrompts.copilot.search.placeholder", {
                  defaultValue: "Search copilot prompts..."
                })}
                style={{ width: 260 }}
                data-testid="copilot-search"
              />
              <Select
                value={copilotKeyFilter}
                onChange={(value) => setCopilotKeyFilter(value)}
                options={[
                  {
                    label: t("managePrompts.copilot.filter.all", {
                      defaultValue: "All prompt types"
                    }),
                    value: "all"
                  },
                  ...copilotPromptKeyOptions
                ]}
                style={{ width: 200 }}
                data-testid="copilot-key-filter"
              />
            </div>

            {filteredCopilotData.length === 0 ? (
              <div className="rounded-md border border-border p-4 text-sm text-text-muted">
                {t("managePrompts.copilot.search.empty", {
                  defaultValue: "No copilot prompts match the current filters."
                })}
              </div>
            ) : (
              <Table
                columns={[
                  {
                    title: t("managePrompts.columns.title"),
                    dataIndex: "key",
                    key: "key",
                    render: (content) => (
                      <span className="line-clamp-1">
                        <Tag color={tagColors[content || "default"]}>
                          {t(`common:copilot.${content}`)}
                        </Tag>
                      </span>
                    )
                  },
                  {
                    title: t("managePrompts.columns.prompt"),
                    dataIndex: "prompt",
                    key: "prompt",
                    render: (content) => <span className="line-clamp-1">{content}</span>
                  },
                  {
                    render: (_, record) => (
                      <div className="flex items-center gap-1">
                        <Tooltip title={t("managePrompts.tooltip.edit")}>
                          <button
                            type="button"
                            aria-label={t("managePrompts.tooltip.edit")}
                            onClick={() => {
                              setEditCopilotId(record.key)
                              editCopilotForm.setFieldsValue(record)
                              setOpenCopilotEdit(true)
                            }}
                            data-testid={`copilot-action-edit-${record.key}`}
                            className="inline-flex min-h-8 min-w-8 items-center justify-center rounded p-2 text-text-muted hover:bg-bg-muted/70 focus:outline-none focus:ring-2 focus:ring-primary"
                          >
                            <Pen className="size-4" />
                          </button>
                        </Tooltip>
                        <Tooltip
                          title={t("managePrompts.copilot.copyToCustom.button", {
                            defaultValue: "Copy to Custom"
                          })}
                        >
                          <button
                            type="button"
                            aria-label={t("managePrompts.copilot.copyToCustom.button", {
                              defaultValue: "Copy to Custom"
                            })}
                            onClick={() => copyCopilotToCustom(record)}
                            data-testid={`copilot-action-copy-custom-${record.key}`}
                            className="inline-flex min-h-8 min-w-8 items-center justify-center rounded p-2 text-text-muted hover:bg-bg-muted/70 focus:outline-none focus:ring-2 focus:ring-primary"
                          >
                            <Copy className="size-4" />
                          </button>
                        </Tooltip>
                        <Tooltip
                          title={t("managePrompts.copilot.copyToClipboard.button", {
                            defaultValue: "Copy to clipboard"
                          })}
                        >
                          <button
                            type="button"
                            aria-label={t("managePrompts.copilot.copyToClipboard.button", {
                              defaultValue: "Copy to clipboard"
                            })}
                            onClick={() => {
                              void copyCopilotPromptToClipboard(record)
                            }}
                            data-testid={`copilot-action-copy-clipboard-${record.key}`}
                            className="inline-flex min-h-8 min-w-8 items-center justify-center rounded p-2 text-text-muted hover:bg-bg-muted/70 focus:outline-none focus:ring-2 focus:ring-primary"
                          >
                            <Clipboard className="size-4" />
                          </button>
                        </Tooltip>
                      </div>
                    )
                  }
                ]}
                bordered
                dataSource={filteredCopilotData}
                rowKey={(record) => record.key}
              />
            )}
          </>
        )}
      </div>
    )
  }

  function trashPrompts() {
    const trashCount = Array.isArray(trashData) ? trashData.length : 0
    const filteredTrashCount = filteredTrashData.length

    const formatDeletedAt = (timestamp: number | null | undefined) => {
      if (!timestamp) return ""
      const date = new Date(timestamp)
      const now = new Date()
      const diffMs = now.getTime() - date.getTime()
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
      if (diffDays === 0) return t("managePrompts.trash.today", { defaultValue: "Today" })
      if (diffDays === 1) return t("managePrompts.trash.yesterday", { defaultValue: "Yesterday" })
      if (diffDays < 7) return t("managePrompts.trash.daysAgo", { defaultValue: "{{count}} days ago", count: diffDays })
      return date.toLocaleDateString()
    }

    return (
      <div data-testid="prompts-trash">
        <div className="mb-6">
          {trashCount > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 bg-warn/10 rounded-md border border-warn/30">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="size-4 text-warn" />
                  <span className="text-sm">
                    {t("managePrompts.trash.autoDeleteWarning", {
                      defaultValue: "Prompts in trash are automatically deleted after 30 days."
                    })}
                  </span>
                </div>
                <button
                  onClick={async () => {
                    const ok = await confirmDanger({
                      title: t("managePrompts.trash.emptyConfirmTitle", { defaultValue: "Empty Trash?" }),
                      content: t("managePrompts.trash.emptyConfirmContent", {
                        defaultValue: "This will permanently delete {{count}} prompts. This action cannot be undone.",
                        count: trashCount
                      }),
                      okText: t("managePrompts.trash.emptyTrash", { defaultValue: "Empty Trash" }),
                      cancelText: t("common:cancel", { defaultValue: "Cancel" })
                    })
                    if (!ok) return
                    emptyTrashMutation()
                  }}
                  disabled={isEmptyingTrash}
                  className="inline-flex items-center gap-1 px-2 py-1 text-sm rounded border border-danger/30 text-danger hover:bg-danger/10 disabled:opacity-50">
                  <Trash2 className="size-3" />
                  {t("managePrompts.trash.emptyTrash", { defaultValue: "Empty Trash" })}
                </button>
              </div>

              <Input
                value={trashSearchText}
                onChange={(event) => setTrashSearchText(event.target.value)}
                allowClear
                placeholder={t("managePrompts.trash.searchPlaceholder", {
                  defaultValue: "Search deleted prompts..."
                })}
                style={{ width: 320, maxWidth: "100%" }}
                data-testid="prompts-trash-search"
              />

              {trashSelectedRowKeys.length > 0 && (
                <div className="flex flex-wrap items-center justify-between gap-2 p-2 rounded-md border border-primary/20 bg-primary/5">
                  <span className="text-sm text-text-muted">
                    {t("managePrompts.bulk.selectedCount", {
                      defaultValue: "{{count}} selected",
                      count: trashSelectedRowKeys.length
                    })}
                  </span>
                  <button
                    type="button"
                    data-testid="prompts-trash-bulk-restore"
                    onClick={() =>
                      bulkRestorePrompts(
                        trashSelectedRowKeys.map((key) => String(key))
                      )
                    }
                    disabled={isBulkRestoring}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-sm rounded border border-primary/30 text-primary hover:bg-primary/10 disabled:opacity-50"
                  >
                    <Undo2 className="size-3" />
                    {t("managePrompts.trash.restoreSelected", {
                      defaultValue: "Restore selected"
                    })}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {trashStatus === "pending" && <Skeleton paragraph={{ rows: 8 }} />}

        {trashStatus === "success" && trashCount === 0 && (
          <FeatureEmptyState
            title={t("managePrompts.trash.emptyTitle", { defaultValue: "Trash is empty" })}
            description={t("managePrompts.trash.emptyDescription", {
              defaultValue: "Deleted prompts will appear here for 30 days before being permanently removed."
            })}
            examples={[
              t("managePrompts.trash.emptyExample1", {
                defaultValue: "You can restore deleted prompts at any time while they're in the trash."
              })
            ]}
          />
        )}

        {trashStatus === "success" && trashCount > 0 && (
          <>
            {filteredTrashCount === 0 ? (
              <div className="rounded-md border border-border p-4 text-sm text-text-muted">
                {t("managePrompts.trash.searchEmpty", {
                  defaultValue: "No deleted prompts match your search."
                })}
              </div>
            ) : (
              <Table
                data-testid="prompts-trash-table"
                columns={[
                  {
                    title: t("managePrompts.columns.title"),
                    dataIndex: "title",
                    key: "title",
                    render: (_: any, record: any) => (
                      <div className="flex max-w-64 flex-col">
                        <span className="line-clamp-1 font-medium text-text-muted">
                          {record?.name || record?.title}
                        </span>
                        {record?.author && (
                          <span className="text-xs text-text-muted opacity-70">
                            {t("managePrompts.form.author.label", { defaultValue: "Author" })}: {record.author}
                          </span>
                        )}
                      </div>
                    )
                  },
                  {
                    title: t("managePrompts.columns.prompt", {
                      defaultValue: "Prompt"
                    }),
                    key: "contentPreview",
                    render: (_: any, record: any) => {
                      const { systemText, userText } = getPromptTexts(record)
                      const preview = (
                        userText ||
                        systemText ||
                        (typeof record?.content === "string" ? record.content : "")
                      ).trim()

                      if (!preview) {
                        return (
                          <span className="text-xs text-text-muted opacity-70">
                            {t("managePrompts.trash.noPreview", {
                              defaultValue: "No content preview"
                            })}
                          </span>
                        )
                      }

                      return (
                        <Tooltip title={preview}>
                          <span className="line-clamp-2 max-w-[26rem] text-sm">
                            {preview}
                          </span>
                        </Tooltip>
                      )
                    }
                  },
                  {
                    title: t("managePrompts.trash.deletedAt", { defaultValue: "Deleted" }),
                    key: "deletedAt",
                    width: 140,
                    render: (_: any, record: any) => (
                      <span className="text-sm text-text-muted">
                        {formatDeletedAt(record.deletedAt)}
                      </span>
                    )
                  },
                  {
                    title: t("managePrompts.trash.remaining", {
                      defaultValue: "Remaining"
                    }),
                    key: "remaining",
                    width: 140,
                    render: (_: any, record: any) => {
                      const remainingDays = getTrashDaysRemaining(record.deletedAt)
                      const severity = getTrashRemainingSeverity(remainingDays)
                      const className =
                        severity === "danger"
                          ? "text-danger"
                          : severity === "warning"
                            ? "text-warn"
                            : "text-text-muted"
                      const label =
                        remainingDays <= 0
                          ? t("managePrompts.trash.remainingExpired", {
                              defaultValue: "Due now"
                            })
                          : `${remainingDays} ${
                              remainingDays === 1
                                ? t("managePrompts.trash.dayLeft", { defaultValue: "day left" })
                                : t("managePrompts.trash.daysLeft", { defaultValue: "days left" })
                            }`

                      return (
                        <span
                          className={`text-sm ${className}`}
                          data-testid={`prompts-trash-remaining-${record.id}`}
                        >
                          {label}
                        </span>
                      )
                    }
                  },
                  {
                    title: t("managePrompts.columns.actions"),
                    width: 160,
                    render: (_: any, record: any) => (
                      <div className="flex items-center gap-2">
                        <Tooltip title={t("managePrompts.trash.restore", { defaultValue: "Restore" })}>
                          <button
                            type="button"
                            data-testid={`prompts-trash-restore-${record.id}`}
                            onClick={() => restorePromptMutation(record.id)}
                            className="inline-flex items-center gap-1 px-2 py-1 text-sm rounded border border-primary/30 text-primary hover:bg-primary/10">
                            <Undo2 className="size-3" />
                            {t("managePrompts.trash.restore", { defaultValue: "Restore" })}
                          </button>
                        </Tooltip>
                        <Tooltip title={t("managePrompts.trash.deletePermanently", { defaultValue: "Delete permanently" })}>
                          <button
                            type="button"
                            onClick={async () => {
                              const ok = await confirmDanger({
                                title: t("managePrompts.trash.permanentDeleteTitle", { defaultValue: "Delete permanently?" }),
                                content: t("managePrompts.trash.permanentDeleteContent", {
                                  defaultValue: "This prompt will be permanently deleted. This action cannot be undone."
                                }),
                                okText: t("common:delete", { defaultValue: "Delete" }),
                                cancelText: t("common:cancel", { defaultValue: "Cancel" })
                              })
                              if (!ok) return
                              permanentDeletePromptMutation(record.id)
                            }}
                            className="text-text-muted hover:text-danger">
                            <Trash2 className="size-4" />
                          </button>
                        </Tooltip>
                      </div>
                    )
                  }
                ]}
                bordered
                dataSource={filteredTrashData}
                rowKey={(record) => record.id}
                rowSelection={{
                  selectedRowKeys: trashSelectedRowKeys,
                  onChange: (keys) => setTrashSelectedRowKeys(keys)
                }}
              />
            )}
          </>
        )}
      </div>
    )
  }

  return (
    <div>
      {/* Screen reader status announcements */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
        id="prompts-status-announcer"
      />

      {/* Firefox Private Mode Warning */}
      {isFireFoxPrivateMode && (
        <Alert
          type="warning"
          showIcon
          icon={<AlertTriangle className="size-4" />}
          className="mb-4"
          title={t("managePrompts.privateMode.title", { defaultValue: "Limited functionality in Private Mode" })}
          description={t("managePrompts.privateMode.description", {
            defaultValue: "Firefox Private Mode doesn't support IndexedDB. You can view existing prompts, but creating, editing, or importing prompts is disabled. Use a normal window for full functionality."
          })}
        />
      )}
      {(promptLoadFailed || copilotLoadFailed) && (
        <Alert
          type="error"
          showIcon
          className="mb-4"
          title={t(
            "managePrompts.partialLoad",
            "Some prompt data isn't available"
          )}
          description={
            loadErrorDescription ||
            t(
              "managePrompts.loadErrorHelp",
              "Check your server connection and refresh to try again."
            )
          }
        />
      )}
      <div className="flex flex-col items-start gap-1 mb-6">
        <Segmented
          size="large"
          options={[
            {
              label: (
                <span className="flex items-center gap-1">
                  {t("managePrompts.segmented.custom", {
                    defaultValue: "Custom prompts"
                  })}
                  {pendingSyncCount > 0 && (
                    <Tooltip
                      title={t("managePrompts.sync.pendingCountTooltip", {
                        defaultValue:
                          "{{count}} prompt(s) have local changes pending sync.",
                        count: pendingSyncCount
                      })}
                    >
                      <span
                        data-testid="prompts-pending-sync-count"
                        className="text-xs bg-warn/20 text-warn px-1.5 py-0.5 rounded-full"
                      >
                        {pendingSyncCount}
                      </span>
                    </Tooltip>
                  )}
                </span>
              ),
              value: "custom"
            },
            {
              label: (
                <Tooltip title={t("managePrompts.segmented.copilotTooltip", {
                  defaultValue: "Predefined prompts from your tldw server that help with common tasks"
                })}>
                  <span>{t("managePrompts.segmented.copilot", { defaultValue: "Copilot prompts" })}</span>
                </Tooltip>
              ),
              value: "copilot",
              disabled: !isOnline
            },
            {
              label: (
                <Tooltip title={t("managePrompts.segmented.studioTooltip", {
                  defaultValue: "Browse and import prompts from Prompt Studio projects on the server"
                })}>
                  <span className="flex items-center gap-1">
                    <Cloud className="size-3" />
                    {t("managePrompts.segmented.studio", { defaultValue: "Studio" })}
                  </span>
                </Tooltip>
              ),
              value: "studio",
              disabled: !isOnline || hasStudio === false
            },
            {
              label: (
                <span className="flex items-center gap-1">
                  <Trash2 className="size-3" />
                  {t("managePrompts.segmented.trash", { defaultValue: "Trash" })}
                  {(trashData?.length || 0) > 0 && (
                    <span className="text-xs bg-text-muted/20 px-1.5 py-0.5 rounded-full">
                      {trashData?.length}
                    </span>
                  )}
                </span>
              ),
              value: "trash"
            }
          ]}
          data-testid="prompts-segmented"
          value={selectedSegment}
          onChange={(value) => {
            setSelectedSegment(value as SegmentType)
          }}
        />
        <p className="text-xs text-text-muted ">
          {selectedSegment === "custom"
            ? t("managePrompts.segmented.helpCustom", {
                defaultValue:
                  "Create and manage reusable prompts you can insert into chat."
              })
            : selectedSegment === "copilot"
            ? t("managePrompts.segmented.helpCopilot", {
                defaultValue:
                  "View and tweak predefined Copilot prompts provided by your server."
              })
            : selectedSegment === "studio"
            ? t("managePrompts.segmented.helpStudio", {
                defaultValue:
                  "Full Prompt Studio: manage projects, prompts, test cases, evaluations, and optimizations."
              })
            : t("managePrompts.segmented.helpTrash", {
                defaultValue:
                  "Restore or permanently delete prompts. Items auto-delete after 30 days."
              })}
        </p>
      </div>
      {selectedSegment === "custom" && customPrompts()}
      {selectedSegment === "copilot" && copilotPrompts()}
      {selectedSegment === "studio" && <StudioTabContainer />}
      {selectedSegment === "trash" && trashPrompts()}

      <PromptDrawer
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false)
          setDrawerInitialValues(null)
        }}
        mode={drawerMode}
        initialValues={drawerInitialValues}
        onSubmit={handleDrawerSubmit}
        isLoading={drawerMode === "create" ? savePromptLoading : isUpdatingPrompt}
        allTags={allTags}
      />

      <PromptInspectorPanel
        open={inspectorOpen}
        prompt={inspectorPrompt}
        onClose={closeInspector}
        onEdit={(promptId) => {
          const promptRecord = getPromptRecordById(promptId)
          if (!promptRecord) return
          closeInspector()
          openEditDrawer(promptRecord)
        }}
        onUseInChat={(promptId) => {
          const promptRecord = getPromptRecordById(promptId)
          if (!promptRecord) return
          closeInspector()
          void handleUsePromptInChat(promptRecord)
        }}
        onDuplicate={(promptId) => {
          const promptRecord = getPromptRecordById(promptId)
          if (!promptRecord) return
          handleDuplicatePrompt(promptRecord)
        }}
        onDelete={(promptId) => {
          const promptRecord = getPromptRecordById(promptId)
          if (!promptRecord) return
          closeInspector()
          void handleDeletePrompt(promptRecord)
        }}
      />

      <Modal
        title={t("managePrompts.modal.editTitle")}
        open={openCopilotEdit}
        onCancel={() => setOpenCopilotEdit(false)}
        footer={null}>
        <Form
          onFinish={(values) =>
            updateCopilotPrompt({
              key: editCopilotId,
              prompt: values.prompt
            })
          }
          layout="vertical"
          form={editCopilotForm}>
          <Form.Item
            name="prompt"
            label={t("managePrompts.form.prompt.label")}
            extra={
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span>
                  {t("managePrompts.form.prompt.copilotPlaceholderHint", {
                    defaultValue: "Must include placeholder"
                  })}
                </span>
                <Tag color={copilotPromptIncludesTextPlaceholder ? "green" : "orange"}>
                  {"{text}"}
                </Tag>
                <span
                  data-testid="copilot-text-placeholder-status"
                  className={
                    copilotPromptIncludesTextPlaceholder
                      ? "text-success"
                      : "text-warn"
                  }
                >
                  {copilotPromptIncludesTextPlaceholder
                    ? t("managePrompts.form.prompt.copilotPlaceholderPresent", {
                        defaultValue: "placeholder detected"
                      })
                    : t("managePrompts.form.prompt.copilotPlaceholderMissing", {
                        defaultValue: "missing placeholder"
                      })}
                </span>
              </div>
            }
            rules={[
              {
                required: true,
                message: t("managePrompts.form.prompt.required")
              },
              {
                validator: (_, value) => {
                  if (value && value.includes("{text}")) {
                    return Promise.resolve()
                  }
                  return Promise.reject(
                    new Error(
                      t("managePrompts.form.prompt.missingTextPlaceholder")
                    )
                  )
                }
              }
            ]}>
            <Input.TextArea
              placeholder={t("managePrompts.form.prompt.placeholder")}
              autoSize={{ minRows: 3, maxRows: 10 }}
              data-testid="copilot-edit-prompt-input"
            />
          </Form.Item>

          <Form.Item>
            <button
              data-testid="copilot-edit-save"
              disabled={isUpdatingCopilotPrompt}
              className="inline-flex justify-center w-full text-center mt-4 items-center rounded-md border border-transparent bg-primary px-2 py-2 text-sm font-medium leading-4 text-white shadow-sm hover:bg-primaryStrong focus:outline-none focus:ring-2 focus:ring-focus focus:ring-offset-2 disabled:opacity-50">
              {isUpdatingCopilotPrompt
                ? t("managePrompts.form.btnEdit.saving")
                : t("managePrompts.form.btnEdit.save")}
            </button>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={t("managePrompts.bulk.addKeyword", { defaultValue: "Add keyword" })}
        open={bulkKeywordModalOpen}
        onCancel={() => {
          setBulkKeywordModalOpen(false)
          setBulkKeywordValue("")
        }}
        onOk={() =>
          bulkAddKeyword({
            ids: selectedRowKeys.map((key) => String(key)),
            keyword: bulkKeywordValue
          })
        }
        okText={t("common:add", { defaultValue: "Add" })}
        cancelText={t("common:cancel", { defaultValue: "Cancel" })}
        okButtonProps={{
          disabled:
            bulkKeywordValue.trim().length === 0 || isBulkAddingKeyword,
          loading: isBulkAddingKeyword
        }}
      >
        <Input
          autoFocus
          value={bulkKeywordValue}
          onChange={(event) => setBulkKeywordValue(event.target.value)}
          onPressEnter={() => {
            if (
              bulkKeywordValue.trim().length === 0 ||
              isBulkAddingKeyword
            ) {
              return
            }
            bulkAddKeyword({
              ids: selectedRowKeys.map((key) => String(key)),
              keyword: bulkKeywordValue
            })
          }}
          placeholder={t("managePrompts.tags.addPlaceholder", {
            defaultValue: "Enter keyword"
          })}
          data-testid="prompts-bulk-keyword-input"
        />
      </Modal>

      <Modal
        title={t("managePrompts.quickTest.modalTitle", {
          defaultValue: "Quick test prompt"
        })}
        open={!!localQuickTestPrompt}
        onCancel={closeLocalQuickTestModal}
        footer={[
          <button
            key="cancel"
            type="button"
            data-testid="prompts-local-quick-test-cancel"
            className="inline-flex items-center justify-center rounded-md border border-border bg-bg px-3 py-2 text-sm text-text hover:bg-surface2"
            onClick={closeLocalQuickTestModal}
            disabled={isRunningLocalQuickTest}
          >
            {t("common:cancel", { defaultValue: "Cancel" })}
          </button>,
          <button
            key="run"
            type="button"
            data-testid="prompts-local-quick-test-run"
            className="inline-flex items-center justify-center rounded-md border border-transparent bg-primary px-3 py-2 text-sm text-white hover:bg-primaryStrong disabled:opacity-50"
            onClick={() => {
              void runLocalQuickTest()
            }}
            disabled={isRunningLocalQuickTest}
          >
            <Play className="mr-1 size-4" />
            {isRunningLocalQuickTest
              ? t("managePrompts.quickTest.running", { defaultValue: "Running..." })
              : t("managePrompts.quickTest.runAction", { defaultValue: "Run test" })}
          </button>
        ]}
        width={720}
      >
        {localQuickTestPrompt && (
          <div className="space-y-3">
            <div className="rounded border border-border bg-surface2 p-3">
              <div className="text-sm font-medium text-text">
                {localQuickTestPrompt.name}
              </div>
              {localQuickTestPrompt.systemText && (
                <div className="mt-2 text-xs text-text-muted">
                  <span className="font-medium">
                    {t("managePrompts.systemPrompt", {
                      defaultValue: "System prompt"
                    })}
                    :
                  </span>{" "}
                  <span className="line-clamp-2">{localQuickTestPrompt.systemText}</span>
                </div>
              )}
              {localQuickTestPrompt.userText && (
                <div className="mt-2 text-xs text-text-muted">
                  <span className="font-medium">
                    {t("managePrompts.quickPrompt", {
                      defaultValue: "Quick prompt"
                    })}
                    :
                  </span>{" "}
                  <span className="line-clamp-3">{localQuickTestPrompt.userText}</span>
                </div>
              )}
            </div>

            <div className="space-y-1">
              <label className="text-sm font-medium text-text">
                {t("managePrompts.quickTest.inputLabel", {
                  defaultValue: "Sample input"
                })}
              </label>
              <Input.TextArea
                value={localQuickTestInput}
                onChange={(event) => setLocalQuickTestInput(event.target.value)}
                placeholder={t("managePrompts.quickTest.inputPlaceholder", {
                  defaultValue:
                    "Optional input text. Used for {{text}} templates or appended to quick prompts."
                })}
                autoSize={{ minRows: 3, maxRows: 8 }}
                data-testid="prompts-local-quick-test-input"
              />
            </div>

            {localQuickTestOutput && (
              <div
                className="rounded border border-border bg-bg p-3"
                data-testid="prompts-local-quick-test-output"
              >
                <div className="mb-1 text-xs text-text-muted">
                  {localQuickTestRunInfo
                    ? t("managePrompts.quickTest.outputMeta", {
                        defaultValue: "Result ({{provider}} / {{model}})",
                        provider:
                          localQuickTestRunInfo.provider ||
                          t("managePrompts.quickTest.defaultProvider", {
                            defaultValue: "default provider"
                          }),
                        model: localQuickTestRunInfo.model
                      })
                    : t("managePrompts.quickTest.outputTitle", {
                        defaultValue: "Result"
                      })}
                </div>
                <pre className="whitespace-pre-wrap break-words text-sm text-text">
                  {localQuickTestOutput}
                </pre>
              </div>
            )}
          </div>
        )}
      </Modal>

      <Modal
        title={t("managePrompts.collections.create", {
          defaultValue: "New collection"
        })}
        open={createCollectionModalOpen}
        onCancel={() => {
          setCreateCollectionModalOpen(false)
          setNewCollectionName("")
          setNewCollectionDescription("")
        }}
        onOk={() =>
          createPromptCollectionMutation({
            name: newCollectionName,
            description: newCollectionDescription
          })
        }
        okText={t("common:create", { defaultValue: "Create" })}
        cancelText={t("common:cancel", { defaultValue: "Cancel" })}
        okButtonProps={{
          loading: isCreatingPromptCollection,
          disabled: newCollectionName.trim().length === 0
        }}
        data-testid="prompts-collection-create-modal"
      >
        <div className="space-y-3">
          <Input
            value={newCollectionName}
            onChange={(event) => setNewCollectionName(event.target.value)}
            placeholder={t("managePrompts.collections.namePlaceholder", {
              defaultValue: "Collection name"
            })}
            data-testid="prompts-collection-name-input"
          />
          <Input.TextArea
            value={newCollectionDescription}
            onChange={(event) => setNewCollectionDescription(event.target.value)}
            placeholder={t("managePrompts.collections.descriptionPlaceholder", {
              defaultValue: "Description (optional)"
            })}
            autoSize={{ minRows: 2, maxRows: 4 }}
            data-testid="prompts-collection-description-input"
          />
        </div>
      </Modal>

      <Modal
        title={t("managePrompts.shortcuts.title", {
          defaultValue: "Keyboard shortcuts"
        })}
        open={shortcutsHelpOpen}
        onCancel={() => setShortcutsHelpOpen(false)}
        footer={null}
        data-testid="prompts-shortcuts-modal"
      >
        <p className="text-sm text-text-muted">
          {t("managePrompts.shortcuts.description", {
            defaultValue:
              "Shortcuts are available when focus is not inside an input field."
          })}
        </p>
        <div className="mt-3 space-y-2 text-sm">
          <div className="flex items-center justify-between rounded border border-border p-2">
            <span>
              {t("managePrompts.shortcuts.newPrompt", {
                defaultValue: "Create new prompt"
              })}
            </span>
            <kbd className="rounded border border-border px-1.5 py-0.5 text-xs">N</kbd>
          </div>
          <div className="flex items-center justify-between rounded border border-border p-2">
            <span>
              {t("managePrompts.shortcuts.focusSearch", {
                defaultValue: "Focus search"
              })}
            </span>
            <kbd className="rounded border border-border px-1.5 py-0.5 text-xs">/</kbd>
          </div>
          <div className="flex items-center justify-between rounded border border-border p-2">
            <span>
              {t("managePrompts.shortcuts.closeDrawer", {
                defaultValue: "Close drawer / modal"
              })}
            </span>
            <kbd className="rounded border border-border px-1.5 py-0.5 text-xs">Esc</kbd>
          </div>
          <div className="flex items-center justify-between rounded border border-border p-2">
            <span>
              {t("managePrompts.shortcuts.openHelp", {
                defaultValue: "Open shortcut help"
              })}
            </span>
            <kbd className="rounded border border-border px-1.5 py-0.5 text-xs">?</kbd>
          </div>
        </div>
      </Modal>

      <Modal
        title={t("option:promptInsert.confirmTitle", {
          defaultValue: "Use prompt in chat?"
        })}
        open={!!insertPrompt}
        onCancel={() => setInsertPrompt(null)}
        footer={null}
        width={520}>
        <div className="space-y-3">
          {/* System option */}
          {insertPrompt?.systemText && (
            <button
              type="button"
              onClick={() => {
                void handleInsertChoice("system")
              }}
              data-testid="prompt-insert-system"
              className="w-full text-left p-4 rounded-lg border border-border hover:border-primary hover:bg-primary/5 transition-colors">
              <div className="flex items-center gap-2 mb-2">
                <Computer className="size-5 text-warn" />
                <span className="font-medium">
                  {t("option:promptInsert.useAsSystem", {
                    defaultValue: "Use as System Instruction"
                  })}
                </span>
              </div>
              <p className="text-xs text-text-muted mb-2">
                {t("option:promptInsert.systemDescription", {
                  defaultValue: "Sets the AI's behavior and persona for the conversation."
                })}
              </p>
              <div className="bg-surface2 rounded p-2 text-xs line-clamp-3 font-mono text-text-muted">
                {insertPrompt.systemText}
              </div>
            </button>
          )}

          {/* Quick/User option */}
          {insertPrompt?.userText && (
            <button
              type="button"
              onClick={() => {
                void handleInsertChoice("quick")
              }}
              data-testid="prompt-insert-quick"
              className="w-full text-left p-4 rounded-lg border border-border hover:border-primary hover:bg-primary/5 transition-colors">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="size-5 text-primary" />
                <span className="font-medium">
                  {t("option:promptInsert.useAsTemplate", {
                    defaultValue: "Insert as Message Template"
                  })}
                </span>
              </div>
              <p className="text-xs text-text-muted mb-2">
                {t("option:promptInsert.templateDescription", {
                  defaultValue: "Adds this text to your message composer."
                })}
              </p>
              <div className="bg-surface2 rounded p-2 text-xs line-clamp-3 font-mono text-text-muted">
                {insertPrompt.userText}
              </div>
            </button>
          )}

          {/* Use Both option - shown when prompt has both system and user */}
          {insertPrompt?.systemText && insertPrompt?.userText && (
            <button
              type="button"
              onClick={() => {
                void handleInsertChoice("both")
              }}
              data-testid="prompt-insert-both"
              className="w-full text-left p-4 rounded-lg border-2 border-primary/50 bg-primary/5 hover:border-primary hover:bg-primary/10 transition-colors">
              <div className="flex items-center gap-2 mb-2">
                <Layers className="size-5 text-primary" />
                <span className="font-medium text-primary">
                  {t("option:promptInsert.useBoth", {
                    defaultValue: "Use Both (Recommended)"
                  })}
                </span>
              </div>
              <p className="text-xs text-text-muted mb-2">
                {t("option:promptInsert.bothDescription", {
                  defaultValue: "Sets the system instruction AND inserts the message template. Best for prompts designed to work together."
                })}
              </p>
            </button>
          )}
        </div>
      </Modal>

      {/* Project Selector for Push to Server */}
      <ProjectSelector
        open={projectSelectorOpen}
        onClose={() => {
          setProjectSelectorOpen(false)
          setPromptToSync(null)
        }}
        onSelect={(projectId) => {
          if (promptToSync) {
            pushToStudioMutation({ localId: promptToSync, projectId })
          }
        }}
        loading={isPushing}
      />

      <ConflictResolutionModal
        open={conflictModalOpen}
        loading={isLoadingConflictInfo || isResolvingConflict}
        conflictInfo={conflictInfo}
        onClose={closeConflictResolution}
        onResolve={handleResolveConflict}
      />
    </div>
  )
}
