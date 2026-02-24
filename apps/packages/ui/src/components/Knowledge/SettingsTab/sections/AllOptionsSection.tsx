import React from "react"
import { Input, InputNumber, Select, Switch } from "antd"
import { useTranslation } from "react-i18next"
import type { TFunction } from "i18next"
import { cn } from "@/libs/utils"
import { DEFAULT_RAG_SETTINGS, type RagSettings } from "@/services/rag/unified-rag"
import { CollapsibleSection } from "../shared/CollapsibleSection"

type AllOptionsSectionProps = {
  settings: RagSettings
  onUpdate: <K extends keyof RagSettings>(key: K, value: RagSettings[K]) => void
  searchFilter?: string
}

type RagKey = keyof RagSettings

const NULLABLE_STRING_KEYS = new Set<RagKey>([
  "generation_model",
  "generation_prompt",
  "user_id",
  "session_id",
  "vlm_backend",
  "agentic_vlm_backend",
  "grading_model",
  "grading_provider",
  "fast_hallucination_provider",
  "fast_hallucination_model",
  "utility_grading_provider",
  "utility_grading_model"
])

const NULLABLE_NUMBER_KEYS = new Set<RagKey>([
  "accumulation_time_budget_sec",
  "subquery_time_budget_sec",
  "subquery_doc_budget"
])

const SETTING_ENUM_OPTIONS: Partial<Record<RagKey, string[]>> = {
  strategy: ["standard", "agentic"],
  search_mode: ["fts", "vector", "hybrid"],
  fts_level: ["media", "chunk"],
  table_method: ["markdown", "html", "hybrid"],
  claim_extractor: ["aps", "claimify", "ner", "auto"],
  claim_verifier: ["nli", "llm", "hybrid"],
  reranking_strategy: [
    "flashrank",
    "cross_encoder",
    "hybrid",
    "llama_cpp",
    "llm_scoring",
    "two_tier",
    "none"
  ],
  citation_style: ["apa", "mla", "chicago", "harvard", "ieee"],
  abstention_behavior: ["continue", "ask", "decline"],
  content_policy_mode: ["redact", "drop", "annotate"],
  low_confidence_behavior: ["continue", "ask", "decline"],
  numeric_fidelity_behavior: ["continue", "ask", "decline", "retry"],
  numeric_precision_mode: ["standard", "strict", "academic"],
  web_fallback_merge_strategy: ["prepend", "append", "interleave"],
  sensitivity_level: ["public", "internal", "confidential", "restricted"]
}

const ARRAY_VALUE_KIND_BY_KEY: Partial<Record<RagKey, "string" | "number">> = {
  include_media_ids: "number",
  include_note_ids: "number",
  expansion_strategies: "string",
  chunk_type_filter: "string",
  content_policy_types: "string",
  html_allowed_tags: "string",
  html_allowed_attrs: "string",
  batch_queries: "string",
  ground_truth_doc_ids: "string"
}

const AUTO_OPTION_EXCLUDED_KEYS = new Set<RagKey>(["query"])

const ALL_OPTION_KEYS = (Object.keys(DEFAULT_RAG_SETTINGS) as RagKey[])
  .filter((key) => !AUTO_OPTION_EXCLUDED_KEYS.has(key))
  .sort((a, b) => a.localeCompare(b))

export const getAllOptionsSectionVisible = (
  searchFilter: string,
  t: TFunction
) => {
  const normalizedFilter = searchFilter.trim().toLowerCase()
  if (!normalizedFilter) return true

  const labels = [
    t("sidepanel:rag.allOptions", "All options"),
    t(
      "sidepanel:rag.allOptionsHelper",
      "Complete key-level access for every RAG option"
    ),
    t("sidepanel:rag.allOptionsFilter", "Filter option keys")
  ]

  if (labels.some((label) => label.toLowerCase().includes(normalizedFilter))) {
    return true
  }

  return ALL_OPTION_KEYS.some((key) => key.toLowerCase().includes(normalizedFilter))
}

const formatArrayDraft = (values: unknown[]): string =>
  values.map((entry) => String(entry)).join(", ")

const parseArrayDraft = (
  key: RagKey,
  draft: string
): { parsed: unknown[]; error?: string } => {
  const normalized = draft.trim()
  if (!normalized) {
    return { parsed: [] }
  }

  const chunks = normalized
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean)

  const kind = ARRAY_VALUE_KIND_BY_KEY[key]
  if (kind === "number") {
    const numbers = chunks.map((part) => Number(part))
    if (numbers.some((value) => !Number.isFinite(value))) {
      return { parsed: [], error: "Use comma-separated numbers only." }
    }
    return { parsed: numbers }
  }

  return { parsed: chunks }
}

function AutoArrayInput({
  fieldKey,
  values,
  onChange
}: {
  fieldKey: RagKey
  values: unknown[]
  onChange: (next: unknown[]) => void
}) {
  const [draft, setDraft] = React.useState(() => formatArrayDraft(values))
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    setDraft(formatArrayDraft(values))
  }, [values])

  const commitDraft = () => {
    const parsed = parseArrayDraft(fieldKey, draft)
    if (parsed.error) {
      setError(parsed.error)
      return
    }
    setError(null)
    onChange(parsed.parsed)
  }

  return (
    <div className="space-y-1">
      <Input
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commitDraft}
        className={cn(error ? "border-danger" : "")}
      />
      <p className="text-[11px] text-text-muted">Comma-separated values</p>
      {error ? <p className="text-[11px] text-danger">{error}</p> : null}
    </div>
  )
}

function AutoOptionRow({
  fieldKey,
  settings,
  onUpdate
}: {
  fieldKey: RagKey
  settings: RagSettings
  onUpdate: <K extends keyof RagSettings>(key: K, value: RagSettings[K]) => void
}) {
  const value = settings[fieldKey]
  const setValue = (next: unknown) =>
    onUpdate(fieldKey, next as RagSettings[typeof fieldKey])
  const enumValues = SETTING_ENUM_OPTIONS[fieldKey]

  let control: React.ReactNode = (
    <span className="text-xs text-text-muted">Unsupported value type</span>
  )

  if (typeof value === "boolean") {
    control = (
      <Switch
        size="small"
        checked={value}
        onChange={(checked) => setValue(checked)}
      />
    )
  } else if (
    typeof value === "number" ||
    (value === null && NULLABLE_NUMBER_KEYS.has(fieldKey))
  ) {
    const step = typeof value === "number" && Number.isInteger(value) ? 1 : 0.01
    control = (
      <InputNumber
        value={typeof value === "number" ? value : null}
        placeholder={NULLABLE_NUMBER_KEYS.has(fieldKey) ? "null" : undefined}
        step={step}
        onChange={(next) => {
          if (next === null) {
            if (NULLABLE_NUMBER_KEYS.has(fieldKey)) {
              setValue(null)
            }
            return
          }
          const parsed = Number(next)
          if (Number.isFinite(parsed)) {
            setValue(parsed)
          }
        }}
        className="w-44"
      />
    )
  } else if (Array.isArray(value)) {
    control = (
      <div className="w-64">
        <AutoArrayInput
          fieldKey={fieldKey}
          values={value}
          onChange={(next) => setValue(next)}
        />
      </div>
    )
  } else if (typeof value === "string" || value === null) {
    if (enumValues && enumValues.length > 0) {
      control = (
        <Select
          value={value ?? ""}
          options={enumValues.map((enumValue) => ({
            label: enumValue,
            value: enumValue
          }))}
          onChange={(next) => setValue(next)}
          className="w-64"
        />
      )
    } else {
      const acceptsNull = NULLABLE_STRING_KEYS.has(fieldKey)
      control = (
        <Input
          value={value ?? ""}
          placeholder={acceptsNull ? "null" : undefined}
          onChange={(event) => {
            const next = event.target.value
            setValue(acceptsNull && next.trim() === "" ? null : next)
          }}
          className="w-64"
        />
      )
    }
  }

  const valueType = Array.isArray(value)
    ? "array"
    : value === null
      ? NULLABLE_NUMBER_KEYS.has(fieldKey)
        ? "null|number"
        : "null|string"
      : typeof value

  return (
    <div className="p-3 flex items-start justify-between gap-4">
      <div className="min-w-0">
        <div className="text-sm font-medium font-mono break-all">{fieldKey}</div>
        <div className="text-[11px] text-text-muted">{valueType}</div>
      </div>
      {control}
    </div>
  )
}

export const AllOptionsSection: React.FC<AllOptionsSectionProps> = ({
  settings,
  onUpdate,
  searchFilter = ""
}) => {
  const { t } = useTranslation(["sidepanel"])
  const [keyFilter, setKeyFilter] = React.useState("")

  const allKeys = React.useMemo(
    () => ALL_OPTION_KEYS.filter((key) => key in settings),
    [settings]
  )

  const effectiveFilter = (
    keyFilter.trim().length > 0 ? keyFilter : searchFilter
  )
    .trim()
    .toLowerCase()

  const filteredKeys = React.useMemo(
    () =>
      effectiveFilter
        ? allKeys.filter((key) => key.toLowerCase().includes(effectiveFilter))
        : allKeys,
    [allKeys, effectiveFilter]
  )

  const sectionVisible = getAllOptionsSectionVisible(searchFilter, t)

  return (
    <CollapsibleSection
      title={t("sidepanel:rag.allOptions", "All options")}
      defaultExpanded={false}
      visible={sectionVisible}
      helperText={t(
        "sidepanel:rag.allOptionsHelper",
        "Complete key-level access for every RAG option"
      )}
    >
      <div className="col-span-2 space-y-3">
        <div className="space-y-1">
          <label
            htmlFor="knowledge-all-options-filter"
            className="text-xs font-medium text-text-muted"
          >
            {t("sidepanel:rag.allOptionsFilter", "Filter option keys")} (
            {filteredKeys.length}/{allKeys.length})
          </label>
          <Input
            id="knowledge-all-options-filter"
            data-testid="knowledge-all-options-filter"
            value={keyFilter}
            onChange={(event) => setKeyFilter(event.target.value)}
            placeholder={t(
              "sidepanel:rag.allOptionsFilterPlaceholder",
              "Type part of an option key (e.g. adaptive_, table_, agentic_)"
            )}
          />
        </div>

        <div
          className="border border-border rounded-md divide-y divide-border max-h-[26rem] overflow-y-auto"
          data-testid="knowledge-all-options-list"
        >
          {filteredKeys.length === 0 ? (
            <div className="p-4 text-sm text-text-muted">
              {t("sidepanel:rag.allOptionsNoMatch", "No option keys match this filter.")}
            </div>
          ) : (
            filteredKeys.map((fieldKey) => (
              <AutoOptionRow
                key={fieldKey}
                fieldKey={fieldKey}
                settings={settings}
                onUpdate={onUpdate}
              />
            ))
          )}
        </div>
      </div>
    </CollapsibleSection>
  )
}
