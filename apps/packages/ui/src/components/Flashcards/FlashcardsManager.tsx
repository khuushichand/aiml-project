import React from "react"
import { Button, Space, Tabs, Tooltip } from "antd"
import { HelpCircle } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"
import { ReviewTab, ManageTab, ImportExportTab, SchedulerTab } from "./tabs"
import { KeyboardShortcutsModal } from "./components"
import type { Flashcard } from "@/services/flashcards"
import { parseFlashcardsGenerateIntentFromLocation } from "@/services/tldw/flashcards-generate-handoff"
import {
  buildQuizAssessmentRouteFromFlashcards,
  parseFlashcardsStudyIntentFromLocation
} from "@/services/tldw/quiz-flashcards-handoff"

const parseInitialFlashcardsTab = (locationLike: { search?: string; hash?: string }): string | null => {
  const search = locationLike.search || ""
  const normalized = search.startsWith("?") ? search.slice(1) : search
  const params = new URLSearchParams(normalized)
  const rawTab = params.get("tab")?.trim().toLowerCase()

  switch (rawTab) {
    case "review":
    case "study":
      return "review"
    case "manage":
    case "cards":
      return "cards"
    case "transfer":
    case "importexport":
      return "importExport"
    case "scheduler":
      return "scheduler"
    default:
      return null
  }
}

/**
 * FlashcardsManager contains all the tabs and core flashcard logic.
 * Connection state is handled by FlashcardsWorkspace.
 *
 * Structure: Study | Manage | Transfer
 * - Study: Spaced repetition review and cram loops
 * - Manage: Browse, filter, create, edit, bulk operations
 * - Transfer: CSV/APKG import and export workflows
 * - Scheduler: Deck-level scheduler policy editing and queue visibility
 */
export const FlashcardsManager: React.FC = () => {
  const { t } = useTranslation(["option", "common"])
  const navigate = useNavigate()
  const initialGenerateIntent = React.useMemo(
    () =>
      typeof window !== "undefined"
        ? parseFlashcardsGenerateIntentFromLocation(window.location)
        : null,
    []
  )
  const initialStudyIntent = React.useMemo(
    () =>
      typeof window !== "undefined"
        ? parseFlashcardsStudyIntentFromLocation(window.location)
        : null,
    []
  )
  const initialTab = React.useMemo(
    () =>
      typeof window !== "undefined"
        ? parseInitialFlashcardsTab(window.location)
        : null,
    []
  )
  const [activeTab, setActiveTab] = React.useState<string>(() =>
    initialTab ?? (initialGenerateIntent ? "importExport" : "review")
  )
  const [reviewDeckId, setReviewDeckId] = React.useState<number | null | undefined>(
    initialStudyIntent?.deckId ?? undefined
  )
  const [reviewOverrideCard, setReviewOverrideCard] = React.useState<Flashcard | null>(null)
  const [openCreateSignal, setOpenCreateSignal] = React.useState(0)
  const [shortcutsModalOpen, setShortcutsModalOpen] = React.useState(false)
  const [schedulerDirty, setSchedulerDirty] = React.useState(false)
  const [schedulerDiscardSignal, setSchedulerDiscardSignal] = React.useState(0)

  // Listen for "?" key to open keyboard shortcuts modal
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger when typing in inputs
      const target = e.target as HTMLElement
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable
      ) {
        return
      }

      if (e.key === "?" || (e.shiftKey && e.key === "/")) {
        e.preventDefault()
        setShortcutsModalOpen(true)
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [])

  const handleReviewCard = React.useCallback(
    (card: Flashcard) => {
      setReviewDeckId(card.deck_id ?? undefined)
      setReviewOverrideCard(card)
      setActiveTab("review")
    },
    []
  )

  const routeToCreateEntryPoint = React.useCallback(() => {
    setActiveTab("cards")
    setOpenCreateSignal((prev) => prev + 1)
  }, [])

  const quizCtaRoute = React.useMemo(() => {
    const startQuizId = initialStudyIntent?.quizId
    return buildQuizAssessmentRouteFromFlashcards({
      startQuizId,
      highlightQuizId: startQuizId,
      deckId: reviewDeckId ?? initialStudyIntent?.deckId,
      sourceAttemptId: initialStudyIntent?.attemptId,
      forceShowWorkspaceItems: initialStudyIntent?.forceShowWorkspaceItems ?? false
    })
  }, [initialStudyIntent?.attemptId, initialStudyIntent?.deckId, initialStudyIntent?.forceShowWorkspaceItems, initialStudyIntent?.quizId, reviewDeckId])

  const handleTabChange = React.useCallback(
    (nextTab: string) => {
      if (activeTab === "scheduler" && nextTab !== "scheduler" && schedulerDirty) {
        const shouldDiscard = window.confirm(
          t("option:flashcards.schedulerDiscardChangesPrompt", {
            defaultValue: "Discard unsaved scheduler changes?"
          })
        )
        if (!shouldDiscard) return
        setSchedulerDirty(false)
        setSchedulerDiscardSignal((current) => current + 1)
      }

      setActiveTab(nextTab)
    },
    [activeTab, schedulerDirty, t]
  )

  return (
    <div className="mx-auto max-w-6xl p-4">
      <Tabs
        data-testid="flashcards-tabs"
        activeKey={activeTab}
        onChange={handleTabChange}
        tabBarExtraContent={(
          <Space size={4}>
            <Button
              size="small"
              data-testid="flashcards-to-quiz-cta"
              onClick={() => navigate(quizCtaRoute)}
            >
              {t("option:flashcards.testWithQuiz", {
                defaultValue: "Test with Quiz"
              })}
            </Button>
            <Tooltip
              title={t("option:flashcards.keyboardShortcutsHelp", {
                defaultValue: "Press ? to show shortcuts"
              })}
            >
              <Button
                type="text"
                size="small"
                icon={<HelpCircle className="size-4" />}
                onClick={() => setShortcutsModalOpen(true)}
                aria-label={t("option:flashcards.keyboardShortcutsTitle", {
                  defaultValue: "Keyboard Shortcuts"
                })}
              />
            </Tooltip>
          </Space>
        )}
        items={[
          {
            key: "review",
            label: t("option:flashcards.tabStudy", { defaultValue: "Study" }),
            children: (
              <ReviewTab
                onNavigateToCreate={routeToCreateEntryPoint}
                onNavigateToImport={() => setActiveTab("importExport")}
                reviewDeckId={reviewDeckId}
                onReviewDeckChange={setReviewDeckId}
                reviewOverrideCard={reviewOverrideCard}
                onClearOverride={() => setReviewOverrideCard(null)}
                isActive={activeTab === "review"}
                forceShowWorkspaceItems={initialStudyIntent?.forceShowWorkspaceItems ?? false}
              />
            )
          },
          {
            key: "cards",
            label: t("option:flashcards.tabManage", { defaultValue: "Manage" }),
            children: (
              <ManageTab
                onNavigateToImport={() => setActiveTab("importExport")}
                onReviewCard={handleReviewCard}
                openCreateSignal={openCreateSignal}
                isActive={activeTab === "cards"}
                initialDeckId={initialTab === "cards" ? initialStudyIntent?.deckId : undefined}
                initialShowWorkspaceDecks={
                  initialTab === "cards" ? (initialStudyIntent?.forceShowWorkspaceItems ?? false) : false
                }
              />
            )
          },
          {
            key: "importExport",
            label: t("option:flashcards.tabTransfer", {
              defaultValue: "Transfer"
            }),
            children: <ImportExportTab generateIntent={initialGenerateIntent} />
          },
          {
            key: "scheduler",
            label: t("option:flashcards.tabScheduler", {
              defaultValue: "Scheduler"
            }),
            children: (
              <SchedulerTab
                isActive={activeTab === "scheduler"}
                onDirtyChange={setSchedulerDirty}
                discardSignal={schedulerDiscardSignal}
              />
            )
          }
        ]}
      />

      <KeyboardShortcutsModal
        open={shortcutsModalOpen}
        onClose={() => setShortcutsModalOpen(false)}
        activeTab={
          activeTab === "importExport"
            ? "import"
            : activeTab === "scheduler"
              ? "scheduler"
              : (activeTab as "review" | "cards")
        }
      />
    </div>
  )
}

export default FlashcardsManager
