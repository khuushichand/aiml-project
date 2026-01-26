/**
 * ExpertSettings - Full 150+ RAG options organized into sections
 */

import React, { useState } from "react"
import {
  ChevronDown,
  ChevronRight,
  Search,
  Sparkles,
  Database,
  Shield,
  Zap,
  FileText,
  Brain,
  CheckCircle2,
  Quote,
  Gauge,
} from "lucide-react"
import { useKnowledgeQA } from "../KnowledgeQAProvider"
import { cn } from "@/lib/utils"
import type { RagSettings } from "@/services/rag/unified-rag"

// Section configuration
type SectionConfig = {
  id: string
  title: string
  icon: React.ElementType
  description: string
  defaultOpen?: boolean
}

const SECTIONS: SectionConfig[] = [
  {
    id: "search",
    title: "Search",
    icon: Search,
    description: "Search mode, top-k, hybrid settings",
    defaultOpen: true,
  },
  {
    id: "query",
    title: "Query Enhancement",
    icon: Sparkles,
    description: "Expansion, spell check, intent routing",
  },
  {
    id: "retrieval",
    title: "Advanced Retrieval",
    icon: Database,
    description: "PRF, HyDE, multi-vector passages",
  },
  {
    id: "chunking",
    title: "Document Context",
    icon: FileText,
    description: "Parent expansion, siblings, chunk types",
  },
  {
    id: "agentic",
    title: "Agentic RAG",
    icon: Brain,
    description: "Query decomposition, tools, planning",
  },
  {
    id: "reranking",
    title: "Reranking",
    icon: Gauge,
    description: "Strategy, model, thresholds",
  },
  {
    id: "generation",
    title: "Answer Generation",
    icon: Sparkles,
    description: "Model, tokens, abstention",
  },
  {
    id: "citations",
    title: "Citations",
    icon: Quote,
    description: "Style, page numbers, chunk-level",
  },
  {
    id: "verification",
    title: "Verification",
    icon: CheckCircle2,
    description: "Claims, post-verification, fidelity",
  },
  {
    id: "security",
    title: "Security",
    icon: Shield,
    description: "PII detection, content policy, sanitization",
  },
  {
    id: "performance",
    title: "Performance",
    icon: Zap,
    description: "Timeout, caching, resilience",
  },
]

export function ExpertSettings() {
  const { settings, updateSetting } = useKnowledgeQA()
  const [openSections, setOpenSections] = useState<Set<string>>(
    new Set(SECTIONS.filter((s) => s.defaultOpen).map((s) => s.id))
  )

  const toggleSection = (id: string) => {
    const newSet = new Set(openSections)
    if (newSet.has(id)) {
      newSet.delete(id)
    } else {
      newSet.add(id)
    }
    setOpenSections(newSet)
  }

  return (
    <div className="space-y-2">
      {SECTIONS.map((section) => (
        <SettingsSection
          key={section.id}
          config={section}
          isOpen={openSections.has(section.id)}
          onToggle={() => toggleSection(section.id)}
          settings={settings}
          updateSetting={updateSetting}
        />
      ))}
    </div>
  )
}

type SettingsSectionProps = {
  config: SectionConfig
  isOpen: boolean
  onToggle: () => void
  settings: RagSettings
  updateSetting: <K extends keyof RagSettings>(key: K, value: RagSettings[K]) => void
}

function SettingsSection({
  config,
  isOpen,
  onToggle,
  settings,
  updateSetting,
}: SettingsSectionProps) {
  const Icon = config.icon

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      {/* Header */}
      <button
        onClick={onToggle}
        className="flex items-center gap-3 w-full px-4 py-3 hover:bg-muted/50 transition-colors"
      >
        {isOpen ? (
          <ChevronDown className="w-4 h-4 text-text-muted" />
        ) : (
          <ChevronRight className="w-4 h-4 text-text-muted" />
        )}
        <Icon className="w-4 h-4 text-primary" />
        <div className="flex-1 text-left">
          <div className="font-medium text-sm">{config.title}</div>
          <div className="text-xs text-text-muted">{config.description}</div>
        </div>
      </button>

      {/* Content */}
      {isOpen && (
        <div className="px-4 pb-4 pt-2 border-t border-border space-y-4">
          <SectionContent
            sectionId={config.id}
            settings={settings}
            updateSetting={updateSetting}
          />
        </div>
      )}
    </div>
  )
}

type SectionSettingsProps = {
  settings: RagSettings
  updateSetting: <K extends keyof RagSettings>(key: K, value: RagSettings[K]) => void
}

type SectionContentProps = SectionSettingsProps & {
  sectionId: string
}

function SectionContent({ sectionId, settings, updateSetting }: SectionContentProps) {
  switch (sectionId) {
    case "search":
      return <SearchSection settings={settings} updateSetting={updateSetting} />
    case "query":
      return <QuerySection settings={settings} updateSetting={updateSetting} />
    case "retrieval":
      return <RetrievalSection settings={settings} updateSetting={updateSetting} />
    case "chunking":
      return <ChunkingSection settings={settings} updateSetting={updateSetting} />
    case "agentic":
      return <AgenticSection settings={settings} updateSetting={updateSetting} />
    case "reranking":
      return <RerankingSection settings={settings} updateSetting={updateSetting} />
    case "generation":
      return <GenerationSection settings={settings} updateSetting={updateSetting} />
    case "citations":
      return <CitationsSection settings={settings} updateSetting={updateSetting} />
    case "verification":
      return <VerificationSection settings={settings} updateSetting={updateSetting} />
    case "security":
      return <SecuritySection settings={settings} updateSetting={updateSetting} />
    case "performance":
      return <PerformanceSection settings={settings} updateSetting={updateSetting} />
    default:
      return <div className="text-sm text-text-muted">Section not found</div>
  }
}

// Reusable form components
function SettingToggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string
  description?: string
  checked: boolean
  onChange: (checked: boolean) => void
}) {
  // Generate a unique ID for accessibility
  const labelId = `toggle-${label.toLowerCase().replace(/\s+/g, '-')}`

  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <div id={labelId} className="text-sm font-medium">{label}</div>
        {description && <div className="text-xs text-text-muted">{description}</div>}
      </div>
      <button
        role="switch"
        aria-checked={checked}
        aria-labelledby={labelId}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative inline-flex h-5 w-9 items-center rounded-full transition-colors flex-shrink-0",
          checked ? "bg-primary" : "bg-muted"
        )}
      >
        <span
          className={cn(
            "inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform",
            checked ? "translate-x-5" : "translate-x-1"
          )}
        />
      </button>
    </div>
  )
}

function SettingSlider({
  label,
  description,
  value,
  onChange,
  min,
  max,
  step = 1,
}: {
  label: string
  description?: string
  value: number
  onChange: (value: number) => void
  min: number
  max: number
  step?: number
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium">{label}</div>
        <div className="text-sm text-text-muted">{value}</div>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full accent-primary"
      />
      {description && <div className="text-xs text-text-muted">{description}</div>}
    </div>
  )
}

function SettingSelect({
  label,
  description,
  value,
  onChange,
  options,
}: {
  label: string
  description?: string
  value: string
  onChange: (value: string) => void
  options: { value: string; label: string }[]
}) {
  return (
    <div className="space-y-1.5">
      <div className="text-sm font-medium">{label}</div>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-1.5 text-sm rounded-md border border-border bg-surface focus:outline-none focus:ring-2 focus:ring-primary"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {description && <div className="text-xs text-text-muted">{description}</div>}
    </div>
  )
}

// Section implementations
function SearchSection({ settings, updateSetting }: SectionSettingsProps) {
  return (
    <div className="space-y-4">
      <SettingSelect
        label="Search Mode"
        value={settings.search_mode}
        onChange={(v) => updateSetting("search_mode", v as typeof settings.search_mode)}
        options={[
          { value: "hybrid", label: "Hybrid (FTS + Vector)" },
          { value: "vector", label: "Vector Only" },
          { value: "fts", label: "Full-Text Only" },
        ]}
      />
      <SettingSelect
        label="FTS Level"
        value={settings.fts_level}
        onChange={(v) => updateSetting("fts_level", v as typeof settings.fts_level)}
        options={[
          { value: "media", label: "Media-level" },
          { value: "chunk", label: "Chunk-level" },
        ]}
      />
      <SettingSlider
        label="Hybrid Alpha"
        description="0 = FTS only, 1 = Vector only"
        value={settings.hybrid_alpha}
        onChange={(v) => updateSetting("hybrid_alpha", v)}
        min={0}
        max={1}
        step={0.1}
      />
      <SettingSlider
        label="Top-K"
        description="Number of documents to retrieve"
        value={settings.top_k}
        onChange={(v) => updateSetting("top_k", v)}
        min={1}
        max={50}
      />
      <SettingSlider
        label="Min Score"
        description="Minimum relevance threshold"
        value={settings.min_score}
        onChange={(v) => updateSetting("min_score", v)}
        min={0}
        max={1}
        step={0.05}
      />
      <SettingToggle
        label="Intent Routing"
        description="Analyze query intent to adjust retrieval"
        checked={settings.enable_intent_routing}
        onChange={(v) => updateSetting("enable_intent_routing", v)}
      />
    </div>
  )
}

function QuerySection({ settings, updateSetting }: SectionSettingsProps) {
  return (
    <div className="space-y-4">
      <SettingToggle
        label="Query Expansion"
        description="Expand query with synonyms and related terms"
        checked={settings.expand_query}
        onChange={(v) => updateSetting("expand_query", v)}
      />
      {settings.expand_query && (
        <div className="pl-4 border-l-2 border-primary/20 space-y-2">
          <div className="text-xs font-medium text-text-muted">Expansion Strategies</div>
          {["acronym", "synonym", "semantic", "domain", "entity"].map((strategy) => (
            <label key={strategy} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={settings.expansion_strategies.includes(strategy as typeof settings.expansion_strategies[number])}
                onChange={(e) => {
                  const newStrategies = e.target.checked
                    ? [...settings.expansion_strategies, strategy as typeof settings.expansion_strategies[number]]
                    : settings.expansion_strategies.filter((s) => s !== strategy)
                  updateSetting("expansion_strategies", newStrategies)
                }}
                className="rounded"
              />
              <span className="capitalize">{strategy}</span>
            </label>
          ))}
        </div>
      )}
      <SettingToggle
        label="Spell Check"
        description="Correct spelling errors in query"
        checked={settings.spell_check}
        onChange={(v) => updateSetting("spell_check", v)}
      />
    </div>
  )
}

function RetrievalSection({ settings, updateSetting }: SectionSettingsProps) {
  return (
    <div className="space-y-4">
      <SettingToggle
        label="Multi-Vector Passages"
        description="ColBERT-style fine-grained matching"
        checked={settings.enable_multi_vector_passages}
        onChange={(v) => updateSetting("enable_multi_vector_passages", v)}
      />
      {settings.enable_multi_vector_passages && (
        <div className="pl-4 border-l-2 border-primary/20 space-y-3">
          <SettingSlider
            label="Span Characters"
            value={settings.mv_span_chars}
            onChange={(v) => updateSetting("mv_span_chars", v)}
            min={50}
            max={500}
          />
          <SettingSlider
            label="Stride"
            value={settings.mv_stride}
            onChange={(v) => updateSetting("mv_stride", v)}
            min={10}
            max={200}
          />
          <SettingSlider
            label="Max Spans"
            value={settings.mv_max_spans}
            onChange={(v) => updateSetting("mv_max_spans", v)}
            min={1}
            max={50}
          />
        </div>
      )}
      <SettingToggle
        label="Numeric Table Boost"
        description="Boost documents with numeric tables"
        checked={settings.enable_numeric_table_boost}
        onChange={(v) => updateSetting("enable_numeric_table_boost", v)}
      />
    </div>
  )
}

function ChunkingSection({ settings, updateSetting }: SectionSettingsProps) {
  return (
    <div className="space-y-4">
      <SettingToggle
        label="Parent Expansion"
        description="Include surrounding context"
        checked={settings.enable_parent_expansion}
        onChange={(v) => updateSetting("enable_parent_expansion", v)}
      />
      {settings.enable_parent_expansion && (
        <SettingSlider
          label="Parent Context Size"
          value={settings.parent_context_size}
          onChange={(v) => updateSetting("parent_context_size", v)}
          min={100}
          max={2000}
          step={100}
        />
      )}
      <SettingToggle
        label="Include Sibling Chunks"
        description="Include adjacent chunks"
        checked={settings.include_sibling_chunks}
        onChange={(v) => updateSetting("include_sibling_chunks", v)}
      />
      {settings.include_sibling_chunks && (
        <SettingSlider
          label="Sibling Window"
          value={settings.sibling_window}
          onChange={(v) => updateSetting("sibling_window", v)}
          min={0}
          max={5}
        />
      )}
      <SettingToggle
        label="Include Parent Document"
        description="Include full parent doc metadata"
        checked={settings.include_parent_document}
        onChange={(v) => updateSetting("include_parent_document", v)}
      />
    </div>
  )
}

function AgenticSection({ settings, updateSetting }: SectionSettingsProps) {
  return (
    <div className="space-y-4">
      <SettingSelect
        label="Strategy"
        value={settings.strategy}
        onChange={(v) => updateSetting("strategy", v as typeof settings.strategy)}
        options={[
          { value: "standard", label: "Standard (pre-chunked)" },
          { value: "agentic", label: "Agentic (query-time)" },
        ]}
      />
      {settings.strategy === "agentic" && (
        <>
          <SettingSlider
            label="Top-K Documents"
            value={settings.agentic_top_k_docs}
            onChange={(v) => updateSetting("agentic_top_k_docs", v)}
            min={1}
            max={20}
          />
          <SettingSlider
            label="Window Characters"
            value={settings.agentic_window_chars}
            onChange={(v) => updateSetting("agentic_window_chars", v)}
            min={200}
            max={5000}
            step={100}
          />
          <SettingToggle
            label="Enable Tools"
            description="Allow agentic tool calls"
            checked={settings.agentic_enable_tools}
            onChange={(v) => updateSetting("agentic_enable_tools", v)}
          />
          <SettingToggle
            label="Query Decomposition"
            description="Break complex queries into sub-questions"
            checked={settings.agentic_enable_query_decomposition}
            onChange={(v) => updateSetting("agentic_enable_query_decomposition", v)}
          />
          <SettingToggle
            label="LLM Planner"
            description="Use LLM for retrieval planning"
            checked={settings.agentic_use_llm_planner}
            onChange={(v) => updateSetting("agentic_use_llm_planner", v)}
          />
        </>
      )}
    </div>
  )
}

function RerankingSection({ settings, updateSetting }: SectionSettingsProps) {
  return (
    <div className="space-y-4">
      <SettingToggle
        label="Enable Reranking"
        description="Re-score results for better relevance"
        checked={settings.enable_reranking}
        onChange={(v) => updateSetting("enable_reranking", v)}
      />
      {settings.enable_reranking && (
        <>
          <SettingSelect
            label="Strategy"
            value={settings.reranking_strategy}
            onChange={(v) => updateSetting("reranking_strategy", v as typeof settings.reranking_strategy)}
            options={[
              { value: "flashrank", label: "FlashRank (fast)" },
              { value: "cross_encoder", label: "Cross-Encoder" },
              { value: "hybrid", label: "Hybrid" },
              { value: "llm_scoring", label: "LLM Scoring" },
              { value: "two_tier", label: "Two-Tier" },
            ]}
          />
          <SettingSlider
            label="Rerank Top-K"
            value={settings.rerank_top_k}
            onChange={(v) => updateSetting("rerank_top_k", v)}
            min={1}
            max={100}
          />
          <SettingSlider
            label="Min Relevance Probability"
            value={settings.rerank_min_relevance_prob}
            onChange={(v) => updateSetting("rerank_min_relevance_prob", v)}
            min={0}
            max={1}
            step={0.05}
          />
        </>
      )}
    </div>
  )
}

function GenerationSection({ settings, updateSetting }: SectionSettingsProps) {
  return (
    <div className="space-y-4">
      <SettingToggle
        label="Enable Generation"
        description="Generate synthesized answer"
        checked={settings.enable_generation}
        onChange={(v) => updateSetting("enable_generation", v)}
      />
      {settings.enable_generation && (
        <>
          <SettingSlider
            label="Max Tokens"
            value={settings.max_generation_tokens}
            onChange={(v) => updateSetting("max_generation_tokens", v)}
            min={50}
            max={2000}
            step={50}
          />
          <SettingToggle
            label="Strict Extractive"
            description="Only quote from sources (no free-form)"
            checked={settings.strict_extractive}
            onChange={(v) => updateSetting("strict_extractive", v)}
          />
          <SettingToggle
            label="Enable Abstention"
            description="Decline to answer if unsure"
            checked={settings.enable_abstention}
            onChange={(v) => updateSetting("enable_abstention", v)}
          />
          {settings.enable_abstention && (
            <SettingSelect
              label="Abstention Behavior"
              value={settings.abstention_behavior}
              onChange={(v) => updateSetting("abstention_behavior", v as typeof settings.abstention_behavior)}
              options={[
                { value: "continue", label: "Continue anyway" },
                { value: "ask", label: "Ask for clarification" },
                { value: "decline", label: "Decline to answer" },
              ]}
            />
          )}
          <SettingToggle
            label="Multi-Turn Synthesis"
            description="Use iterative refinement"
            checked={settings.enable_multi_turn_synthesis}
            onChange={(v) => updateSetting("enable_multi_turn_synthesis", v)}
          />
        </>
      )}
    </div>
  )
}

function CitationsSection({ settings, updateSetting }: SectionSettingsProps) {
  return (
    <div className="space-y-4">
      <SettingToggle
        label="Enable Citations"
        description="Generate inline citations"
        checked={settings.enable_citations}
        onChange={(v) => updateSetting("enable_citations", v)}
      />
      {settings.enable_citations && (
        <>
          <SettingSelect
            label="Citation Style"
            value={settings.citation_style}
            onChange={(v) => updateSetting("citation_style", v as typeof settings.citation_style)}
            options={[
              { value: "apa", label: "APA" },
              { value: "mla", label: "MLA" },
              { value: "chicago", label: "Chicago" },
              { value: "harvard", label: "Harvard" },
              { value: "ieee", label: "IEEE" },
            ]}
          />
          <SettingToggle
            label="Include Page Numbers"
            description="Add page numbers to citations"
            checked={settings.include_page_numbers}
            onChange={(v) => updateSetting("include_page_numbers", v)}
          />
          <SettingToggle
            label="Chunk-Level Citations"
            description="Cite specific chunks vs documents"
            checked={settings.enable_chunk_citations}
            onChange={(v) => updateSetting("enable_chunk_citations", v)}
          />
        </>
      )}
    </div>
  )
}

function VerificationSection({ settings, updateSetting }: SectionSettingsProps) {
  return (
    <div className="space-y-4">
      <SettingToggle
        label="Enable Claims Extraction"
        description="Extract and verify factual claims"
        checked={settings.enable_claims}
        onChange={(v) => updateSetting("enable_claims", v)}
      />
      {settings.enable_claims && (
        <>
          <SettingSelect
            label="Claim Extractor"
            value={settings.claim_extractor}
            onChange={(v) => updateSetting("claim_extractor", v as typeof settings.claim_extractor)}
            options={[
              { value: "auto", label: "Auto" },
              { value: "aps", label: "APS" },
              { value: "claimify", label: "Claimify" },
              { value: "ner", label: "NER" },
            ]}
          />
          <SettingSelect
            label="Claim Verifier"
            value={settings.claim_verifier}
            onChange={(v) => updateSetting("claim_verifier", v as typeof settings.claim_verifier)}
            options={[
              { value: "nli", label: "NLI" },
              { value: "llm", label: "LLM" },
              { value: "hybrid", label: "Hybrid" },
            ]}
          />
          <SettingSlider
            label="Confidence Threshold"
            value={settings.claims_conf_threshold}
            onChange={(v) => updateSetting("claims_conf_threshold", v)}
            min={0}
            max={1}
            step={0.05}
          />
        </>
      )}
      <SettingToggle
        label="Post-Verification"
        description="Verify answer after generation"
        checked={settings.enable_post_verification}
        onChange={(v) => updateSetting("enable_post_verification", v)}
      />
      <SettingToggle
        label="Require Hard Citations"
        description="Every claim must have source spans"
        checked={settings.require_hard_citations}
        onChange={(v) => updateSetting("require_hard_citations", v)}
      />
      <SettingToggle
        label="Numeric Fidelity Check"
        description="Verify numbers appear in sources"
        checked={settings.enable_numeric_fidelity}
        onChange={(v) => updateSetting("enable_numeric_fidelity", v)}
      />
    </div>
  )
}

function SecuritySection({ settings, updateSetting }: SectionSettingsProps) {
  return (
    <div className="space-y-4">
      <SettingToggle
        label="Security Filter"
        description="Enable security filtering"
        checked={settings.enable_security_filter}
        onChange={(v) => updateSetting("enable_security_filter", v)}
      />
      <SettingToggle
        label="Detect PII"
        description="Detect personally identifiable information"
        checked={settings.detect_pii}
        onChange={(v) => updateSetting("detect_pii", v)}
      />
      <SettingToggle
        label="Redact PII"
        description="Automatically redact PII from results"
        checked={settings.redact_pii}
        onChange={(v) => updateSetting("redact_pii", v)}
      />
      <SettingSelect
        label="Sensitivity Level"
        value={settings.sensitivity_level}
        onChange={(v) => updateSetting("sensitivity_level", v as typeof settings.sensitivity_level)}
        options={[
          { value: "public", label: "Public" },
          { value: "internal", label: "Internal" },
          { value: "confidential", label: "Confidential" },
          { value: "restricted", label: "Restricted" },
        ]}
      />
      <SettingToggle
        label="Content Policy Filter"
        description="Filter content by policy"
        checked={settings.enable_content_policy_filter}
        onChange={(v) => updateSetting("enable_content_policy_filter", v)}
      />
      <SettingToggle
        label="HTML Sanitizer"
        description="Sanitize HTML in responses"
        checked={settings.enable_html_sanitizer}
        onChange={(v) => updateSetting("enable_html_sanitizer", v)}
      />
    </div>
  )
}

function PerformanceSection({ settings, updateSetting }: SectionSettingsProps) {
  return (
    <div className="space-y-4">
      <SettingSlider
        label="Timeout (seconds)"
        value={settings.timeout_seconds}
        onChange={(v) => updateSetting("timeout_seconds", v)}
        min={5}
        max={120}
      />
      <SettingToggle
        label="Enable Cache"
        description="Cache semantic search results"
        checked={settings.enable_cache}
        onChange={(v) => updateSetting("enable_cache", v)}
      />
      {settings.enable_cache && (
        <>
          <SettingSlider
            label="Cache Threshold"
            description="Similarity threshold for cache hits"
            value={settings.cache_threshold}
            onChange={(v) => updateSetting("cache_threshold", v)}
            min={0.5}
            max={1}
            step={0.05}
          />
          <SettingToggle
            label="Adaptive Cache"
            description="Adjust cache based on query patterns"
            checked={settings.adaptive_cache}
            onChange={(v) => updateSetting("adaptive_cache", v)}
          />
        </>
      )}
      <SettingToggle
        label="Enable Resilience"
        description="Retry on transient failures"
        checked={settings.enable_resilience}
        onChange={(v) => updateSetting("enable_resilience", v)}
      />
      {settings.enable_resilience && (
        <SettingSlider
          label="Retry Attempts"
          value={settings.retry_attempts}
          onChange={(v) => updateSetting("retry_attempts", v)}
          min={1}
          max={5}
        />
      )}
      <SettingToggle
        label="Circuit Breaker"
        description="Prevent cascading failures"
        checked={settings.circuit_breaker}
        onChange={(v) => updateSetting("circuit_breaker", v)}
      />
    </div>
  )
}
