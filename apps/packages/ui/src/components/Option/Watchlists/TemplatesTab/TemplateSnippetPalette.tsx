import React, { useMemo, useState } from "react"
import { Button, Input, Tag } from "antd"

export interface TemplateSnippet {
  label: string
  category: string
  description: string
  snippet: {
    md: string
    html: string
  }
}

const SNIPPETS: TemplateSnippet[] = [
  {
    label: "Items loop",
    category: "Basic",
    description: "Iterate over all items",
    snippet: {
      md: "{% for item in items %}\n## {{ item.title }}\n{{ item.url }}\n\n{{ item.summary }}\n\n---\n{% endfor %}",
      html: "{% for item in items %}\n<div class=\"item\">\n  <h3><a href=\"{{ item.url }}\">{{ item.title }}</a></h3>\n  <p>{{ item.summary }}</p>\n</div>\n{% endfor %}",
    },
  },
  {
    label: "Groups loop",
    category: "Groups",
    description: "Iterate over item groups",
    snippet: {
      md: "{% if has_groups %}\n{% for group in groups %}\n## {{ group.name }} ({{ group.item_count }} items)\n\n{% if group.summary %}\n> {{ group.summary }}\n{% endif %}\n\n{% for item in group.items %}\n- [{{ item.title }}]({{ item.url }})\n{% endfor %}\n\n{% endfor %}\n{% endif %}",
      html: "{% if has_groups %}\n{% for group in groups %}\n<div class=\"group\">\n  <h2>{{ group.name }} ({{ group.item_count }})</h2>\n  {% if group.summary %}<p class=\"group-summary\">{{ group.summary }}</p>{% endif %}\n  {% for item in group.items %}\n  <div class=\"item\"><a href=\"{{ item.url }}\">{{ item.title }}</a></div>\n  {% endfor %}\n</div>\n{% endfor %}\n{% endif %}",
    },
  },
  {
    label: "Briefing summary",
    category: "Summary",
    description: "Show briefing-level executive summary",
    snippet: {
      md: "{% if has_briefing_summary %}\n## Executive Summary\n\n{{ briefing_summary }}\n\n---\n{% endif %}",
      html: "{% if has_briefing_summary %}\n<div class=\"briefing-summary\">\n  <h2>Executive Summary</h2>\n  <p>{{ briefing_summary }}</p>\n</div>\n{% endif %}",
    },
  },
  {
    label: "Group summary",
    category: "Groups",
    description: "Show per-group LLM summary",
    snippet: {
      md: "{% if group.summary %}\n> {{ group.summary }}\n{% endif %}",
      html: "{% if group.summary %}\n<blockquote>{{ group.summary }}</blockquote>\n{% endif %}",
    },
  },
  {
    label: "LLM summary with fallback",
    category: "Summary",
    description: "Show LLM summary if available, else regular summary",
    snippet: {
      md: "{% if item.llm_summary %}\n{{ item.llm_summary }}\n{% elif item.summary %}\n{{ item.summary }}\n{% endif %}",
      html: "{% if item.llm_summary %}\n<p>{{ item.llm_summary }}</p>\n{% elif item.summary %}\n<p>{{ item.summary }}</p>\n{% endif %}",
    },
  },
  {
    label: "Conditional LLM check",
    category: "Conditional",
    description: "Check if LLM summaries were generated",
    snippet: {
      md: "{% if has_llm_summaries %}\n*AI-enhanced summaries included*\n{% endif %}",
      html: "{% if has_llm_summaries %}\n<em>AI-enhanced summaries included</em>\n{% endif %}",
    },
  },
  {
    label: "Item metadata",
    category: "Basic",
    description: "Show item tags and publish date",
    snippet: {
      md: "{% if item.published_at %}- Published: {{ item.published_at }}{% endif %}\n{% if item.tags %}- Tags: {{ item.tags | join(\", \") }}{% endif %}",
      html: "{% if item.published_at %}<span class=\"date\">{{ item.published_at }}</span>{% endif %}\n{% if item.tags %}<span class=\"tags\">{{ item.tags | join(\", \") }}</span>{% endif %}",
    },
  },
  {
    label: "Header",
    category: "Basic",
    description: "Title and generation info",
    snippet: {
      md: "# {{ title }}\n\nGenerated: {{ generated_at }} | Items: {{ item_count }}",
      html: "<h1>{{ title }}</h1>\n<p>Generated: {{ generated_at }} | Items: {{ item_count }}</p>",
    },
  },
]

const SNIPPET_CATEGORIES = ["Basic", "Groups", "Summary", "Conditional"]

interface TemplateSnippetPaletteProps {
  format: "md" | "html"
  onInsert: (snippet: string) => void
}

export const TemplateSnippetPalette: React.FC<TemplateSnippetPaletteProps> = ({ format, onInsert }) => {
  const [search, setSearch] = useState("")

  const filtered = useMemo(() => {
    if (!search.trim()) return SNIPPETS
    const q = search.toLowerCase()
    return SNIPPETS.filter(
      (s) =>
        s.label.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q) ||
        s.category.toLowerCase().includes(q)
    )
  }, [search])

  const grouped = useMemo(() => {
    const map: Record<string, TemplateSnippet[]> = {}
    for (const s of filtered) {
      ;(map[s.category] ??= []).push(s)
    }
    return map
  }, [filtered])

  return (
    <div className="space-y-3">
      <Input
        placeholder="Search snippets…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        allowClear
        size="small"
      />
      <div className="max-h-[420px] overflow-auto space-y-3">
        {SNIPPET_CATEGORIES.filter((cat) => grouped[cat]?.length).map((cat) => (
          <div key={cat}>
            <div className="text-xs font-semibold text-text-muted mb-1">
              {cat} <Tag className="ml-1">{grouped[cat].length}</Tag>
            </div>
            <div className="space-y-1 ml-1">
              {grouped[cat].map((s) => (
                <div
                  key={s.label}
                  className="flex items-center justify-between gap-2 rounded px-2 py-1.5 hover:bg-surface border border-transparent hover:border-border"
                >
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-medium">{s.label}</div>
                    <div className="text-[11px] text-text-muted">{s.description}</div>
                  </div>
                  <Button
                    size="small"
                    onClick={() => onInsert(s.snippet[format])}
                  >
                    Insert
                  </Button>
                </div>
              ))}
            </div>
          </div>
        ))}
        {Object.keys(grouped).length === 0 && (
          <div className="text-xs text-text-muted p-2">No matching snippets found.</div>
        )}
      </div>
    </div>
  )
}

export default TemplateSnippetPalette
