import React, { useEffect, useMemo, useState } from "react"
import {
  Alert,
  Button,
  Divider,
  Form,
  Input,
  Modal,
  Radio,
  Select,
  Space,
  Tabs,
  message
} from "antd"
import DOMPurify from "dompurify"
import { marked } from "marked"
import { useTranslation } from "react-i18next"
import {
  createWatchlistTemplate,
  getWatchlistTemplate,
  getWatchlistTemplateVersions
} from "@/services/watchlists"
import type {
  WatchlistTemplate,
  WatchlistTemplateCreate,
  WatchlistTemplateVersionSummary
} from "@/types/watchlists"

interface TemplateEditorProps {
  template: WatchlistTemplate | null
  open: boolean
  onClose: (saved?: boolean) => void
}

export const TemplateEditor: React.FC<TemplateEditorProps> = ({
  template,
  open,
  onClose
}) => {
  const { t } = useTranslation(["watchlists", "common"])
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)
  const [loadingVersion, setLoadingVersion] = useState(false)
  const [activeTab, setActiveTab] = useState<"editor" | "preview" | "docs">("editor")
  const [templateVersions, setTemplateVersions] = useState<WatchlistTemplateVersionSummary[]>([])
  const [selectedVersion, setSelectedVersion] = useState<number | undefined>(undefined)
  const [loadedVersion, setLoadedVersion] = useState<number | null>(null)
  const [loadedContentBaseline, setLoadedContentBaseline] = useState("")

  const isEditing = !!template
  const formatValue = Form.useWatch("format", form)
  const contentValue = Form.useWatch("content", form)

  const loadTemplate = async (templateName: string, version?: number) => {
    setLoadingVersion(true)
    try {
      const result = await getWatchlistTemplate(templateName, version ? { version } : undefined)
      form.setFieldsValue({
        name: result.name,
        description: result.description || "",
        content: result.content || "",
        format: result.format || "html"
      })
      setLoadedVersion(typeof result.version === "number" ? result.version : null)
      setLoadedContentBaseline(result.content || "")
    } finally {
      setLoadingVersion(false)
    }
  }

  // Load template content/version history when editing
  useEffect(() => {
    if (open && template) {
      Promise.all([
        getWatchlistTemplate(template.name),
        getWatchlistTemplateVersions(template.name).catch(() => ({ items: [] }))
      ])
        .then(([result, versions]) => {
          form.setFieldsValue({
            name: result.name,
            description: result.description || "",
            content: result.content || "",
            format: result.format || "html"
          })
          setLoadedVersion(typeof result.version === "number" ? result.version : null)
          setLoadedContentBaseline(result.content || "")
          setTemplateVersions(Array.isArray(versions.items) ? versions.items : [])
          setSelectedVersion(undefined)
        })
        .catch((err) => {
          console.error("Failed to load template:", err)
          message.error(t("watchlists:templates.loadError", "Failed to load template"))
          setTemplateVersions([])
          setSelectedVersion(undefined)
          setLoadedVersion(null)
          setLoadedContentBaseline("")
        })
    } else if (open) {
      form.resetFields()
      form.setFieldsValue({
        format: "html",
        content: DEFAULT_HTML_TEMPLATE
      })
      setTemplateVersions([])
      setSelectedVersion(undefined)
      setLoadedVersion(null)
      setLoadedContentBaseline(DEFAULT_HTML_TEMPLATE)
    }
  }, [open, template, form, t])

  const handleLoadSelectedVersion = async () => {
    if (!template || !selectedVersion) return
    try {
      await loadTemplate(template.name, selectedVersion)
      message.success(
        t("watchlists:templates.versionLoaded", "Loaded template version {{version}}", {
          version: selectedVersion,
        })
      )
    } catch (err) {
      console.error("Failed to load template version:", err)
      message.error(t("watchlists:templates.versionLoadError", "Failed to load template version"))
    }
  }

  const handleLoadLatest = async () => {
    if (!template) return
    try {
      await loadTemplate(template.name)
      setSelectedVersion(undefined)
      message.success(t("watchlists:templates.latestLoaded", "Loaded latest template version"))
    } catch (err) {
      console.error("Failed to load latest template version:", err)
      message.error(t("watchlists:templates.latestLoadError", "Failed to load latest template"))
    }
  }

  // Handle save
  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)

      const payload: WatchlistTemplateCreate = {
        name: values.name,
        description: values.description || null,
        content: values.content,
        format: values.format,
        overwrite: isEditing
      }

      await createWatchlistTemplate(payload)
      message.success(
        isEditing
          ? t("watchlists:templates.updated", "Template updated")
          : t("watchlists:templates.created", "Template created")
      )
      onClose(true)
    } catch (err: any) {
      if (err.errorFields) return // Validation error
      console.error("Failed to save template:", err)
      message.error(t("watchlists:templates.saveError", "Failed to save template"))
    } finally {
      setSaving(false)
    }
  }

  useEffect(() => {
    if (!open || isEditing) return
    const touched = form.isFieldTouched("content")
    if (touched) return
    if (formatValue === "md") {
      form.setFieldsValue({ content: DEFAULT_MARKDOWN_TEMPLATE })
      return
    }
    if (formatValue === "html") {
      form.setFieldsValue({ content: DEFAULT_HTML_TEMPLATE })
    }
  }, [formatValue, form, isEditing, open])

  const previewHtml = useMemo(() => {
    if (!contentValue) return ""
    if (formatValue === "md") {
      const rendered = marked.parse(contentValue)
      return DOMPurify.sanitize(String(rendered), { USE_PROFILES: { html: true } })
    }
    return DOMPurify.sanitize(contentValue, { USE_PROFILES: { html: true } })
  }, [contentValue, formatValue])

  const hasVersionDrift = useMemo(() => {
    if (!isEditing || typeof loadedVersion !== "number") return false
    return String(contentValue || "") !== loadedContentBaseline
  }, [contentValue, isEditing, loadedContentBaseline, loadedVersion])

  const insertSnippet = (snippet: string) => {
    const current = String(form.getFieldValue("content") || "")
    const needsSpacer = current.length > 0 && !current.endsWith("\n")
    const nextValue = `${current}${needsSpacer ? "\n\n" : ""}${snippet}`
    form.setFieldsValue({ content: nextValue })
    setActiveTab("editor")
  }

  const tabItems = [
    {
      key: "editor",
      label: t("watchlists:templates.editor.tab", "Editor"),
      children: (
        <div className="space-y-3">
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
            <div className="mb-2 text-xs font-medium text-zinc-500">
              {t("watchlists:templates.quickInsert", "Quick insert snippets")}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button size="small" onClick={() => insertSnippet("{% for item in items %}\n{{ item.title }}\n{% endfor %}")}>
                {t("watchlists:templates.snippetLoop", "Items loop")}
              </Button>
              <Button size="small" onClick={() => insertSnippet("{% if filter_tallies %}\n{{ filter_tallies }}\n{% endif %}")}>
                {t("watchlists:templates.snippetTallies", "Filter tallies")}
              </Button>
              <Button size="small" onClick={() => insertSnippet("{% if item.summary %}\n{{ item.summary }}\n{% endif %}")}>
                {t("watchlists:templates.snippetSummary", "Summary block")}
              </Button>
              <Button size="small" onClick={() => insertSnippet("{{ generated_at }}")}>
                {t("watchlists:templates.snippetGeneratedAt", "Generated timestamp")}
              </Button>
            </div>
          </div>

          <Form.Item
            name="content"
            rules={[{ required: true, message: t("watchlists:templates.contentRequired", "Template content is required") }]}
            className="mb-0"
          >
            <Input.TextArea
              rows={18}
              placeholder={t("watchlists:templates.contentPlaceholder", "Enter Jinja2 template...")}
              className="font-mono text-sm"
              style={{ resize: "none" }}
            />
          </Form.Item>
        </div>
      )
    },
    {
      key: "preview",
      label: t("watchlists:templates.preview.tab", "Preview"),
      children: (
        <div className="space-y-3">
          <Alert
            message={t(
              "watchlists:templates.preview.note",
              "Preview shows rendered markup only; Jinja2 logic is not evaluated."
            )}
            type="info"
            showIcon
          />
          {previewHtml ? (
            <div
              className="prose dark:prose-invert max-w-none p-4 bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-700 overflow-auto max-h-96"
              dangerouslySetInnerHTML={{ __html: previewHtml }}
            />
          ) : (
            <div className="text-sm text-zinc-500">
              {t("watchlists:templates.preview.empty", "Nothing to preview yet.")}
            </div>
          )}
        </div>
      )
    },
    {
      key: "docs",
      label: t("watchlists:templates.docs.tab", "Variables"),
      children: (
        <div className="space-y-4 text-sm">
          <Alert
            message={t("watchlists:templates.docs.title", "Available Variables")}
            description={t("watchlists:templates.docs.description", "These variables are available in your Jinja2 template.")}
            type="info"
            showIcon
          />
          <div className="bg-zinc-50 dark:bg-zinc-900 rounded-lg p-4 font-mono text-xs space-y-2 max-h-80 overflow-auto">
            <div><span className="text-blue-600">{"{{ job }}"}</span> - Job object with name, description, filters</div>
            <div><span className="text-blue-600">{"{{ run }}"}</span> - Run object with status, stats, timestamps</div>
            <div><span className="text-blue-600">{"{{ items }}"}</span> - List of scraped items</div>
            <div className="ml-4"><span className="text-green-600">item.title</span> - Item title</div>
            <div className="ml-4"><span className="text-green-600">item.url</span> - Source URL</div>
            <div className="ml-4"><span className="text-green-600">item.content</span> - Full content text</div>
            <div className="ml-4"><span className="text-green-600">item.summary</span> - AI-generated summary</div>
            <div className="ml-4"><span className="text-green-600">item.author</span> - Author name</div>
            <div className="ml-4"><span className="text-green-600">item.published_at</span> - Publish date</div>
            <div className="ml-4"><span className="text-green-600">item.source</span> - Source object</div>
            <div className="ml-4"><span className="text-green-600">item.filter_matches</span> - Matched filter names</div>
            <div><span className="text-blue-600">{"{{ filter_tallies }}"}</span> - Dict of filter name → count</div>
            <div><span className="text-blue-600">{"{{ generated_at }}"}</span> - Generation timestamp</div>
          </div>

          <div className="text-zinc-500 text-xs">
            {t("watchlists:templates.docs.hint", "Use Jinja2 syntax: {% for item in items %}, {{ item.title }}, {% if condition %}, etc.")}
          </div>
        </div>
      )
    }
  ]

  return (
    <Modal
      title={
        isEditing
          ? t("watchlists:templates.editTitle", "Edit Template")
          : t("watchlists:templates.createTitle", "Create Template")
      }
      open={open}
      onCancel={() => onClose()}
      width={800}
      footer={
        <Space>
          <Button onClick={() => onClose()}>
            {t("common:cancel", "Cancel")}
          </Button>
          <Button type="primary" onClick={handleSave} loading={saving}>
            {t("common:save", "Save")}
          </Button>
        </Space>
      }
    >
      <Form form={form} layout="vertical" className="mt-4">
        <div className="grid grid-cols-2 gap-4">
          <Form.Item
            name="name"
            label={t("watchlists:templates.fields.name", "Template Name")}
            rules={[{ required: true, message: t("watchlists:templates.nameRequired", "Name is required") }]}
          >
            <Input
              placeholder={t("watchlists:templates.namePlaceholder", "my-briefing-template")}
              disabled={isEditing}
            />
          </Form.Item>

          <Form.Item
            name="format"
            label={t("watchlists:templates.fields.format", "Output Format")}
          >
            <Radio.Group>
              <Radio value="html">HTML</Radio>
              <Radio value="md">Markdown</Radio>
            </Radio.Group>
          </Form.Item>
        </div>

        <Form.Item
          name="description"
          label={t("watchlists:templates.fields.description", "Description")}
        >
          <Input
            placeholder={t("watchlists:templates.descriptionPlaceholder", "Optional description...")}
          />
        </Form.Item>

        {isEditing && (
          <>
            <Divider className="my-3" />
            <div className="mb-4 rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
              <div className="mb-2 text-sm font-medium">
                {t("watchlists:templates.versionTools", "Version tools")}
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_auto_auto]">
                <Select
                  allowClear
                  value={selectedVersion}
                  onChange={(value) => setSelectedVersion(value)}
                  placeholder={t("watchlists:templates.selectVersion", "Select a historical version")}
                  options={templateVersions.map((entry) => ({
                    value: entry.version,
                    label: entry.is_current
                      ? t("watchlists:templates.versionCurrent", "v{{version}} (current)", { version: entry.version })
                      : t("watchlists:templates.versionLabel", "v{{version}}", { version: entry.version })
                  }))}
                />
                <Button
                  onClick={handleLoadSelectedVersion}
                  disabled={!selectedVersion}
                  loading={loadingVersion}
                >
                  {t("watchlists:templates.loadVersion", "Load version")}
                </Button>
                <Button
                  onClick={handleLoadLatest}
                  loading={loadingVersion}
                >
                  {t("watchlists:templates.loadLatest", "Load latest")}
                </Button>
              </div>
              {typeof loadedVersion === "number" && (
                <div className="mt-2 text-xs text-zinc-500">
                  {t(
                    "watchlists:templates.loadedVersionHint",
                    "Currently loaded: v{{version}}. Saving restores this content as a new latest version.",
                    { version: loadedVersion }
                  )}
                </div>
              )}
              {hasVersionDrift && (
                <Alert
                  className="mt-3"
                  type="warning"
                  showIcon
                  message={t(
                    "watchlists:templates.unsavedDrift",
                    "Current editor content differs from the loaded version."
                  )}
                />
              )}
            </div>
          </>
        )}

        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as "editor" | "preview" | "docs")}
          items={tabItems}
        />
      </Form>
    </Modal>
  )
}

// Default template for new templates
const DEFAULT_HTML_TEMPLATE = `<!DOCTYPE html>
<html>
<head>
  <title>{{ job.name }} - {{ generated_at }}</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
    .header { border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 20px; }
    .item { margin-bottom: 24px; padding: 16px; background: #f9f9f9; border-radius: 8px; }
    .item-title { font-size: 1.1em; font-weight: 600; margin-bottom: 8px; }
    .item-title a { color: #2563eb; text-decoration: none; }
    .item-meta { font-size: 0.85em; color: #666; margin-bottom: 8px; }
    .item-summary { line-height: 1.6; }
    .filters { display: flex; gap: 8px; margin-top: 8px; }
    .filter-tag { background: #e0e7ff; color: #3730a3; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; }
  </style>
</head>
<body>
  <div class="header">
    <h1>{{ job.name }}</h1>
    <p>Generated: {{ generated_at }} | Items: {{ items | length }}</p>
  </div>

  {% for item in items %}
  <div class="item">
    <div class="item-title">
      <a href="{{ item.url }}" target="_blank">{{ item.title }}</a>
    </div>
    <div class="item-meta">
      {% if item.author %}By {{ item.author }} | {% endif %}
      {{ item.published_at | default('Unknown date') }}
      {% if item.source %} | {{ item.source.name }}{% endif %}
    </div>
    {% if item.summary %}
    <div class="item-summary">{{ item.summary }}</div>
    {% endif %}
    {% if item.filter_matches %}
    <div class="filters">
      {% for filter in item.filter_matches %}
      <span class="filter-tag">{{ filter }}</span>
      {% endfor %}
    </div>
    {% endif %}
  </div>
  {% endfor %}
</body>
</html>`

const DEFAULT_MARKDOWN_TEMPLATE = `# {{ job.name }}

Generated: {{ generated_at }}
Items: {{ items | length }}

{% for item in items %}
## {{ item.title }}
{{ item.url }}

{% if item.summary %}
{{ item.summary }}
{% endif %}

{% if item.author %}
- Author: {{ item.author }}
{% endif %}
{% if item.published_at %}
- Published: {{ item.published_at }}
{% endif %}
{% if item.source %}
- Source: {{ item.source.name }}
{% endif %}

{% if item.filter_matches %}
Matched filters: {{ item.filter_matches | join(", ") }}
{% endif %}

---
{% endfor %}
`
