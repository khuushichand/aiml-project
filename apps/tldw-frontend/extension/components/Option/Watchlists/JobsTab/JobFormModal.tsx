import React, { useEffect, useState } from "react"
import { Collapse, Form, Input, Modal, Select, Switch, message } from "antd"
import { useTranslation } from "react-i18next"
import { useTldwApiClient } from "@/hooks/useTldwApiClient"
import { createWatchlistJob, fetchWatchlistTemplates, updateWatchlistJob } from "@/services/watchlists"
import type {
  JobScope,
  WatchlistFilter,
  WatchlistJob,
  WatchlistJobCreate,
  WatchlistTemplate
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

export const JobFormModal: React.FC<JobFormModalProps> = ({
  open,
  onClose,
  onSuccess,
  initialValues
}) => {
  const { t } = useTranslation(["watchlists", "common"])
  const api = useTldwApiClient()
  const [form] = Form.useForm<FormValues>()
  const [submitting, setSubmitting] = useState(false)

  const isEditing = !!initialValues

  // Managed state for complex fields
  const [scope, setScope] = useState<JobScope>({})
  const [filters, setFilters] = useState<WatchlistFilter[]>([])
  const [schedule, setSchedule] = useState<string | null>(null)
  const [timezone, setTimezone] = useState("UTC")
  const [outputTemplateName, setOutputTemplateName] = useState<string | null>(null)
  const [templateOptions, setTemplateOptions] = useState<Array<{ label: string; options: Array<{ label: string; value: string }> }>>([])
  const [templatesLoading, setTemplatesLoading] = useState(false)
  const [templatesError, setTemplatesError] = useState<string | null>(null)

  // Reset form when modal opens/closes or initialValues change
  useEffect(() => {
    if (open) {
      if (initialValues) {
        const outputPrefs =
          initialValues.output_prefs && typeof initialValues.output_prefs === "object"
            ? (initialValues.output_prefs as Record<string, unknown>)
            : null
        const templatePrefs =
          outputPrefs && typeof outputPrefs.template === "object"
            ? (outputPrefs.template as Record<string, unknown>)
            : null
        form.setFieldsValue({
          name: initialValues.name,
          description: initialValues.description || "",
          active: initialValues.active
        })
        setScope(initialValues.scope || {})
        setFilters(initialValues.job_filters?.filters || [])
        setSchedule(initialValues.schedule_expr || null)
        setTimezone(initialValues.timezone || "UTC")
        const defaultTemplateName =
          templatePrefs && typeof templatePrefs.default_name === "string"
            ? templatePrefs.default_name
            : null
        const legacyTemplateName =
          outputPrefs && typeof outputPrefs.template_name === "string"
            ? outputPrefs.template_name
            : null
        setOutputTemplateName(defaultTemplateName || legacyTemplateName)
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
        setOutputTemplateName(null)
      }
    }
  }, [open, initialValues, form])

  useEffect(() => {
    if (!open) return
    let cancelled = false

    const loadTemplates = async () => {
      setTemplatesLoading(true)
      setTemplatesError(null)
      try {
        const [outputsResult, legacyResult] = await Promise.allSettled([
          api.getOutputTemplates({ limit: 200, offset: 0 }),
          fetchWatchlistTemplates()
        ])
        if (cancelled) return

        const outputTemplates =
          outputsResult.status === "fulfilled" && Array.isArray(outputsResult.value?.items)
            ? outputsResult.value.items
            : []
        const legacyTemplates =
          legacyResult.status === "fulfilled" && Array.isArray(legacyResult.value?.items)
            ? (legacyResult.value.items as WatchlistTemplate[])
            : []

        const getStringField = (value: unknown, key: string): string | null => {
          if (!value || typeof value !== "object") return null
          const record = value as Record<string, unknown>
          const field = record[key]
          return typeof field === "string" ? field : null
        }

        const outputOptions = outputTemplates
          .map((tpl) => {
            const name = getStringField(tpl, "name")
            const format = getStringField(tpl, "format")
            if (!name || !format) return null
            return { name, format }
          })
          .filter(
            (tpl): tpl is { name: string; format: string } => Boolean(tpl)
          )
          .filter((tpl) => tpl.format === "md" || tpl.format === "html")
          .map((tpl) => ({
            label: `${tpl.name} (${tpl.format})`,
            value: tpl.name
          }))
        const legacyOptions = legacyTemplates.map((tpl: WatchlistTemplate) => ({
          label: `${tpl.name} (${tpl.format})`,
          value: tpl.name
        }))

        const grouped: Array<{ label: string; options: Array<{ label: string; value: string }> }> = []
        if (outputOptions.length > 0) {
          grouped.push({
            label: t("watchlists:jobs.outputPrefs.outputsTemplates", "Outputs templates"),
            options: outputOptions
          })
        }
        if (legacyOptions.length > 0) {
          grouped.push({
            label: t("watchlists:jobs.outputPrefs.legacyTemplates", "Legacy watchlists templates"),
            options: legacyOptions
          })
        }
        setTemplateOptions(grouped)

        const errors = []
        if (outputsResult.status === "rejected") {
          errors.push(t("watchlists:jobs.outputPrefs.outputsTemplatesError", "Failed to load outputs templates"))
        }
        if (legacyResult.status === "rejected") {
          errors.push(t("watchlists:jobs.outputPrefs.legacyTemplatesError", "Failed to load legacy templates"))
        }
        setTemplatesError(errors.length ? errors.join(" ") : null)
      } catch {
        if (!cancelled) {
          setTemplatesError(t("watchlists:jobs.outputPrefs.templatesError", "Failed to load templates"))
        }
      } finally {
        if (!cancelled) {
          setTemplatesLoading(false)
        }
      }
    }

    void loadTemplates()
    return () => {
      cancelled = true
    }
  }, [open, api, t])

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

      const jobData: WatchlistJobCreate = {
        name: values.name,
        description: values.description || undefined,
        active: values.active,
        scope,
        schedule_expr: schedule || undefined,
        timezone: timezone || undefined,
        job_filters: filters.length > 0 ? { filters } : undefined
      }
      const baseOutputPrefs =
        initialValues?.output_prefs && typeof initialValues.output_prefs === "object"
          ? { ...(initialValues.output_prefs as Record<string, unknown>) }
          : {}
      const templatePrefs =
        baseOutputPrefs.template && typeof baseOutputPrefs.template === "object"
          ? { ...(baseOutputPrefs.template as Record<string, unknown>) }
          : {}
      if (outputTemplateName) {
        templatePrefs.default_name = outputTemplateName
        baseOutputPrefs.template_name = outputTemplateName
      } else {
        delete templatePrefs.default_name
        delete baseOutputPrefs.template_name
      }
      if (Object.keys(templatePrefs).length > 0) {
        baseOutputPrefs.template = templatePrefs
      } else {
        delete baseOutputPrefs.template
      }
      if (Object.keys(baseOutputPrefs).length > 0) {
        jobData.output_prefs = baseOutputPrefs
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
      key: "outputs",
      label: (
        <span className="font-medium">
          {t("watchlists:jobs.form.outputs", "Outputs")}
        </span>
      ),
      children: (
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-sm font-medium">
              {t("watchlists:jobs.outputPrefs.defaultTemplateLabel", "Default template")}
            </label>
            <Select
              value={outputTemplateName ?? undefined}
              onChange={(value) => setOutputTemplateName(value ?? null)}
              placeholder={t("watchlists:jobs.outputPrefs.defaultTemplatePlaceholder", "Select a template")}
              options={templateOptions}
              loading={templatesLoading}
              allowClear
              showSearch
              optionFilterProp="label"
            />
            {templatesError && (
              <div className="mt-2 text-xs text-red-500">{templatesError}</div>
            )}
            <div className="mt-2 text-xs text-zinc-500">
              {t(
                "watchlists:jobs.outputPrefs.defaultTemplateHint",
                "Used when generating outputs for this job unless overridden."
              )}
            </div>
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
      destroyOnClose
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
