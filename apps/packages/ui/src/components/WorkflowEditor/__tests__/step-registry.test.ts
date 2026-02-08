import { describe, expect, it } from "vitest"
import {
  buildStepRegistry,
  humanizeStepType,
  resolveStepCategory,
  resolveStepIcon,
  STEP_CATEGORIES,
  BASE_STEP_REGISTRY
} from "../step-registry"
import { schemaToConfigFields } from "../schema-utils"
import { STEP_ICON_COMPONENTS } from "../step-icons"
import type { WorkflowStepSchema, StepCategory } from "@/types/workflow-editor"

// All 124 backend step types grouped by expected category
const ALL_STEP_TYPES: Record<StepCategory, string[]> = {
  ai: [
    "prompt", "llm", "llm_with_tools", "llm_compare", "llm_critique",
    "summarize", "image_gen", "image_describe", "translate", "voice_intent",
    "flashcard_generate", "quiz_generate", "quiz_evaluate", "outline_generate",
    "glossary_extract", "mindmap_generate", "report_generate", "newsletter_generate",
    "slides_generate", "diagram_generate", "literature_review", "moderation"
  ],
  search: [
    "rag_search", "web_search", "query_expand", "query_rewrite", "hyde_generate",
    "semantic_cache_check", "search_aggregate", "rerank", "embed", "rss_fetch",
    "atom_fetch"
  ],
  media: [
    "media_ingest", "process_media", "pdf_extract", "ocr", "document_table_extract",
    "chunking", "claims_extract", "citations", "bibliography_generate",
    "document_merge", "document_diff"
  ],
  text: [
    "json_transform", "json_validate", "csv_to_json", "json_to_csv", "regex_extract",
    "text_clean", "xml_transform", "template_render", "markdown_to_html",
    "html_to_markdown", "keyword_extract", "sentiment_analyze", "language_detect",
    "topic_model", "entity_extract", "context_build"
  ],
  research: [
    "arxiv_search", "arxiv_download", "pubmed_search", "semantic_scholar_search",
    "google_scholar_search", "patent_search", "doi_resolve", "reference_parse",
    "bibtex_generate"
  ],
  audio: [
    "tts", "multi_voice_tts", "stt_transcribe", "audio_normalize", "audio_concat",
    "audio_trim", "audio_convert", "audio_extract", "audio_mix", "audio_diarize",
    "audio_briefing_compose"
  ],
  video: [
    "video_trim", "video_concat", "video_convert", "video_thumbnail",
    "video_extract_frames", "subtitle_generate", "subtitle_translate", "subtitle_burn"
  ],
  control: [
    "branch", "map", "batch", "parallel", "retry", "cache_result", "checkpoint",
    "workflow_call", "wait_for_human", "wait_for_approval"
  ],
  io: [
    "webhook", "notify", "kanban", "s3_upload", "s3_download", "github_create_issue",
    "email_send", "screenshot_capture", "mcp_tool", "chatbooks", "character_chat",
    "notes", "prompts", "collections", "evaluations", "schedule_workflow"
  ],
  utility: [
    "delay", "log", "token_count", "context_window_check", "policy_check",
    "diff_change_detector", "sandbox_exec", "timing_start", "timing_stop",
    "eval_readability"
  ]
}

const FLAT_STEP_TYPES = Object.values(ALL_STEP_TYPES).flat()

const sampleSchema: WorkflowStepSchema = {
  type: "object",
  properties: {
    url: { type: "string", description: "Target URL" },
    count: { type: "integer", default: 2 },
    enabled: { type: "boolean", default: true },
    mode: { type: "string", enum: ["fast", "safe"] },
    tags: { type: "array", items: { type: "string", enum: ["a", "b"] } }
  },
  required: ["url"]
}

describe("workflow step registry", () => {
  it("builds registry entries for server-provided steps", () => {
    const registry = buildStepRegistry([
      { name: "foo_step", description: "Foo step", schema: sampleSchema }
    ])

    expect(registry.foo_step).toBeDefined()
    expect(registry.foo_step.label).toBe(humanizeStepType("foo_step"))
    expect(registry.foo_step.description).toBe("Foo step")
  })

  it("every backend step type has an explicit CATEGORY_OVERRIDES entry", () => {
    for (const [expectedCategory, types] of Object.entries(ALL_STEP_TYPES)) {
      for (const stepType of types) {
        const category = resolveStepCategory(stepType)
        expect(category, `${stepType} should be ${expectedCategory} but is ${category}`).toBe(expectedCategory)
      }
    }
  })

  it("every icon name in ICON_OVERRIDES exists in STEP_ICON_COMPONENTS", () => {
    for (const stepType of FLAT_STEP_TYPES) {
      const iconName = resolveStepIcon(stepType)
      expect(
        STEP_ICON_COMPONENTS[iconName],
        `Icon "${iconName}" for step "${stepType}" not in STEP_ICON_COMPONENTS`
      ).toBeDefined()
    }
    // Also check start/end
    for (const special of ["start", "end"]) {
      const iconName = resolveStepIcon(special)
      expect(
        STEP_ICON_COMPONENTS[iconName],
        `Icon "${iconName}" for step "${special}" not in STEP_ICON_COMPONENTS`
      ).toBeDefined()
    }
  })

  it("buildStepRegistry assigns correct categories for all step types", () => {
    const serverSteps = FLAT_STEP_TYPES.map((name) => ({
      name,
      description: `${name} description`
    }))
    const registry = buildStepRegistry(serverSteps)

    for (const [expectedCategory, types] of Object.entries(ALL_STEP_TYPES)) {
      for (const stepType of types) {
        expect(registry[stepType]).toBeDefined()
        expect(
          registry[stepType].category,
          `${stepType} in built registry should be ${expectedCategory}`
        ).toBe(expectedCategory)
      }
    }
  })

  it("no regressions on existing BASE_STEP_REGISTRY entries", () => {
    const expectedBaseEntries = [
      "prompt", "rag_search", "media_ingest", "branch", "map",
      "wait_for_human", "webhook", "tts", "stt_transcribe", "delay",
      "log", "start", "end"
    ]
    for (const type of expectedBaseEntries) {
      expect(BASE_STEP_REGISTRY[type], `${type} should be in BASE_STEP_REGISTRY`).toBeDefined()
      expect(BASE_STEP_REGISTRY[type].label).toBeTruthy()
      expect(BASE_STEP_REGISTRY[type].configSchema.length).toBeGreaterThan(0)
    }
  })

  it("STEP_CATEGORIES has all 10 categories", () => {
    const expected: StepCategory[] = [
      "ai", "search", "media", "text", "research",
      "audio", "video", "control", "io", "utility"
    ]
    for (const cat of expected) {
      expect(STEP_CATEGORIES[cat], `Category ${cat} should exist`).toBeDefined()
      expect(STEP_CATEGORIES[cat].label).toBeTruthy()
      expect(STEP_CATEGORIES[cat].color).toBeTruthy()
    }
  })

  it("all step types have unique non-default icons", () => {
    const stepsWithDefaultIcon: string[] = []
    for (const stepType of FLAT_STEP_TYPES) {
      const icon = resolveStepIcon(stepType)
      if (icon === "MessageSquare" && stepType !== "prompt" && stepType !== "llm" && stepType !== "prompts") {
        stepsWithDefaultIcon.push(stepType)
      }
    }
    expect(
      stepsWithDefaultIcon,
      `These step types still use the default MessageSquare icon: ${stepsWithDefaultIcon.join(", ")}`
    ).toEqual([])
  })

  it("total step type count is 124", () => {
    expect(FLAT_STEP_TYPES.length).toBe(124)
  })

  it("categories are ordered correctly", () => {
    const entries = Object.entries(STEP_CATEGORIES).sort(
      (a, b) => a[1].order - b[1].order
    )
    expect(entries.map(([k]) => k)).toEqual([
      "ai", "search", "media", "text", "research",
      "audio", "video", "control", "io", "utility"
    ])
  })
})

describe("schemaToConfigFields", () => {
  it("maps JSON schema properties to config fields", () => {
    const fields = schemaToConfigFields(sampleSchema)
    const byKey = Object.fromEntries(fields.map((field) => [field.key, field]))

    expect(byKey.url.type).toBe("url")
    expect(byKey.url.required).toBe(true)
    expect(byKey.count.type).toBe("number")
    expect(byKey.enabled.type).toBe("checkbox")
    expect(byKey.mode.type).toBe("select")
    expect(byKey.tags.type).toBe("multiselect")
  })

  it("assigns dynamic field types for common resource references", () => {
    const schema: WorkflowStepSchema = {
      type: "object",
      properties: {
        model: { type: "string" },
        prompt_id: { type: "string" },
        collection_id: { type: "string" },
        provider: { type: "string" },
        voice: { type: "string" },
        dataset_id: { type: "string" },
        run_id: { type: "string" },
        item_id: { type: "string" },
        output_id: { type: "string" },
        run_ids: { type: "array", items: { type: "string" } },
        item_ids: { type: "array", items: { type: "string" } }
      }
    }
    const fields = schemaToConfigFields(schema)
    const byKey = Object.fromEntries(fields.map((field) => [field.key, field]))

    expect(byKey.model.type).toBe("model-picker")
    expect(byKey.prompt_id.type).toBe("select")
    expect(byKey.collection_id.type).toBe("collection-picker")
    expect(byKey.provider.type).toBe("select")
    expect(byKey.voice.type).toBe("select")
    expect(byKey.dataset_id.type).toBe("select")
    expect(byKey.run_id.type).toBe("select")
    expect(byKey.item_id.type).toBe("select")
    expect(byKey.output_id.type).toBe("select")
    expect(byKey.run_ids.type).toBe("multiselect")
    expect(byKey.item_ids.type).toBe("multiselect")
  })
})
