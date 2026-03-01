import { describe, expect, it } from "vitest"
import {
  buildTemplateFromRecipe,
  createDefaultTemplateRecipeOptions
} from "../template-recipes"

describe("template recipe builder", () => {
  it("builds briefing markdown recipe with optional sections", () => {
    const options = {
      ...createDefaultTemplateRecipeOptions(),
      includeExecutiveSummary: false,
      includeTags: false
    }

    const result = buildTemplateFromRecipe("briefing_md", options)

    expect(result.format).toBe("md")
    expect(result.suggestedName).toBe("briefing_md")
    expect(result.content).toContain("# {{ title }}")
    expect(result.content).not.toContain("## Executive Summary")
    expect(result.content).not.toContain("Tags: {{ item.tags")
  })

  it("builds newsletter html recipe and honors link toggle", () => {
    const options = {
      ...createDefaultTemplateRecipeOptions(),
      includeLinks: false
    }

    const result = buildTemplateFromRecipe("newsletter_html", options)

    expect(result.format).toBe("html")
    expect(result.suggestedName).toBe("newsletter_html")
    expect(result.content).toContain("<html>")
    expect(result.content).not.toContain("Read more</a>")
  })

  it("builds mece markdown recipe with category grouping", () => {
    const result = buildTemplateFromRecipe("mece_md", createDefaultTemplateRecipeOptions())

    expect(result.format).toBe("md")
    expect(result.suggestedName).toBe("mece_md")
    expect(result.content).toContain("{% set categorized = {} %}")
    expect(result.content).toContain("{% for category, cat_items in categorized.items() %}")
  })
})
