import React from "react"
import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Divider,
  Input,
  Modal,
  Select,
  Segmented,
  Skeleton,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message
} from "antd"
import type { InputRef } from "antd"
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  QuestionCircleOutlined,
  ReloadOutlined,
  SearchOutlined,
  WarningOutlined
} from "@ant-design/icons"
import type { ColumnsType } from "antd/es/table"
import { useTranslation } from "react-i18next"
import { useQuery } from "@tanstack/react-query"

import { useServerOnline } from "@/hooks/useServerOnline"
import {
  appendManagedBlocklist,
  deleteManagedBlocklistItem,
  deleteUserOverride,
  getBlocklist,
  getEffectivePolicy,
  getManagedBlocklist,
  getModerationSettings,
  getUserOverride,
  lintBlocklist,
  listUserOverrides,
  reloadModeration,
  setUserOverride,
  testModeration,
  updateBlocklist,
  updateModerationSettings,
  type BlocklistLintItem,
  type BlocklistLintResponse,
  type BlocklistManagedItem,
  type ModerationSettingsResponse,
  type ModerationTestResponse,
  type ModerationUserOverride
} from "@/services/moderation"

const { Title, Text } = Typography
const { TextArea } = Input

const HERO_STYLE: React.CSSProperties = {
  background:
    "linear-gradient(180deg, var(--moderation-hero-start, #fdf7ec) 0%, var(--moderation-hero-end, #f6efdf) 100%)",
  border: "1px solid var(--moderation-hero-border, #e8dcc8)",
  boxShadow: "0 24px 70px var(--moderation-hero-shadow, rgba(110, 86, 48, 0.18))"
}

const HERO_GRID_STYLE: React.CSSProperties = {
  backgroundImage:
    "linear-gradient(var(--moderation-hero-grid-1, rgba(73, 55, 36, 0.08)) 1px, transparent 1px), linear-gradient(90deg, var(--moderation-hero-grid-2, rgba(73, 55, 36, 0.06)) 1px, transparent 1px)",
  backgroundSize: "28px 28px",
  opacity: "var(--moderation-hero-grid-opacity, 0.35)"
}

const normalizeCategories = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean)
  }
  if (typeof value === "string") {
    return value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean)
  }
  return []
}

const formatJson = (value: unknown) => {
  try {
    return JSON.stringify(value ?? {}, null, 2)
  } catch {
    return "{}"
  }
}

const buildOverridePayload = (draft: ModerationUserOverride): ModerationUserOverride => {
  const payload: ModerationUserOverride = {}
  if (draft.enabled !== undefined) payload.enabled = draft.enabled
  if (draft.input_enabled !== undefined) payload.input_enabled = draft.input_enabled
  if (draft.output_enabled !== undefined) payload.output_enabled = draft.output_enabled
  if (draft.input_action) payload.input_action = draft.input_action
  if (draft.output_action) payload.output_action = draft.output_action
  if (draft.redact_replacement) payload.redact_replacement = draft.redact_replacement
  if (draft.categories_enabled !== undefined) {
    payload.categories_enabled = normalizeCategories(draft.categories_enabled)
  }
  return payload
}

const presetProfiles: Record<
  string,
  { label: string; description: string; payload: ModerationUserOverride }
> = {
  strict: {
    label: "Strict",
    description: "Block risky inputs and redact sensitive outputs.",
    payload: {
      enabled: true,
      input_enabled: true,
      output_enabled: true,
      input_action: "block",
      output_action: "redact"
    }
  },
  balanced: {
    label: "Balanced",
    description: "Warn on inputs, redact outputs.",
    payload: {
      enabled: true,
      input_enabled: true,
      output_enabled: true,
      input_action: "warn",
      output_action: "redact"
    }
  },
  monitor: {
    label: "Monitor",
    description: "Warn only, never block.",
    payload: {
      enabled: true,
      input_enabled: true,
      output_enabled: true,
      input_action: "warn",
      output_action: "warn"
    }
  }
}

// Common category suggestions for dropdowns
const CATEGORY_SUGGESTIONS = [
  { value: "pii", label: "PII (Personal Info)" },
  { value: "pii_email", label: "Email Addresses" },
  { value: "pii_phone", label: "Phone Numbers" },
  { value: "pii_address", label: "Physical Addresses" },
  { value: "confidential", label: "Confidential" },
  { value: "profanity", label: "Profanity" },
  { value: "custom", label: "Custom Rules" }
]

// Action options with descriptions
const ACTION_OPTIONS = [
  { value: "block", label: "Block", description: "Reject the message entirely" },
  { value: "redact", label: "Redact", description: "Replace flagged content with [REDACTED]" },
  { value: "warn", label: "Warn", description: "Allow but record in logs" }
]

const ONBOARDING_KEY = "moderation-playground-onboarded"

const stableSort = (items: string[]) => [...items].sort((a, b) => a.localeCompare(b))

const normalizeSettingsDraft = (draft: {
  piiEnabled: boolean
  categoriesEnabled: string[]
  persist: boolean
}) => ({
  piiEnabled: Boolean(draft.piiEnabled),
  categoriesEnabled: stableSort(normalizeCategories(draft.categoriesEnabled)),
  persist: Boolean(draft.persist)
})

const normalizeOverrideForCompare = (draft: ModerationUserOverride) => {
  const payload = buildOverridePayload(draft)
  if (payload.categories_enabled !== undefined) {
    payload.categories_enabled = stableSort(normalizeCategories(payload.categories_enabled))
  }
  return payload
}

const isEqualJson = (left: unknown, right: unknown) =>
  JSON.stringify(left) === JSON.stringify(right)

export const ModerationPlayground: React.FC = () => {
  const { t } = useTranslation(["option", "common"])
  const online = useServerOnline()
  const [messageApi, contextHolder] = message.useMessage()

  const [scope, setScope] = React.useState<"server" | "user">("server")
  const [userIdDraft, setUserIdDraft] = React.useState("")
  const [activeUserId, setActiveUserId] = React.useState<string | null>(null)
  const [showAdvanced, setShowAdvanced] = React.useState(false)

  const [settingsDraft, setSettingsDraft] = React.useState({
    piiEnabled: false,
    categoriesEnabled: [] as string[],
    persist: false
  })
  const [settingsBaseline, setSettingsBaseline] = React.useState<{
    piiEnabled: boolean
    categoriesEnabled: string[]
    persist: boolean
  } | null>(null)

  const [overrideDraft, setOverrideDraft] = React.useState<ModerationUserOverride>({})
  const [overrideLoaded, setOverrideLoaded] = React.useState(false)
  const [overrideLoading, setOverrideLoading] = React.useState(false)
  const [overrideBaseline, setOverrideBaseline] = React.useState<ModerationUserOverride | null>(
    null
  )

  const [blocklistText, setBlocklistText] = React.useState("")
  const [blocklistLint, setBlocklistLint] = React.useState<BlocklistLintResponse | null>(null)
  const [blocklistLoading, setBlocklistLoading] = React.useState(false)

  const [managedItems, setManagedItems] = React.useState<BlocklistManagedItem[]>([])
  const [managedVersion, setManagedVersion] = React.useState("")
  const [managedLine, setManagedLine] = React.useState("")
  const [managedLint, setManagedLint] = React.useState<BlocklistLintResponse | null>(null)
  const [managedLoading, setManagedLoading] = React.useState(false)

  const [testPhase, setTestPhase] = React.useState<"input" | "output">("input")
  const [testText, setTestText] = React.useState("")
  const [testUserId, setTestUserId] = React.useState("")
  const [testResult, setTestResult] = React.useState<ModerationTestResponse | null>(null)

  // UX improvement states
  const [showOnboarding, setShowOnboarding] = React.useState(() => {
    if (typeof window === "undefined") return false
    return !localStorage.getItem(ONBOARDING_KEY)
  })
  const [overrideSearchFilter, setOverrideSearchFilter] = React.useState("")
  const [userIdError, setUserIdError] = React.useState<string | null>(null)
  const [selectedOverrideIds, setSelectedOverrideIds] = React.useState<React.Key[]>([])

  // Refs
  const userIdInputRef = React.useRef<InputRef>(null)

  const settingsQuery = useQuery<ModerationSettingsResponse>({
    queryKey: ["moderation-settings"],
    queryFn: getModerationSettings,
    enabled: online
  })

  const policyQuery = useQuery<Record<string, any>>({
    queryKey: ["moderation-policy", activeUserId ?? "server"],
    queryFn: () => getEffectivePolicy(activeUserId || undefined),
    enabled: online
  })

  const overridesQuery = useQuery({
    queryKey: ["moderation-overrides"],
    queryFn: listUserOverrides,
    enabled: online && showAdvanced
  })

  React.useEffect(() => {
    if (!settingsQuery.data) return
    const data = settingsQuery.data
    const categories = data.categories_enabled ?? data.effective?.categories_enabled ?? []
    const piiEnabled =
      data.pii_enabled ??
      (typeof data.effective?.pii_enabled === "boolean"
        ? data.effective?.pii_enabled
        : false)
    setSettingsDraft((prev) => ({
      ...prev,
      piiEnabled,
      categoriesEnabled: categories || []
    }))
    setSettingsBaseline((prev) => ({
      piiEnabled,
      categoriesEnabled: categories || [],
      persist: prev?.persist ?? false
    }))
  }, [settingsQuery.data])

  React.useEffect(() => {
    if (scope === "server") {
      setActiveUserId(null)
      setOverrideDraft({})
      setOverrideLoaded(false)
      return
    }
    if (!userIdDraft.trim()) {
      setActiveUserId(null)
    }
  }, [scope, userIdDraft])

  React.useEffect(() => {
    if (!activeUserId) {
      setOverrideDraft({})
      setOverrideLoaded(false)
      setUserIdError(null)
      setOverrideBaseline({})
      return
    }
    let cancelled = false
    const loadOverride = async () => {
      setOverrideLoading(true)
      setUserIdError(null)
      try {
        const data = await getUserOverride(activeUserId)
        if (cancelled) return
        const normalizedCategories =
          typeof data.categories_enabled === "undefined"
            ? undefined
            : normalizeCategories(data.categories_enabled)
        const normalized: ModerationUserOverride = {
          enabled: data.enabled,
          input_enabled: data.input_enabled,
          output_enabled: data.output_enabled,
          input_action: data.input_action,
          output_action: data.output_action,
          redact_replacement: data.redact_replacement,
          categories_enabled: normalizedCategories
        }
        setOverrideDraft(normalized)
        setOverrideLoaded(true)
        setOverrideBaseline(normalized)
      } catch (err: any) {
        if (cancelled) return
        if (err?.status === 404) {
          // User has no existing override - this is OK, they can create one
          setOverrideDraft({})
          setOverrideLoaded(false)
          // Show informational message instead of error
          setUserIdError(`No override found for "${activeUserId}". You can create a new one.`)
          setOverrideBaseline({})
        } else {
          messageApi.error("Failed to load user override")
        }
      } finally {
        if (!cancelled) setOverrideLoading(false)
      }
    }
    void loadOverride()
    return () => {
      cancelled = true
    }
  }, [activeUserId, messageApi])

  React.useEffect(() => {
    if (activeUserId && !testUserId) {
      setTestUserId(activeUserId)
    }
  }, [activeUserId, testUserId])

  // Keyboard shortcut: Ctrl+S to save
  React.useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "s") {
        event.preventDefault()
        if (scope === "user" && activeUserId) {
          void handleSaveOverride()
        } else if (scope === "server") {
          void handleSaveSettings()
        }
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [scope, activeUserId, overrideDraft, settingsDraft])

  const normalizedSettingsDraft = normalizeSettingsDraft(settingsDraft)
  const normalizedSettingsBaseline = normalizeSettingsDraft(settingsBaseline ?? settingsDraft)
  const settingsDirty =
    settingsBaseline !== null && !isEqualJson(normalizedSettingsDraft, normalizedSettingsBaseline)
  const normalizedOverrideDraft = normalizeOverrideForCompare(overrideDraft)
  const normalizedOverrideBaseline = normalizeOverrideForCompare(overrideBaseline ?? {})
  const overrideDirty =
    Boolean(activeUserId) && !isEqualJson(normalizedOverrideDraft, normalizedOverrideBaseline)
  const hasUnsavedChanges = settingsDirty || overrideDirty

  React.useEffect(() => {
    if (!hasUnsavedChanges) return
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ""
    }
    window.addEventListener("beforeunload", handleBeforeUnload)
    return () => window.removeEventListener("beforeunload", handleBeforeUnload)
  }, [hasUnsavedChanges])

  const handleLoadUser = () => {
    if (!userIdDraft.trim()) {
      messageApi.warning("Enter a user id to load overrides")
      return
    }
    setActiveUserId(userIdDraft.trim())
  }

  const handleSaveSettings = async () => {
    try {
      const payload = {
        pii_enabled: settingsDraft.piiEnabled,
        categories_enabled: settingsDraft.categoriesEnabled,
        persist: settingsDraft.persist
      }
      await updateModerationSettings(payload)
      messageApi.success("Moderation settings updated")
      setSettingsBaseline(normalizedSettingsDraft)
      await settingsQuery.refetch()
      await policyQuery.refetch()
    } catch (err: any) {
      messageApi.error(err?.message || "Failed to update settings")
    }
  }

  const handleApplyPreset = async (key: string) => {
    if (!activeUserId) {
      messageApi.warning("Select a user to apply presets")
      return
    }
    try {
      const preset = presetProfiles[key]
      const payload = buildOverridePayload(preset.payload)
      await setUserOverride(activeUserId, payload)
      messageApi.success(`Applied ${preset.label} profile`)
      setOverrideDraft((prev) => ({ ...prev, ...preset.payload }))
      await policyQuery.refetch()
      if (showAdvanced) {
        await overridesQuery.refetch()
      }
    } catch (err: any) {
      messageApi.error(err?.message || "Failed to apply preset")
    }
  }

  const handleSaveOverride = async () => {
    if (!activeUserId) {
      messageApi.warning("Select a user to save overrides")
      return
    }
    try {
      const payload = buildOverridePayload(overrideDraft)
      await setUserOverride(activeUserId, payload)
      messageApi.success("User override saved")
      setOverrideLoaded(true)
      setOverrideBaseline(normalizedOverrideDraft)
      await policyQuery.refetch()
      if (showAdvanced) {
        await overridesQuery.refetch()
      }
    } catch (err: any) {
      messageApi.error(err?.message || "Failed to save override")
    }
  }

  const handleResetSettings = () => {
    if (!settingsBaseline) return
    setSettingsDraft({
      piiEnabled: settingsBaseline.piiEnabled,
      categoriesEnabled: [...settingsBaseline.categoriesEnabled],
      persist: settingsBaseline.persist
    })
  }

  const handleResetOverride = () => {
    const baseline = overrideBaseline ?? {}
    const normalized: ModerationUserOverride = {
      ...baseline,
      categories_enabled:
        baseline.categories_enabled !== undefined
          ? normalizeCategories(baseline.categories_enabled)
          : undefined
    }
    setOverrideDraft(normalized)
  }

  const handleDeleteOverride = async (userId?: string | null) => {
    const targetId = userId || activeUserId
    if (!targetId) return
    try {
      await deleteUserOverride(targetId)
      messageApi.success("Override removed")
      if (targetId === activeUserId) {
        setOverrideDraft({})
        setOverrideLoaded(false)
        setUserIdError(null)
        setOverrideBaseline({})
        await policyQuery.refetch()
      }
      if (showAdvanced) {
        await overridesQuery.refetch()
      }
    } catch (err: any) {
      messageApi.error(err?.message || "Failed to delete override")
    }
  }

  const confirmDeleteOverride = (userId?: string | null) => {
    const targetId = userId || activeUserId
    if (!targetId) return
    Modal.confirm({
      title: "Delete User Override?",
      icon: <ExclamationCircleOutlined />,
      content: `This will remove all custom safety settings for "${targetId}". The user will fall back to server defaults. This action cannot be undone.`,
      okText: "Delete",
      okType: "danger",
      cancelText: "Cancel",
      onOk: () => handleDeleteOverride(targetId)
    })
  }

  const confirmDeleteManagedItem = (itemId: number, line: string) => {
    Modal.confirm({
      title: "Delete Blocklist Rule?",
      icon: <ExclamationCircleOutlined />,
      content: (
        <div>
          <p>Remove this rule from the blocklist?</p>
          <code className="block mt-2 p-2 bg-surface rounded text-sm">{line}</code>
        </div>
      ),
      okText: "Delete",
      okType: "danger",
      cancelText: "Cancel",
      onOk: () => handleDeleteManaged(itemId)
    })
  }

  const handleBulkDeleteOverrides = async (userIds: string[]) => {
    if (!userIds.length) return
    const failed: string[] = []
    for (const userId of userIds) {
      try {
        await deleteUserOverride(userId)
      } catch {
        failed.push(userId)
      }
    }
    const successCount = userIds.length - failed.length
    if (successCount) {
      messageApi.success(`Deleted ${successCount} overrides`)
    }
    if (failed.length) {
      messageApi.error(`Failed to delete: ${failed.join(", ")}`)
    }
    if (activeUserId && userIds.includes(activeUserId)) {
      setOverrideDraft({})
      setOverrideLoaded(false)
      setUserIdError(null)
      setOverrideBaseline({})
      await policyQuery.refetch()
    }
    if (showAdvanced) {
      await overridesQuery.refetch()
    }
    setSelectedOverrideIds([])
  }

  const confirmBulkDeleteOverrides = () => {
    const targetIds = selectedOverrideIds.map((id) => String(id))
    if (!targetIds.length) return
    Modal.confirm({
      title: "Delete Selected Overrides?",
      icon: <ExclamationCircleOutlined />,
      content: `This will remove ${targetIds.length} user overrides and revert them to server defaults. This action cannot be undone.`,
      okText: "Delete",
      okType: "danger",
      cancelText: "Cancel",
      onOk: () => handleBulkDeleteOverrides(targetIds)
    })
  }

  const handlePersistChange = (checked: boolean) => {
    if (checked) {
      Modal.confirm({
        title: "Save Settings to Disk?",
        icon: <WarningOutlined style={{ color: "#faad14" }} />,
        content: "This will permanently save your moderation settings to disk. Changes will persist after server restarts. Are you sure?",
        okText: "Yes, persist settings",
        cancelText: "Cancel",
        onOk: () => setSettingsDraft((prev) => ({ ...prev, persist: true }))
      })
    } else {
      setSettingsDraft((prev) => ({ ...prev, persist: false }))
    }
  }

  const dismissOnboarding = () => {
    setShowOnboarding(false)
    if (typeof window !== "undefined") {
      localStorage.setItem(ONBOARDING_KEY, "true")
    }
  }

  const handleReload = async () => {
    try {
      await reloadModeration()
      messageApi.success("Reloaded moderation config")
      await settingsQuery.refetch()
      await policyQuery.refetch()
      if (showAdvanced) {
        await overridesQuery.refetch()
      }
    } catch (err: any) {
      messageApi.error(err?.message || "Reload failed")
    }
  }

  const handleLoadBlocklist = async () => {
    setBlocklistLoading(true)
    try {
      const lines = await getBlocklist()
      setBlocklistText((lines || []).join("\n"))
      setBlocklistLint(null)
    } catch (err: any) {
      messageApi.error(err?.message || "Failed to load blocklist")
    } finally {
      setBlocklistLoading(false)
    }
  }

  const handleSaveBlocklist = async () => {
    setBlocklistLoading(true)
    try {
      const lines = blocklistText
        .split(/\r?\n/)
        .map((line) => line.trimEnd())
      await updateBlocklist(lines)
      messageApi.success("Blocklist saved")
    } catch (err: any) {
      messageApi.error(err?.message || "Failed to save blocklist")
    } finally {
      setBlocklistLoading(false)
    }
  }

  const handleLintBlocklist = async () => {
    setBlocklistLoading(true)
    try {
      const lines = blocklistText.split(/\r?\n/)
      const lint = await lintBlocklist({ lines })
      setBlocklistLint(lint)
    } catch (err: any) {
      messageApi.error(err?.message || "Lint failed")
    } finally {
      setBlocklistLoading(false)
    }
  }

  const handleLoadManaged = async () => {
    setManagedLoading(true)
    try {
      const { data, etag } = await getManagedBlocklist()
      setManagedItems(data.items || [])
      setManagedVersion(data.version || etag || "")
    } catch (err: any) {
      messageApi.error(err?.message || "Failed to load managed blocklist")
    } finally {
      setManagedLoading(false)
    }
  }

  const handleAppendManaged = async () => {
    if (!managedVersion) {
      messageApi.warning("Load the managed blocklist first")
      return
    }
    const line = managedLine.trim()
    if (!line) {
      messageApi.warning("Enter a line to append")
      return
    }
    setManagedLoading(true)
    try {
      await appendManagedBlocklist(managedVersion, line)
      setManagedLine("")
      await handleLoadManaged()
      messageApi.success("Line appended")
    } catch (err: any) {
      messageApi.error(err?.message || "Append failed")
    } finally {
      setManagedLoading(false)
    }
  }

  const handleDeleteManaged = async (itemId: number) => {
    if (!managedVersion) return
    setManagedLoading(true)
    try {
      await deleteManagedBlocklistItem(managedVersion, itemId)
      await handleLoadManaged()
      messageApi.success("Line deleted")
    } catch (err: any) {
      messageApi.error(err?.message || "Delete failed")
    } finally {
      setManagedLoading(false)
    }
  }

  const handleLintManagedLine = async () => {
    if (!managedLine.trim()) {
      messageApi.warning("Enter a line to lint")
      return
    }
    setManagedLoading(true)
    try {
      const lint = await lintBlocklist({ line: managedLine.trim() })
      setManagedLint(lint)
    } catch (err: any) {
      messageApi.error(err?.message || "Lint failed")
    } finally {
      setManagedLoading(false)
    }
  }

  const handleRunTest = async () => {
    if (!testText.trim()) {
      messageApi.warning("Enter sample text to test")
      return
    }
    try {
      const payload = {
        user_id: testUserId ? testUserId.trim() : undefined,
        phase: testPhase,
        text: testText
      }
      const res = await testModeration(payload)
      setTestResult(res)
    } catch (err: any) {
      messageApi.error(err?.message || "Moderation test failed")
    }
  }

  const buildLintColumns = (showStatus: boolean): ColumnsType<BlocklistLintItem> => {
    const columns: ColumnsType<BlocklistLintItem> = [
      { title: "Rule", dataIndex: "line", key: "line", ellipsis: true },
      {
        title: "Action",
        dataIndex: "action",
        key: "action",
        width: 110,
        render: (action: string) => {
          const colors: Record<string, string> = { block: "red", redact: "orange", warn: "blue" }
          return action ? <Tag color={colors[action] || "default"}>{action}</Tag> : "-"
        }
      },
      {
        title: "Categories",
        dataIndex: "categories",
        key: "categories",
        width: 160,
        render: (cats: string[]) => (
          cats && cats.length ? (
            <Space wrap size={4}>
              {cats.map((cat) => <Tag key={cat} className="text-xs">{cat}</Tag>)}
            </Space>
          ) : "-"
        )
      }
    ]

    if (showStatus) {
      columns.splice(1, 0, {
        title: "Status",
        dataIndex: "ok",
        key: "ok",
        width: 90,
        render: (ok: boolean) => (
          ok ? (
            <Tag color="green" icon={<CheckCircleOutlined />}>Valid</Tag>
          ) : (
            <Tag color="red" icon={<CloseCircleOutlined />}>Invalid</Tag>
          )
        )
      })
      columns.push({
        title: "Issue",
        dataIndex: "error",
        key: "error",
        ellipsis: true,
        render: (error: string) => error ? <Text type="danger">{error}</Text> : "-"
      })
    }

    return columns
  }

  const overrideColumns: ColumnsType<{ user_id: string; override: Record<string, any> }> = [
    { title: "User ID", dataIndex: "user_id", key: "user_id", width: 160 },
    {
      title: "Settings",
      dataIndex: "override",
      key: "override",
      render: (override: Record<string, any>) => {
        // Show a summary instead of full JSON
        const enabled = override.enabled !== false
        const inputAction = override.input_action || "default"
        const outputAction = override.output_action || "default"
        return (
          <Space wrap>
            <Tag color={enabled ? "green" : "red"} icon={enabled ? <CheckCircleOutlined /> : <CloseCircleOutlined />}>
              {enabled ? "Active" : "Disabled"}
            </Tag>
            {override.input_action && <Tag>Input: {inputAction}</Tag>}
            {override.output_action && <Tag>Output: {outputAction}</Tag>}
          </Space>
        )
      }
    },
    {
      title: "Actions",
      key: "actions",
      width: 160,
      render: (_value, record) => (
        <Space>
          <Tooltip title="Edit this user's settings">
            <Button size="small" onClick={() => {
              setScope("user")
              setUserIdDraft(record.user_id)
              setActiveUserId(record.user_id)
            }} aria-label={`Edit settings for ${record.user_id}`}>
              Edit
            </Button>
          </Tooltip>
          <Tooltip title="Remove override (user will use server defaults)">
            <Button size="small" danger onClick={() => confirmDeleteOverride(record.user_id)} aria-label={`Delete override for ${record.user_id}`}>
              Delete
            </Button>
          </Tooltip>
        </Space>
      )
    }
  ]

  const policySnapshot = policyQuery.data || {}
  const policyCategories = normalizeCategories(policySnapshot.categories_enabled)
  const blocklistCount = policySnapshot.blocklist_count ?? 0
  const overridesData = Object.entries(overridesQuery.data?.overrides || {})
    .map(([user_id, override]) => ({ user_id, override }))
    .filter((item) =>
      !overrideSearchFilter ||
      item.user_id.toLowerCase().includes(overrideSearchFilter.toLowerCase())
    )
  const overrideRowSelection = {
    selectedRowKeys: selectedOverrideIds,
    onChange: (keys: React.Key[]) => setSelectedOverrideIds(keys)
  }

  return (
    <div className="space-y-6">
      {contextHolder}

      {/* Onboarding Banner */}
      {showOnboarding && (
        <Alert
          type="info"
          showIcon
          icon={<InfoCircleOutlined />}
          closable
          onClose={dismissOnboarding}
          message="Welcome to Moderation Playground"
          description={
            <div className="mt-2">
              <Text>Configure content safety rules to protect your users. Here's how to get started:</Text>
              <ol className="mt-2 ml-4 list-decimal space-y-1">
                <li><strong>Choose scope:</strong> Server-wide rules apply to everyone, or select User for individual settings</li>
                <li><strong>Set safety level:</strong> Use a quick preset or customize filters manually</li>
                <li><strong>Test your rules:</strong> Try sample content to verify behavior before deploying</li>
              </ol>
              <Button type="link" className="p-0 mt-2" onClick={dismissOnboarding}>
                Got it, let's start
              </Button>
            </div>
          }
        />
      )}

      <div
        className="relative overflow-hidden rounded-[28px] p-6 sm:p-8 text-text"
        style={HERO_STYLE}
      >
        <div className="absolute inset-0" style={HERO_GRID_STYLE} />
        <div className="relative">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <Title level={2} className="!mb-1 font-display">
                {t("option:moderationPlayground.title", "Moderation Playground")}
              </Title>
              <Text className="text-text-muted">
                {t(
                  "option:moderationPlayground.subtitle",
                  "Family safety controls and server guardrails in one place."
                )}
              </Text>
              <div className="mt-3 flex flex-wrap gap-2">
                <Tag color={online ? "green" : "red"} icon={online ? <CheckCircleOutlined /> : <CloseCircleOutlined />}>
                  {online ? "Server online" : "Server offline"}
                </Tag>
              </div>
            </div>
            <Space align="center" wrap>
              <Tooltip title="Enable Blocklist Studio and Per-user Overrides table">
                <Space>
                  <Text className="text-text-muted">Advanced</Text>
                  <Switch checked={showAdvanced} onChange={setShowAdvanced} />
                </Space>
              </Tooltip>
              <Tooltip title="Reload moderation rules from server config files">
                <Button icon={<ReloadOutlined />} onClick={handleReload} aria-label="Reload moderation configuration">Reload config</Button>
              </Tooltip>
            </Space>
          </div>

          <Divider className="!my-4" />

          <div className="flex flex-wrap items-center gap-3">
            <Tooltip title="Server-wide rules apply to all users. User scope allows individual overrides.">
              <Segmented
                value={scope}
                onChange={(value) => {
                  const nextScope = value as "server" | "user"
                  setScope(nextScope)
                  if (nextScope === "user") {
                    const trimmed = userIdDraft.trim()
                    if (trimmed && trimmed !== activeUserId) {
                      setActiveUserId(trimmed)
                    }
                  }
                }}
                options={[
                  { label: "Server (Global)", value: "server" },
                  { label: "User (Individual)", value: "user" }
                ]}
              />
            </Tooltip>
            <Input
              ref={userIdInputRef}
              placeholder="Enter User ID"
              value={userIdDraft}
              onChange={(event) => {
                setUserIdDraft(event.target.value)
                setUserIdError(null)
              }}
              onPressEnter={handleLoadUser}
              disabled={scope !== "user"}
              style={{ width: 220 }}
              status={userIdError ? "warning" : undefined}
              suffix={scope === "user" && userIdDraft && <SearchOutlined className="text-text-muted" />}
            />
            <Button disabled={scope !== "user"} onClick={handleLoadUser} loading={overrideLoading}>
              Load user
            </Button>
            {activeUserId && (
              <Tag color="geekblue" className="text-sm font-medium py-1 px-3">
                Configuring: {activeUserId}
              </Tag>
            )}
          </div>
          {userIdError && (
            <Alert
              type="info"
              showIcon
              icon={<InfoCircleOutlined />}
              message={userIdError}
              className="mt-3"
            />
          )}
        </div>
      </div>

      {!online && (
        <Alert
          type="warning"
          message="Connect to your tldw server to use moderation controls."
          showIcon
        />
      )}

      {/* Advanced features hint when advanced mode is off */}
      {!showAdvanced && (
        <Alert
          type="info"
          showIcon
          icon={<QuestionCircleOutlined />}
          message={
            <span>
              Looking for blocklist rules or user overrides?{" "}
              <Button type="link" className="p-0" onClick={() => setShowAdvanced(true)}>
                Enable Advanced mode
              </Button>
            </span>
          }
          className="!py-2"
        />
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card
          title={
            <Space>
              <span>Global Server Rules</span>
              <Tooltip title="These settings apply to all users unless overridden">
                <QuestionCircleOutlined className="text-text-muted" />
              </Tooltip>
            </Space>
          }
          className="shadow-sm order-2 lg:order-2"
          extra={
            <Space size="small">
              <Tag color="blue">Server-wide</Tag>
              {settingsDirty && <Tag color="orange">Unsaved changes</Tag>}
            </Space>
          }
        >
          <Space direction="vertical" size="middle" className="w-full">
            <div className="flex items-center justify-between gap-3">
              <div>
                <Space>
                  <Text strong>Personal Data Protection</Text>
                  <Tooltip title="Automatically detects and handles personal information like emails, phone numbers, and addresses">
                    <QuestionCircleOutlined className="text-text-muted" />
                  </Tooltip>
                </Space>
                <div className="text-text-muted text-xs">
                  Enable built-in rules to detect and redact personal information.
                </div>
              </div>
              <Switch
                checked={settingsDraft.piiEnabled}
                onChange={(value) =>
                  setSettingsDraft((prev) => ({ ...prev, piiEnabled: value }))
                }
              />
            </div>

            <div>
              <Space>
                <Text strong>Content Categories to Monitor</Text>
                <Tooltip title="Choose which types of content to monitor. Leave empty to apply all rules.">
                  <QuestionCircleOutlined className="text-text-muted" />
                </Tooltip>
              </Space>
              <div className="text-text-muted text-xs mb-2">
                Select categories or type custom ones. Leave empty to monitor all.
              </div>
              <Select
                mode="tags"
                style={{ width: "100%" }}
                placeholder="Select or type categories..."
                value={settingsDraft.categoriesEnabled}
                onChange={(value) =>
                  setSettingsDraft((prev) => ({
                    ...prev,
                    categoriesEnabled: value as string[]
                  }))
                }
                options={CATEGORY_SUGGESTIONS}
              />
            </div>

            <div className="p-3 bg-warning-bg border border-warning-border rounded-lg">
              <Checkbox
                checked={settingsDraft.persist}
                onChange={(event) => handlePersistChange(event.target.checked)}
              >
                <Space>
                  <span>Save settings to disk</span>
                  <Tooltip title="When enabled, changes persist after server restart. Use with caution.">
                    <WarningOutlined className="text-warning" />
                  </Tooltip>
                </Space>
              </Checkbox>
            </div>

            <Space wrap>
              <Tooltip title="Keyboard shortcut: Ctrl+S (when in Server scope)">
                <Button
                  type="primary"
                  onClick={handleSaveSettings}
                  loading={settingsQuery.isFetching}
                  aria-label="Save server runtime settings"
                >
                  Save runtime settings
                </Button>
              </Tooltip>
              <Tooltip title="Revert unsaved changes">
                <Button onClick={handleResetSettings} disabled={!settingsDirty}>
                  Reset changes
                </Button>
              </Tooltip>
            </Space>

            {settingsQuery.data && (
              <Alert
                type="info"
                showIcon
                message={
                  <span>
                    Active categories: {normalizeCategories(settingsQuery.data.effective?.categories_enabled).join(", ") || "all categories"}
                  </span>
                }
              />
            )}
          </Space>
        </Card>

        <Card
          title={
            <Space>
              <span>Per-User Safety Rules</span>
              <Tooltip title="Override server rules for specific users">
                <QuestionCircleOutlined className="text-text-muted" />
              </Tooltip>
            </Space>
          }
          className="shadow-sm order-1 lg:order-1"
          extra={
            <Space size="small">
              <Tag color="purple">User overrides</Tag>
              {overrideDirty && <Tag color="orange">Unsaved changes</Tag>}
            </Space>
          }
        >
          {scope !== "user" ? (
            <div className="space-y-4">
              <Alert
                type="info"
                showIcon
                message="Switch to User scope to configure individual safety rules."
                description="User-specific rules override server defaults for that user only."
              />
              {/* Show disabled preview of controls */}
              <div className="opacity-50 pointer-events-none">
                <Text strong className="block mb-2">Quick Presets (Preview)</Text>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(presetProfiles).map(([key, preset]) => (
                    <Tooltip key={key} title={preset.description}>
                      <Button disabled>{preset.label}</Button>
                    </Tooltip>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <Space direction="vertical" size="middle" className="w-full">
              <div>
                <Text strong>Quick Presets</Text>
                <div className="text-text-muted text-xs mb-2">
                  Apply a pre-configured safety profile with one click.
                </div>
                <div className="grid gap-2 sm:grid-cols-3">
                  {Object.entries(presetProfiles).map(([key, preset]) => (
                    <Card
                      key={key}
                      size="small"
                      hoverable
                      onClick={() => !overrideLoading && activeUserId && handleApplyPreset(key)}
                      className={`cursor-pointer transition-all ${(!activeUserId || overrideLoading) ? "opacity-50 cursor-not-allowed" : "hover:border-primary"}`}
                    >
                      <Text strong>{preset.label}</Text>
                      <div className="text-xs text-text-muted mt-1">{preset.description}</div>
                    </Card>
                  ))}
                </div>
              </div>

              <Divider className="!my-2" />

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="flex items-center justify-between">
                  <Tooltip title="Enable or disable all moderation for this user">
                    <Text>Moderation Enabled</Text>
                  </Tooltip>
                  <Switch
                    checked={Boolean(overrideDraft.enabled)}
                    onChange={(value) =>
                      setOverrideDraft((prev) => ({ ...prev, enabled: value }))
                    }
                  />
                </div>
                <div className="flex items-center justify-between">
                  <Tooltip title="Filter content when this user sends messages">
                    <Text>Filter what user sends</Text>
                  </Tooltip>
                  <Switch
                    checked={Boolean(overrideDraft.input_enabled)}
                    onChange={(value) =>
                      setOverrideDraft((prev) => ({ ...prev, input_enabled: value }))
                    }
                  />
                </div>
                <div className="flex items-center justify-between col-span-full sm:col-span-1">
                  <Tooltip title="Filter AI responses shown to this user">
                    <Text>Filter AI responses</Text>
                  </Tooltip>
                  <Switch
                    checked={Boolean(overrideDraft.output_enabled)}
                    onChange={(value) =>
                      setOverrideDraft((prev) => ({ ...prev, output_enabled: value }))
                    }
                  />
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <Tooltip title="What happens when user's message matches a safety rule">
                    <Text>When user sends flagged content</Text>
                  </Tooltip>
                  <Select
                    value={overrideDraft.input_action}
                    onChange={(value) =>
                      setOverrideDraft((prev) => ({ ...prev, input_action: value }))
                    }
                    style={{ width: "100%" }}
                    optionRender={(option) => {
                      const actionInfo = ACTION_OPTIONS.find((a) => a.value === option.value)
                      return (
                        <div>
                          <div>{option.label}</div>
                          {actionInfo && <div className="text-xs text-text-muted">{actionInfo.description}</div>}
                        </div>
                      )
                    }}
                    options={ACTION_OPTIONS.map((a) => ({ value: a.value, label: a.label }))}
                  />
                </div>
                <div>
                  <Tooltip title="What happens when AI response contains flagged content">
                    <Text>When AI response is flagged</Text>
                  </Tooltip>
                  <Select
                    value={overrideDraft.output_action}
                    onChange={(value) =>
                      setOverrideDraft((prev) => ({ ...prev, output_action: value }))
                    }
                    style={{ width: "100%" }}
                    optionRender={(option) => {
                      const actionInfo = ACTION_OPTIONS.find((a) => a.value === option.value)
                      return (
                        <div>
                          <div>{option.label}</div>
                          {actionInfo && <div className="text-xs text-text-muted">{actionInfo.description}</div>}
                        </div>
                      )
                    }}
                    options={ACTION_OPTIONS.map((a) => ({ value: a.value, label: a.label }))}
                  />
                </div>
              </div>

              <div>
                <Tooltip title="Text shown instead of blocked content when using Redact action">
                  <Text>Replacement text for redacted content</Text>
                </Tooltip>
                <Input
                  placeholder="[REDACTED]"
                  value={overrideDraft.redact_replacement}
                  onChange={(event) =>
                    setOverrideDraft((prev) => ({
                      ...prev,
                      redact_replacement: event.target.value
                    }))
                  }
                />
              </div>

              <div>
                <Space>
                  <Text>Content categories to monitor</Text>
                  <Tooltip title="Limit which content categories are checked for this user">
                    <QuestionCircleOutlined className="text-text-muted" />
                  </Tooltip>
                </Space>
                <Select
                  mode="tags"
                  style={{ width: "100%" }}
                  placeholder="Leave empty to monitor all categories"
                  value={overrideDraft.categories_enabled as string[] | undefined}
                  onChange={(value) =>
                    setOverrideDraft((prev) => ({
                      ...prev,
                      categories_enabled: value as string[]
                    }))
                  }
                  options={CATEGORY_SUGGESTIONS}
                />
              </div>

              <Space>
                <Tooltip title="Keyboard shortcut: Ctrl+S (when user is loaded)">
                  <Button type="primary" onClick={handleSaveOverride} disabled={!activeUserId} aria-label="Save user override settings">
                    Save override
                  </Button>
                </Tooltip>
                <Tooltip title="Revert unsaved changes for this user">
                  <Button onClick={handleResetOverride} disabled={!overrideDirty}>
                    Reset changes
                  </Button>
                </Tooltip>
                <Button danger onClick={() => confirmDeleteOverride()} disabled={!overrideLoaded} aria-label="Delete user override settings">
                  Delete override
                </Button>
              </Space>
            </Space>
          )}
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card
          title={
            <Space>
              <span>Test Your Rules</span>
              <Tooltip title="Verify how your moderation rules will handle different content">
                <QuestionCircleOutlined className="text-text-muted" />
              </Tooltip>
            </Space>
          }
          className="shadow-sm"
        >
          <Space direction="vertical" size="middle" className="w-full">
            <div className="flex flex-wrap gap-2">
              <Tooltip title="Test user input (what they send) or AI output (what they receive)">
                <Segmented
                  value={testPhase}
                  onChange={(value) => setTestPhase(value as "input" | "output")}
                  options={[
                    { label: "User message", value: "input" },
                    { label: "AI response", value: "output" }
                  ]}
                />
              </Tooltip>
              <Input
                placeholder="User ID (optional)"
                value={testUserId}
                onChange={(event) => setTestUserId(event.target.value)}
                style={{ width: 220 }}
              />
            </div>
            <TextArea
              rows={5}
              placeholder="Enter sample text to test against moderation policy..."
              value={testText}
              onChange={(event) => setTestText(event.target.value)}
            />
            <Button type="primary" onClick={handleRunTest}>Run test</Button>
            {testResult && (
              <Alert
                type={testResult.flagged ? "warning" : "success"}
                showIcon
                icon={
                  testResult.action === "pass" ? <CheckCircleOutlined /> :
                  testResult.action === "block" ? <CloseCircleOutlined /> :
                  testResult.action === "redact" ? <ExclamationCircleOutlined /> :
                  <WarningOutlined />
                }
                message={
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Badge
                        status={
                          testResult.action === "pass" ? "success" :
                          testResult.action === "block" ? "error" : "warning"
                        }
                      />
                      <Text strong>
                        {testResult.action === "pass" ? "Content Allowed" :
                         testResult.action === "block" ? "Content Blocked" :
                         testResult.action === "redact" ? "Content Redacted" : "Warning Logged"}
                      </Text>
                    </div>
                    {testResult.category && (
                      <div>
                        <Text className="text-text-muted text-sm">Triggered by rule: </Text>
                        <Tag color="orange">{testResult.category}</Tag>
                      </div>
                    )}
                    {testResult.sample && (
                      <div>
                        <Text className="text-text-muted text-sm">Matched pattern: </Text>
                        <code className="bg-surface px-2 py-1 rounded text-sm">{testResult.sample}</code>
                      </div>
                    )}
                    {testResult.redacted_text && (
                      <div className="mt-2 p-2 bg-bg rounded border">
                        <Text className="text-text-muted text-xs block mb-1">Redacted output:</Text>
                        <Text code className="whitespace-pre-wrap">{testResult.redacted_text}</Text>
                      </div>
                    )}
                  </div>
                }
              />
            )}
          </Space>
        </Card>

        <Card
          title={
            <Space>
              <span>Current Policy Status</span>
              <Tooltip title="View the effective moderation policy for the current scope">
                <QuestionCircleOutlined className="text-text-muted" />
              </Tooltip>
            </Space>
          }
          className="shadow-sm"
        >
          <Space direction="vertical" size="middle" className="w-full">
            <div className="flex flex-wrap gap-2">
              <Tag color={policySnapshot.enabled ? "green" : "red"} icon={policySnapshot.enabled ? <CheckCircleOutlined /> : <CloseCircleOutlined />}>
                {policySnapshot.enabled ? "Enabled" : "Disabled"}
              </Tag>
              <Tag color={policySnapshot.input_enabled ? "blue" : "default"}>
                User messages: {policySnapshot.input_action || "pass"}
              </Tag>
              <Tag color={policySnapshot.output_enabled ? "purple" : "default"}>
                AI responses: {policySnapshot.output_action || "pass"}
              </Tag>
              <Tag color="gold">Blocklist rules: {blocklistCount}</Tag>
            </div>
            <div>
              <Text className="text-text-muted">Active Categories</Text>
              <div className="mt-1 flex flex-wrap gap-2">
                {policyCategories.length ? (
                  policyCategories.map((cat: string) => (
                    <Tag key={cat}>{cat}</Tag>
                  ))
                ) : (
                  <Text className="text-text-muted">All categories monitored</Text>
                )}
              </div>
            </div>
            {showAdvanced && (
              <details className="mt-2">
                <summary className="cursor-pointer text-text-muted text-sm hover:text-text">
                  View full policy JSON
                </summary>
                <TextArea className="mt-2" rows={10} value={formatJson(policySnapshot)} readOnly />
              </details>
            )}
          </Space>
        </Card>
      </div>

      {showAdvanced && (
        <>
          <Card
            title={
              <Space>
                <span>Blocklist Studio</span>
                <Tooltip title="Create and manage content filtering rules">
                  <QuestionCircleOutlined className="text-text-muted" />
                </Tooltip>
              </Space>
            }
            className="shadow-sm"
          >
            <Tabs
              items={[
                {
                  key: "managed",
                  label: (
                    <Tooltip title="Add and remove individual rules with version tracking">
                      <span>Managed Rules</span>
                    </Tooltip>
                  ),
                  children: (
                    <Space direction="vertical" size="middle" className="w-full">
                      <div className="flex flex-wrap items-center gap-2">
                        <Button onClick={handleLoadManaged} loading={managedLoading}>
                          Load managed list
                        </Button>
                        {managedVersion && (
                          <Tooltip title="Internal version identifier for conflict detection">
                            <Tag color="default">Version: {managedVersion.substring(0, 8)}...</Tag>
                          </Tooltip>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Input
                          placeholder="Add a blocklist rule (e.g., /pattern/i:block)"
                          value={managedLine}
                          onChange={(event) => setManagedLine(event.target.value)}
                          style={{ minWidth: 280, flex: 1 }}
                        />
                        <Tooltip title="Check rule syntax before adding">
                          <Button onClick={handleLintManagedLine}>Validate</Button>
                        </Tooltip>
                        <Button type="primary" onClick={handleAppendManaged}>
                          Add rule
                        </Button>
                      </div>
                      {managedLint && (
                        <Table
                          size="small"
                          rowKey={(record) => `${record.index}-${record.line}`}
                          columns={buildLintColumns(Boolean(managedLint?.invalid_count))}
                          dataSource={managedLint.items}
                          pagination={false}
                        />
                      )}
                      <Table
                        size="small"
                        rowKey={(record) => record.id}
                        columns={[
                          { title: "#", dataIndex: "id", key: "id", width: 60 },
                          { title: "Rule", dataIndex: "line", key: "line" },
                          {
                            title: "Actions",
                            key: "actions",
                            width: 120,
                            render: (_value, record) => (
                              <Button
                                danger
                                size="small"
                                onClick={() => confirmDeleteManagedItem(record.id, record.line)}
                                aria-label={`Delete rule: ${record.line.substring(0, 30)}${record.line.length > 30 ? "..." : ""}`}
                              >
                                Delete
                              </Button>
                            )
                          }
                        ]}
                        dataSource={managedItems}
                        pagination={{ pageSize: 8 }}
                        locale={{
                          emptyText: (
                            <div className="py-4 text-center text-text-muted">
                              No rules loaded. Click "Load managed list" to view existing rules.
                            </div>
                          )
                        }}
                      />
                    </Space>
                  )
                },
                {
                  key: "raw",
                  label: (
                    <Tooltip title="Edit the entire blocklist file directly">
                      <span>Raw File Editor</span>
                    </Tooltip>
                  ),
                  children: (
                    <Space direction="vertical" size="middle" className="w-full">
                      <Alert
                        type="warning"
                        showIcon
                        icon={<WarningOutlined />}
                        message="Raw file editing replaces all existing rules. Use with caution."
                        className="!py-2"
                      />
                      <div className="flex flex-wrap gap-2">
                        <Button onClick={handleLoadBlocklist} loading={blocklistLoading}>
                          Load blocklist
                        </Button>
                        <Button onClick={handleLintBlocklist} loading={blocklistLoading}>
                          Validate all
                        </Button>
                        <Button type="primary" onClick={handleSaveBlocklist} loading={blocklistLoading}>
                          Save / Replace
                        </Button>
                      </div>
                      <TextArea
                        rows={10}
                        value={blocklistText}
                        onChange={(event) => setBlocklistText(event.target.value)}
                        placeholder="One rule per line. Examples:&#10;badword:block&#10;/regex pattern/i:redact&#10;# Comment line"
                      />
                      {blocklistLint && (
                        <Table
                          size="small"
                          rowKey={(record) => `${record.index}-${record.line}`}
                          columns={buildLintColumns(Boolean(blocklistLint?.invalid_count))}
                          dataSource={blocklistLint.items}
                          pagination={{ pageSize: 6 }}
                        />
                      )}
                    </Space>
                  )
                }
              ]}
            />
          </Card>

          <Card
            title={
              <Space>
                <span>Per-user Overrides</span>
                <Tooltip title="View and manage all user-specific moderation settings">
                  <QuestionCircleOutlined className="text-text-muted" />
                </Tooltip>
              </Space>
            }
            className="shadow-sm"
          >
            <Space direction="vertical" size="middle" className="w-full">
              <Space wrap align="center">
                <Input
                  placeholder="Search by user ID..."
                  prefix={<SearchOutlined className="text-text-muted" />}
                  value={overrideSearchFilter}
                  onChange={(e) => setOverrideSearchFilter(e.target.value)}
                  style={{ maxWidth: 300 }}
                  allowClear
                />
                <Tooltip title="Delete selected overrides">
                  <Button
                    danger
                    disabled={!selectedOverrideIds.length}
                    onClick={confirmBulkDeleteOverrides}
                    aria-label="Delete selected user overrides"
                  >
                    Delete selected
                  </Button>
                </Tooltip>
                <Button
                  disabled={!selectedOverrideIds.length}
                  onClick={() => setSelectedOverrideIds([])}
                >
                  Clear selection
                </Button>
              </Space>
              {overridesQuery.isFetching ? (
                <Skeleton active paragraph={{ rows: 4 }} />
              ) : (
                <Table
                  size="small"
                  rowKey={(record) => record.user_id}
                  columns={overrideColumns}
                  dataSource={overridesData}
                  rowSelection={overrideRowSelection}
                  pagination={{ pageSize: 6 }}
                  locale={{
                    emptyText: (
                      <div className="py-8 text-center">
                        <Text className="text-text-muted">
                          {overrideSearchFilter
                            ? `No users found matching "${overrideSearchFilter}"`
                            : "No user overrides configured yet."}
                        </Text>
                        {!overrideSearchFilter && (
                          <div className="mt-2">
                            <Button
                              type="link"
                              onClick={() => {
                                setScope("user")
                                // Focus on user ID input after state update
                                setTimeout(() => userIdInputRef.current?.focus(), 0)
                              }}
                            >
                              Configure your first user
                            </Button>
                          </div>
                        )}
                      </div>
                    )
                  }}
                />
              )}
            </Space>
          </Card>
        </>
      )}
    </div>
  )
}
