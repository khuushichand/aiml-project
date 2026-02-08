import React, { useEffect, useState } from "react"
import { Button, Collapse, Form, Input, InputNumber, Modal, Select, Switch, message } from "antd"
import { useTranslation } from "react-i18next"
import {
  createWatchlistJob,
  fetchWatchlistTemplates,
  updateWatchlistJob
} from "@/services/watchlists"
import type {
  JobOutputPrefs,
  JobScope,
  WatchlistFilter,
  WatchlistJob,
  WatchlistJobCreate
} from "@/types/watchlists"
import { ScopeSelector } from "./ScopeSelector"
import { FilterBuilder } from "./FilterBuilder"
import { SchedulePicker } from "./SchedulePicker"

interface JobFormModalProps {
  open: boolean
  onClose: () => void
  onSuccess: () => void
  initialValues?: WatchlistJob
}

interface FormValues {
  name: string
  description: string
  active: boolean
}

type EmailBodyFormat = "auto" | "text" | "html"
type OutputFormat = "md" | "html"
type OutputPresetId = "briefing_md" | "newsletter_html" | "mece_md"

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

const cloneRecord = (value: Record<string, unknown>): Record<string, unknown> => {
  try {
    return JSON.parse(JSON.stringify(value)) as Record<string, unknown>
  } catch {
    return { ...value }
  }
}

const isEmailBodyFormat = (value: unknown): value is EmailBodyFormat =>
  value === "auto" || value === "text" || value === "html"

const isOutputFormat = (value: unknown): value is OutputFormat =>
  value === "md" || value === "html"

const OUTPUT_PRESETS: Record<
  OutputPresetId,
  {
    templateName: string
    format: OutputFormat
    emailEnabled: boolean
    emailBodyFormat: EmailBodyFormat
  }
> = {
  briefing_md: {
    templateName: "briefing_markdown",
    format: "md",
    emailEnabled: false,
    emailBodyFormat: "auto",
  },
  newsletter_html: {
    templateName: "newsletter_html",
    format: "html",
    emailEnabled: true,
    emailBodyFormat: "html",
  },
  mece_md: {
    templateName: "mece_markdown",
    format: "md",
    emailEnabled: false,
    emailBodyFormat: "auto",
  },
}

export const JobFormModal: React.FC<JobFormModalProps> = ({
  open,
  onClose,
  onSuccess,
  initialValues
}) => {
  const { t } = useTranslation(["watchlists", "common"])
  const [form] = Form.useForm<FormValues>()
  const [submitting, setSubmitting] = useState(false)

  const isEditing = !!initialValues

  // Managed state for complex fields
  const [scope, setScope] = useState<JobScope>({})
  const [filters, setFilters] = useState<WatchlistFilter[]>([])
  const [schedule, setSchedule] = useState<string | null>(null)
  const [timezone, setTimezone] = useState("UTC")
  const [templateOptions, setTemplateOptions] = useState<Array<{ label: string; value: string }>>([])
  const [outputPreset, setOutputPreset] = useState<OutputPresetId | undefined>(undefined)
  const [outputTemplateName, setOutputTemplateName] = useState<string | undefined>(undefined)
  const [outputTemplateVersion, setOutputTemplateVersion] = useState<number | null>(null)
  const [outputTemplateFormat, setOutputTemplateFormat] = useState<OutputFormat | undefined>(undefined)
  const [retentionDefaultSeconds, setRetentionDefaultSeconds] = useState<number | null>(null)
  const [retentionTemporarySeconds, setRetentionTemporarySeconds] = useState<number | null>(null)
  const [deliveryEmailEnabled, setDeliveryEmailEnabled] = useState(false)
  const [deliveryEmailRecipients, setDeliveryEmailRecipients] = useState<string[]>([])
  const [deliveryEmailSubject, setDeliveryEmailSubject] = useState("")
  const [deliveryEmailAttachFile, setDeliveryEmailAttachFile] = useState(true)
  const [deliveryEmailBodyFormat, setDeliveryEmailBodyFormat] = useState<EmailBodyFormat>("auto")
  const [deliveryChatbookEnabled, setDeliveryChatbookEnabled] = useState(false)
  const [deliveryChatbookTitle, setDeliveryChatbookTitle] = useState("")
  const [deliveryChatbookDescription, setDeliveryChatbookDescription] = useState("")
  const [deliveryChatbookConversationId, setDeliveryChatbookConversationId] = useState<number | null>(null)

  const applyOutputPrefsState = (prefs: JobOutputPrefs | null | undefined) => {
    const prefsRecord = isRecord(prefs) ? prefs : {}
    const templateRecord = isRecord(prefsRecord.template) ? prefsRecord.template : {}
    const retentionRecord = isRecord(prefsRecord.retention) ? prefsRecord.retention : {}
    const deliveriesRecord = isRecord(prefsRecord.deliveries) ? prefsRecord.deliveries : {}
    const emailRecord = isRecord(deliveriesRecord.email) ? deliveriesRecord.email : null
    const chatbookRecord = isRecord(deliveriesRecord.chatbook) ? deliveriesRecord.chatbook : null

    setOutputTemplateName(
      typeof templateRecord.default_name === "string" && templateRecord.default_name.trim().length > 0
        ? templateRecord.default_name
        : undefined
    )

    const parsedTemplateVersion = Number(templateRecord.default_version)
    setOutputTemplateVersion(
      Number.isFinite(parsedTemplateVersion) && parsedTemplateVersion > 0
        ? Math.floor(parsedTemplateVersion)
        : null
    )
    setOutputTemplateFormat(
      isOutputFormat(templateRecord.default_format) ? templateRecord.default_format : undefined
    )
    const parsedDefaultRetention = Number(retentionRecord.default_seconds)
    setRetentionDefaultSeconds(
      Number.isFinite(parsedDefaultRetention) && parsedDefaultRetention >= 0
        ? Math.floor(parsedDefaultRetention)
        : null
    )
    const parsedTemporaryRetention = Number(retentionRecord.temporary_seconds)
    setRetentionTemporarySeconds(
      Number.isFinite(parsedTemporaryRetention) && parsedTemporaryRetention >= 0
        ? Math.floor(parsedTemporaryRetention)
        : null
    )

    setDeliveryEmailEnabled(Boolean(emailRecord) && emailRecord.enabled !== false)
    setDeliveryEmailRecipients(
      Array.isArray(emailRecord?.recipients)
        ? emailRecord.recipients
          .filter((entry): entry is string => typeof entry === "string")
          .map((entry) => entry.trim())
          .filter((entry) => entry.length > 0)
        : []
    )
    setDeliveryEmailSubject(
      typeof emailRecord?.subject === "string" ? emailRecord.subject : ""
    )
    setDeliveryEmailAttachFile(
      emailRecord?.attach_file === undefined ? true : Boolean(emailRecord.attach_file)
    )
    setDeliveryEmailBodyFormat(
      isEmailBodyFormat(emailRecord?.body_format) ? emailRecord.body_format : "auto"
    )

    setDeliveryChatbookEnabled(Boolean(chatbookRecord) && chatbookRecord.enabled !== false)
    setDeliveryChatbookTitle(
      typeof chatbookRecord?.title === "string" ? chatbookRecord.title : ""
    )
    setDeliveryChatbookDescription(
      typeof chatbookRecord?.description === "string" ? chatbookRecord.description : ""
    )
    const parsedConversationId = Number(chatbookRecord?.conversation_id)
    setDeliveryChatbookConversationId(
      Number.isFinite(parsedConversationId) && parsedConversationId > 0
        ? Math.floor(parsedConversationId)
        : null
    )
  }

  const buildOutputPrefs = (): JobOutputPrefs | undefined => {
    const basePrefs = (
      isEditing &&
      initialValues?.output_prefs &&
      isRecord(initialValues.output_prefs)
    )
      ? cloneRecord(initialValues.output_prefs)
      : {}

    const templatePrefs = isRecord(basePrefs.template) ? { ...basePrefs.template } : {}
    const normalizedTemplateName = outputTemplateName?.trim() || ""
    if (normalizedTemplateName) {
      templatePrefs.default_name = normalizedTemplateName
    } else {
      delete templatePrefs.default_name
    }
    if (typeof outputTemplateVersion === "number" && outputTemplateVersion > 0) {
      templatePrefs.default_version = Math.floor(outputTemplateVersion)
    } else {
      delete templatePrefs.default_version
    }
    if (isOutputFormat(outputTemplateFormat)) {
      templatePrefs.default_format = outputTemplateFormat
    } else {
      delete templatePrefs.default_format
    }
    if (Object.keys(templatePrefs).length > 0) {
      basePrefs.template = templatePrefs
    } else {
      delete basePrefs.template
    }

    const retentionPrefs = isRecord(basePrefs.retention) ? { ...basePrefs.retention } : {}
    if (typeof retentionDefaultSeconds === "number" && retentionDefaultSeconds >= 0) {
      retentionPrefs.default_seconds = Math.floor(retentionDefaultSeconds)
    } else {
      delete retentionPrefs.default_seconds
    }
    if (typeof retentionTemporarySeconds === "number" && retentionTemporarySeconds >= 0) {
      retentionPrefs.temporary_seconds = Math.floor(retentionTemporarySeconds)
    } else {
      delete retentionPrefs.temporary_seconds
    }
    if (Object.keys(retentionPrefs).length > 0) {
      basePrefs.retention = retentionPrefs
    } else {
      delete basePrefs.retention
    }

    const deliveriesPrefs = isRecord(basePrefs.deliveries) ? { ...basePrefs.deliveries } : {}

    const normalizedEmailSubject = deliveryEmailSubject.trim()
    const shouldPersistEmail = (
      deliveryEmailEnabled ||
      deliveryEmailRecipients.length > 0 ||
      normalizedEmailSubject.length > 0
    )
    if (shouldPersistEmail) {
      const emailPrefs = isRecord(deliveriesPrefs.email) ? { ...deliveriesPrefs.email } : {}
      emailPrefs.enabled = deliveryEmailEnabled
      if (deliveryEmailRecipients.length > 0) {
        emailPrefs.recipients = deliveryEmailRecipients
      } else {
        delete emailPrefs.recipients
      }
      emailPrefs.attach_file = deliveryEmailAttachFile
      emailPrefs.body_format = deliveryEmailBodyFormat
      if (normalizedEmailSubject.length > 0) {
        emailPrefs.subject = normalizedEmailSubject
      } else {
        delete emailPrefs.subject
      }
      deliveriesPrefs.email = emailPrefs
    } else {
      delete deliveriesPrefs.email
    }

    const shouldPersistChatbook = (
      deliveryChatbookEnabled ||
      deliveryChatbookTitle.trim().length > 0 ||
      deliveryChatbookDescription.trim().length > 0 ||
      deliveryChatbookConversationId !== null
    )
    if (shouldPersistChatbook) {
      const chatbookPrefs = isRecord(deliveriesPrefs.chatbook) ? { ...deliveriesPrefs.chatbook } : {}
      chatbookPrefs.enabled = deliveryChatbookEnabled
      if (deliveryChatbookTitle.trim().length > 0) {
        chatbookPrefs.title = deliveryChatbookTitle.trim()
      } else {
        delete chatbookPrefs.title
      }
      if (deliveryChatbookDescription.trim().length > 0) {
        chatbookPrefs.description = deliveryChatbookDescription.trim()
      } else {
        delete chatbookPrefs.description
      }
      if (typeof deliveryChatbookConversationId === "number" && deliveryChatbookConversationId > 0) {
        chatbookPrefs.conversation_id = Math.floor(deliveryChatbookConversationId)
      } else {
        delete chatbookPrefs.conversation_id
      }
      deliveriesPrefs.chatbook = chatbookPrefs
    } else {
      delete deliveriesPrefs.chatbook
    }

    if (Object.keys(deliveriesPrefs).length > 0) {
      basePrefs.deliveries = deliveriesPrefs
    } else {
      delete basePrefs.deliveries
    }

    if (Object.keys(basePrefs).length > 0) {
      return basePrefs as JobOutputPrefs
    }
    if (isEditing) {
      return {}
    }
    return undefined
  }

  const applyPreset = (presetId: OutputPresetId | undefined) => {
    if (!presetId) return
    const preset = OUTPUT_PRESETS[presetId]
    if (!preset) return
    setOutputTemplateName(preset.templateName)
    setOutputTemplateVersion(null)
    setOutputTemplateFormat(preset.format)
    setDeliveryEmailEnabled(preset.emailEnabled)
    setDeliveryEmailBodyFormat(preset.emailBodyFormat)
    setOutputPreset(presetId)
    message.success(t("watchlists:jobs.form.presetApplied", "Preset applied"))
  }

  // Reset form when modal opens/closes or initialValues change
  useEffect(() => {
    if (open) {
      if (initialValues) {
        form.setFieldsValue({
          name: initialValues.name,
          description: initialValues.description || "",
          active: initialValues.active
        })
        setScope(initialValues.scope || {})
        setFilters(initialValues.job_filters?.filters || [])
        setSchedule(initialValues.schedule_expr || null)
        setTimezone(initialValues.timezone || "UTC")
        setOutputPreset(undefined)
        applyOutputPrefsState(initialValues.output_prefs)
      } else {
        form.resetFields()
        form.setFieldsValue({
          name: "",
          description: "",
          active: true
        })
        setScope({})
        setFilters([])
        setSchedule(null)
        setTimezone("UTC")
        setOutputPreset(undefined)
        applyOutputPrefsState(null)
      }
    }
  }, [open, initialValues, form])

  useEffect(() => {
    if (!open) return
    let cancelled = false
    fetchWatchlistTemplates()
      .then((result) => {
        if (cancelled) return
        const items = Array.isArray(result.items) ? result.items : []
        setTemplateOptions(
          items.map((item) => ({
            label: item.name,
            value: item.name
          }))
        )
      })
      .catch((err) => {
        console.error("Failed to load watchlist templates for job form:", err)
        if (!cancelled) {
          setTemplateOptions([])
        }
      })
    return () => {
      cancelled = true
    }
  }, [open])

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()

      // Validate scope
      const hasScope =
        (scope.sources?.length ?? 0) > 0 ||
        (scope.groups?.length ?? 0) > 0 ||
        (scope.tags?.length ?? 0) > 0

      if (!hasScope) {
        message.error(t("watchlists:jobs.form.scopeRequired", "Please select at least one source, group, or tag"))
        return
      }

      setSubmitting(true)

      const outputPrefs = buildOutputPrefs()

      const jobData: WatchlistJobCreate = {
        name: values.name,
        description: values.description || undefined,
        active: values.active,
        scope,
        schedule_expr: schedule || undefined,
        timezone: timezone || undefined,
        output_prefs: isEditing ? (outputPrefs || {}) : outputPrefs,
        job_filters: filters.length > 0 ? { filters } : undefined
      }

      if (isEditing && initialValues) {
        await updateWatchlistJob(initialValues.id, jobData)
        message.success(t("watchlists:jobs.updated", "Job updated"))
      } else {
        await createWatchlistJob(jobData)
        message.success(t("watchlists:jobs.created", "Job created"))
      }

      onSuccess()
    } catch (err) {
      console.error("Form submit error:", err)
      if (err && typeof err === "object" && "errorFields" in err) {
        // Validation error - handled by form
        return
      }
      message.error(t("watchlists:jobs.saveError", "Failed to save job"))
    } finally {
      setSubmitting(false)
    }
  }

  const handleCancel = () => {
    form.resetFields()
    onClose()
  }

  const collapseItems = [
    {
      key: "scope",
      label: (
        <span className="font-medium">
          {t("watchlists:jobs.form.scope", "Scope")}
          <span className="text-red-500 ml-1">*</span>
        </span>
      ),
      children: <ScopeSelector value={scope} onChange={setScope} />,
      forceRender: true
    },
    {
      key: "schedule",
      label: (
        <span className="font-medium">
          {t("watchlists:jobs.form.schedule", "Schedule")}
        </span>
      ),
      children: (
        <SchedulePicker
          value={schedule}
          onChange={setSchedule}
          timezone={timezone}
          onTimezoneChange={setTimezone}
        />
      )
    },
    {
      key: "filters",
      label: (
        <span className="font-medium">
          {t("watchlists:jobs.form.filters", "Filters")}
          {filters.length > 0 && (
            <span className="ml-2 text-zinc-500">({filters.length})</span>
          )}
        </span>
      ),
      children: <FilterBuilder value={filters} onChange={setFilters} />
    },
    {
      key: "output_prefs",
      label: (
        <span className="font-medium">
          {t("watchlists:jobs.form.outputPrefs", "Output & Delivery")}
        </span>
      ),
      children: (
        <div className="space-y-4">
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
            <div className="mb-3 text-sm font-medium">
              {t("watchlists:jobs.form.guidedPresets", "Guided presets")}
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_auto]">
              <Select
                value={outputPreset}
                onChange={(value) => setOutputPreset(value as OutputPresetId)}
                options={[
                  {
                    value: "briefing_md",
                    label: t("watchlists:jobs.form.presetBriefingMd", "Daily briefing (Markdown)"),
                  },
                  {
                    value: "newsletter_html",
                    label: t("watchlists:jobs.form.presetNewsletterHtml", "Newsletter (HTML + email)"),
                  },
                  {
                    value: "mece_md",
                    label: t("watchlists:jobs.form.presetMeceMd", "MECE review (Markdown)"),
                  },
                ]}
                placeholder={t("watchlists:jobs.form.presetPlaceholder", "Choose a preset")}
              />
              <Button
                onClick={() => applyPreset(outputPreset)}
                disabled={!outputPreset}
              >
                {t("watchlists:jobs.form.applyPreset", "Apply preset")}
              </Button>
            </div>
            <div className="mt-2 text-xs text-zinc-500">
              {t(
                "watchlists:jobs.form.presetHint",
                "Presets prefill template/delivery defaults. You can still customize fields below."
              )}
            </div>
          </div>

          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
            <div className="mb-3 text-sm font-medium">
              {t("watchlists:jobs.form.defaultTemplate", "Default template")}
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <div>
                <div className="mb-1 text-xs text-zinc-500">
                  {t("watchlists:jobs.form.defaultTemplateName", "Template name")}
                </div>
                <Select
                  allowClear
                  showSearch
                  value={outputTemplateName}
                  options={templateOptions}
                  optionFilterProp="label"
                  placeholder={t("watchlists:jobs.form.defaultTemplatePlaceholder", "Select a template")}
                  onChange={(value) => {
                    setOutputTemplateName(value)
                    if (!value) {
                      setOutputTemplateVersion(null)
                    }
                  }}
                />
              </div>
              <div>
                <div className="mb-1 text-xs text-zinc-500">
                  {t("watchlists:jobs.form.defaultTemplateVersion", "Template version")}
                </div>
                <InputNumber
                  min={1}
                  precision={0}
                  value={outputTemplateVersion}
                  disabled={!outputTemplateName}
                  onChange={(value) =>
                    setOutputTemplateVersion(
                      typeof value === "number" && value > 0 ? Math.floor(value) : null
                    )
                  }
                  className="w-full"
                  placeholder={t("watchlists:jobs.form.defaultTemplateVersionAuto", "Latest")}
                />
              </div>
              <div>
                <div className="mb-1 text-xs text-zinc-500">
                  {t("watchlists:jobs.form.defaultTemplateFormat", "Default output format")}
                </div>
                <Select
                  allowClear
                  value={outputTemplateFormat}
                  onChange={(value) => setOutputTemplateFormat(value as OutputFormat | undefined)}
                  placeholder={t("watchlists:jobs.form.defaultTemplateFormatAuto", "Template/default")}
                  options={[
                    { value: "md", label: "Markdown (md)" },
                    { value: "html", label: "HTML" },
                  ]}
                />
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
            <div className="mb-3 text-sm font-medium">
              {t("watchlists:jobs.form.retentionDefaults", "Retention defaults")}
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div>
                <div className="mb-1 text-xs text-zinc-500">
                  {t("watchlists:jobs.form.retentionDefaultSeconds", "Default TTL (seconds)")}
                </div>
                <InputNumber
                  min={0}
                  precision={0}
                  value={retentionDefaultSeconds}
                  onChange={(value) =>
                    setRetentionDefaultSeconds(
                      typeof value === "number" && value >= 0 ? Math.floor(value) : null
                    )
                  }
                  className="w-full"
                  placeholder={t("watchlists:jobs.form.retentionDefaultSecondsPlaceholder", "Server default")}
                />
              </div>
              <div>
                <div className="mb-1 text-xs text-zinc-500">
                  {t("watchlists:jobs.form.retentionTemporarySeconds", "Temporary TTL (seconds)")}
                </div>
                <InputNumber
                  min={0}
                  precision={0}
                  value={retentionTemporarySeconds}
                  onChange={(value) =>
                    setRetentionTemporarySeconds(
                      typeof value === "number" && value >= 0 ? Math.floor(value) : null
                    )
                  }
                  className="w-full"
                  placeholder={t("watchlists:jobs.form.retentionTemporarySecondsPlaceholder", "Server temporary default")}
                />
              </div>
            </div>
            <div className="mt-2 text-xs text-zinc-500">
              {t(
                "watchlists:jobs.form.retentionHint",
                "Set 0 for no expiry. Leave blank to use server defaults."
              )}
            </div>
          </div>

          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="text-sm font-medium">
                {t("watchlists:jobs.form.emailDelivery", "Email delivery")}
              </div>
              <Switch checked={deliveryEmailEnabled} onChange={setDeliveryEmailEnabled} />
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <div>
                <div className="mb-1 text-xs text-zinc-500">
                  {t("watchlists:jobs.form.emailRecipients", "Recipients")}
                </div>
                <Select
                  mode="tags"
                  value={deliveryEmailRecipients}
                  onChange={setDeliveryEmailRecipients}
                  placeholder={t("watchlists:jobs.form.emailRecipientsPlaceholder", "Enter email addresses")}
                  className="w-full"
                  tokenSeparators={[","]}
                />
              </div>
              <div>
                <div className="mb-1 text-xs text-zinc-500">
                  {t("watchlists:jobs.form.emailSubject", "Default subject")}
                </div>
                <Input
                  value={deliveryEmailSubject}
                  onChange={(event) => setDeliveryEmailSubject(event.target.value)}
                  placeholder={t(
                    "watchlists:jobs.form.emailSubjectPlaceholder",
                    "Defaults to output title"
                  )}
                />
              </div>
              <div>
                <div className="mb-1 text-xs text-zinc-500">
                  {t("watchlists:jobs.form.emailBodyFormat", "Body format")}
                </div>
                <Select
                  value={deliveryEmailBodyFormat}
                  onChange={(value: EmailBodyFormat) => setDeliveryEmailBodyFormat(value)}
                  options={[
                    { value: "auto", label: t("watchlists:jobs.form.emailBodyAuto", "Auto") },
                    { value: "text", label: t("watchlists:jobs.form.emailBodyText", "Text") },
                    { value: "html", label: t("watchlists:jobs.form.emailBodyHtml", "HTML") }
                  ]}
                />
              </div>
            </div>
            <div className="mt-3 flex items-center justify-between rounded-md bg-zinc-50 px-3 py-2 text-sm dark:bg-zinc-900/40">
              <span>{t("watchlists:jobs.form.emailAttachFile", "Attach output file")}</span>
              <Switch
                checked={deliveryEmailAttachFile}
                onChange={setDeliveryEmailAttachFile}
              />
            </div>
          </div>

          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="text-sm font-medium">
                {t("watchlists:jobs.form.chatbookDelivery", "Chatbook delivery")}
              </div>
              <Switch checked={deliveryChatbookEnabled} onChange={setDeliveryChatbookEnabled} />
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Input
                value={deliveryChatbookTitle}
                onChange={(event) => setDeliveryChatbookTitle(event.target.value)}
                placeholder={t("watchlists:jobs.form.chatbookTitle", "Document title (optional)")}
              />
              <InputNumber
                min={1}
                precision={0}
                value={deliveryChatbookConversationId}
                onChange={(value) =>
                  setDeliveryChatbookConversationId(
                    typeof value === "number" && value > 0 ? Math.floor(value) : null
                  )
                }
                className="w-full"
                placeholder={t("watchlists:jobs.form.chatbookConversationId", "Conversation ID (optional)")}
              />
            </div>
            <Input.TextArea
              value={deliveryChatbookDescription}
              onChange={(event) => setDeliveryChatbookDescription(event.target.value)}
              rows={2}
              className="mt-3"
              placeholder={t("watchlists:jobs.form.chatbookDescription", "Description (optional)")}
            />
          </div>
        </div>
      )
    }
  ]

  return (
    <Modal
      title={
        isEditing
          ? t("watchlists:jobs.editJob", "Edit Job")
          : t("watchlists:jobs.addJob", "Add Job")
      }
      open={open}
      onOk={handleSubmit}
      onCancel={handleCancel}
      okText={isEditing ? t("common:save", "Save") : t("common:create", "Create")}
      cancelText={t("common:cancel", "Cancel")}
      confirmLoading={submitting}
      destroyOnHidden
      width={700}
      styles={{ body: { maxHeight: "70vh", overflowY: "auto" } }}
    >
      <Form form={form} layout="vertical" className="mt-4">
        <Form.Item
          name="name"
          label={t("watchlists:jobs.form.name", "Name")}
          rules={[
            {
              required: true,
              message: t("watchlists:jobs.form.nameRequired", "Please enter a name")
            },
            {
              max: 200,
              message: t("watchlists:jobs.form.nameTooLong", "Name must be less than 200 characters")
            }
          ]}
        >
          <Input
            placeholder={t("watchlists:jobs.form.namePlaceholder", "e.g., Daily Tech News")}
          />
        </Form.Item>

        <Form.Item
          name="description"
          label={t("watchlists:jobs.form.description", "Description")}
        >
          <Input.TextArea
            placeholder={t(
              "watchlists:jobs.form.descriptionPlaceholder",
              "Optional description of what this job does"
            )}
            rows={2}
          />
        </Form.Item>

        <Form.Item
          name="active"
          label={t("watchlists:jobs.form.active", "Active")}
          valuePropName="checked"
        >
          <Switch />
        </Form.Item>
      </Form>

      <Collapse
        items={collapseItems}
        defaultActiveKey={["scope"]}
        className="mt-4"
        expandIconPosition="end"
      />
    </Modal>
  )
}
