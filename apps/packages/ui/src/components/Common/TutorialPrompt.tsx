/**
 * TutorialPrompt Component
 * Shows a toast notification on first visit to pages with tutorials
 */

import React, { useEffect, useRef } from "react"
import { useLocation } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { notification, Button, Space } from "antd"
import { GraduationCap } from "lucide-react"
import { useTutorialStore } from "@/store/tutorials"
import { getPrimaryTutorialForRoute, hasTutorialsForRoute } from "@/tutorials"

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

/** Delay before showing the prompt (ms) to let the page settle */
const PROMPT_DELAY_MS = 2000

/** Duration the notification stays open (0 = manual close only) */
const NOTIFICATION_DURATION = 0

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────

export const TutorialPrompt: React.FC = () => {
  const { t } = useTranslation(["tutorials", "common"])
  const location = useLocation()
  const [api, contextHolder] = notification.useNotification()
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const shownRef = useRef<Set<string>>(new Set())

  const hasSeenPromptForPage = useTutorialStore((state) => state.hasSeenPromptForPage)
  const markPromptSeen = useTutorialStore((state) => state.markPromptSeen)
  const startTutorial = useTutorialStore((state) => state.startTutorial)

  useEffect(() => {
    const pageKey = location.pathname

    // Clean up previous timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }

    // Skip if we've already shown a prompt for this page in this session
    if (shownRef.current.has(pageKey)) {
      return
    }

    // Skip if page has no tutorials
    if (!hasTutorialsForRoute(pageKey)) {
      return
    }

    // Skip if user has already seen the prompt for this page
    if (hasSeenPromptForPage(pageKey)) {
      return
    }

    // Get the primary tutorial for this page
    const primaryTutorial = getPrimaryTutorialForRoute(pageKey)
    if (!primaryTutorial) {
      return
    }

    // Mark as shown for this session immediately
    shownRef.current.add(pageKey)

    // Show notification after a delay
    timeoutRef.current = setTimeout(() => {
      const notificationKey = `tutorial-prompt-${pageKey}`

      const handleDismiss = () => {
        api.destroy(notificationKey)
        markPromptSeen(pageKey)
      }

      const handleStartTour = () => {
        api.destroy(notificationKey)
        markPromptSeen(pageKey)
        startTutorial(primaryTutorial.id)
      }

      api.info({
        key: notificationKey,
        message: (
          <span className="font-medium">
            {t("tutorials:prompt.title", "New to this page?")}
          </span>
        ),
        description: (
          <span className="text-text-muted">
            {t("tutorials:prompt.description", {
              defaultValue: "Take a quick tour to learn the key features.",
              tutorialName: t(primaryTutorial.labelKey, primaryTutorial.labelFallback)
            })}
          </span>
        ),
        icon: (
          <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10">
            <GraduationCap className="size-4 text-primary" />
          </div>
        ),
        btn: (
          <Space>
            <Button size="small" onClick={handleDismiss}>
              {t("tutorials:prompt.dismiss", "Not now")}
            </Button>
            <Button type="primary" size="small" onClick={handleStartTour}>
              {t("tutorials:prompt.startTour", "Start tour")}
            </Button>
          </Space>
        ),
        duration: NOTIFICATION_DURATION,
        placement: "bottomRight",
        className: "tutorial-prompt-notification",
        onClose: () => {
          // Mark as seen when notification is closed (including auto-close)
          markPromptSeen(pageKey)
        }
      })
    }, PROMPT_DELAY_MS)

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }
    }
  }, [
    location.pathname,
    api,
    t,
    hasSeenPromptForPage,
    markPromptSeen,
    startTutorial
  ])

  return contextHolder
}

export default TutorialPrompt
