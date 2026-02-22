import React, { useCallback, useMemo, useState } from "react"
import { useTranslation } from "react-i18next"
import {
  Alert,
  Button,
  Card,
  Collapse,
  Divider,
  Form,
  Input,
  InputNumber,
  Popconfirm,
  Segmented,
  Select,
  Space,
  Switch,
  Tabs,
  Tag,
  Typography
} from "antd"
import { useQuery } from "@tanstack/react-query"

import { useAntdMessage } from "@/hooks/useAntdMessage"
import {
  applyChunkingTemplate,
  createChunkingTemplate,
  deleteChunkingTemplate,
  getChunkingCapabilities,
  getChunkingTemplateDiagnostics,
  learnChunkingTemplate,
  listChunkingTemplates,
  matchChunkingTemplates,
  updateChunkingTemplate,
  validateChunkingTemplate,
  type ApplyTemplateResponse,
  type ChunkingCapabilities,
  type ChunkingTemplateResponse,
  type TemplateDiagnosticsResponse,
  type TemplateConfig,
  type TemplateLearnResponse,
  type TemplateMatchResponse,
  type TemplateValidationResponse
} from "@/services/chunking"
import { getLanguageOptions } from "./constants"

const { TextArea } = Input
const { Text, Title } = Typography

const parseJson = (raw: string) => {
  if (!raw.trim()) return { value: undefined, error: null }
  try {
    return { value: JSON.parse(raw), error: null }
  } catch (err) {
    return { value: null, error: err instanceof Error ? err.message : String(err) }
  }
}

const formatJson = (value: unknown) => JSON.stringify(value, null, 2)

export const ChunkingTemplatesPanel: React.FC = () => {
  const { t } = useTranslation(["settings", "common"])
  const message = useAntdMessage()

  const [activeTab, setActiveTab] = useState("browse")

  const [includeBuiltin, setIncludeBuiltin] = useState(true)
  const [includeCustom, setIncludeCustom] = useState(true)
  const [tagFilters, setTagFilters] = useState<string[]>([])
  const [userIdFilter, setUserIdFilter] = useState("")
  const [hardDelete, setHardDelete] = useState(false)

  const [selectedTemplateName, setSelectedTemplateName] = useState("")

  const [editorName, setEditorName] = useState("")
  const [editorDescription, setEditorDescription] = useState("")
  const [editorTags, setEditorTags] = useState<string[]>([])
  const [editorUserId, setEditorUserId] = useState("")
  const [editorTemplateJson, setEditorTemplateJson] = useState("")
  const [editorResponse, setEditorResponse] =
    useState<ChunkingTemplateResponse | null>(null)

  // Form vs JSON editor mode
  const [editorMode, setEditorMode] = useState<"form" | "json">("form")

  // Form-mode state for chunking options
  const [formMethod, setFormMethod] = useState("words")
  const [formMaxSize, setFormMaxSize] = useState<number | null>(400)
  const [formOverlap, setFormOverlap] = useState<number | null>(0)
  const [formLanguage, setFormLanguage] = useState("en")
  const [formTokenizer, setFormTokenizer] = useState("")
  const [formAdaptive, setFormAdaptive] = useState(false)
  const [formMultiLevel, setFormMultiLevel] = useState(false)
  const [formCodeMode, setFormCodeMode] = useState<"auto" | "ast" | "heuristic">("auto")
  const [formSemanticThreshold, setFormSemanticThreshold] = useState<number | null>(null)
  const [formSemanticOverlap, setFormSemanticOverlap] = useState<number | null>(null)
  const [formJsonDataKey, setFormJsonDataKey] = useState("")
  const [formFrontmatterParsing, setFormFrontmatterParsing] = useState(true)
  const [formFrontmatterKey, setFormFrontmatterKey] = useState("")
  const [formCustomChapterPattern, setFormCustomChapterPattern] = useState("")
  const [formSummarizationDetail, setFormSummarizationDetail] = useState<number | null>(null)
  const [formPropositionEngine, setFormPropositionEngine] = useState("")
  const [formPropositionAggressiveness, setFormPropositionAggressiveness] = useState<number | null>(null)
  const [formPropositionMinLength, setFormPropositionMinLength] = useState<number | null>(null)
  const [formPropositionPromptProfile, setFormPropositionPromptProfile] = useState("")

  const [applyTemplateName, setApplyTemplateName] = useState("")
  const [applyText, setApplyText] = useState("")
  const [applyOverrideOptions, setApplyOverrideOptions] = useState("")
  const [applyIncludeMetadata, setApplyIncludeMetadata] = useState(false)
  const [applyResponse, setApplyResponse] =
    useState<ApplyTemplateResponse | null>(null)

  const [validateJson, setValidateJson] = useState("")
  const [validateResponse, setValidateResponse] =
    useState<TemplateValidationResponse | null>(null)

  const [matchMediaType, setMatchMediaType] = useState("")
  const [matchTitle, setMatchTitle] = useState("")
  const [matchUrl, setMatchUrl] = useState("")
  const [matchFilename, setMatchFilename] = useState("")
  const [matchResponse, setMatchResponse] =
    useState<TemplateMatchResponse | null>(null)

  const [learnName, setLearnName] = useState("")
  const [learnExampleText, setLearnExampleText] = useState("")
  const [learnDescription, setLearnDescription] = useState("")
  const [learnSave, setLearnSave] = useState(false)
  const [learnClassifierJson, setLearnClassifierJson] = useState("")
  const [learnResponse, setLearnResponse] =
    useState<TemplateLearnResponse | null>(null)

  const [diagnosticsResponse, setDiagnosticsResponse] =
    useState<TemplateDiagnosticsResponse | null>(null)

  const {
    data: templateList,
    isLoading: templateLoading,
    error: templateError,
    refetch: refetchTemplates
  } = useQuery({
    queryKey: [
      "chunking-templates",
      includeBuiltin,
      includeCustom,
      tagFilters,
      userIdFilter
    ],
    queryFn: () =>
      listChunkingTemplates({
        includeBuiltin,
        includeCustom,
        tags: tagFilters.length ? tagFilters : undefined,
        userId: userIdFilter || undefined
      }),
    staleTime: 60 * 1000
  })

  // Fetch capabilities for method options
  const { data: capabilities } = useQuery<ChunkingCapabilities>({
    queryKey: ["chunking-capabilities"],
    queryFn: getChunkingCapabilities,
    staleTime: 5 * 60 * 1000
  })

  const templates = templateList?.templates ?? []
  const selectedTemplate = templates.find(
    (template) => template.name === selectedTemplateName
  )

  const templateOptions = useMemo(
    () =>
      templates.map((template) => ({
        value: template.name,
        label: template.name
      })),
    [templates]
  )

  const methodOptions = useMemo(() => {
    if (!capabilities?.methods) {
      return [
        { value: "words", label: "Words" },
        { value: "sentences", label: "Sentences" },
        { value: "paragraphs", label: "Paragraphs" },
        { value: "tokens", label: "Tokens" },
        { value: "semantic", label: "Semantic" },
        { value: "code", label: "Code" }
      ]
    }
    return capabilities.methods.map((m) => ({
      value: m,
      label: m.charAt(0).toUpperCase() + m.slice(1).replace(/_/g, " ")
    }))
  }, [capabilities])

  const languageOptions = useMemo(() => getLanguageOptions(t), [t])

  const codeModeOptions = useMemo(() => {
    const available =
      capabilities?.method_specific_options?.code?.code_mode ?? [
        "auto",
        "ast",
        "heuristic"
      ]
    return available.map((mode) => ({
      value: mode,
      label: mode.toUpperCase()
    }))
  }, [capabilities])

  const propositionEngineOptions = useMemo(
    () => [
      { value: "", label: t("common:default", "Default") },
      { value: "heuristic", label: "Heuristic" },
      { value: "spacy", label: "SpaCy" },
      { value: "llm", label: "LLM" },
      { value: "auto", label: "Auto" }
    ],
    [t]
  )

  const propositionPromptOptions = useMemo(
    () => [
      { value: "", label: t("common:default", "Default") },
      { value: "generic", label: "Generic" },
      { value: "claimify", label: "Claimify" },
      { value: "gemma_aps", label: "Gemma APS" }
    ],
    [t]
  )

  // Build template config from form state
  const buildTemplateConfigFromForm = useCallback((): TemplateConfig => {
    const chunking: Record<string, any> = {
      method: formMethod
    }

    if (formMaxSize != null) chunking.max_size = formMaxSize
    if (formOverlap != null) chunking.overlap = formOverlap
    if (formLanguage && formLanguage !== "auto") chunking.language = formLanguage
    if (formTokenizer.trim()) chunking.tokenizer_name_or_path = formTokenizer.trim()
    if (formAdaptive) chunking.adaptive = formAdaptive
    if (formMultiLevel) chunking.multi_level = formMultiLevel
    if (formMethod === "code" && formCodeMode) chunking.code_mode = formCodeMode
    if (formSemanticThreshold != null) chunking.semantic_similarity_threshold = formSemanticThreshold
    if (formSemanticOverlap != null) chunking.semantic_overlap_sentences = formSemanticOverlap
    if (formJsonDataKey.trim()) chunking.json_chunkable_data_key = formJsonDataKey.trim()
    if (!formFrontmatterParsing) chunking.enable_frontmatter_parsing = false
    if (formFrontmatterKey.trim()) chunking.frontmatter_sentinel_key = formFrontmatterKey.trim()
    if (formCustomChapterPattern.trim()) chunking.custom_chapter_pattern = formCustomChapterPattern.trim()
    if (formSummarizationDetail != null) chunking.summarization_detail = formSummarizationDetail
    if (formPropositionEngine) chunking.proposition_engine = formPropositionEngine
    if (formPropositionAggressiveness != null) chunking.proposition_aggressiveness = formPropositionAggressiveness
    if (formPropositionMinLength != null) chunking.proposition_min_proposition_length = formPropositionMinLength
    if (formPropositionPromptProfile) chunking.proposition_prompt_profile = formPropositionPromptProfile

    return { chunking }
  }, [
    formMethod,
    formMaxSize,
    formOverlap,
    formLanguage,
    formTokenizer,
    formAdaptive,
    formMultiLevel,
    formCodeMode,
    formSemanticThreshold,
    formSemanticOverlap,
    formJsonDataKey,
    formFrontmatterParsing,
    formFrontmatterKey,
    formCustomChapterPattern,
    formSummarizationDetail,
    formPropositionEngine,
    formPropositionAggressiveness,
    formPropositionMinLength,
    formPropositionPromptProfile
  ])

  // Load template config into form state
  const loadConfigIntoForm = useCallback((config: TemplateConfig) => {
    const chunking = config.chunking || {}

    setFormMethod(chunking.method ?? "words")
    setFormMaxSize(chunking.max_size ?? 400)
    setFormOverlap(chunking.overlap ?? 0)
    setFormLanguage(chunking.language ?? "en")
    setFormTokenizer(chunking.tokenizer_name_or_path ?? "")
    setFormAdaptive(Boolean(chunking.adaptive))
    setFormMultiLevel(Boolean(chunking.multi_level))
    setFormCodeMode(chunking.code_mode ?? "auto")
    setFormSemanticThreshold(chunking.semantic_similarity_threshold ?? null)
    setFormSemanticOverlap(chunking.semantic_overlap_sentences ?? null)
    setFormJsonDataKey(chunking.json_chunkable_data_key ?? "")
    setFormFrontmatterParsing(chunking.enable_frontmatter_parsing !== false)
    setFormFrontmatterKey(chunking.frontmatter_sentinel_key ?? "")
    setFormCustomChapterPattern(chunking.custom_chapter_pattern ?? "")
    setFormSummarizationDetail(chunking.summarization_detail ?? null)
    setFormPropositionEngine(chunking.proposition_engine ?? "")
    setFormPropositionAggressiveness(chunking.proposition_aggressiveness ?? null)
    setFormPropositionMinLength(chunking.proposition_min_proposition_length ?? null)
    setFormPropositionPromptProfile(chunking.proposition_prompt_profile ?? "")
  }, [])

  // Sync JSON to form when switching to form mode
  const syncJsonToForm = useCallback(() => {
    const parsed = parseJson(editorTemplateJson)
    if (parsed.value && !parsed.error) {
      loadConfigIntoForm(parsed.value as TemplateConfig)
    }
  }, [editorTemplateJson, loadConfigIntoForm])

  // Sync form to JSON when switching to JSON mode
  const syncFormToJson = useCallback(() => {
    const config = buildTemplateConfigFromForm()
    setEditorTemplateJson(formatJson(config))
  }, [buildTemplateConfigFromForm])

  // Handle editor mode change
  const handleEditorModeChange = useCallback(
    (mode: "form" | "json") => {
      if (mode === "form" && editorMode === "json") {
        syncJsonToForm()
      } else if (mode === "json" && editorMode === "form") {
        syncFormToJson()
      }
      setEditorMode(mode)
    },
    [editorMode, syncJsonToForm, syncFormToJson]
  )

  // Get current template config (from form or JSON based on mode)
  const getCurrentTemplateConfig = useCallback((): TemplateConfig | null => {
    if (editorMode === "form") {
      return buildTemplateConfigFromForm()
    } else {
      const parsed = parseJson(editorTemplateJson)
      if (parsed.error || !parsed.value) return null
      return parsed.value as TemplateConfig
    }
  }, [editorMode, buildTemplateConfigFromForm, editorTemplateJson])

  const loadTemplateIntoEditor = useCallback(
    (template: ChunkingTemplateResponse, asCopy = false) => {
      const name = asCopy ? `${template.name} (Copy)` : template.name
      setEditorName(name)
      setEditorDescription(template.description ?? "")
      setEditorTags(template.tags ?? [])
      setEditorUserId(template.user_id ? String(template.user_id) : "")
      try {
        const parsed = JSON.parse(template.template_json)
        setEditorTemplateJson(formatJson(parsed))
        // Also load into form state
        loadConfigIntoForm(parsed as TemplateConfig)
      } catch {
        setEditorTemplateJson(template.template_json)
      }
      setEditorResponse(null)
      setActiveTab("editor")
    },
    [loadConfigIntoForm]
  )

  const duplicateTemplate = useCallback(
    (template: ChunkingTemplateResponse) => {
      loadTemplateIntoEditor(template, true)
      message.success(
        t(
          "settings:chunkingPlayground.templates.duplicated",
          "Template duplicated. Update the name and save."
        )
      )
    },
    [loadTemplateIntoEditor, message, t]
  )

  const handleCreate = async () => {
    if (!editorName.trim()) {
      message.error(
        t(
          "settings:chunkingPlayground.templates.nameRequired",
          "Template name is required."
        )
      )
      return
    }

    const templateConfig = getCurrentTemplateConfig()
    if (!templateConfig) {
      message.error(
        t("settings:chunkingPlayground.templates.jsonError", "Invalid JSON. Please fix and try again.")
      )
      return
    }

    try {
      const response = await createChunkingTemplate({
        name: editorName.trim(),
        description: editorDescription.trim() || undefined,
        tags: editorTags.length ? editorTags : undefined,
        user_id: editorUserId.trim() || undefined,
        template: templateConfig
      })
      setEditorResponse(response)
      await refetchTemplates()
      message.success(t("common:create", "Create"))
    } catch (err: unknown) {
      message.error(err instanceof Error ? err.message : "Create failed")
    }
  }

  const handleUpdate = async () => {
    if (!editorName.trim()) {
      message.error(
        t(
          "settings:chunkingPlayground.templates.nameRequired",
          "Template name is required."
        )
      )
      return
    }

    const templateConfig = getCurrentTemplateConfig()
    if (!templateConfig) {
      message.error(
        t("settings:chunkingPlayground.templates.jsonError", "Invalid JSON. Please fix and try again.")
      )
      return
    }

    try {
      const response = await updateChunkingTemplate(editorName.trim(), {
        description: editorDescription.trim() || undefined,
        tags: editorTags.length ? editorTags : undefined,
        template: templateConfig
      })
      setEditorResponse(response)
      await refetchTemplates()
      message.success(
        t("settings:chunkingPlayground.templates.updateAction", "Update")
      )
    } catch (err: unknown) {
      message.error(err instanceof Error ? err.message : "Update failed")
    }
  }

  const handleDelete = async () => {
    if (!selectedTemplateName.trim()) return
    try {
      await deleteChunkingTemplate(selectedTemplateName.trim(), hardDelete)
      await refetchTemplates()
      setSelectedTemplateName("")
      message.success(t("common:delete", "Delete"))
    } catch (err: unknown) {
      message.error(err instanceof Error ? err.message : "Delete failed")
    }
  }

  const handleApply = async () => {
    if (!applyTemplateName.trim() || !applyText.trim()) {
      message.error(t("settings:chunkingPlayground.noInput", "Please provide text to chunk"))
      return
    }
    const parsed = parseJson(applyOverrideOptions)
    if (parsed.error) {
      message.error(
        t("settings:chunkingPlayground.templates.jsonError", "Invalid JSON. Please fix and try again.")
      )
      return
    }

    try {
      const payload: {
        template_name: string
        text: string
        override_options?: Record<string, any>
      } = {
        template_name: applyTemplateName.trim(),
        text: applyText
      }
      if (parsed.value !== undefined) {
        payload.override_options = parsed.value
      }
      const response = await applyChunkingTemplate(payload, applyIncludeMetadata)
      setApplyResponse(response)
      message.success(
        t("settings:chunkingPlayground.templates.applyAction", "Apply")
      )
    } catch (err: unknown) {
      message.error(err instanceof Error ? err.message : "Apply failed")
    }
  }

  const handleValidate = async () => {
    const parsed = parseJson(validateJson)
    if (parsed.error || !parsed.value) {
      message.error(
        t("settings:chunkingPlayground.templates.jsonError", "Invalid JSON. Please fix and try again.")
      )
      return
    }

    try {
      const response = await validateChunkingTemplate(parsed.value)
      setValidateResponse(response)
      message.success(
        t("settings:chunkingPlayground.templates.validateAction", "Validate")
      )
    } catch (err: unknown) {
      message.error(err instanceof Error ? err.message : "Validate failed")
    }
  }

  const handleMatch = async () => {
    try {
      const response = await matchChunkingTemplates({
        mediaType: matchMediaType.trim() || undefined,
        title: matchTitle.trim() || undefined,
        url: matchUrl.trim() || undefined,
        filename: matchFilename.trim() || undefined
      })
      setMatchResponse(response)
      message.success(
        t("settings:chunkingPlayground.templates.matchAction", "Match")
      )
    } catch (err: unknown) {
      message.error(err instanceof Error ? err.message : "Match failed")
    }
  }

  const handleLearn = async () => {
    if (!learnName.trim()) {
      message.error(
        t(
          "settings:chunkingPlayground.templates.nameRequired",
          "Template name is required."
        )
      )
      return
    }
    const parsed = parseJson(learnClassifierJson)
    if (parsed.error) {
      message.error(
        t("settings:chunkingPlayground.templates.jsonError", "Invalid JSON. Please fix and try again.")
      )
      return
    }

    try {
      const response = await learnChunkingTemplate({
        name: learnName.trim(),
        example_text: learnExampleText.trim() || undefined,
        description: learnDescription.trim() || undefined,
        save: learnSave,
        classifier: parsed.value
      })
      setLearnResponse(response)
      if (learnSave) await refetchTemplates()
      message.success(
        t("settings:chunkingPlayground.templates.learnAction", "Learn")
      )
    } catch (err: unknown) {
      message.error(err instanceof Error ? err.message : "Learn failed")
    }
  }

  const handleDiagnostics = async () => {
    try {
      const response = await getChunkingTemplateDiagnostics()
      setDiagnosticsResponse(response)
      message.success(
        t(
          "settings:chunkingPlayground.templates.diagnosticsAction",
          "Run diagnostics"
        )
      )
    } catch (err: unknown) {
      message.error(err instanceof Error ? err.message : "Diagnostics failed")
    }
  }

  const renderResponse = (value: unknown) => {
    if (!value) {
      return <Text type="secondary">{t("common:noData", "No data")}</Text>
    }
    return (
      <pre className="text-xs bg-surface2 rounded p-2 overflow-x-auto">
        {formatJson(value)}
      </pre>
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <Title level={4} className="mb-1">
          {t(
            "settings:chunkingPlayground.templates.title",
            "Chunking Templates"
          )}
        </Title>
        <Text type="secondary">
          {t(
            "settings:chunkingPlayground.templates.description",
            "Manage, validate, and apply chunking templates."
          )}
        </Text>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: "browse",
            label: t(
              "settings:chunkingPlayground.templates.tabBrowse",
              "Browse"
            ),
            children: (
              <Card size="small">
                <Form layout="vertical" size="small">
                  <Form.Item
                    label={t(
                      "settings:chunkingPlayground.templates.filtersTitle",
                      "Filters"
                    )}>
                    <Space orientation="vertical" size={8} className="w-full">
                      <div className="flex items-center justify-between">
                        <Text>
                          {t(
                            "settings:chunkingPlayground.templates.includeBuiltin",
                            "Include built-in"
                          )}
                        </Text>
                        <Switch
                          checked={includeBuiltin}
                          onChange={setIncludeBuiltin}
                        />
                      </div>
                      <div className="flex items-center justify-between">
                        <Text>
                          {t(
                            "settings:chunkingPlayground.templates.includeCustom",
                            "Include custom"
                          )}
                        </Text>
                        <Switch
                          checked={includeCustom}
                          onChange={setIncludeCustom}
                        />
                      </div>
                      <Select
                        mode="tags"
                        value={tagFilters}
                        onChange={setTagFilters}
                        placeholder={t(
                          "settings:chunkingPlayground.templates.tagsPlaceholder",
                          "Add tags"
                        )}
                      />
                      <Input
                        value={userIdFilter}
                        onChange={(e) => setUserIdFilter(e.target.value)}
                        placeholder={t(
                          "settings:chunkingPlayground.templates.userIdLabel",
                          "User ID"
                        )}
                      />
                      <Button
                        size="small"
                        onClick={() => refetchTemplates()}
                        loading={templateLoading}>
                        {t("common:refresh", "Refresh")}
                      </Button>
                    </Space>
                  </Form.Item>
                </Form>

                {templateError && (
                  <Alert
                    type="warning"
                    showIcon
                    title={(templateError as Error)?.message}
                  />
                )}

                <Divider className="my-3" />

                <Form layout="vertical" size="small">
                  <Form.Item
                    label={t(
                      "settings:chunkingPlayground.templates.selectLabel",
                      "Template"
                    )}>
                    <Select
                      showSearch
                      value={selectedTemplateName || undefined}
                      onChange={setSelectedTemplateName}
                      options={templateOptions}
                      loading={templateLoading}
                      placeholder={t(
                        "settings:chunkingPlayground.templates.selectPlaceholder",
                        "Select a template"
                      )}
                      filterOption={(inputValue, option) =>
                        (option?.value ?? "")
                          .toString()
                          .toLowerCase()
                          .includes(inputValue.toLowerCase())
                      }
                    />
                  </Form.Item>
                </Form>

                {selectedTemplate ? (
                  <Card
                    size="small"
                    title={t(
                      "settings:chunkingPlayground.templates.detailsTitle",
                      "Template details"
                    )}
                    className="mt-3">
                    <Space orientation="vertical" size="small" className="w-full">
                      <div>
                        <Text strong>{selectedTemplate.name}</Text>
                      </div>
                      {selectedTemplate.description && (
                        <Text type="secondary">
                          {selectedTemplate.description}
                        </Text>
                      )}
                      <div className="flex flex-wrap gap-2">
                        {selectedTemplate.is_builtin && (
                          <Tag color="blue">
                            {t(
                              "settings:chunkingPlayground.templates.isBuiltin",
                              "Built-in"
                            )}
                          </Tag>
                        )}
                        <Tag>
                          {t(
                            "settings:chunkingPlayground.templates.version",
                            "Version"
                          )}
                          : {selectedTemplate.version}
                        </Tag>
                        {selectedTemplate.tags?.map((tag) => (
                          <Tag key={tag}>{tag}</Tag>
                        ))}
                      </div>
                      <Text type="secondary" className="text-xs">
                        {t(
                          "settings:chunkingPlayground.templates.updatedAt",
                          "Updated"
                        )}
                        : {selectedTemplate.updated_at}
                      </Text>
                      <pre className="text-xs bg-surface2 rounded p-2 overflow-x-auto">
                        {selectedTemplate.template_json}
                      </pre>
                      <Space wrap>
                        <Button
                          size="small"
                          onClick={() => loadTemplateIntoEditor(selectedTemplate)}>
                          {t(
                            "settings:chunkingPlayground.templates.loadIntoEditor",
                            "Load into editor"
                          )}
                        </Button>
                        <Button
                          size="small"
                          onClick={() => duplicateTemplate(selectedTemplate)}>
                          {t(
                            "settings:chunkingPlayground.templates.duplicate",
                            "Duplicate"
                          )}
                        </Button>
                        <Popconfirm
                          title={t(
                            "settings:chunkingPlayground.templates.deleteConfirm",
                            "Delete this template?"
                          )}
                          onConfirm={handleDelete}>
                          <Button danger size="small">
                            {t("common:delete", "Delete")}
                          </Button>
                        </Popconfirm>
                        <Space size="small">
                          <Text type="secondary" className="text-xs">
                            {t(
                              "settings:chunkingPlayground.templates.hardDeleteLabel",
                              "Hard delete"
                            )}
                          </Text>
                          <Switch
                            checked={hardDelete}
                            onChange={setHardDelete}
                          />
                        </Space>
                      </Space>
                    </Space>
                  </Card>
                ) : (
                  <Text type="secondary">
                    {t(
                      "settings:chunkingPlayground.templates.noSelection",
                      "Select a template to view details."
                    )}
                  </Text>
                )}
              </Card>
            )
          },
          {
            key: "editor",
            label: t(
              "settings:chunkingPlayground.templates.tabEditor",
              "Editor"
            ),
            children: (
              <Card size="small">
                <Form layout="vertical" size="small">
                  <Form.Item
                    label={t(
                      "settings:chunkingPlayground.templates.learnNameLabel",
                      "Template name"
                    )}>
                    <Input
                      value={editorName}
                      onChange={(e) => setEditorName(e.target.value)}
                    />
                  </Form.Item>

                  <Form.Item
                    label={t(
                      "settings:chunkingPlayground.templates.learnDescriptionLabel",
                      "Description"
                    )}>
                    <Input
                      value={editorDescription}
                      onChange={(e) => setEditorDescription(e.target.value)}
                    />
                  </Form.Item>

                  <Form.Item
                    label={t(
                      "settings:chunkingPlayground.templates.tagsLabel",
                      "Tags"
                    )}>
                    <Select
                      mode="tags"
                      value={editorTags}
                      onChange={setEditorTags}
                      placeholder={t(
                        "settings:chunkingPlayground.templates.tagsPlaceholder",
                        "Add tags"
                      )}
                    />
                  </Form.Item>

                  <Form.Item
                    label={t(
                      "settings:chunkingPlayground.templates.userIdLabel",
                      "User ID"
                    )}>
                    <Input
                      value={editorUserId}
                      onChange={(e) => setEditorUserId(e.target.value)}
                    />
                  </Form.Item>

                  <Divider className="my-2" />

                  <Form.Item
                    label={t(
                      "settings:chunkingPlayground.templates.editorMode",
                      "Editor mode"
                    )}>
                    <Segmented
                      value={editorMode}
                      onChange={(val) =>
                        handleEditorModeChange(val as "form" | "json")
                      }
                      options={[
                        {
                          value: "form",
                          label: t(
                            "settings:chunkingPlayground.templates.formMode",
                            "Form"
                          )
                        },
                        {
                          value: "json",
                          label: t(
                            "settings:chunkingPlayground.templates.jsonMode",
                            "JSON"
                          )
                        }
                      ]}
                    />
                  </Form.Item>

                  {editorMode === "form" ? (
                    <>
                      {/* Core Options */}
                      <Form.Item
                        label={t(
                          "settings:chunkingPlayground.method",
                          "Method"
                        )}>
                        <Select
                          value={formMethod}
                          onChange={setFormMethod}
                          options={methodOptions}
                        />
                      </Form.Item>

                      <div className="grid grid-cols-2 gap-2">
                        <Form.Item
                          label={t(
                            "settings:chunkingPlayground.maxSize",
                            "Max size"
                          )}>
                          <InputNumber
                            value={formMaxSize}
                            onChange={(val) => setFormMaxSize(val)}
                            min={1}
                            className="w-full"
                          />
                        </Form.Item>

                        <Form.Item
                          label={t(
                            "settings:chunkingPlayground.overlap",
                            "Overlap"
                          )}>
                          <InputNumber
                            value={formOverlap}
                            onChange={(val) => setFormOverlap(val)}
                            min={0}
                            className="w-full"
                          />
                        </Form.Item>
                      </div>

                      <Form.Item
                        label={t(
                          "settings:chunkingPlayground.language",
                          "Language"
                        )}>
                        <Select
                          value={formLanguage}
                          onChange={setFormLanguage}
                          options={languageOptions}
                          showSearch
                        />
                      </Form.Item>

                      <div className="flex items-center justify-between mb-4">
                        <Text>
                          {t(
                            "settings:chunkingPlayground.adaptive",
                            "Adaptive"
                          )}
                        </Text>
                        <Switch
                          checked={formAdaptive}
                          onChange={setFormAdaptive}
                        />
                      </div>

                      <div className="flex items-center justify-between mb-4">
                        <Text>
                          {t(
                            "settings:chunkingPlayground.multiLevel",
                            "Multi-level"
                          )}
                        </Text>
                        <Switch
                          checked={formMultiLevel}
                          onChange={setFormMultiLevel}
                        />
                      </div>

                      {/* Method-specific options */}
                      {formMethod === "code" && (
                        <Form.Item
                          label={t(
                            "settings:chunkingPlayground.codeMode",
                            "Code mode"
                          )}>
                          <Select
                            value={formCodeMode}
                            onChange={setFormCodeMode}
                            options={codeModeOptions}
                          />
                        </Form.Item>
                      )}

                      {/* Advanced Options */}
                      <Collapse
                        size="small"
                        items={[
                          {
                            key: "advanced",
                            label: t(
                              "settings:chunkingPlayground.advancedOptions",
                              "Advanced options"
                            ),
                            children: (
                              <Space
                                orientation="vertical"
                                size="small"
                                className="w-full">
                                <Form.Item
                                  label={t(
                                    "settings:chunkingPlayground.tokenizer",
                                    "Tokenizer"
                                  )}
                                  className="mb-2">
                                  <Input
                                    value={formTokenizer}
                                    onChange={(e) =>
                                      setFormTokenizer(e.target.value)
                                    }
                                    placeholder="gpt2"
                                  />
                                </Form.Item>

                                <div className="grid grid-cols-2 gap-2">
                                  <Form.Item
                                    label={t(
                                      "settings:chunkingPlayground.semanticThreshold",
                                      "Semantic threshold"
                                    )}
                                    className="mb-2">
                                    <InputNumber
                                      value={formSemanticThreshold}
                                      onChange={(val) =>
                                        setFormSemanticThreshold(val)
                                      }
                                      min={0}
                                      max={1}
                                      step={0.1}
                                      className="w-full"
                                    />
                                  </Form.Item>

                                  <Form.Item
                                    label={t(
                                      "settings:chunkingPlayground.semanticOverlap",
                                      "Semantic overlap"
                                    )}
                                    className="mb-2">
                                    <InputNumber
                                      value={formSemanticOverlap}
                                      onChange={(val) =>
                                        setFormSemanticOverlap(val)
                                      }
                                      min={0}
                                      className="w-full"
                                    />
                                  </Form.Item>
                                </div>

                                <Form.Item
                                  label={t(
                                    "settings:chunkingPlayground.jsonDataKey",
                                    "JSON data key"
                                  )}
                                  className="mb-2">
                                  <Input
                                    value={formJsonDataKey}
                                    onChange={(e) =>
                                      setFormJsonDataKey(e.target.value)
                                    }
                                    placeholder="data"
                                  />
                                </Form.Item>

                                <div className="flex items-center justify-between mb-2">
                                  <Text>
                                    {t(
                                      "settings:chunkingPlayground.frontmatterParsing",
                                      "Frontmatter parsing"
                                    )}
                                  </Text>
                                  <Switch
                                    checked={formFrontmatterParsing}
                                    onChange={setFormFrontmatterParsing}
                                  />
                                </div>

                                <Form.Item
                                  label={t(
                                    "settings:chunkingPlayground.frontmatterKey",
                                    "Frontmatter key"
                                  )}
                                  className="mb-2">
                                  <Input
                                    value={formFrontmatterKey}
                                    onChange={(e) =>
                                      setFormFrontmatterKey(e.target.value)
                                    }
                                    placeholder="__tldw_frontmatter__"
                                  />
                                </Form.Item>

                                <Form.Item
                                  label={t(
                                    "settings:chunkingPlayground.chapterPattern",
                                    "Chapter pattern"
                                  )}
                                  className="mb-2">
                                  <Input
                                    value={formCustomChapterPattern}
                                    onChange={(e) =>
                                      setFormCustomChapterPattern(e.target.value)
                                    }
                                    placeholder={t(
                                      "settings:chunkingPlayground.chapterPatternPlaceholder",
                                      "Regex pattern"
                                    )}
                                  />
                                </Form.Item>

                                <Form.Item
                                  label={t(
                                    "settings:chunkingPlayground.summarizationDetail",
                                    "Summarization detail"
                                  )}
                                  className="mb-2">
                                  <InputNumber
                                    value={formSummarizationDetail}
                                    onChange={(val) =>
                                      setFormSummarizationDetail(val)
                                    }
                                    min={0}
                                    max={10}
                                    className="w-full"
                                  />
                                </Form.Item>

                                <Divider className="my-2">
                                  {t(
                                    "settings:chunkingPlayground.propositionOptions",
                                    "Proposition options"
                                  )}
                                </Divider>

                                <Form.Item
                                  label={t(
                                    "settings:chunkingPlayground.propositionEngine",
                                    "Engine"
                                  )}
                                  className="mb-2">
                                  <Select
                                    value={formPropositionEngine}
                                    onChange={setFormPropositionEngine}
                                    options={propositionEngineOptions}
                                  />
                                </Form.Item>

                                <div className="grid grid-cols-2 gap-2">
                                  <Form.Item
                                    label={t(
                                      "settings:chunkingPlayground.propositionAggressiveness",
                                      "Aggressiveness"
                                    )}
                                    className="mb-2">
                                    <InputNumber
                                      value={formPropositionAggressiveness}
                                      onChange={(val) =>
                                        setFormPropositionAggressiveness(val)
                                      }
                                      min={0}
                                      max={10}
                                      className="w-full"
                                    />
                                  </Form.Item>

                                  <Form.Item
                                    label={t(
                                      "settings:chunkingPlayground.propositionMinLength",
                                      "Min length"
                                    )}
                                    className="mb-2">
                                    <InputNumber
                                      value={formPropositionMinLength}
                                      onChange={(val) =>
                                        setFormPropositionMinLength(val)
                                      }
                                      min={0}
                                      className="w-full"
                                    />
                                  </Form.Item>
                                </div>

                                <Form.Item
                                  label={t(
                                    "settings:chunkingPlayground.propositionPromptProfile",
                                    "Prompt profile"
                                  )}
                                  className="mb-2">
                                  <Select
                                    value={formPropositionPromptProfile}
                                    onChange={setFormPropositionPromptProfile}
                                    options={propositionPromptOptions}
                                  />
                                </Form.Item>
                              </Space>
                            )
                          }
                        ]}
                      />
                    </>
                  ) : (
                    <Form.Item
                      label={t(
                        "settings:chunkingPlayground.templates.templateJsonLabel",
                        "Template JSON"
                      )}>
                      <TextArea
                        value={editorTemplateJson}
                        onChange={(e) => setEditorTemplateJson(e.target.value)}
                        rows={12}
                        className="font-mono text-xs"
                      />
                    </Form.Item>
                  )}
                </Form>

                <Space className="mt-3">
                  <Button onClick={handleCreate}>
                    {t("common:create", "Create")}
                  </Button>
                  <Button onClick={handleUpdate}>
                    {t(
                      "settings:chunkingPlayground.templates.updateAction",
                      "Update"
                    )}
                  </Button>
                </Space>

                <Divider className="my-3" />
                {renderResponse(editorResponse)}
              </Card>
            )
          },
          {
            key: "apply",
            label: t(
              "settings:chunkingPlayground.templates.tabApply",
              "Apply"
            ),
            children: (
              <Card size="small">
                <Form layout="vertical" size="small">
                  <Form.Item
                    label={t(
                      "settings:chunkingPlayground.templates.selectLabel",
                      "Template"
                    )}>
                    <Select
                      showSearch
                      value={applyTemplateName || undefined}
                      onChange={setApplyTemplateName}
                      options={templateOptions}
                      placeholder={t(
                        "settings:chunkingPlayground.templates.selectPlaceholder",
                        "Select a template"
                      )}
                    />
                  </Form.Item>

                  <Form.Item
                    label={t(
                      "settings:chunkingPlayground.templates.applyTextLabel",
                      "Text to apply template"
                    )}>
                    <TextArea
                      value={applyText}
                      onChange={(e) => setApplyText(e.target.value)}
                      rows={6}
                      placeholder={t(
                        "settings:chunkingPlayground.templates.applyTextPlaceholder",
                        "Paste text to chunk with this template"
                      )}
                    />
                  </Form.Item>

                  <Form.Item
                    label={t(
                      "settings:chunkingPlayground.templates.overrideOptionsLabel",
                      "Override options (JSON)"
                    )}>
                    <TextArea
                      value={applyOverrideOptions}
                      onChange={(e) => setApplyOverrideOptions(e.target.value)}
                      rows={4}
                    />
                  </Form.Item>

                  <div className="flex items-center justify-between">
                    <Text>
                      {t(
                        "settings:chunkingPlayground.templates.includeMetadataLabel",
                        "Include metadata"
                      )}
                    </Text>
                    <Switch
                      checked={applyIncludeMetadata}
                      onChange={setApplyIncludeMetadata}
                    />
                  </div>
                </Form>

                <Space className="mt-3">
                  <Button onClick={handleApply}>
                    {t(
                      "settings:chunkingPlayground.templates.applyAction",
                      "Apply"
                    )}
                  </Button>
                </Space>

                <Divider className="my-3" />
                {renderResponse(applyResponse)}
              </Card>
            )
          },
          {
            key: "validate",
            label: t(
              "settings:chunkingPlayground.templates.tabValidate",
              "Validate"
            ),
            children: (
              <Card size="small">
                <Form layout="vertical" size="small">
                  <Form.Item
                    label={t(
                      "settings:chunkingPlayground.templates.validateLabel",
                      "Template JSON to validate"
                    )}>
                    <TextArea
                      value={validateJson}
                      onChange={(e) => setValidateJson(e.target.value)}
                      rows={8}
                    />
                  </Form.Item>
                </Form>

                <Button onClick={handleValidate}>
                  {t(
                    "settings:chunkingPlayground.templates.validateAction",
                    "Validate"
                  )}
                </Button>

                <Divider className="my-3" />
                {renderResponse(validateResponse)}
              </Card>
            )
          },
          {
            key: "match",
            label: t(
              "settings:chunkingPlayground.templates.tabMatch",
              "Match"
            ),
            children: (
              <Card size="small">
                <Form layout="vertical" size="small">
                  <Form.Item
                    label={t(
                      "settings:chunkingPlayground.templates.matchMediaTypeLabel",
                      "Media type"
                    )}>
                    <Input
                      value={matchMediaType}
                      onChange={(e) => setMatchMediaType(e.target.value)}
                    />
                  </Form.Item>

                  <Form.Item
                    label={t(
                      "settings:chunkingPlayground.templates.matchTitleLabel",
                      "Title"
                    )}>
                    <Input
                      value={matchTitle}
                      onChange={(e) => setMatchTitle(e.target.value)}
                    />
                  </Form.Item>

                  <Form.Item
                    label={t(
                      "settings:chunkingPlayground.templates.matchUrlLabel",
                      "URL"
                    )}>
                    <Input
                      value={matchUrl}
                      onChange={(e) => setMatchUrl(e.target.value)}
                    />
                  </Form.Item>

                  <Form.Item
                    label={t(
                      "settings:chunkingPlayground.templates.matchFilenameLabel",
                      "Filename"
                    )}>
                    <Input
                      value={matchFilename}
                      onChange={(e) => setMatchFilename(e.target.value)}
                    />
                  </Form.Item>
                </Form>

                <Button onClick={handleMatch}>
                  {t(
                    "settings:chunkingPlayground.templates.matchAction",
                    "Match"
                  )}
                </Button>

                <Divider className="my-3" />
                {renderResponse(matchResponse)}
              </Card>
            )
          },
          {
            key: "learn",
            label: t(
              "settings:chunkingPlayground.templates.tabLearn",
              "Learn"
            ),
            children: (
              <Card size="small">
                <Form layout="vertical" size="small">
                  <Form.Item
                    label={t(
                      "settings:chunkingPlayground.templates.learnNameLabel",
                      "Template name"
                    )}>
                    <Input
                      value={learnName}
                      onChange={(e) => setLearnName(e.target.value)}
                    />
                  </Form.Item>

                  <Form.Item
                    label={t(
                      "settings:chunkingPlayground.templates.learnExampleLabel",
                      "Example text"
                    )}>
                    <TextArea
                      value={learnExampleText}
                      onChange={(e) => setLearnExampleText(e.target.value)}
                      rows={6}
                    />
                  </Form.Item>

                  <Form.Item
                    label={t(
                      "settings:chunkingPlayground.templates.learnDescriptionLabel",
                      "Description"
                    )}>
                    <Input
                      value={learnDescription}
                      onChange={(e) => setLearnDescription(e.target.value)}
                    />
                  </Form.Item>

                  <Form.Item
                    label={t(
                      "settings:chunkingPlayground.templates.learnClassifierLabel",
                      "Classifier (JSON)"
                    )}>
                    <TextArea
                      value={learnClassifierJson}
                      onChange={(e) => setLearnClassifierJson(e.target.value)}
                      rows={4}
                    />
                  </Form.Item>

                  <div className="flex items-center justify-between">
                    <Text>
                      {t(
                        "settings:chunkingPlayground.templates.learnSaveLabel",
                        "Save template"
                      )}
                    </Text>
                    <Switch checked={learnSave} onChange={setLearnSave} />
                  </div>
                </Form>

                <Button onClick={handleLearn}>
                  {t(
                    "settings:chunkingPlayground.templates.learnAction",
                    "Learn"
                  )}
                </Button>

                <Divider className="my-3" />
                {renderResponse(learnResponse)}
              </Card>
            )
          },
          {
            key: "diagnostics",
            label: t(
              "settings:chunkingPlayground.templates.tabDiagnostics",
              "Diagnostics"
            ),
            children: (
              <Card size="small">
                <Button onClick={handleDiagnostics}>
                  {t(
                    "settings:chunkingPlayground.templates.diagnosticsAction",
                    "Run diagnostics"
                  )}
                </Button>

                <Divider className="my-3" />
                {renderResponse(diagnosticsResponse)}
              </Card>
            )
          }
        ]}
      />
    </div>
  )
}
