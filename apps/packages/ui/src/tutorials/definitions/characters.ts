/**
 * Characters Tutorial Definitions
 */

import { UsersRound } from "lucide-react"
import type { TutorialDefinition } from "../registry"

const charactersBasics: TutorialDefinition = {
  id: "characters-basics",
  routePattern: "/characters",
  labelKey: "tutorials:characters.basics.label",
  labelFallback: "Characters Basics",
  descriptionKey: "tutorials:characters.basics.description",
  descriptionFallback:
    "Create, filter, and manage reusable character assistants for chat workflows",
  icon: UsersRound,
  priority: 1,
  steps: [
    {
      target: '[data-testid="characters-new-button"]',
      titleKey: "tutorials:characters.basics.newTitle",
      titleFallback: "Create Character",
      contentKey: "tutorials:characters.basics.newContent",
      contentFallback:
        "Start here to create a new character with persona, prompt, greeting, and metadata.",
      placement: "bottom",
      disableBeacon: true
    },
    {
      target: '[data-testid="characters-search-input"]',
      titleKey: "tutorials:characters.basics.searchTitle",
      titleFallback: "Search Characters",
      contentKey: "tutorials:characters.basics.searchContent",
      contentFallback:
        "Filter your character library by name, description, tags, or prompt content.",
      placement: "bottom"
    },
    {
      target: '[data-testid="characters-scope-segmented"]',
      titleKey: "tutorials:characters.basics.scopeTitle",
      titleFallback: "Active vs Deleted",
      contentKey: "tutorials:characters.basics.scopeContent",
      contentFallback:
        "Switch between active and deleted characters to recover or permanently remove entries.",
      placement: "bottom"
    },
    {
      target: '[data-testid="characters-view-mode-segmented"]',
      titleKey: "tutorials:characters.basics.viewTitle",
      titleFallback: "Table and Gallery Views",
      contentKey: "tutorials:characters.basics.viewContent",
      contentFallback:
        "Toggle between table and gallery layouts based on whether you need dense controls or visual browsing.",
      placement: "bottom"
    },
    {
      target:
        '[data-testid="characters-table-view"], [data-testid="characters-gallery-view"]',
      titleKey: "tutorials:characters.basics.libraryTitle",
      titleFallback: "Character Library",
      contentKey: "tutorials:characters.basics.libraryContent",
      contentFallback:
        "Open character actions to chat, quick-chat, edit, duplicate, export, or review version history.",
      placement: "top"
    }
  ]
}

export const charactersTutorials: TutorialDefinition[] = [charactersBasics]
