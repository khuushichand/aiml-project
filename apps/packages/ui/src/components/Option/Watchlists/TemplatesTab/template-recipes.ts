export type TemplateRecipeId = "briefing_md" | "newsletter_html" | "mece_md"

export interface TemplateRecipeDefinition {
  id: TemplateRecipeId
  format: "md" | "html"
  labelKey: string
  fallbackLabel: string
  descriptionKey: string
  fallbackDescription: string
  supports: {
    executiveSummary?: boolean
    publishedAt?: boolean
    tags?: boolean
  }
}

export interface TemplateRecipeOptions {
  includeExecutiveSummary: boolean
  includeLinks: boolean
  includePublishedAt: boolean
  includeTags: boolean
}

export interface GeneratedTemplateRecipe {
  format: "md" | "html"
  content: string
  suggestedName: string
  suggestedDescription: string
}

export const TEMPLATE_RECIPE_DEFINITIONS: TemplateRecipeDefinition[] = [
  {
    id: "briefing_md",
    format: "md",
    labelKey: "watchlists:templates.recipe.briefingMd",
    fallbackLabel: "Briefing (Markdown)",
    descriptionKey: "watchlists:templates.recipe.briefingMdDescription",
    fallbackDescription: "Daily digest layout with summary and per-item entries.",
    supports: {
      executiveSummary: true,
      publishedAt: true,
      tags: true
    }
  },
  {
    id: "newsletter_html",
    format: "html",
    labelKey: "watchlists:templates.recipe.newsletterHtml",
    fallbackLabel: "Newsletter (HTML)",
    descriptionKey: "watchlists:templates.recipe.newsletterHtmlDescription",
    fallbackDescription: "Email-friendly HTML brief with linked story sections.",
    supports: {
      publishedAt: true
    }
  },
  {
    id: "mece_md",
    format: "md",
    labelKey: "watchlists:templates.recipe.meceMd",
    fallbackLabel: "MECE analysis (Markdown)",
    descriptionKey: "watchlists:templates.recipe.meceMdDescription",
    fallbackDescription: "Groups developments into distinct categories for analysis.",
    supports: {
      publishedAt: true,
      tags: true
    }
  }
]

export const createDefaultTemplateRecipeOptions = (): TemplateRecipeOptions => ({
  includeExecutiveSummary: true,
  includeLinks: true,
  includePublishedAt: true,
  includeTags: true
})

const buildBriefingMarkdown = (options: TemplateRecipeOptions): string => {
  const lines: string[] = [
    "# {{ title }}",
    "",
    "Generated: {{ generated_at }}",
    "Items: {{ item_count }}",
    ""
  ]

  if (options.includeExecutiveSummary) {
    lines.push(
      "{% if has_briefing_summary %}",
      "## Executive Summary",
      "",
      "{{ briefing_summary }}",
      "",
      "---",
      "{% endif %}",
      ""
    )
  }

  lines.push("{% for item in items %}", "## {{ item.title or 'Untitled' }}", "")

  if (options.includeLinks) {
    lines.push("{% if item.url %}[Read more]({{ item.url }}){% endif %}", "")
  }

  lines.push("{% if item.llm_summary %}{{ item.llm_summary }}{% elif item.summary %}{{ item.summary }}{% endif %}")

  if (options.includePublishedAt) {
    lines.push("", "{% if item.published_at %}Published: {{ item.published_at }}{% endif %}")
  }

  if (options.includeTags) {
    lines.push("{% if item.tags %}Tags: {{ item.tags | join(', ') }}{% endif %}")
  }

  lines.push("", "---", "{% endfor %}")
  return lines.join("\n")
}

const buildNewsletterHtml = (options: TemplateRecipeOptions): string => {
  const lines: string[] = [
    "<!DOCTYPE html>",
    "<html>",
    "<head><meta charset=\"utf-8\"><title>{{ title }}</title></head>",
    "<body>",
    "<h1>{{ title }}</h1>",
    "<p><em>Generated: {{ generated_at }}</em></p>",
    "<hr>",
    "{% for item in items %}",
    "<h2>{{ item.title or 'Untitled' }}</h2>",
    "{% if item.llm_summary %}<p>{{ item.llm_summary }}</p>{% elif item.summary %}<p>{{ item.summary }}</p>{% endif %}"
  ]

  if (options.includeLinks) {
    lines.push("{% if item.url %}<p><a href=\"{{ item.url }}\">Read more</a></p>{% endif %}")
  }

  if (options.includePublishedAt) {
    lines.push("{% if item.published_at %}<p><small>Published: {{ item.published_at }}</small></p>{% endif %}")
  }

  lines.push("<hr>", "{% endfor %}", "</body>", "</html>")
  return lines.join("\n")
}

const buildMecMarkdown = (options: TemplateRecipeOptions): string => {
  const lines: string[] = [
    "# {{ title }} — MECE Analysis",
    "",
    "Generated: {{ generated_at }}",
    "",
    "{% set categorized = {} %}",
    "{% for item in items %}",
    "{% set cat = item.tags[0] if item.tags else 'Uncategorized' %}",
    "{% if cat not in categorized %}{% set _ = categorized.update({cat: []}) %}{% endif %}",
    "{% set _ = categorized[cat].append(item) %}",
    "{% endfor %}",
    "",
    "{% for category, cat_items in categorized.items() %}",
    "## {{ category }}",
    ""
  ]

  lines.push("{% for item in cat_items %}", "- **{{ item.title or 'Untitled' }}**")

  if (options.includeLinks) {
    lines.push("  {% if item.url %}[link]({{ item.url }}){% endif %}")
  }

  lines.push("  {% if item.llm_summary %}{{ item.llm_summary }}{% elif item.summary %}{{ item.summary }}{% endif %}")

  if (options.includePublishedAt) {
    lines.push("  {% if item.published_at %}Published: {{ item.published_at }}{% endif %}")
  }

  if (options.includeTags) {
    lines.push("  {% if item.tags %}Tags: {{ item.tags | join(', ') }}{% endif %}")
  }

  lines.push("{% endfor %}", "", "{% endfor %}")

  return lines.join("\n")
}

export const buildTemplateFromRecipe = (
  recipeId: TemplateRecipeId,
  options: TemplateRecipeOptions
): GeneratedTemplateRecipe => {
  if (recipeId === "newsletter_html") {
    return {
      format: "html",
      content: buildNewsletterHtml(options),
      suggestedName: "newsletter_html",
      suggestedDescription: "Newsletter-style HTML briefing template"
    }
  }

  if (recipeId === "mece_md") {
    return {
      format: "md",
      content: buildMecMarkdown(options),
      suggestedName: "mece_md",
      suggestedDescription: "MECE analytical markdown briefing template"
    }
  }

  return {
    format: "md",
    content: buildBriefingMarkdown(options),
    suggestedName: "briefing_md",
    suggestedDescription: "Daily markdown briefing template"
  }
}
