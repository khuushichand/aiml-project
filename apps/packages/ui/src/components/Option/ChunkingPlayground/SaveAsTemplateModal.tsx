import React, { useState, useMemo } from "react"
import { useTranslation } from "react-i18next"
import {
  Modal,
  Form,
  Input,
  Select,
  InputNumber,
  Collapse,
  Typography,
  Space,
  Alert
} from "antd"
import { useQueryClient } from "@tanstack/react-query"

import { useAntdMessage } from "@/hooks/useAntdMessage"
import {
  createChunkingTemplate,
  type ChunkingOptions,
  type TemplateConfig
} from "@/services/chunking"

const { TextArea } = Input
const { Text } = Typography

interface SaveAsTemplateModalProps {
  open: boolean
  onClose: () => void
  chunkingOptions: ChunkingOptions
}

const MEDIA_TYPE_OPTIONS = [
  { value: "video", label: "Video" },
  { value: "audio", label: "Audio" },
  { value: "pdf", label: "PDF" },
  { value: "document", label: "Document" },
  { value: "epub", label: "EPUB" },
  { value: "html", label: "HTML" },
  { value: "markdown", label: "Markdown" },
  { value: "text", label: "Text" },
  { value: "code", label: "Code" }
]

export const SaveAsTemplateModal: React.FC<SaveAsTemplateModalProps> = ({
  open,
  onClose,
  chunkingOptions
}) => {
  const { t } = useTranslation(["settings", "common"])
  const message = useAntdMessage()
  const queryClient = useQueryClient()

  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [tags, setTags] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Classifier options
  const [mediaTypes, setMediaTypes] = useState<string[]>([])
  const [filenamePattern, setFilenamePattern] = useState("")
  const [titlePattern, setTitlePattern] = useState("")
  const [priority, setPriority] = useState<number | null>(null)

  const templateConfig: TemplateConfig = useMemo(() => {
    const chunking: Record<string, any> = {}

    if (chunkingOptions.method) chunking.method = chunkingOptions.method
    if (chunkingOptions.max_size != null) chunking.max_size = chunkingOptions.max_size
    if (chunkingOptions.overlap != null) chunking.overlap = chunkingOptions.overlap
    if (chunkingOptions.language) chunking.language = chunkingOptions.language
    if (chunkingOptions.tokenizer_name_or_path) {
      chunking.tokenizer_name_or_path = chunkingOptions.tokenizer_name_or_path
    }
    if (chunkingOptions.adaptive) chunking.adaptive = chunkingOptions.adaptive
    if (chunkingOptions.multi_level) chunking.multi_level = chunkingOptions.multi_level
    if (chunkingOptions.code_mode) chunking.code_mode = chunkingOptions.code_mode
    if (chunkingOptions.semantic_similarity_threshold != null) {
      chunking.semantic_similarity_threshold = chunkingOptions.semantic_similarity_threshold
    }
    if (chunkingOptions.semantic_overlap_sentences != null) {
      chunking.semantic_overlap_sentences = chunkingOptions.semantic_overlap_sentences
    }
    if (chunkingOptions.custom_chapter_pattern) {
      chunking.custom_chapter_pattern = chunkingOptions.custom_chapter_pattern
    }
    if (chunkingOptions.json_chunkable_data_key) {
      chunking.json_chunkable_data_key = chunkingOptions.json_chunkable_data_key
    }
    if (chunkingOptions.enable_frontmatter_parsing != null) {
      chunking.enable_frontmatter_parsing = chunkingOptions.enable_frontmatter_parsing
    }
    if (chunkingOptions.frontmatter_sentinel_key) {
      chunking.frontmatter_sentinel_key = chunkingOptions.frontmatter_sentinel_key
    }
    if (chunkingOptions.summarization_detail != null) {
      chunking.summarization_detail = chunkingOptions.summarization_detail
    }
    if (chunkingOptions.proposition_engine) {
      chunking.proposition_engine = chunkingOptions.proposition_engine
    }
    if (chunkingOptions.proposition_aggressiveness != null) {
      chunking.proposition_aggressiveness = chunkingOptions.proposition_aggressiveness
    }
    if (chunkingOptions.proposition_min_proposition_length != null) {
      chunking.proposition_min_proposition_length = chunkingOptions.proposition_min_proposition_length
    }
    if (chunkingOptions.proposition_prompt_profile) {
      chunking.proposition_prompt_profile = chunkingOptions.proposition_prompt_profile
    }
    if (chunkingOptions.llm_options_for_internal_steps) {
      chunking.llm_options_for_internal_steps = chunkingOptions.llm_options_for_internal_steps
    }

    const config: TemplateConfig = { chunking }

    // Add classifier if any classifier options are set
    const hasClassifier = mediaTypes.length > 0 || filenamePattern.trim() || titlePattern.trim() || priority != null
    if (hasClassifier) {
      const classifier: Record<string, any> = {}
      if (mediaTypes.length > 0) classifier.media_types = mediaTypes
      if (filenamePattern.trim()) classifier.filename_pattern = filenamePattern.trim()
      if (titlePattern.trim()) classifier.title_pattern = titlePattern.trim()
      if (priority != null) classifier.priority = priority
      config.classifier = classifier
    }

    return config
  }, [chunkingOptions, mediaTypes, filenamePattern, titlePattern, priority])

  const handleSave = async () => {
    if (!name.trim()) {
      message.error(
        t(
          "settings:chunkingPlayground.templates.nameRequired",
          "Template name is required."
        )
      )
      return
    }

    setSaving(true)
    setError(null)

    try {
      await createChunkingTemplate({
        name: name.trim(),
        description: description.trim() || undefined,
        tags: tags.length > 0 ? tags : undefined,
        template: templateConfig
      })

      // Invalidate template queries to refresh lists
      await queryClient.invalidateQueries({ queryKey: ["chunking-templates"] })

      message.success(
        t(
          "settings:chunkingPlayground.saveAsTemplate.success",
          "Template saved successfully"
        )
      )

      // Reset form and close
      resetForm()
      onClose()
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Failed to save template"
      setError(errorMsg)
      message.error(errorMsg)
    } finally {
      setSaving(false)
    }
  }

  const resetForm = () => {
    setName("")
    setDescription("")
    setTags([])
    setMediaTypes([])
    setFilenamePattern("")
    setTitlePattern("")
    setPriority(null)
    setError(null)
  }

  const handleCancel = () => {
    resetForm()
    onClose()
  }

  return (
    <Modal
      title={t(
        "settings:chunkingPlayground.saveAsTemplate.title",
        "Save as Template"
      )}
      open={open}
      onOk={handleSave}
      onCancel={handleCancel}
      confirmLoading={saving}
      okText={t("common:save", "Save")}
      cancelText={t("common:cancel", "Cancel")}
      width={600}
      destroyOnHidden
    >
      <div className="space-y-4">
        {error && (
          <Alert
            type="error"
            title={error}
            closable
            onClose={() => setError(null)}
          />
        )}

        <Form layout="vertical" size="small">
          <Form.Item
            label={t(
              "settings:chunkingPlayground.saveAsTemplate.nameLabel",
              "Template Name"
            )}
            required
          >
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t(
                "settings:chunkingPlayground.saveAsTemplate.namePlaceholder",
                "e.g., my-custom-chunking"
              )}
              maxLength={100}
            />
          </Form.Item>

          <Form.Item
            label={t(
              "settings:chunkingPlayground.saveAsTemplate.descriptionLabel",
              "Description"
            )}
          >
            <TextArea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t(
                "settings:chunkingPlayground.saveAsTemplate.descriptionPlaceholder",
                "Optional description of what this template is for..."
              )}
              rows={2}
              maxLength={500}
            />
          </Form.Item>

          <Form.Item
            label={t(
              "settings:chunkingPlayground.saveAsTemplate.tagsLabel",
              "Tags"
            )}
          >
            <Select
              mode="tags"
              value={tags}
              onChange={setTags}
              placeholder={t(
                "settings:chunkingPlayground.saveAsTemplate.tagsPlaceholder",
                "Add tags to organize templates"
              )}
              tokenSeparators={[","]}
            />
          </Form.Item>
        </Form>

        <Collapse
          ghost
          items={[
            {
              key: "classifier",
              label: t(
                "settings:chunkingPlayground.saveAsTemplate.classifierTitle",
                "Auto-match Classifier (Advanced)"
              ),
              children: (
                <div className="space-y-3">
                  <Text type="secondary" className="text-xs">
                    {t(
                      "settings:chunkingPlayground.saveAsTemplate.classifierDescription",
                      "Configure rules to automatically match this template to content during ingest."
                    )}
                  </Text>

                  <Form layout="vertical" size="small">
                    <Form.Item
                      label={t(
                        "settings:chunkingPlayground.saveAsTemplate.mediaTypesLabel",
                        "Media Types"
                      )}
                    >
                      <Select
                        mode="multiple"
                        value={mediaTypes}
                        onChange={setMediaTypes}
                        options={MEDIA_TYPE_OPTIONS}
                        placeholder={t(
                          "settings:chunkingPlayground.saveAsTemplate.mediaTypesPlaceholder",
                          "Select media types this template should match"
                        )}
                      />
                    </Form.Item>

                    <Form.Item
                      label={t(
                        "settings:chunkingPlayground.saveAsTemplate.filenamePatternLabel",
                        "Filename Pattern (Regex)"
                      )}
                    >
                      <Input
                        value={filenamePattern}
                        onChange={(e) => setFilenamePattern(e.target.value)}
                        placeholder={t(
                          "settings:chunkingPlayground.saveAsTemplate.filenamePatternPlaceholder",
                          "e.g., .*\\.pdf$"
                        )}
                      />
                    </Form.Item>

                    <Form.Item
                      label={t(
                        "settings:chunkingPlayground.saveAsTemplate.titlePatternLabel",
                        "Title Pattern (Regex)"
                      )}
                    >
                      <Input
                        value={titlePattern}
                        onChange={(e) => setTitlePattern(e.target.value)}
                        placeholder={t(
                          "settings:chunkingPlayground.saveAsTemplate.titlePatternPlaceholder",
                          "e.g., ^Meeting Notes.*"
                        )}
                      />
                    </Form.Item>

                    <Form.Item
                      label={t(
                        "settings:chunkingPlayground.saveAsTemplate.priorityLabel",
                        "Priority"
                      )}
                    >
                      <Space orientation="vertical" size={4} className="w-full">
                        <InputNumber
                          value={priority}
                          onChange={(v) => setPriority(v)}
                          min={0}
                          max={100}
                          className="w-full"
                          placeholder="0"
                        />
                        <Text type="secondary" className="text-xs">
                          {t(
                            "settings:chunkingPlayground.saveAsTemplate.priorityHint",
                            "Higher priority templates are matched first (default: 0)"
                          )}
                        </Text>
                      </Space>
                    </Form.Item>
                  </Form>
                </div>
              )
            },
            {
              key: "preview",
              label: t(
                "settings:chunkingPlayground.saveAsTemplate.previewTitle",
                "Settings Preview"
              ),
              children: (
                <pre className="text-xs bg-surface2 rounded p-2 overflow-x-auto max-h-64">
                  {JSON.stringify(templateConfig, null, 2)}
                </pre>
              )
            }
          ]}
        />
      </div>
    </Modal>
  )
}

export default SaveAsTemplateModal
