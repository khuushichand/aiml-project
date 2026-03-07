import React, { useEffect, useCallback, useState } from "react"
import { Form, Input, Select, Collapse } from "antd"
import { useTranslation } from "react-i18next"
import { ArrowLeft, Save } from "lucide-react"
import { PromptEditorPreview } from "./PromptEditorPreview"
import { useFormDraft, formatDraftAge } from "@/hooks/useFormDraft"
import {
  estimatePromptTokens,
  getPromptTokenBudgetState,
} from "./prompt-length-utils"
import { validateTemplateVariableSyntax } from "./prompt-template-variable-utils"

const { TextArea } = Input

type PromptFullPageEditorProps = {
  open: boolean
  onClose: () => void
  mode: "create" | "edit"
  initialValues?: Record<string, any> | null
  onSubmit: (values: any) => void
  isLoading: boolean
  allTags: string[]
}

const DRAFT_KEY_PREFIX = "tldw-prompt-fullpage-draft-"

export const PromptFullPageEditor: React.FC<PromptFullPageEditorProps> = ({
  open,
  onClose,
  mode,
  initialValues,
  onSubmit,
  isLoading,
  allTags,
}) => {
  const { t } = useTranslation(["settings", "common"])
  const [form] = Form.useForm()
  const [dirty, setDirty] = useState(false)
  const [showMobilePreview, setShowMobilePreview] = useState(false)

  const draftKey = `${DRAFT_KEY_PREFIX}${mode === "edit" ? initialValues?.id || "new" : "new"}`
  const { hasDraft, draftData, clearDraft, saveDraft, applyDraft, lastSaved } = useFormDraft({
    storageKey: draftKey,
    formType: mode,
    editId: mode === "edit" ? initialValues?.id : undefined,
    autoSaveInterval: 5000,
  })

  const systemPromptValue = Form.useWatch("system_prompt", form) || ""
  const userPromptValue = Form.useWatch("user_prompt", form) || ""

  // Set initial values
  useEffect(() => {
    if (!open) return
    if (hasDraft && draftData) {
      const recovered = applyDraft()
      if (recovered) {
        form.setFieldsValue(recovered)
        return
      }
    }
    if (initialValues) {
      form.setFieldsValue({
        name: initialValues.name || "",
        author: initialValues.author || "",
        details: initialValues.details || "",
        system_prompt: initialValues.system_prompt || "",
        user_prompt: initialValues.user_prompt || "",
        keywords: initialValues.keywords || [],
        changeDescription: initialValues.changeDescription || "",
      })
    } else {
      form.resetFields()
    }
    setDirty(false)
  }, [open, initialValues, hasDraft, draftData, applyDraft, form])

  // Mark dirty changes for auto-save
  useEffect(() => {
    if (!open || !dirty) return
    saveDraft(form.getFieldsValue())
  }, [open, dirty, form, saveDraft])

  // beforeunload guard
  useEffect(() => {
    if (!open || !dirty) return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
    }
    window.addEventListener("beforeunload", handler)
    return () => window.removeEventListener("beforeunload", handler)
  }, [open, dirty])

  const handleRequestClose = useCallback(() => {
    if (dirty) {
      const ok = window.confirm(
        t("managePrompts.drawer.unsavedChanges", {
          defaultValue: "You have unsaved changes. Discard them?",
        })
      )
      if (!ok) return
    }
    clearDraft()
    onClose()
  }, [dirty, clearDraft, onClose, t])

  // Keyboard shortcuts
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault()
        form.submit()
      }
      if (e.key === "Escape") {
        e.preventDefault()
        handleRequestClose()
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [open, form, handleRequestClose])

  const handleFinish = (values: any) => {
    const keywords = Array.isArray(values.keywords)
      ? values.keywords
          .map((k: string) => (typeof k === "string" ? k.trim() : ""))
          .filter((k: string) => k.length > 0)
          .sort()
      : []

    onSubmit({
      ...values,
      keywords,
      name: (values.name || "").trim(),
      author: (values.author || "").trim(),
      details: (values.details || "").trim(),
      system_prompt: (values.system_prompt || "").trim(),
      user_prompt: (values.user_prompt || "").trim(),
    })
    clearDraft()
    setDirty(false)
  }

  const templateFieldValidator = (_: any, value: string) => {
    if (!value) return Promise.resolve()
    const result = validateTemplateVariableSyntax(value)
    if (!result.isValid) {
      const msg = result.code === "unmatched_braces"
        ? "Unmatched {{ or }} braces"
        : `Invalid template variable: ${result.invalidTokens?.[0] ?? ""}`
      return Promise.reject(msg)
    }
    return Promise.resolve()
  }

  const sysTokens = estimatePromptTokens(systemPromptValue)
  const userTokens = estimatePromptTokens(userPromptValue)
  const sysBudget = getPromptTokenBudgetState(sysTokens)
  const userBudget = getPromptTokenBudgetState(userTokens)

  const tokenLabel = (count: number, budget: string) => {
    const color =
      budget === "danger"
        ? "text-danger"
        : budget === "warning"
        ? "text-warning"
        : "text-text-muted"
    return (
      <span className={`text-xs ${color}`}>
        {count} chars / ~{Math.round(count / 4)} tokens
      </span>
    )
  }

  if (!open) return null

  const title =
    mode === "edit"
      ? initialValues?.name
        ? `Editing: ${initialValues.name}`
        : "Edit Prompt"
      : "New Prompt"

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col bg-background"
      data-testid="prompt-full-page-editor"
    >
      {/* Top bar */}
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleRequestClose}
            className="flex items-center gap-1 rounded px-2 py-1 text-sm text-text-muted hover:bg-surface2 hover:text-text"
            data-testid="full-editor-back"
          >
            <ArrowLeft className="size-4" />
            Back to Prompts
          </button>
          <span className="text-sm font-medium text-text">{title}</span>
          {lastSaved && (
            <span className="text-xs text-text-muted">
              Draft saved {formatDraftAge(lastSaved)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleRequestClose}
            className="rounded px-3 py-1.5 text-sm text-text-muted hover:bg-surface2"
            data-testid="full-editor-cancel"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => form.submit()}
            disabled={isLoading}
            className="flex items-center gap-1 rounded bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primaryStrong disabled:opacity-50"
            data-testid="full-editor-save"
          >
            <Save className="size-3.5" />
            {isLoading ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      {/* Two-column layout */}
      <div className="flex flex-1 min-h-0">
        {/* Editor column */}
        <div className="flex-[55] overflow-y-auto border-r border-border p-6">
          <Form
            form={form}
            layout="vertical"
            onFinish={handleFinish}
            onValuesChange={() => setDirty(true)}
            className="mx-auto max-w-2xl space-y-6"
          >
            {/* Identity section */}
            <div>
              <h3 className="mb-3 text-sm font-semibold text-text">Identity</h3>
              <div className="grid grid-cols-2 gap-4">
                <Form.Item
                  name="name"
                  label="Title"
                  rules={[{ required: true, message: "Title is required" }]}
                >
                  <Input
                    placeholder="e.g. Code Review Assistant"
                    data-testid="full-editor-name"
                  />
                </Form.Item>
                <Form.Item name="author" label="Author">
                  <Input placeholder="Optional" data-testid="full-editor-author" />
                </Form.Item>
              </div>
            </div>

            {/* Prompt Content */}
            <div>
              <h3 className="mb-3 text-sm font-semibold text-text">
                Prompt Content
              </h3>
              <Form.Item
                name="system_prompt"
                label="AI Instructions (System Prompt)"
                rules={[{ validator: templateFieldValidator }]}
              >
                <TextArea
                  autoSize={{ minRows: 6, maxRows: 30 }}
                  placeholder="You are a helpful assistant that..."
                  data-testid="full-editor-system-prompt"
                />
              </Form.Item>
              <div className="mb-4 -mt-2">{tokenLabel(systemPromptValue.length, sysBudget)}</div>

              <Form.Item
                name="user_prompt"
                label="Message Template (User Prompt)"
                rules={[{ validator: templateFieldValidator }]}
              >
                <TextArea
                  autoSize={{ minRows: 4, maxRows: 20 }}
                  placeholder="Analyze the following: {{input}}"
                  data-testid="full-editor-user-prompt"
                />
              </Form.Item>
              <div className="-mt-2">{tokenLabel(userPromptValue.length, userBudget)}</div>
            </div>

            {/* Organization */}
            <div>
              <h3 className="mb-3 text-sm font-semibold text-text">
                Organization
              </h3>
              <Form.Item name="keywords" label="Tags">
                <Select
                  mode="tags"
                  placeholder="Add tags..."
                  options={allTags.map((t) => ({ label: t, value: t }))}
                  data-testid="full-editor-keywords"
                />
              </Form.Item>
              <Form.Item name="details" label="Notes">
                <TextArea
                  autoSize={{ minRows: 2, maxRows: 6 }}
                  placeholder="Internal notes about this prompt..."
                  data-testid="full-editor-details"
                />
              </Form.Item>
            </div>

            {/* Advanced (collapsed) */}
            <Collapse
              ghost
              items={[
                {
                  key: "advanced",
                  label: (
                    <span className="text-sm font-medium text-text-muted">
                      Advanced
                    </span>
                  ),
                  children: (
                    <div className="space-y-4">
                      <Form.Item
                        name="changeDescription"
                        label="Change Description"
                      >
                        <Input placeholder="What changed in this version?" />
                      </Form.Item>
                    </div>
                  ),
                },
              ]}
            />
          </Form>
        </div>

        {/* Preview column - desktop */}
        <div className="hidden flex-[45] md:flex flex-col bg-surface">
          <PromptEditorPreview
            systemPrompt={systemPromptValue}
            userPrompt={userPromptValue}
          />
        </div>
      </div>

      {/* Mobile preview toggle */}
      <div className="md:hidden">
        <button
          type="button"
          onClick={() => setShowMobilePreview(!showMobilePreview)}
          className="fixed bottom-4 right-4 z-50 rounded-full bg-primary px-4 py-2 text-sm font-medium text-white shadow-lg"
        >
          {showMobilePreview ? "Editor" : "Preview"}
        </button>
        {showMobilePreview && (
          <div className="fixed inset-0 z-40 bg-background pt-12">
            <PromptEditorPreview
              systemPrompt={systemPromptValue}
              userPrompt={userPromptValue}
            />
          </div>
        )}
      </div>
    </div>
  )
}
