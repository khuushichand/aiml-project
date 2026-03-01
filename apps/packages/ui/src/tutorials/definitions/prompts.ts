/**
 * Prompts Tutorial Definitions
 */

import { SquarePen } from "lucide-react"
import type { TutorialDefinition } from "../registry"

const promptsBasics: TutorialDefinition = {
  id: "prompts-basics",
  routePattern: "/prompts",
  labelKey: "tutorials:prompts.basics.label",
  labelFallback: "Prompts Basics",
  descriptionKey: "tutorials:prompts.basics.description",
  descriptionFallback:
    "Create reusable prompts, search your library, and manage prompt workflow segments",
  icon: SquarePen,
  priority: 1,
  steps: [
    {
      target: '[data-testid="prompts-segmented"]',
      titleKey: "tutorials:prompts.basics.segmentedTitle",
      titleFallback: "Prompt Workspaces",
      contentKey: "tutorials:prompts.basics.segmentedContent",
      contentFallback:
        "Switch between Custom, Copilot, Studio, and Trash to manage different prompt sources.",
      placement: "bottom",
      disableBeacon: true
    },
    {
      target: '[data-testid="prompts-add"]',
      titleKey: "tutorials:prompts.basics.createTitle",
      titleFallback: "Create Prompt",
      contentKey: "tutorials:prompts.basics.createContent",
      contentFallback:
        "Create a reusable prompt template you can insert into chat conversations.",
      placement: "bottom"
    },
    {
      target: '[data-testid="prompts-search"]',
      titleKey: "tutorials:prompts.basics.searchTitle",
      titleFallback: "Search Prompts",
      contentKey: "tutorials:prompts.basics.searchContent",
      contentFallback:
        "Search prompt names, content, and keywords to quickly find the right template.",
      placement: "bottom"
    },
    {
      target: '[data-testid="prompts-type-filter"], [data-testid="prompts-tag-filter"]',
      titleKey: "tutorials:prompts.basics.filtersTitle",
      titleFallback: "Filter and Scope",
      contentKey: "tutorials:prompts.basics.filtersContent",
      contentFallback:
        "Use type and tag filters to narrow your prompt list before editing or running prompts.",
      placement: "bottom"
    },
    {
      target: '[data-testid="prompts-export"], [data-testid="prompts-import"]',
      titleKey: "tutorials:prompts.basics.transferTitle",
      titleFallback: "Import and Export",
      contentKey: "tutorials:prompts.basics.transferContent",
      contentFallback:
        "Export prompts for backup or sharing, and import prompt sets to bootstrap new workflows.",
      placement: "left"
    }
  ]
}

export const promptsTutorials: TutorialDefinition[] = [promptsBasics]
