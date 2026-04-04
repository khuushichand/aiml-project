/**
 * Moderation Playground Tutorial Definitions
 */

import { ShieldCheck } from "lucide-react"
import type { TutorialDefinition } from "../registry"

const moderationBasics: TutorialDefinition = {
  id: "moderation-basics",
  routePattern: "/moderation-playground",
  labelKey: "tutorials:moderation.basics.label",
  labelFallback: "Content Controls Basics",
  descriptionKey: "tutorials:moderation.basics.description",
  descriptionFallback:
    "Learn how to set up content safety rules, blocklists, and test moderation.",
  icon: ShieldCheck,
  priority: 1,
  steps: [
    {
      target: '[data-testid="moderation-hero"]',
      titleKey: "tutorials:moderation.basics.heroTitle",
      titleFallback: "Moderation Dashboard",
      contentKey: "tutorials:moderation.basics.heroContent",
      contentFallback:
        "This is your content safety hub. The status badge shows whether your server is connected.",
      placement: "bottom",
      disableBeacon: true
    },
    {
      target: '[data-testid="moderation-tab-policy"]',
      titleKey: "tutorials:moderation.basics.policyTitle",
      titleFallback: "Policy & Settings",
      contentKey: "tutorials:moderation.basics.policyContent",
      contentFallback:
        "Start here. Set your base content safety policy — what categories to filter and how strictly.",
      placement: "bottom",
      disableBeacon: true
    },
    {
      target: '[data-testid="moderation-tab-blocklist"]',
      titleKey: "tutorials:moderation.basics.blocklistTitle",
      titleFallback: "Blocklist Studio",
      contentKey: "tutorials:moderation.basics.blocklistContent",
      contentFallback:
        "Add specific words, phrases, or patterns you want to always block or flag.",
      placement: "bottom",
      disableBeacon: true
    },
    {
      target: '[data-testid="moderation-tab-test"]',
      titleKey: "tutorials:moderation.basics.testTitle",
      titleFallback: "Test Sandbox",
      contentKey: "tutorials:moderation.basics.testContent",
      contentFallback:
        "Try your rules in real time. Type a message and see whether it would be allowed or blocked.",
      placement: "bottom",
      disableBeacon: true
    }
  ]
}

export const moderationTutorials: TutorialDefinition[] = [moderationBasics]
