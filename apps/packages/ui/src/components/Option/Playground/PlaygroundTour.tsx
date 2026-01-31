import React from "react"
import Joyride, { CallBackProps, STATUS, Step } from "react-joyride"
import { useTranslation } from "react-i18next"

const TOUR_STORAGE_KEY = "playground-tour-completed"

interface PlaygroundTourProps {
  run: boolean
  onComplete: () => void
}

/**
 * Guided onboarding tour for the Playground using react-joyride.
 * Highlights key features: model selector, chat input, tools button, and voice chat.
 */
export const PlaygroundTour: React.FC<PlaygroundTourProps> = ({ run, onComplete }) => {
  const { t } = useTranslation(["playground"])

  const steps: Step[] = React.useMemo(() => [
    {
      target: '[data-testid="model-selector"]',
      title: t("playground:tour.modelTitle", "Choose a Model"),
      content: t("playground:tour.modelContent", "Select an AI model to chat with. Different models have different capabilities - look for tags like 'Vision' or 'Fast'. Star your favorites for quick access."),
      disableBeacon: true,
      placement: "bottom" as const
    },
    {
      target: '[data-testid="chat-input"]',
      title: t("playground:tour.slashTitle", "Slash Commands"),
      content: t("playground:tour.slashContent", "Type / to see available commands. Try /search to find content in your knowledge base, or /web to search the internet."),
      placement: "top" as const
    },
    {
      target: '[data-testid="attachment-button"]',
      title: t("playground:tour.toolsTitle", "Attach files"),
      content: t("playground:tour.toolsContent", "Attach images or documents to include them in your message. Manage context from Knowledge Search → Context."),
      placement: "top" as const
    },
    {
      target: '[data-testid="voice-chat-button"]',
      title: t("playground:tour.voiceTitle", "Voice Chat"),
      content: t("playground:tour.voiceContent", "Start a hands-free voice conversation. Speak naturally and hear AI responses aloud."),
      placement: "top" as const,
      isFixed: true
    }
  ], [t])

  const handleJoyrideCallback = React.useCallback((data: CallBackProps) => {
    const { status } = data
    const finishedStatuses: string[] = [STATUS.FINISHED, STATUS.SKIPPED]

    if (finishedStatuses.includes(status)) {
      if (typeof window !== "undefined") {
        localStorage.setItem(TOUR_STORAGE_KEY, "true")
      }
      onComplete()
    }
  }, [onComplete])

  return (
    <Joyride
      steps={steps}
      run={run}
      continuous
      showProgress
      showSkipButton
      callback={handleJoyrideCallback}
      styles={{
        options: {
          primaryColor: "var(--color-primary, #6366f1)",
          textColor: "var(--color-text, #1f2937)",
          backgroundColor: "var(--color-surface, #ffffff)",
          arrowColor: "var(--color-surface, #ffffff)",
          overlayColor: "rgba(0, 0, 0, 0.5)",
          zIndex: 10000
        },
        tooltip: {
          borderRadius: 12,
          padding: 16
        },
        buttonNext: {
          borderRadius: 8,
          padding: "8px 16px"
        },
        buttonBack: {
          marginRight: 8
        },
        buttonSkip: {
          color: "var(--color-text-muted, #6b7280)"
        }
      }}
      locale={{
        back: t("playground:tour.back", "Back"),
        close: t("playground:tour.close", "Close"),
        last: t("playground:tour.finish", "Finish"),
        next: t("playground:tour.next", "Next"),
        skip: t("playground:tour.skip", "Skip tour")
      }}
    />
  )
}

/**
 * Hook for managing the playground tour state.
 * Automatically starts the tour for first-time users.
 */
export const usePlaygroundTour = () => {
  const [runTour, setRunTour] = React.useState(false)
  const [hasSeenTour, setHasSeenTour] = React.useState(true)

  React.useEffect(() => {
    if (typeof window === "undefined") return
    const seen = localStorage.getItem(TOUR_STORAGE_KEY)
    setHasSeenTour(!!seen)
    // Auto-start tour for first-time users after a short delay
    if (!seen) {
      const timer = setTimeout(() => setRunTour(true), 1500)
      return () => clearTimeout(timer)
    }
  }, [])

  const startTour = React.useCallback(() => {
    setRunTour(true)
  }, [])

  const completeTour = React.useCallback(() => {
    setRunTour(false)
    setHasSeenTour(true)
  }, [])

  const resetTour = React.useCallback(() => {
    if (typeof window !== "undefined") {
      localStorage.removeItem(TOUR_STORAGE_KEY)
    }
    setHasSeenTour(false)
    setRunTour(true)
  }, [])

  return { runTour, hasSeenTour, startTour, completeTour, resetTour }
}
