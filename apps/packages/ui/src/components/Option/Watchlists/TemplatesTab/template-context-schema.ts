/**
 * Canonical template context variable definitions.
 * Must match the output of _build_output_context() in watchlists.py.
 */

export interface TemplateVariable {
  key: string
  label: string
  description: string
  type: "string" | "number" | "boolean" | "object" | "array"
  category: "top_level" | "job" | "run" | "item" | "groups" | "conditional"
  insertText: string
  /** If true, this is a nested property (e.g., item.title) */
  nested?: boolean
}

export const TEMPLATE_VARIABLES: TemplateVariable[] = [
  // Top-level
  { key: "title", label: "title", description: "Output title", type: "string", category: "top_level", insertText: "{{ title }}" },
  { key: "generated_at", label: "generated_at", description: "Generation timestamp (ISO 8601)", type: "string", category: "top_level", insertText: "{{ generated_at }}" },
  { key: "item_count", label: "item_count", description: "Total number of items", type: "number", category: "top_level", insertText: "{{ item_count }}" },
  { key: "items", label: "items", description: "List of scraped items", type: "array", category: "top_level", insertText: "{{ items }}" },
  { key: "items_markdown", label: "items_markdown", description: "Pre-rendered markdown lines for each item", type: "array", category: "top_level", insertText: "{{ items_markdown }}" },
  { key: "items_html", label: "items_html", description: "Pre-rendered HTML entries for each item", type: "array", category: "top_level", insertText: "{{ items_html }}" },

  // Job
  { key: "job", label: "job", description: "Job object", type: "object", category: "job", insertText: "{{ job }}" },
  { key: "job.id", label: "job.id", description: "Job ID", type: "number", category: "job", insertText: "{{ job.id }}", nested: true },
  { key: "job.name", label: "job.name", description: "Job name", type: "string", category: "job", insertText: "{{ job.name }}", nested: true },
  { key: "job.description", label: "job.description", description: "Job description", type: "string", category: "job", insertText: "{{ job.description }}", nested: true },

  // Run
  { key: "run", label: "run", description: "Run object", type: "object", category: "run", insertText: "{{ run }}" },
  { key: "run.id", label: "run.id", description: "Run ID", type: "number", category: "run", insertText: "{{ run.id }}", nested: true },
  { key: "run.status", label: "run.status", description: "Run status", type: "string", category: "run", insertText: "{{ run.status }}", nested: true },
  { key: "run.stats", label: "run.stats", description: "Run statistics object", type: "object", category: "run", insertText: "{{ run.stats }}", nested: true },

  // Item properties (used inside {% for item in items %})
  { key: "item.id", label: "item.id", description: "Item ID", type: "number", category: "item", insertText: "{{ item.id }}", nested: true },
  { key: "item.title", label: "item.title", description: "Item title", type: "string", category: "item", insertText: "{{ item.title }}", nested: true },
  { key: "item.url", label: "item.url", description: "Item URL", type: "string", category: "item", insertText: "{{ item.url }}", nested: true },
  { key: "item.domain", label: "item.domain", description: "Item domain", type: "string", category: "item", insertText: "{{ item.domain }}", nested: true },
  { key: "item.summary", label: "item.summary", description: "Item summary text", type: "string", category: "item", insertText: "{{ item.summary }}", nested: true },
  { key: "item.llm_summary", label: "item.llm_summary", description: "LLM-generated summary (when summarize=true)", type: "string", category: "item", insertText: "{{ item.llm_summary }}", nested: true },
  { key: "item.published_at", label: "item.published_at", description: "Publish date", type: "string", category: "item", insertText: "{{ item.published_at }}", nested: true },
  { key: "item.tags", label: "item.tags", description: "Tag list", type: "array", category: "item", insertText: "{{ item.tags }}", nested: true },
  { key: "item.source_id", label: "item.source_id", description: "Source ID", type: "number", category: "item", insertText: "{{ item.source_id }}", nested: true },
  { key: "item.index", label: "item.index", description: "1-based item index", type: "number", category: "item", insertText: "{{ item.index }}", nested: true },
  { key: "item.markdown_line", label: "item.markdown_line", description: "Pre-rendered markdown for this item", type: "string", category: "item", insertText: "{{ item.markdown_line }}", nested: true },
  { key: "item.html_entry", label: "item.html_entry", description: "Pre-rendered HTML for this item", type: "string", category: "item", insertText: "{{ item.html_entry }}", nested: true },

  // Groups
  { key: "groups", label: "groups", description: "List of item groups", type: "array", category: "groups", insertText: "{{ groups }}" },
  { key: "group_count", label: "group_count", description: "Number of groups", type: "number", category: "groups", insertText: "{{ group_count }}" },
  { key: "has_groups", label: "has_groups", description: "Whether groups are available", type: "boolean", category: "groups", insertText: "{{ has_groups }}" },
  { key: "group.name", label: "group.name", description: "Group name", type: "string", category: "groups", insertText: "{{ group.name }}", nested: true },
  { key: "group.items", label: "group.items", description: "Items in this group", type: "array", category: "groups", insertText: "{{ group.items }}", nested: true },
  { key: "group.item_count", label: "group.item_count", description: "Count of items in group", type: "number", category: "groups", insertText: "{{ group.item_count }}", nested: true },
  { key: "group.summary", label: "group.summary", description: "Group LLM summary (when per_group_summaries=true)", type: "string", category: "groups", insertText: "{{ group.summary }}", nested: true },

  // Conditional / Briefing
  { key: "briefing_summary", label: "briefing_summary", description: "Briefing-level LLM summary", type: "string", category: "conditional", insertText: "{{ briefing_summary }}" },
  { key: "has_briefing_summary", label: "has_briefing_summary", description: "Whether briefing summary is available", type: "boolean", category: "conditional", insertText: "{{ has_briefing_summary }}" },
  { key: "has_llm_summaries", label: "has_llm_summaries", description: "Whether LLM per-item summaries exist", type: "boolean", category: "conditional", insertText: "{{ has_llm_summaries }}" },
]

export const CATEGORY_LABELS: Record<string, string> = {
  top_level: "Top-level",
  job: "Job",
  run: "Run",
  item: "Item (inside loop)",
  groups: "Groups",
  conditional: "Conditional / Summary",
}

export const CATEGORY_ORDER: string[] = ["top_level", "job", "run", "item", "groups", "conditional"]
