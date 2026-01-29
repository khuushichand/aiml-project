import React from "react"
import { Button, Drawer, Form, Input, Select, Collapse, Tooltip, Space, Tag } from "antd"
import { useTranslation } from "react-i18next"
import { ChevronDown, ChevronUp, Info, Cloud, HardDrive, Link2, Unlink } from "lucide-react"
import type { PromptSyncStatus, PromptSourceSystem } from "@/db/dexie/types"

interface PromptDrawerProps {
  open: boolean
  onClose: () => void
  mode: "create" | "edit"
  initialValues?: {
    name?: string
    author?: string
    details?: string
    system_prompt?: string
    user_prompt?: string
    keywords?: string[]
    // Sync fields
    serverId?: number | null
    syncStatus?: PromptSyncStatus
    sourceSystem?: PromptSourceSystem
    studioProjectId?: number | null
    lastSyncedAt?: number | null
    // Advanced fields
    fewShotExamples?: Array<{ input: string; output: string }> | null
    modulesConfig?: Array<{ name: string; enabled: boolean }> | null
    changeDescription?: string | null
    versionNumber?: number | null
  }
  onSubmit: (values: any) => void
  isLoading: boolean
  allTags: string[]
}

export const PromptDrawer: React.FC<PromptDrawerProps> = ({
  open,
  onClose,
  mode,
  initialValues,
  onSubmit,
  isLoading,
  allTags
}) => {
  const { t } = useTranslation(["settings", "common"])
  const [form] = Form.useForm()
  const [showSystemHelp, setShowSystemHelp] = React.useState(false)
  const [showUserHelp, setShowUserHelp] = React.useState(false)

  // Check if prompt is synced
  const isSynced = initialValues?.serverId != null
  const syncStatus = initialValues?.syncStatus || "local"

  React.useEffect(() => {
    if (open && initialValues) {
      form.setFieldsValue(initialValues)
    }
    if (open && mode === "create") {
      form.resetFields()
    }
  }, [open, initialValues, mode, form])

  const handleFinish = (values: any) => {
    onSubmit(values)
  }

  const title =
    mode === "create"
      ? t("managePrompts.modal.addTitle")
      : t("managePrompts.modal.editTitle")

  const formatLastSync = (timestamp: number | null | undefined) => {
    if (!timestamp) return null
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / (1000 * 60))
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffMins < 1) return t("common:justNow", "Just now")
    if (diffMins < 60) return t("common:minutesAgo", "{{count}}m ago", { count: diffMins })
    if (diffHours < 24) return t("common:hoursAgo", "{{count}}h ago", { count: diffHours })
    return t("common:daysAgo", "{{count}}d ago", { count: diffDays })
  }

  // Build collapsible items for advanced sections
  const collapseItems = []

  // Advanced section (for synced prompts or if data exists)
  if (mode === "edit" && (isSynced || initialValues?.fewShotExamples?.length)) {
    collapseItems.push({
      key: "advanced",
      label: (
        <span className="font-medium">
          {t("managePrompts.drawer.sectionAdvanced", { defaultValue: "Advanced" })}
        </span>
      ),
      children: (
        <div className="space-y-4">
          <Form.Item
            name="changeDescription"
            label={t("managePrompts.form.changeDescription.label", {
              defaultValue: "Change description"
            })}
            help={t("managePrompts.form.changeDescription.help", {
              defaultValue: "Describe what changed in this version (for version history)."
            })}
          >
            <Input
              placeholder={t("managePrompts.form.changeDescription.placeholder", {
                defaultValue: "e.g., Added clearer instructions for code formatting"
              })}
              data-testid="prompt-drawer-change-desc"
            />
          </Form.Item>

          {initialValues?.fewShotExamples && initialValues.fewShotExamples.length > 0 && (
            <div className="p-3 bg-surface2 rounded-md">
              <div className="text-xs font-medium text-text-muted mb-2">
                {t("managePrompts.drawer.fewShotExamples", {
                  defaultValue: "Few-shot examples"
                })}
              </div>
              <p className="text-xs text-text-muted">
                {t("managePrompts.drawer.fewShotExamplesCount", {
                  defaultValue: "{{count}} examples configured",
                  count: initialValues.fewShotExamples.length
                })}
              </p>
              <p className="text-xs text-text-muted mt-1">
                {t("managePrompts.drawer.fewShotExamplesHint", {
                  defaultValue: "Edit examples in Prompt Studio for advanced configuration."
                })}
              </p>
            </div>
          )}

          {initialValues?.versionNumber && (
            <div className="flex items-center gap-2 text-xs text-text-muted">
              <span>
                {t("managePrompts.drawer.versionNumber", {
                  defaultValue: "Version {{version}}",
                  version: initialValues.versionNumber
                })}
              </span>
            </div>
          )}
        </div>
      )
    })
  }

  // Sync section (only in edit mode when synced)
  if (mode === "edit" && isSynced) {
    collapseItems.push({
      key: "sync",
      label: (
        <span className="font-medium flex items-center gap-2">
          {t("managePrompts.drawer.sectionSync", { defaultValue: "Sync Status" })}
          <Tag color={syncStatus === "synced" ? "green" : syncStatus === "pending" ? "gold" : "default"} className="text-xs">
            {syncStatus === "synced" ? t("settings:managePrompts.sync.synced", "Synced") :
             syncStatus === "pending" ? t("settings:managePrompts.sync.pending", "Pending") :
             t("settings:managePrompts.sync.local", "Local")}
          </Tag>
        </span>
      ),
      children: (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Cloud className="size-4 text-primary" />
            <span className="text-sm">
              {t("managePrompts.drawer.linkedToServer", {
                defaultValue: "Linked to Prompt Studio"
              })}
            </span>
          </div>

          {initialValues?.studioProjectId && (
            <div className="text-xs text-text-muted">
              {t("managePrompts.drawer.projectId", {
                defaultValue: "Project ID: {{id}}",
                id: initialValues.studioProjectId
              })}
            </div>
          )}

          {initialValues?.serverId && (
            <div className="text-xs text-text-muted">
              {t("managePrompts.drawer.serverId", {
                defaultValue: "Server ID: {{id}}",
                id: initialValues.serverId
              })}
            </div>
          )}

          {initialValues?.lastSyncedAt && (
            <div className="text-xs text-text-muted">
              {t("managePrompts.drawer.lastSynced", {
                defaultValue: "Last synced: {{time}}",
                time: formatLastSync(initialValues.lastSyncedAt)
              })}
            </div>
          )}
        </div>
      )
    })
  }

  return (
    <Drawer
      placement="right"
      width={480}
      open={open}
      onClose={onClose}
      title={title}
      footer={
        <div className="flex justify-end gap-2">
          <Button onClick={onClose}>
            {t("common:cancel", { defaultValue: "Cancel" })}
          </Button>
          <Button
            type="primary"
            loading={isLoading}
            onClick={() => form.submit()}
          >
            {isLoading
              ? t("managePrompts.form.btnSave.saving")
              : t("managePrompts.form.btnSave.save")}
          </Button>
        </div>
      }
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={handleFinish}
        initialValues={{ keywords: [] }}
      >
        {/* Section: Identity */}
        <div className="mb-6">
          <h3 className="text-sm font-medium text-text-muted mb-3 flex items-center gap-2">
            {t("managePrompts.drawer.sectionIdentity", { defaultValue: "Identity" })}
            {isSynced && (
              <Tooltip title={t("managePrompts.drawer.syncedIndicator", { defaultValue: "Synced with Prompt Studio" })}>
                <Cloud className="size-3 text-primary" />
              </Tooltip>
            )}
          </h3>
          <div className="space-y-4">
            <Form.Item
              name="name"
              label={t("managePrompts.form.title.label")}
              rules={[
                {
                  required: true,
                  message: t("managePrompts.form.title.required")
                }
              ]}
            >
              <Input
                placeholder={t("managePrompts.form.title.placeholder")}
                data-testid="prompt-drawer-name"
              />
            </Form.Item>

            <Form.Item
              name="author"
              label={t("managePrompts.form.author.label", { defaultValue: "Author" })}
            >
              <Input
                placeholder={t("managePrompts.form.author.placeholder", {
                  defaultValue: "Optional author"
                })}
                data-testid="prompt-drawer-author"
              />
            </Form.Item>
          </div>
        </div>

        {/* Section: Prompt Content */}
        <div className="mb-6">
          <h3 className="text-sm font-medium text-text-muted mb-3">
            {t("managePrompts.drawer.sectionContent", { defaultValue: "Prompt Content" })}
          </h3>
          <div className="space-y-4">
            <Form.Item
              name="system_prompt"
              label={
                <span className="flex items-center gap-1">
                  {t("managePrompts.form.systemPrompt.labelImproved", {
                    defaultValue: "AI Instructions"
                  })}
                  <Tooltip title={t("managePrompts.form.systemPrompt.tooltip", {
                    defaultValue: "Also known as 'System prompt'. Sets how the AI should behave."
                  })}>
                    <Info className="size-3 text-text-muted cursor-help" />
                  </Tooltip>
                </span>
              }
              help={
                <span>
                  {t("managePrompts.form.systemPrompt.help", {
                    defaultValue: "Sets the AI's behavior and persona. Sent as the system message."
                  })}
                  <button
                    type="button"
                    className="ml-1 text-primary hover:underline text-xs"
                    onClick={() => setShowSystemHelp(!showSystemHelp)}
                  >
                    {showSystemHelp
                      ? t("common:showLess", { defaultValue: "Show less" })
                      : t("common:learnMore", { defaultValue: "Learn more" })}
                  </button>
                </span>
              }
            >
              <Input.TextArea
                placeholder={t("managePrompts.form.systemPrompt.placeholder", {
                  defaultValue: "Optional system prompt sent as the system message"
                })}
                autoSize={{ minRows: 3, maxRows: 10 }}
                data-testid="prompt-drawer-system"
              />
            </Form.Item>

            {/* Expandable help for system prompt */}
            {showSystemHelp && (
              <div className="bg-surface2 p-3 rounded-md text-xs text-text-muted -mt-2 mb-2">
                <p className="font-medium mb-2">
                  {t("managePrompts.form.systemPrompt.helpTitle", {
                    defaultValue: "What are AI Instructions?"
                  })}
                </p>
                <p className="mb-2">
                  {t("managePrompts.form.systemPrompt.helpDesc", {
                    defaultValue: "AI Instructions (system prompts) define how the AI should behave throughout the conversation. They're sent before any user messages and set the context, tone, and capabilities."
                  })}
                </p>
                <p className="font-medium mb-1">
                  {t("managePrompts.form.systemPrompt.helpExampleTitle", {
                    defaultValue: "Example:"
                  })}
                </p>
                <pre className="bg-surface p-2 rounded text-xs overflow-x-auto">
                  {`You are a helpful code review assistant.\nFocus on:\n- Code quality and best practices\n- Performance implications\n- Security concerns`}
                </pre>
              </div>
            )}

            <Form.Item
              name="user_prompt"
              label={
                <span className="flex items-center gap-1">
                  {t("managePrompts.form.userPrompt.labelImproved", {
                    defaultValue: "Message Template"
                  })}
                  <Tooltip title={t("managePrompts.form.userPrompt.tooltip", {
                    defaultValue: "Also known as 'User prompt'. A template you can quickly insert."
                  })}>
                    <Info className="size-3 text-text-muted cursor-help" />
                  </Tooltip>
                </span>
              }
              help={
                <span>
                  {t("managePrompts.form.userPrompt.help", {
                    defaultValue: "Template inserted as the user message when using this prompt."
                  })}
                  <button
                    type="button"
                    className="ml-1 text-primary hover:underline text-xs"
                    onClick={() => setShowUserHelp(!showUserHelp)}
                  >
                    {showUserHelp
                      ? t("common:showLess", { defaultValue: "Show less" })
                      : t("common:learnMore", { defaultValue: "Learn more" })}
                  </button>
                </span>
              }
            >
              <Input.TextArea
                placeholder={t("managePrompts.form.userPrompt.placeholder", {
                  defaultValue: "Optional user prompt template"
                })}
                autoSize={{ minRows: 3, maxRows: 10 }}
                data-testid="prompt-drawer-user"
              />
            </Form.Item>

            {/* Expandable help for user prompt */}
            {showUserHelp && (
              <div className="bg-surface2 p-3 rounded-md text-xs text-text-muted -mt-2 mb-2">
                <p className="font-medium mb-2">
                  {t("managePrompts.form.userPrompt.helpTitle", {
                    defaultValue: "What are Message Templates?"
                  })}
                </p>
                <p className="mb-2">
                  {t("managePrompts.form.userPrompt.helpDesc", {
                    defaultValue: "Message templates are pre-written text you can quickly insert into your chat input. They save time on repetitive requests and ensure consistent phrasing."
                  })}
                </p>
                <p className="font-medium mb-1">
                  {t("managePrompts.form.userPrompt.helpExampleTitle", {
                    defaultValue: "Example:"
                  })}
                </p>
                <pre className="bg-surface p-2 rounded text-xs overflow-x-auto">
                  {`Please review the following code and provide:\n1. A brief summary\n2. Potential issues\n3. Suggestions for improvement\n\nCode:\n{paste your code here}`}
                </pre>
              </div>
            )}
          </div>
        </div>

        {/* Section: Organization */}
        <div className="mb-6">
          <h3 className="text-sm font-medium text-text-muted mb-3">
            {t("managePrompts.drawer.sectionOrganization", { defaultValue: "Organization" })}
          </h3>
          <div className="space-y-4">
            <Form.Item
              name="keywords"
              label={t("managePrompts.tags.label", { defaultValue: "Keywords" })}
            >
              <Select
                mode="tags"
                allowClear
                placeholder={t("managePrompts.tags.placeholder", {
                  defaultValue: "Add keywords"
                })}
                options={allTags.map((tag) => ({ label: tag, value: tag }))}
                data-testid="prompt-drawer-keywords"
              />
            </Form.Item>

            <Form.Item
              name="details"
              label={t("managePrompts.form.details.label", {
                defaultValue: "Notes"
              })}
            >
              <Input.TextArea
                placeholder={t("managePrompts.form.details.placeholder", {
                  defaultValue: "Add context or usage notes"
                })}
                autoSize={{ minRows: 2, maxRows: 6 }}
                data-testid="prompt-drawer-details"
              />
            </Form.Item>
          </div>
        </div>

        {/* Collapsible Advanced/Sync Sections */}
        {collapseItems.length > 0 && (
          <Collapse
            items={collapseItems}
            bordered={false}
            className="bg-transparent"
            expandIconPosition="end"
          />
        )}
      </Form>
    </Drawer>
  )
}
