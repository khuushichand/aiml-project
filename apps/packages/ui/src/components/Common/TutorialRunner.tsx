/**
 * TutorialRunner Component
 * Wraps React Joyride to run tutorials from the registry
 */

import React from "react"
import Joyride, {
  CallBackProps,
  STATUS,
  EVENTS,
  ACTIONS,
  type Step
} from "react-joyride"
import { useTranslation } from "react-i18next"
import { useActiveTutorial } from "@/store/tutorials"
import { getTutorialById, type TutorialDefinition } from "@/tutorials"

// ─────────────────────────────────────────────────────────────────────────────
// Styles
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Joyride styles matching the app's design system
 */
const tutorialStyles = {
  options: {
    primaryColor: "rgb(var(--color-primary, 99 102 241))",
    textColor: "rgb(var(--color-text, 31 41 55))",
    backgroundColor: "rgb(var(--color-surface, 255 255 255))",
    arrowColor: "rgb(var(--color-surface, 255 255 255))",
    overlayColor: "rgba(0, 0, 0, 0.5)",
    zIndex: 10000
  },
  tooltip: {
    borderRadius: 12,
    padding: 16
  },
  tooltipContainer: {
    textAlign: "left" as const
  },
  tooltipTitle: {
    fontSize: 16,
    fontWeight: 600,
    marginBottom: 8
  },
  tooltipContent: {
    fontSize: 14,
    lineHeight: 1.5
  },
  buttonNext: {
    borderRadius: 8,
    padding: "8px 16px",
    fontSize: 14,
    fontWeight: 500
  },
  buttonBack: {
    marginRight: 8,
    fontSize: 14
  },
  buttonSkip: {
    color: "rgb(var(--color-text-muted, 107 114 128))",
    fontSize: 14
  },
  buttonClose: {
    padding: 8
  },
  spotlight: {
    borderRadius: 8
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────

export const TutorialRunner: React.FC = () => {
  const { t } = useTranslation(["tutorials", "common"])
  const {
    activeTutorialId,
    activeStepIndex,
    endTutorial,
    setStepIndex,
    markComplete
  } = useActiveTutorial()

  // Get the tutorial definition
  const tutorial: TutorialDefinition | undefined = activeTutorialId
    ? getTutorialById(activeTutorialId)
    : undefined

  /**
   * Convert tutorial steps to Joyride format with i18n
   */
  const joyrideSteps: Step[] = React.useMemo(() => {
    if (!tutorial) return []

    return tutorial.steps.map((step) => ({
      target: step.target,
      title: t(step.titleKey, step.titleFallback),
      content: t(step.contentKey, step.contentFallback),
      placement: step.placement || "auto",
      disableBeacon: step.disableBeacon ?? false,
      spotlightClicks: step.spotlightClicks ?? false,
      isFixed: step.isFixed ?? false
    }))
  }, [tutorial, t])

  /**
   * Joyride locale strings
   */
  const joyrideLocale = React.useMemo(
    () => ({
      back: t("tutorials:controls.back", "Back"),
      close: t("tutorials:controls.close", "Close"),
      last: t("tutorials:controls.finish", "Finish"),
      next: t("tutorials:controls.next", "Next"),
      skip: t("tutorials:controls.skip", "Skip tour"),
      open: t("tutorials:controls.open", "Open the dialog")
    }),
    [t]
  )

  /**
   * Handle Joyride callbacks
   */
  const handleCallback = React.useCallback(
    (data: CallBackProps) => {
      const { status, index, type, action } = data

      // Tutorial finished or skipped
      if (status === STATUS.FINISHED || status === STATUS.SKIPPED) {
        if (status === STATUS.FINISHED && activeTutorialId) {
          markComplete(activeTutorialId)
        }
        endTutorial()
        return
      }

      // Step progression
      if (type === EVENTS.STEP_AFTER) {
        if (action === ACTIONS.NEXT) {
          setStepIndex(index + 1)
        } else if (action === ACTIONS.PREV) {
          setStepIndex(index - 1)
        }
      }

      // Target not found - skip to next step or end
      if (type === EVENTS.TARGET_NOT_FOUND) {
        console.warn(
          `[TutorialRunner] Target not found for step ${index}:`,
          joyrideSteps[index]?.target
        )
        // Try to move to the next step
        if (index < joyrideSteps.length - 1) {
          setStepIndex(index + 1)
        } else {
          // Last step, end the tutorial
          if (activeTutorialId) {
            markComplete(activeTutorialId)
          }
          endTutorial()
        }
      }
    },
    [
      activeTutorialId,
      endTutorial,
      markComplete,
      setStepIndex,
      joyrideSteps.length
    ]
  )

  // Don't render if no active tutorial
  if (!tutorial || joyrideSteps.length === 0) {
    return null
  }

  return (
    <Joyride
      steps={joyrideSteps}
      run={true}
      stepIndex={activeStepIndex}
      continuous
      showProgress
      showSkipButton
      scrollToFirstStep
      disableScrolling={false}
      callback={handleCallback}
      styles={tutorialStyles}
      locale={joyrideLocale}
      floaterProps={{
        disableAnimation: false
      }}
    />
  )
}

export default TutorialRunner
