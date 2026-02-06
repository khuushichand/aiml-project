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
import { Computer, Zap, Star, StarOff, UploadCloud, Download, Trash2, Pen, Undo2, AlertTriangle, Layers, Cloud } from "lucide-react"
import { PromptActionsMenu } from "./PromptActionsMenu"
import { PromptDrawer } from "./PromptDrawer"
import { SyncStatusBadge } from "./SyncStatusBadge"
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
  emptyTrash
} from "@/db/dexie/helpers"
import {
  getAllCopilotPrompts,
  setAllCopilotPrompts
} from "@/services/application"
import { tagColors } from "@/utils/color"
import { isFireFoxPrivateMode } from "@/utils/is-private-mode"
import { useConfirmDanger } from "@/components/Common/confirm-danger"
import { useServerOnline } from "@/hooks/useServerOnline"
import FeatureEmptyState from "@/components/Common/FeatureEmptyState"
import ConnectFeatureBanner from "@/components/Common/ConnectFeatureBanner"
import { useMessageOption } from "@/hooks/useMessageOption"
import {
  pushToStudio,
  pullFromStudio,
  unlinkPrompt as unlinkPromptFromServer
} from "@/services/prompt-sync"
import { hasPromptStudio } from "@/services/prompt-studio"
import { StudioTabContainer } from "./Studio/StudioTabContainer"

type SegmentType = "custom" | "copilot" | "studio" | "trash"

const VALID_SEGMENTS: SegmentType[] = ["custom", "copilot", "studio", "trash"]

const getSegmentFromParam = (param: string | null): SegmentType => {
  if (param && VALID_SEGMENTS.includes(param as SegmentType)) {
    return param as SegmentType
  }
  return "custom"
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
  const [tagFilter, setTagFilter] = useState<string[]>([])
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const searchInputRef = useRef<InputRef | null>(null)
  const [importMode, setImportMode] = useState<"merge" | "replace">("merge")
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [insertPrompt, setInsertPrompt] = useState<{
    id: string
    systemText?: string
    userText?: string
  } | null>(null)
  const confirmDanger = useConfirmDanger()

  // Sync state
  const [projectSelectorOpen, setProjectSelectorOpen] = useState(false)
  const [promptToSync, setPromptToSync] = useState<string | null>(null)

  const [openCopilotEdit, setOpenCopilotEdit] = useState(false)
  const [editCopilotId, setEditCopilotId] = useState("")
  const [editCopilotForm] = Form.useForm()

  const { setSelectedQuickPrompt, setSelectedSystemPrompt } = useMessageOption()

  const { data, status } = useQuery({
    queryKey: ["fetchAllPrompts"],
    queryFn: getAllPrompts
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

  // Prompt Studio capability check
  const { data: hasStudio } = useQuery({
    queryKey: ["prompt-studio", "capability"],
    queryFn: hasPromptStudio,
    enabled: isOnline
  })

  // Handle ?prompt= deep-link for opening a specific prompt
  useEffect(() => {
    const promptId = searchParams.get("prompt")
    if (!promptId || deepLinkProcessedRef.current) return
    if (status !== "success" || !Array.isArray(data)) return

    // Find the prompt in the data
    const promptRecord = data.find((p: any) => p.id === promptId)
    if (promptRecord) {
      deepLinkProcessedRef.current = true
      // Remove the prompt param from URL to avoid re-opening on navigation
      const newParams = new URLSearchParams(searchParams)
      newParams.delete("prompt")
      setSearchParams(newParams, { replace: true })
      // Open the edit drawer for this prompt
      setEditId(promptRecord.id)
      setDrawerMode("edit")
      setDrawerInitialValues({
        name: promptRecord?.name || promptRecord?.title,
        author: promptRecord?.author,
        details: promptRecord?.details,
        system_prompt: promptRecord?.system_prompt || (promptRecord?.is_system ? promptRecord?.content : undefined),
        user_prompt: promptRecord?.user_prompt || (!promptRecord?.is_system ? promptRecord?.content : undefined),
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
    } else {
      // Prompt not found - show notification
      deepLinkProcessedRef.current = true
      const newParams = new URLSearchParams(searchParams)
      newParams.delete("prompt")
      setSearchParams(newParams, { replace: true })
      notification.warning({
        message: t("managePrompts.notification.promptNotFound", { defaultValue: "Prompt not found" }),
        description: t("managePrompts.notification.promptNotFoundDesc", {
          defaultValue: "The requested prompt could not be found. It may have been deleted."
        })
      })
    }
  }, [searchParams, data, status, setSearchParams, t])

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
  const systemPromptLabel = t("managePrompts.systemPrompt")
  const quickPromptLabel = t("managePrompts.quickPrompt")

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
      for (const id of ids) {
        await deletePromptById(id)
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["fetchAllPrompts"]
      })
      setSelectedRowKeys([])
      notification.success({
        message: t("managePrompts.notification.bulkDeletedSuccess", { defaultValue: "Prompts deleted" }),
        description: t("managePrompts.notification.bulkDeletedSuccessDesc", { defaultValue: "Selected prompts have been deleted." })
      })
    },
    onError: (error) => {
      notification.error({
        message: t("managePrompts.notification.error"),
        description: error?.message || t("managePrompts.notification.someError")
      })
    }
  })

  const { mutate: savePromptMutation, isPending: savePromptLoading } =
    useMutation({
      mutationFn: savePrompt,
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["fetchAllPrompts"]
        })
        setDrawerOpen(false)
        setDrawerInitialValues(null)
        notification.success({
          message: t("managePrompts.notification.addSuccess"),
          description: t("managePrompts.notification.addSuccessDesc")
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

  const { mutate: updatePromptDirect } = useMutation({
    mutationFn: updatePrompt,
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
        return await updatePrompt({
          ...data,
          id: editId
        })
      },
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["fetchAllPrompts"]
        })
        setDrawerOpen(false)
        setDrawerInitialValues(null)
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

  const { mutate: updateCopilotPrompt, isPending: isUpdatingCopilotPrompt } =
    useMutation({
      mutationFn: async (data: any) => {
        return await setAllCopilotPrompts([
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

  const filteredData = useMemo(() => {
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
    if (tagFilter.length > 0) {
      items = items.filter((p) =>
        (getPromptKeywords(p) || []).some((t: string) => tagFilter.includes(t))
      )
    }
    if (searchText.trim().length > 0) {
      const q = searchText.toLowerCase()
      items = items.filter(
        (p) => {
          const haystack = [
            p.title,
            p.name,
            p.content,
            p.system_prompt,
            p.user_prompt,
            p.details,
            p.author,
            ...(getPromptKeywords(p) || [])
          ]
          return haystack.some((field: any) =>
            typeof field === "string" ? field.toLowerCase().includes(q) : false
          )
        }
      )
    }
    // favorites first, then newest
    items = items.sort(
      (a, b) =>
        Number(!!b.favorite) - Number(!!a.favorite) ||
        (b.createdAt || 0) - (a.createdAt || 0)
    )
    return items
  }, [data, projectFilter, typeFilter, tagFilter, searchText, getPromptKeywords, getPromptType])

  React.useEffect(() => {
    // Only clear selection for items that are no longer visible
    const visibleIds = new Set(filteredData.map((p: any) => p.id))
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
  }, [filteredData, t])

  const triggerExport = async () => {
    try {
      if (guardPrivateMode()) return
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
      const json = JSON.parse(text)
      const prompts = Array.isArray(json) ? json : json?.prompts || []

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

      await importPromptsV2(prompts, {
        replaceExisting: importMode === "replace",
        mergeData: importMode === "merge"
      })
      queryClient.invalidateQueries({ queryKey: ["fetchAllPrompts"] })
      queryClient.invalidateQueries({ queryKey: ["fetchDeletedPrompts"] })
      notification.success({
        message: t("managePrompts.notification.addSuccess"),
        description: importMode === "replace"
          ? t("managePrompts.notification.replaceSuccessDesc", {
              defaultValue: "Prompts replaced successfully. Check your downloads for the backup file."
            })
          : t("managePrompts.notification.addSuccessDesc")
      })
    } catch (e) {
      notification.error({
        message: t("managePrompts.notification.error"),
        description: t("managePrompts.notification.someError")
      })
    }
  }

  const handleInsertChoice = (choice: "system" | "quick" | "both") => {
    if (!insertPrompt) return
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

  const openCreateDrawer = () => {
    if (guardPrivateMode()) return
    setDrawerMode("create")
    setEditId("")
    setDrawerInitialValues(null)
    setDrawerOpen(true)
  }

  // Keyboard shortcuts: N = new prompt, / = focus search, Esc = close drawer
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      const isInput = target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT" || target.isContentEditable
      if (e.key === "Escape" && drawerOpen) {
        setDrawerOpen(false)
        return
      }
      if (isInput) return
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
  }, [drawerOpen])

  const openEditDrawer = (record: any) => {
    if (guardPrivateMode()) return
    setEditId(record.id)
    setDrawerMode("edit")
    const { systemText, userText } = getPromptTexts(record)
    setDrawerInitialValues({
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

  function customPrompts() {
    return (
      <div data-testid="prompts-custom">
        {/* Project filter banner - shown when filtering by project */}
        {projectFilter && (
          <Alert
            type="info"
            showIcon
            className="mb-4"
            message={t("managePrompts.projectFilter.active", {
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
            <div className="flex items-center gap-3 p-2 bg-primary/10 rounded-md border border-primary/30">
              <span className="text-sm text-primary">
                {t("managePrompts.bulk.selected", {
                  defaultValue: "{{count}} selected",
                  count: selectedRowKeys.length
                })}
              </span>
              <button
                onClick={() => triggerBulkExport()}
                data-testid="prompts-bulk-export"
                className="inline-flex items-center gap-1 px-2 py-1 text-sm rounded border border-primary/30 text-primary hover:bg-primary/10">
                <Download className="size-3" /> {t("managePrompts.bulk.export", { defaultValue: "Export selected" })}
              </button>
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
                className="inline-flex items-center gap-1 px-2 py-1 text-sm rounded border border-danger/30 text-danger hover:bg-danger/10 disabled:opacity-50">
                <Trash2 className="size-3" /> {t("managePrompts.bulk.delete", { defaultValue: "Delete selected" })}
              </button>
              <button
                onClick={() => setSelectedRowKeys([])}
                data-testid="prompts-clear-selection"
                className="ml-auto text-sm text-text-muted hover:text-text">
                {t("common:clearSelection", { defaultValue: "Clear selection" })}
              </button>
            </div>
          )}
          <div className="flex flex-wrap items-center justify-between gap-3">
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
              <button
                onClick={() => triggerExport()}
                data-testid="prompts-export"
                aria-label={t("managePrompts.exportLabel", { defaultValue: "Export prompts" })}
                className="inline-flex items-center gap-2 rounded-md border border-border px-2 py-2 text-md font-medium leading-4 text-text hover:bg-surface2">
                <Download className="size-4" /> {t("managePrompts.export", { defaultValue: "Export" })}
              </button>
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
            <div className="flex flex-wrap items-center gap-2">
              <Input
                  ref={searchInputRef}
                  allowClear
                  placeholder={t("managePrompts.searchWithScope", { defaultValue: "Search name, content, keywords..." })}
                  value={searchText}
                  onChange={(e) => setSearchText(e.target.value)}
                  data-testid="prompts-search"
                  aria-label={t("managePrompts.search", { defaultValue: "Search prompts..." })}
                  suffix={<kbd className="rounded border border-border px-1 text-xs text-text-subtle">/</kbd>}
                  style={{ width: 260 }}
                />
              <Select
                value={typeFilter}
                onChange={(v) => setTypeFilter(v as any)}
                data-testid="prompts-type-filter"
                aria-label={t("managePrompts.filter.typeLabel", { defaultValue: "Filter by type" })}
                style={{ width: 130 }}
                options={[
                  { label: t("managePrompts.filter.all", { defaultValue: "All types" }), value: "all" },
                  { label: t("managePrompts.filter.system", { defaultValue: "System" }), value: "system" },
                  { label: t("managePrompts.filter.quick", { defaultValue: "Quick" }), value: "quick" }
                ]}
              />
              <Select
                mode="multiple"
                allowClear
                placeholder={t("managePrompts.tags.placeholder", { defaultValue: "Filter keywords" })}
                style={{ minWidth: 180 }}
                value={tagFilter}
                onChange={(v) => setTagFilter(v)}
                data-testid="prompts-tag-filter"
                aria-label={t("managePrompts.tags.filterLabel", { defaultValue: "Filter by keywords" })}
                options={allTags.map((t) => ({ label: t, value: t }))}
              />
            </div>
          </div>
        </div>

        {status === "pending" && <Skeleton paragraph={{ rows: 8 }} />}

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
          <Table
            data-testid="prompts-table"
            columns={[
              {
                title: "",
                dataIndex: "favorite",
                key: "favorite",
                width: 48,
                render: (_: any, record: any) => (
                  <button
                    onClick={() =>
                      updatePromptDirect({
                        id: record.id,
                        title: record.title,
                        name: record.name,
                        content: record.content,
                        is_system: record.is_system,
                        keywords: getPromptKeywords(record),
                        tags: getPromptKeywords(record),
                        favorite: !record?.favorite
                      })
                    }
                    className={record?.favorite ? "text-warn" : "text-text-muted hover:text-warn"}
                    title={record?.favorite ? t("managePrompts.unfavorite", { defaultValue: "Unfavorite" }) : t("managePrompts.favorite", { defaultValue: "Favorite" })}
                    aria-label={record?.favorite ? t("managePrompts.unfavorite", { defaultValue: "Unfavorite" }) : t("managePrompts.favorite", { defaultValue: "Favorite" })}
                    aria-pressed={!!record?.favorite}
                    data-testid={`prompt-favorite-${record.id}`}
                  >
                    {record?.favorite ? (
                      <Star className="size-4 fill-current" />
                    ) : (
                      <Star className="size-4" />
                    )}
                  </button>
                )
              },
              {
                title: t("managePrompts.columns.title"),
                dataIndex: "title",
                key: "title",
                render: (_: any, record: any) => (
                  <div className="flex max-w-64 flex-col">
                    <span className="line-clamp-1 font-medium">
                      {record?.name || record?.title}
                    </span>
                    {record?.author && (
                      <span className="text-xs text-text-muted ">
                        {t("managePrompts.form.author.label", {
                          defaultValue: "Author"
                        })}
                        : {record.author}
                      </span>
                    )}
                    {record?.details && (
                      <span className="text-xs text-text-muted line-clamp-2">
                        {record.details}
                      </span>
                    )}
                  </div>
                )
              },
              {
                title: t("managePrompts.columns.prompt"),
                key: "content",
                render: (_: any, record: any) => {
                  const { systemText, userText } = getPromptTexts(record)
                  return (
                    <div className="flex max-w-[26rem] flex-col gap-1">
                      {systemText && (
                        <div className="flex items-start gap-2">
                          <Tag color="volcano">
                            {t("managePrompts.form.systemPrompt.shortLabel", {
                              defaultValue: "System"
                            })}
                          </Tag>
                          <span className="line-clamp-2">{systemText}</span>
                        </div>
                      )}
                      {userText && (
                        <div className="flex items-start gap-2">
                          <Tag color="blue">
                            {t("managePrompts.form.userPrompt.shortLabel", {
                              defaultValue: "User"
                            })}
                          </Tag>
                          <span className="line-clamp-2">{userText}</span>
                        </div>
                      )}
                    </div>
                  )
                }
              },
              {
                title: t("managePrompts.tags.label", { defaultValue: "Keywords" }),
                dataIndex: "keywords",
                key: "keywords",
                render: (_: any, record: any) => {
                  const tags = getPromptKeywords(record)
                  return (
                    <div className="flex max-w-64 flex-wrap gap-1">
                      {(tags || []).map((tag: string) => (
                        <Tag key={tag}>{tag}</Tag>
                      ))}
                    </div>
                  )
                }
              },
              {
                title: t("managePrompts.columns.type"),
                key: "type",
                width: 80,
                render: (_: any, record: any) => {
                  const promptType = getPromptType(record)
                  const hasSystem = promptType === "system" || promptType === "mixed"
                  const hasQuick = promptType === "quick" || promptType === "mixed"
                  const typeDescription = hasSystem && hasQuick
                    ? t("managePrompts.type.mixed", { defaultValue: "System and quick prompt" })
                    : hasSystem
                    ? t("managePrompts.type.system", { defaultValue: "System prompt" })
                    : t("managePrompts.type.quick", { defaultValue: "Quick prompt" })
                  return (
                    <div
                      className="flex items-center gap-1"
                      role="group"
                      aria-label={t("managePrompts.type.ariaLabel", { defaultValue: "Prompt type: {{type}}", type: typeDescription })}
                    >
                      <Tooltip title={systemPromptLabel}>
                        <span>
                          <Computer
                            className={`size-4 ${hasSystem ? "text-orange-500" : "text-text-muted/30"}`}
                            aria-hidden="true"
                          />
                        </span>
                      </Tooltip>
                      <Tooltip title={quickPromptLabel}>
                        <span>
                          <Zap
                            className={`size-4 ${hasQuick ? "text-blue-500" : "text-text-muted/30"}`}
                            aria-hidden="true"
                          />
                        </span>
                      </Tooltip>
                    </div>
                  )
                }
              },
              // Sync status column (only show when online)
              ...(isOnline ? [{
                title: t("managePrompts.columns.sync", { defaultValue: "Sync" }),
                key: "syncStatus",
                width: 100,
                render: (_: any, record: any) => (
                  <SyncStatusBadge
                    syncStatus={record.syncStatus || "local"}
                    sourceSystem={record.sourceSystem || "workspace"}
                    serverId={record.serverId}
                    lastSyncedAt={record.lastSyncedAt}
                    compact
                  />
                )
              }] : []),
              {
                title: t("managePrompts.columns.actions"),
                width: 140,
                render: (_, record) => (
                  <PromptActionsMenu
                    promptId={record.id}
                    disabled={isFireFoxPrivateMode}
                    syncStatus={record.syncStatus}
                    serverId={record.serverId}
                    onEdit={() => openEditDrawer(record)}
                    onDuplicate={() => {
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
                    }}
                    onUseInChat={() => {
                      const { systemText, userText } = getPromptTexts(record)
                      const hasSystem =
                        typeof systemText === "string" &&
                        systemText.trim().length > 0
                      const hasUser =
                        typeof userText === "string" &&
                        userText.trim().length > 0

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
                        setSelectedQuickPrompt(quickContent)
                        setSelectedSystemPrompt(undefined)
                        navigate("/chat")
                      }
                    }}
                    onDelete={async () => {
                      const ok = await confirmDanger({
                        title: t("common:confirmTitle", { defaultValue: "Please confirm" }),
                        content: t("managePrompts.confirm.delete"),
                        okText: t("common:delete", { defaultValue: "Delete" }),
                        cancelText: t("common:cancel", { defaultValue: "Cancel" })
                      })
                      if (!ok) return
                      deletePrompt(record.id)
                    }}
                    // Sync actions (only when online)
                    onPushToServer={isOnline ? () => {
                      setPromptToSync(record.id)
                      setProjectSelectorOpen(true)
                    } : undefined}
                    onPullFromServer={isOnline && record.serverId ? () => {
                      pullFromStudioMutation({ serverId: record.serverId, localId: record.id })
                    } : undefined}
                    onUnlink={isOnline && record.serverId ? () => {
                      unlinkPromptMutation(record.id)
                    } : undefined}
                  />
                )
              }
            ]}
            bordered
            dataSource={filteredData}
            rowKey={(record) => record.id}
            onRow={(record) =>
              ({
                "data-testid": `prompt-row-${record.id}`,
                tabIndex: 0,
                role: "row",
                onKeyDown: (e: React.KeyboardEvent) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault()
                    openEditDrawer(record)
                  }
                },
                onDoubleClick: () => openEditDrawer(record),
                className: "cursor-pointer focus:outline-none focus:ring-2 focus:ring-inset focus:ring-primary"
              } as React.HTMLAttributes<HTMLTableRowElement>)
            }
            rowSelection={{
              selectedRowKeys,
              onChange: (keys) => setSelectedRowKeys(keys),
              getCheckboxProps: () => ({
                disabled: isFireFoxPrivateMode
              })
            }}
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
                render: (content) => (
                  <span className="line-clamp-1">{content}</span>
                )
              },
              {
                render: (_, record) => (
                  <div className="flex gap-4">
                    <Tooltip title={t("managePrompts.tooltip.edit")}>
                      <button
                        type="button"
                        aria-label={t("managePrompts.tooltip.edit")}
                        onClick={() => {
                          setEditCopilotId(record.key)
                          editCopilotForm.setFieldsValue(record)
                          setOpenCopilotEdit(true)
                        }}
                        className="text-text-muted ">
                        <Pen className="size-4" />
                      </button>
                    </Tooltip>
                  </div>
                )
              }
            ]}
            bordered
            dataSource={copilotData}
            rowKey={(record) => record.key}
          />
        )}
      </div>
    )
  }

  function trashPrompts() {
    const trashCount = trashData?.length || 0
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
            <div className="flex items-center justify-between p-3 bg-warn/10 rounded-md border border-warn/30 mb-4">
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
                title: t("managePrompts.columns.actions"),
                width: 160,
                render: (_: any, record: any) => (
                  <div className="flex items-center gap-2">
                    <Tooltip title={t("managePrompts.trash.restore", { defaultValue: "Restore" })}>
                      <button
                        onClick={() => restorePromptMutation(record.id)}
                        className="inline-flex items-center gap-1 px-2 py-1 text-sm rounded border border-primary/30 text-primary hover:bg-primary/10">
                        <Undo2 className="size-3" />
                        {t("managePrompts.trash.restore", { defaultValue: "Restore" })}
                      </button>
                    </Tooltip>
                    <Tooltip title={t("managePrompts.trash.deletePermanently", { defaultValue: "Delete permanently" })}>
                      <button
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
            dataSource={trashData}
            rowKey={(record) => record.id}
          />
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
          message={t("managePrompts.privateMode.title", { defaultValue: "Limited functionality in Private Mode" })}
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
          message={t(
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
              label: t("managePrompts.segmented.custom", {
                defaultValue: "Custom prompts"
              }),
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
            />
          </Form.Item>

          <Form.Item>
            <button
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
              onClick={() => handleInsertChoice("system")}
              data-testid="prompt-insert-system"
              className="w-full text-left p-4 rounded-lg border border-border hover:border-primary hover:bg-primary/5 transition-colors">
              <div className="flex items-center gap-2 mb-2">
                <Computer className="size-5 text-orange-500" />
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
              onClick={() => handleInsertChoice("quick")}
              data-testid="prompt-insert-quick"
              className="w-full text-left p-4 rounded-lg border border-border hover:border-primary hover:bg-primary/5 transition-colors">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="size-5 text-blue-500" />
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
              onClick={() => handleInsertChoice("both")}
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
    </div>
  )
}
