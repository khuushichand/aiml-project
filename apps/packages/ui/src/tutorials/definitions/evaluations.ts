/**
 * Evaluations Tutorial Definitions
 */

import { FlaskConical } from "lucide-react"
import type { TutorialDefinition } from "../registry"

const evaluationsBasics: TutorialDefinition = {
  id: "evaluations-basics",
  routePattern: "/evaluations",
  labelKey: "tutorials:evaluations.basics.label",
  labelFallback: "Evaluations Basics",
  descriptionKey: "tutorials:evaluations.basics.description",
  descriptionFallback:
    "Create evaluations, inspect recent runs, and navigate evaluation tabs",
  icon: FlaskConical,
  priority: 1,
  steps: [
    {
      target: '[data-testid="evaluations-page-title"]',
      titleKey: "tutorials:evaluations.basics.headerTitle",
      titleFallback: "Evaluations Workspace",
      contentKey: "tutorials:evaluations.basics.headerContent",
      contentFallback:
        "Use this workspace to define evaluation specs and monitor quality over time.",
      placement: "bottom",
      disableBeacon: true
    },
    {
      target: '[data-testid="evaluations-tabs"]',
      titleKey: "tutorials:evaluations.basics.tabsTitle",
      titleFallback: "Tab Navigation",
      contentKey: "tutorials:evaluations.basics.tabsContent",
      contentFallback:
        "Switch between Evaluations, Runs, Datasets, Webhooks, and History depending on your workflow stage.",
      placement: "bottom"
    },
    {
      target: '[data-testid="evaluations-create-button"]',
      titleKey: "tutorials:evaluations.basics.createTitle",
      titleFallback: "Create Evaluation",
      contentKey: "tutorials:evaluations.basics.createContent",
      contentFallback:
        "Start here to define a new evaluation and attach a dataset or inline samples.",
      placement: "left"
    },
    {
      target: '[data-testid="evaluations-list-card"]',
      titleKey: "tutorials:evaluations.basics.listTitle",
      titleFallback: "Recent Evaluations",
      contentKey: "tutorials:evaluations.basics.listContent",
      contentFallback:
        "Select an evaluation from this list to inspect details, edit it, or run it.",
      placement: "right"
    },
    {
      target: '[data-testid="evaluations-detail-card"]',
      titleKey: "tutorials:evaluations.basics.detailTitle",
      titleFallback: "Evaluation Details",
      contentKey: "tutorials:evaluations.basics.detailContent",
      contentFallback:
        "Review selected evaluation metadata and copy IDs needed for automation and debugging.",
      placement: "top"
    }
  ]
}

export const evaluationsTutorials: TutorialDefinition[] = [evaluationsBasics]
