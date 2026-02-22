import React, { useEffect, useMemo, useState } from "react"
import { Button, Collapse, Form, Input, InputNumber, Modal, Select, Switch, message } from "antd"
import { useTranslation } from "react-i18next"
import {
  createWatchlistJob,
  fetchWatchlistGroups,
  fetchJobOutputTemplates,
  fetchWatchlistSources,
  fetchWatchlistTemplates,
  previewWatchlistJob,
  updateWatchlistJob
} from "@/services/watchlists"
import type {
  JobOutputPrefs,
  JobPreviewResult,
  JobScope,
  PreviewItem,
  WatchlistFilter,
  WatchlistJob,
  WatchlistJobCreate
} from "@/types/watchlists"
import { CronDisplay, WatchlistsHelpTooltip } from "../shared"
import {
  buildScopeTooltipLines,
  summarizeScopeCounts
} from "./job-summaries"
import { evaluatePreviewItems } from "./filter-preview"
import { ScopeSelector } from "./ScopeSelector"
import { FilterBuilder } from "./FilterBuilder"
import { SchedulePicker } from "./SchedulePicker"
import { findInvalidEmailRecipients } from "./email-utils"
import { analyzeScheduleFrequency, MIN_SCHEDULE_INTERVAL_MINUTES } from "./schedule-frequency"
import {
  durationToSeconds,
  secondsToDurationInput,
  type DurationInputValue,
  type DurationUnit
} from "./duration-utils"
import {
  trackWatchlistsPreventionTelemetry,
  type WatchlistsPreventionRule
} from "@/utils/watchlists-prevention-telemetry"

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
const RETENTION_UNITS: DurationUnit[] = ["minutes", "hours", "days", "weeks", "seconds"]
const JOB_PREVIEW_LIMIT = 60
const JOB_PREVIEW_PER_SOURCE = 12
const JOB_SCOPE_CATALOG_PAGE_SIZE = 500

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

type WatchlistsValidationErrorDetail = {
  code?: string
  rule?: string
  message_key?: string
  message?: string
  remediation_key?: string
  remediation?: string
  meta?: Record<string, unknown>
}

const KNOWN_PREVENTION_RULES = new Set<WatchlistsPreventionRule>([
  "scope_required",
  "schedule_too_frequent",
  "invalid_email_recipients",
  "group_cycle_parent"
])

const asWatchlistsValidationErrorDetail = (
  candidate: unknown
): WatchlistsValidationErrorDetail | null => {
  if (!isRecord(candidate)) return null
  const detailCandidate = isRecord(candidate.detail) ? candidate.detail : candidate
  if (!isRecord(detailCandidate)) return null
  if (detailCandidate.code !== "watchlists_validation_error") return null
  return detailCandidate as WatchlistsValidationErrorDetail
}

const extractWatchlistsValidationErrorDetail = (
  error: unknown
): WatchlistsValidationErrorDetail | null => {
  const direct = asWatchlistsValidationErrorDetail(error)
  if (direct) return direct
  if (!isRecord(error)) return null
  const fromDetails = asWatchlistsValidationErrorDetail(error.details)
  if (fromDetails) return fromDetails
  const fromCause = asWatchlistsValidationErrorDetail(error.cause)
  if (fromCause) return fromCause
  if (isRecord(error.cause)) {
    return asWatchlistsValidationErrorDetail(error.cause.details)
  }
  return null
}

const toKnownPreventionRule = (
  rule: string | undefined
): WatchlistsPreventionRule | null => {
  if (!rule) return null
  return KNOWN_PREVENTION_RULES.has(rule as WatchlistsPreventionRule)
    ? (rule as WatchlistsPreventionRule)
    : null
}

const toOptionalNumber = (value: unknown): number | null => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

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
  const [retentionDefaultDuration, setRetentionDefaultDuration] = useState<DurationInputValue>({
    value: null,
    unit: "days"
  })
  const [retentionTemporaryDuration, setRetentionTemporaryDuration] = useState<DurationInputValue>({
    value: null,
    unit: "days"
  })
  const [deliveryEmailEnabled, setDeliveryEmailEnabled] = useState(false)
  const [deliveryEmailRecipients, setDeliveryEmailRecipients] = useState<string[]>([])
  const [deliveryEmailSubject, setDeliveryEmailSubject] = useState("")
  const [deliveryEmailAttachFile, setDeliveryEmailAttachFile] = useState(true)
  const [deliveryEmailBodyFormat, setDeliveryEmailBodyFormat] = useState<EmailBodyFormat>("auto")
  const [deliveryChatbookEnabled, setDeliveryChatbookEnabled] = useState(false)
  const [deliveryChatbookTitle, setDeliveryChatbookTitle] = useState("")
  const [deliveryChatbookDescription, setDeliveryChatbookDescription] = useState("")
  const [deliveryChatbookConversationId, setDeliveryChatbookConversationId] = useState<number | null>(null)
  const [scopeSourceNamesById, setScopeSourceNamesById] = useState<Record<number, string>>({})
  const [scopeGroupNamesById, setScopeGroupNamesById] = useState<Record<number, string>>({})
  const [previewCandidates, setPreviewCandidates] = useState<PreviewItem[]>([])
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)

  const watchedName = Form.useWatch("name", form)

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
    setRetentionDefaultDuration(
      secondsToDurationInput(
        Number.isFinite(parsedDefaultRetention) && parsedDefaultRetention >= 0
          ? Math.floor(parsedDefaultRetention)
          : null
      )
    )
    const parsedTemporaryRetention = Number(retentionRecord.temporary_seconds)
    setRetentionTemporaryDuration(
      secondsToDurationInput(
        Number.isFinite(parsedTemporaryRetention) && parsedTemporaryRetention >= 0
          ? Math.floor(parsedTemporaryRetention)
          : null
      )
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
    const defaultRetentionSeconds = durationToSeconds(retentionDefaultDuration)
    if (typeof defaultRetentionSeconds === "number" && defaultRetentionSeconds >= 0) {
      retentionPrefs.default_seconds = defaultRetentionSeconds
    } else {
      delete retentionPrefs.default_seconds
    }
    const temporaryRetentionSeconds = durationToSeconds(retentionTemporaryDuration)
    if (typeof temporaryRetentionSeconds === "number" && temporaryRetentionSeconds >= 0) {
      retentionPrefs.temporary_seconds = temporaryRetentionSeconds
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
    if (!open) {
      setScopeSourceNamesById({})
      setScopeGroupNamesById({})
      return
    }
    let cancelled = false

    Promise.all([
      fetchWatchlistSources({ page: 1, size: JOB_SCOPE_CATALOG_PAGE_SIZE }),
      fetchWatchlistGroups({ page: 1, size: JOB_SCOPE_CATALOG_PAGE_SIZE })
    ])
      .then(([sourcesResult, groupsResult]) => {
        if (cancelled) return
        const nextSources: Record<number, string> = {}
        const nextGroups: Record<number, string> = {}
        for (const source of sourcesResult.items || []) {
          nextSources[source.id] = source.name
        }
        for (const group of groupsResult.items || []) {
          nextGroups[group.id] = group.name
        }
        setScopeSourceNamesById(nextSources)
        setScopeGroupNamesById(nextGroups)
      })
      .catch((err) => {
        console.warn("Failed to load monitor scope summary catalog:", err)
      })

    return () => {
      cancelled = true
    }
  }, [open])

  useEffect(() => {
    if (!open || !isEditing || !initialValues?.id) {
      setPreviewCandidates([])
      setPreviewError(null)
      setPreviewLoading(false)
      return
    }
    let cancelled = false
    setPreviewLoading(true)
    setPreviewError(null)

    previewWatchlistJob(initialValues.id, {
      limit: JOB_PREVIEW_LIMIT,
      per_source: JOB_PREVIEW_PER_SOURCE
    })
      .then((result: JobPreviewResult) => {
        if (cancelled) return
        setPreviewCandidates(Array.isArray(result.items) ? result.items : [])
      })
      .catch((err) => {
        if (cancelled) return
        console.error("Failed to load monitor preview candidates:", err)
        setPreviewCandidates([])
        setPreviewError(
          t(
            "watchlists:jobs.form.previewLoadError",
            "Could not load sample candidates for this monitor."
          )
        )
      })
      .finally(() => {
        if (!cancelled) {
          setPreviewLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [initialValues?.id, isEditing, open, t])

  useEffect(() => {
    if (!open) return
    let cancelled = false
    const loadTemplates = async () => {
      const [outputsResult, legacyResult] = await Promise.allSettled([
        fetchJobOutputTemplates({ limit: 200, offset: 0 }),
        fetchWatchlistTemplates()
      ])
      if (cancelled) return

      const optionsByName = new Map<string, { label: string; value: string }>()

      if (outputsResult.status === "fulfilled") {
        for (const item of outputsResult.value.items) {
          const normalizedName = item.name.trim()
          if (!normalizedName) continue
          const formatSuffix = item.format ? ` (${String(item.format).toUpperCase()})` : ""
          optionsByName.set(normalizedName, {
            label: `${normalizedName}${formatSuffix} · ${t("watchlists:jobs.form.templateSource.outputs", "Outputs template")}`,
            value: normalizedName
          })
        }
      }

      if (legacyResult.status === "fulfilled") {
        const items = Array.isArray(legacyResult.value.items) ? legacyResult.value.items : []
        for (const item of items) {
          const normalizedName = item.name.trim()
          if (!normalizedName || optionsByName.has(normalizedName)) continue
          optionsByName.set(normalizedName, {
            label: `${normalizedName} · ${t("watchlists:jobs.form.templateSource.legacy", "Legacy watchlists template")}`,
            value: normalizedName
          })
        }
      }

      if (outputsResult.status === "rejected" && legacyResult.status === "rejected") {
        console.error("Failed to load output template options for job form", {
          outputs: outputsResult.reason,
          legacy: legacyResult.reason
        })
      }

      setTemplateOptions(
        Array.from(optionsByName.values()).sort((a, b) => a.label.localeCompare(b.label))
      )
    }

    void loadTemplates().catch((err) => {
      console.error("Failed to load output template options for job form:", err)
      if (!cancelled) {
        setTemplateOptions([])
      }
    })
    return () => {
      cancelled = true
    }
  }, [open, t])

  useEffect(() => {
    const normalizedName = outputTemplateName?.trim()
    if (!normalizedName) return
    setTemplateOptions((previous) => {
      if (previous.some((option) => option.value === normalizedName)) {
        return previous
      }
      return [
        ...previous,
        {
          label: `${normalizedName} · ${t("watchlists:jobs.form.templateSource.current", "Current selection")}`,
          value: normalizedName
        }
      ]
    })
  }, [outputTemplateName, t])

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()

      // Validate scope
      const hasScope =
        (scope.sources?.length ?? 0) > 0 ||
        (scope.groups?.length ?? 0) > 0 ||
        (scope.tags?.length ?? 0) > 0

      if (!hasScope) {
        void trackWatchlistsPreventionTelemetry({
          type: "watchlists_validation_blocked",
          surface: "job_form",
          rule: "scope_required",
          remediation: "select_scope"
        })
        message.error(t("watchlists:jobs.form.scopeRequired", "Please select at least one feed, group, or tag"))
        return
      }

      const scheduleFrequency = analyzeScheduleFrequency(schedule, MIN_SCHEDULE_INTERVAL_MINUTES)
      if (scheduleFrequency.tooFrequent) {
        void trackWatchlistsPreventionTelemetry({
          type: "watchlists_validation_blocked",
          surface: "job_form",
          rule: "schedule_too_frequent",
          remediation: "increase_interval",
          minutes: MIN_SCHEDULE_INTERVAL_MINUTES
        })
        message.error(
          t(
            "watchlists:jobs.form.scheduleTooFrequent",
            "Schedule is too frequent. Minimum interval is every {{minutes}} minutes.",
            { minutes: MIN_SCHEDULE_INTERVAL_MINUTES }
          )
        )
        return
      }

      if (invalidEmailRecipients.length > 0) {
        void trackWatchlistsPreventionTelemetry({
          type: "watchlists_validation_blocked",
          surface: "job_form",
          rule: "invalid_email_recipients",
          remediation: "fix_recipients",
          count: invalidEmailRecipients.length
        })
        message.error(
          t(
            "watchlists:jobs.form.emailRecipientsInvalidSubmit",
            "Fix invalid email recipients before saving."
          )
        )
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
        message.success(t("watchlists:jobs.updated", "Monitor updated"))
      } else {
        await createWatchlistJob(jobData)
        message.success(t("watchlists:jobs.created", "Monitor created"))
      }

      onSuccess()
    } catch (err) {
      if (err && typeof err === "object" && "errorFields" in err) {
        // Validation error - handled by form
        return
      }
      const validationDetail = extractWatchlistsValidationErrorDetail(err)
      if (validationDetail) {
        const meta = isRecord(validationDetail.meta) ? validationDetail.meta : {}
        const minimumMinutes = toOptionalNumber(meta.minimum_minutes)
        const tValues =
          minimumMinutes != null
            ? { minutes: Math.max(1, Math.round(minimumMinutes)) }
            : undefined
        const localizedMessage = validationDetail.message_key
          ? t(
            validationDetail.message_key,
            validationDetail.message || "Validation failed.",
            tValues
          )
          : validationDetail.message || t("watchlists:jobs.saveError", "Failed to save monitor")
        const localizedRemediation = validationDetail.remediation_key
          ? t(validationDetail.remediation_key, validationDetail.remediation || "", tValues)
          : validationDetail.remediation || ""
        const knownRule = toKnownPreventionRule(validationDetail.rule)
        if (knownRule) {
          void trackWatchlistsPreventionTelemetry({
            type: "watchlists_validation_blocked",
            surface: "job_form",
            rule: knownRule,
            remediation: "server_validation_error"
          })
        }
        const combinedMessage = [localizedMessage, localizedRemediation]
          .map((part) => String(part || "").trim())
          .filter((part) => part.length > 0)
          .join(" ")
        message.error(combinedMessage || t("watchlists:jobs.saveError", "Failed to save monitor"))
        return
      }
      console.error("Form submit error:", err)
      message.error(t("watchlists:jobs.saveError", "Failed to save monitor"))
    } finally {
      setSubmitting(false)
    }
  }

  const handleCancel = () => {
    form.resetFields()
    onClose()
  }

  const retentionUnitOptions = RETENTION_UNITS.map((unit) => ({
    value: unit,
    label: t(
      `watchlists:jobs.form.retentionUnit.${unit}`,
      unit.charAt(0).toUpperCase() + unit.slice(1)
    )
  }))

  const retentionDefaultSeconds = durationToSeconds(retentionDefaultDuration)
  const retentionTemporarySeconds = durationToSeconds(retentionTemporaryDuration)
  const invalidEmailRecipients = findInvalidEmailRecipients(deliveryEmailRecipients)

  const scopeSummary = summarizeScopeCounts(scope, t)
  const scopeSummaryLines = buildScopeTooltipLines(
    scope,
    {
      sources: scopeSourceNamesById,
      groups: scopeGroupNamesById
    },
    t,
    4
  )

  const scopedPreviewCandidates = useMemo(() => {
    const selectedSourceIds = Array.isArray(scope.sources) ? scope.sources : []
    if (selectedSourceIds.length === 0) return previewCandidates
    const allowedSourceIds = new Set(selectedSourceIds)
    return previewCandidates.filter((item) => allowedSourceIds.has(item.source_id))
  }, [previewCandidates, scope.sources])

  const filterPreviewOutcome = useMemo(
    () => evaluatePreviewItems(scopedPreviewCandidates, filters),
    [filters, scopedPreviewCandidates]
  )

  const filterPreviewUnavailableReason = useMemo(() => {
    if (previewLoading) return null
    if (!isEditing) {
      return t(
        "watchlists:jobs.form.previewCreateHint",
        "Save this monitor once to load sample candidates for live filter preview."
      )
    }
    if (previewError) return previewError
    return null
  }, [isEditing, previewError, previewLoading, t])

  const filterPreviewSummaryText = useMemo(() => {
    if (previewLoading) {
      return t("watchlists:filters.preview.loading", "Loading sample candidates...")
    }
    if (filterPreviewUnavailableReason) {
      return filterPreviewUnavailableReason
    }
    return t(
      "watchlists:jobs.form.previewSummary",
      "{{ingestable}} ingestable, {{filtered}} filtered from {{total}} sample items.",
      {
        ingestable: filterPreviewOutcome.ingestable,
        filtered: filterPreviewOutcome.filtered,
        total: filterPreviewOutcome.total
      }
    )
  }, [
    filterPreviewOutcome.filtered,
    filterPreviewOutcome.ingestable,
    filterPreviewOutcome.total,
    filterPreviewUnavailableReason,
    previewLoading,
    t
  ])

  const collapseItems = [
    {
      key: "scope",
      label: (
        <span className="font-medium">
          {t("watchlists:jobs.form.scope", "Feeds to Include")}
          <span className="text-danger ml-1">*</span>
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
            <span className="ml-2 text-text-muted">({filters.length})</span>
          )}
        </span>
      ),
      children: (
        <FilterBuilder
          value={filters}
          onChange={setFilters}
          preview={{
            loading: previewLoading,
            unavailableReason: filterPreviewUnavailableReason,
            outcome: filterPreviewOutcome
          }}
        />
      )
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
          <div className="rounded-lg border border-border p-3">
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
                    label: t("watchlists:jobs.form.presetMeceMd", "Structured review (Markdown)"),
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
            <div className="mt-2 text-xs text-text-muted">
              {t(
                "watchlists:jobs.form.presetHint",
                "Presets prefill template and delivery defaults. Structured review groups content into non-overlapping sections for easier scanning."
              )}
            </div>
          </div>

          <div className="rounded-lg border border-border p-3">
            <div className="mb-3 flex items-center gap-1 text-sm font-medium">
              {t("watchlists:jobs.form.defaultTemplate", "Default template")}
              <WatchlistsHelpTooltip topic="jinja2" />
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <div>
                <div className="mb-1 text-xs text-text-muted">
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
                <div className="mb-1 text-xs text-text-muted">
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
                <div className="mb-1 text-xs text-text-muted">
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

          <div className="rounded-lg border border-border p-3">
            <div className="mb-3 flex items-center gap-1 text-sm font-medium">
              {t("watchlists:jobs.form.retentionDefaults", "Retention defaults")}
              <WatchlistsHelpTooltip topic="ttl" />
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div>
                <div className="mb-1 text-xs text-text-muted">
                  {t("watchlists:jobs.form.retentionDefault", "Default retention")}
                </div>
                <div className="grid grid-cols-[1fr_140px] gap-2">
                  <InputNumber
                    min={0}
                    precision={0}
                    value={retentionDefaultDuration.value}
                    onChange={(value) =>
                      setRetentionDefaultDuration((prev) => ({
                        ...prev,
                        value: typeof value === "number" && value >= 0 ? Math.floor(value) : null
                      }))
                    }
                    className="w-full"
                    placeholder={t("watchlists:jobs.form.retentionDefaultPlaceholder", "Server default")}
                  />
                  <Select
                    value={retentionDefaultDuration.unit}
                    onChange={(unit: DurationUnit) =>
                      setRetentionDefaultDuration((prev) => ({ ...prev, unit }))
                    }
                    options={retentionUnitOptions}
                  />
                </div>
                {typeof retentionDefaultSeconds === "number" && (
                  <div className="mt-1 text-xs text-text-muted">
                    {t(
                      "watchlists:jobs.form.retentionDefaultPreview",
                      "Saved internally as {{seconds}} seconds",
                      { seconds: retentionDefaultSeconds }
                    )}
                  </div>
                )}
              </div>
              <div>
                <div className="mb-1 text-xs text-text-muted">
                  {t("watchlists:jobs.form.retentionTemporary", "Temporary retention")}
                </div>
                <div className="grid grid-cols-[1fr_140px] gap-2">
                  <InputNumber
                    min={0}
                    precision={0}
                    value={retentionTemporaryDuration.value}
                    onChange={(value) =>
                      setRetentionTemporaryDuration((prev) => ({
                        ...prev,
                        value: typeof value === "number" && value >= 0 ? Math.floor(value) : null
                      }))
                    }
                    className="w-full"
                    placeholder={t(
                      "watchlists:jobs.form.retentionTemporaryPlaceholder",
                      "Server temporary default"
                    )}
                  />
                  <Select
                    value={retentionTemporaryDuration.unit}
                    onChange={(unit: DurationUnit) =>
                      setRetentionTemporaryDuration((prev) => ({ ...prev, unit }))
                    }
                    options={retentionUnitOptions}
                  />
                </div>
                {typeof retentionTemporarySeconds === "number" && (
                  <div className="mt-1 text-xs text-text-muted">
                    {t(
                      "watchlists:jobs.form.retentionTemporaryPreview",
                      "Saved internally as {{seconds}} seconds",
                      { seconds: retentionTemporarySeconds }
                    )}
                  </div>
                )}
              </div>
            </div>
            <div className="mt-2 text-xs text-text-muted">
              {t(
                "watchlists:jobs.form.retentionHint",
                "Set 0 for no expiry. Leave blank to use server defaults. Values are converted safely to seconds when saved."
              )}
            </div>
          </div>

          <div className="rounded-lg border border-border p-3">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="text-sm font-medium">
                {t("watchlists:jobs.form.emailDelivery", "Email delivery")}
              </div>
              <Switch checked={deliveryEmailEnabled} onChange={setDeliveryEmailEnabled} />
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <div>
                <div className="mb-1 text-xs text-text-muted">
                  {t("watchlists:jobs.form.emailRecipients", "Recipients")}
                </div>
                <Select
                  mode="tags"
                  value={deliveryEmailRecipients}
                  onChange={setDeliveryEmailRecipients}
                  placeholder={t("watchlists:jobs.form.emailRecipientsPlaceholder", "Enter email addresses")}
                  className="w-full"
                  tokenSeparators={[","]}
                  status={invalidEmailRecipients.length > 0 ? "error" : undefined}
                />
                {invalidEmailRecipients.length > 0 && (
                  <div className="mt-1 text-xs text-danger">
                    {t(
                      "watchlists:jobs.form.emailRecipientsInvalidInline",
                      "Invalid addresses: {{emails}}",
                      { emails: invalidEmailRecipients.join(", ") }
                    )}
                  </div>
                )}
              </div>
              <div>
                <div className="mb-1 text-xs text-text-muted">
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
                <div className="mb-1 text-xs text-text-muted">
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
            <div className="mt-3 flex items-center justify-between rounded-md bg-surface px-3 py-2 text-sm">
              <span>{t("watchlists:jobs.form.emailAttachFile", "Attach output file")}</span>
              <Switch
                checked={deliveryEmailAttachFile}
                onChange={setDeliveryEmailAttachFile}
              />
            </div>
          </div>

          <div className="rounded-lg border border-border p-3">
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
          ? t("watchlists:jobs.editJob", "Edit Monitor")
          : t("watchlists:jobs.addJob", "Add Monitor")
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
              "Optional description of what this monitor does"
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

      <div
        className="mt-4 rounded-lg border border-border bg-surface p-3 space-y-2"
        data-testid="job-form-live-summary"
      >
        <div className="text-sm font-medium">
          {t("watchlists:jobs.form.liveSummaryTitle", "Live setup summary")}
        </div>
        <div className="text-xs text-text-muted" data-testid="job-form-summary-name">
          {t("watchlists:jobs.form.liveSummary.name", "Monitor")}:{" "}
          {String(watchedName || "").trim() || t("watchlists:jobs.form.liveSummary.unnamed", "Untitled monitor")}
        </div>
        <div className="grid grid-cols-1 gap-2 text-xs text-text-muted md:grid-cols-3">
          <div>
            <div className="font-medium text-text">{t("watchlists:jobs.form.liveSummary.scope", "Scope")}</div>
            <div data-testid="job-form-summary-scope">{scopeSummary}</div>
          </div>
          <div>
            <div className="font-medium text-text">{t("watchlists:jobs.form.liveSummary.schedule", "Schedule")}</div>
            <div data-testid="job-form-summary-schedule">
              {schedule ? (
                <CronDisplay expression={schedule} showIcon={false} />
              ) : (
                t("watchlists:jobs.form.liveSummary.notScheduled", "Not scheduled")
              )}
            </div>
          </div>
          <div>
            <div className="font-medium text-text">{t("watchlists:jobs.form.liveSummary.filters", "Filters")}</div>
            <div data-testid="job-form-summary-filters">
              {filters.length > 0
                ? t("watchlists:jobs.form.liveSummary.filtersConfigured", "{{count}} filters configured", {
                  count: filters.length
                })
                : t("watchlists:jobs.form.liveSummary.noFilters", "No filters configured")}
            </div>
          </div>
        </div>
        <div className="text-xs text-text-muted" data-testid="job-form-summary-scope-lines">
          {scopeSummaryLines.join(" · ")}
        </div>
        <div className="text-xs text-text-muted" data-testid="job-form-summary-preview">
          {filterPreviewSummaryText}
        </div>
      </div>

      <Collapse
        items={collapseItems}
        defaultActiveKey={["scope"]}
        className="mt-4"
        expandIconPlacement="end"
      />
    </Modal>
  )
}
