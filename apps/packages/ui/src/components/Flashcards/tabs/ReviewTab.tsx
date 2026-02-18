import React from "react"
import { Button, Card, Empty, Input, Segmented, Select, Space, Switch, Tag, Tooltip, Typography } from "antd"
import { X, Minus, Check, Star, Calendar, Undo2 } from "lucide-react"
import dayjs from "dayjs"
import relativeTime from "dayjs/plugin/relativeTime"
import { useTranslation } from "react-i18next"
import { useAntdMessage } from "@/hooks/useAntdMessage"
import type { Flashcard, FlashcardUpdate } from "@/services/flashcards"
import {
  useDecksQuery,
  useCramQueueQuery,
  useReviewQuery,
  useReviewFlashcardMutation,
  useUpdateFlashcardMutation,
  useResetFlashcardSchedulingMutation,
  useDeleteFlashcardMutation,
  useFlashcardShortcuts,
  useDueCountsQuery,
  useDeckDueCountsQuery,
  useReviewAnalyticsSummaryQuery,
  useHasCardsQuery,
  useNextDueQuery
} from "../hooks"
import { MarkdownWithBoundary, ReviewProgress, ReviewAnalyticsSummary, FlashcardEditDrawer } from "../components"
import { calculateIntervals } from "../utils/calculateIntervals"
import { formatCardType } from "../utils/model-type-labels"
import { buildReviewUndoState } from "../utils/review-undo"
import { getFlashcardSourceMeta } from "../utils/source-reference"
import { useFlashcardsShortcutHintDensity } from "../hooks/useFlashcardsShortcutHintDensity"

dayjs.extend(relativeTime)

const { Text, Title } = Typography

interface ReviewTabProps {
  onNavigateToCreate: () => void
  onNavigateToImport: () => void
  reviewDeckId: number | null | undefined
  onReviewDeckChange: (deckId: number | null | undefined) => void
  reviewOverrideCard?: Flashcard | null
  onClearOverride?: () => void
  isActive: boolean
}

/**
 * Review tab for studying flashcards with spaced repetition.
 */
export const ReviewTab: React.FC<ReviewTabProps> = ({
  onNavigateToCreate,
  onNavigateToImport,
  reviewDeckId,
  onReviewDeckChange,
  reviewOverrideCard,
  onClearOverride,
  isActive
}) => {
  const { t } = useTranslation(["option", "common"])
  const message = useAntdMessage()

  // State
  const [showAnswer, setShowAnswer] = React.useState(false)
  const [reviewedCount, setReviewedCount] = React.useState(0)
  const [localOverrideCard, setLocalOverrideCard] = React.useState<Flashcard | null>(null)
  const [editDrawerOpen, setEditDrawerOpen] = React.useState(false)
  const [showRatingRationale, setShowRatingRationale] = React.useState(false)
  const [reviewMode, setReviewMode] = React.useState<"due" | "cram">("due")
  const [cramTag, setCramTag] = React.useState("")
  const [cramUpdatesSchedule, setCramUpdatesSchedule] = React.useState(false)
  const [cramQueueIndex, setCramQueueIndex] = React.useState(0)
  const [shortcutHintDensity, setShortcutHintDensity] = useFlashcardsShortcutHintDensity()

  // Undo state - stores the last reviewed card for potential re-rating
  const [lastReviewedCard, setLastReviewedCard] = React.useState<Flashcard | null>(null)
  const [showUndoButton, setShowUndoButton] = React.useState(false)
  const [undoCountdown, setUndoCountdown] = React.useState(0)
  const undoTimeoutRef = React.useRef<number | null>(null)
  const undoIntervalRef = React.useRef<number | null>(null)
  const autoRevealAnswerRef = React.useRef(false)

  // Auto-track answer time - stores the timestamp when answer was revealed
  const answerStartTimeRef = React.useRef<number | null>(null)

  // Queries and mutations
  const decksQuery = useDecksQuery()
  const reviewQuery = useReviewQuery(reviewDeckId, {
    enabled: reviewMode === "due"
  })
  const cramTagFilter = cramTag.trim() || undefined
  const cramQueueQuery = useCramQueueQuery(reviewDeckId, cramTagFilter, {
    enabled: reviewMode === "cram"
  })
  const reviewMutation = useReviewFlashcardMutation()
  const updateMutation = useUpdateFlashcardMutation()
  const resetSchedulingMutation = useResetFlashcardSchedulingMutation()
  const deleteMutation = useDeleteFlashcardMutation()
  const dueCountsQuery = useDueCountsQuery(reviewDeckId)
  const deckDueCountsQuery = useDeckDueCountsQuery()
  const analyticsSummaryQuery = useReviewAnalyticsSummaryQuery(reviewDeckId)
  const hasCardsQuery = useHasCardsQuery()
  const nextDueQuery = useNextDueQuery(reviewDeckId)
  const nextDueInfo = nextDueQuery.data
  const cramQueue = cramQueueQuery.data || []
  const cramQueueCard =
    reviewMode === "cram" && cramQueueIndex < cramQueue.length
      ? cramQueue[cramQueueIndex]
      : null
  const activeCard =
    localOverrideCard ??
    reviewOverrideCard ??
    (reviewMode === "cram" ? cramQueueCard : reviewQuery.data)
  const reviewProgressTotal =
    reviewMode === "cram" ? cramQueue.length : dueCountsQuery.data?.total ?? 0
  const isCramMode = reviewMode === "cram"
  const activeCardSource = React.useMemo(
    () => (activeCard ? getFlashcardSourceMeta(activeCard) : null),
    [activeCard]
  )
  const cycleShortcutHintDensity = React.useCallback(() => {
    void setShortcutHintDensity((prev) => {
      if (prev === "expanded") return "compact"
      if (prev === "compact") return "hidden"
      return "expanded"
    })
  }, [setShortcutHintDensity])
  const shortcutHintToggleLabel =
    shortcutHintDensity === "expanded"
      ? t("option:flashcards.shortcutHintsCompact", {
          defaultValue: "Compact hints"
        })
      : shortcutHintDensity === "compact"
        ? t("option:flashcards.shortcutHintsHide", {
            defaultValue: "Hide hints"
          })
        : t("option:flashcards.shortcutHintsShow", {
            defaultValue: "Show hints"
          })

  // Get deck name for progress display
  const currentDeckName = React.useMemo(() => {
    if (!reviewDeckId || !decksQuery.data) return undefined
    return decksQuery.data.find((d) => d.id === reviewDeckId)?.name
  }, [reviewDeckId, decksQuery.data])

  // Calculate intervals for current card
  const intervals = React.useMemo(() => {
    if (!activeCard) return null
    return calculateIntervals(activeCard)
  }, [activeCard])

  // Rating options for Anki-style review with colors, shortcuts, icons, and interval previews
  const ratingOptions = React.useMemo(
    () => [
      {
        value: 0,
        key: "1",
        label: t("option:flashcards.ratingAgain", { defaultValue: "Again" }),
        description: t("option:flashcards.ratingAgainHelp", {
          defaultValue: "I didn't remember this card."
        }),
        interval: intervals?.again ?? "< 1 min",
        // WCAG AA compliant: 5.6:1 contrast ratio
        bgClass: "bg-danger hover:bg-danger/90 border-danger text-white",
        icon: X
      },
      {
        value: 2,
        key: "2",
        label: t("option:flashcards.ratingHard", { defaultValue: "Hard" }),
        description: t("option:flashcards.ratingHardHelp", {
          defaultValue: "I barely remembered; it felt difficult."
        }),
        interval: intervals?.hard ?? "< 10 min",
        // WCAG AA compliant: 9.3:1 contrast ratio (dark text on light bg)
        bgClass: "bg-warn/10 hover:bg-warn/20 border-warn/30 !text-warn",
        icon: Minus
      },
      {
        value: 3,
        key: "3",
        label: t("option:flashcards.ratingGood", { defaultValue: "Good" }),
        description: t("option:flashcards.ratingGoodHelp", {
          defaultValue: "I remembered with a bit of effort."
        }),
        interval: intervals?.good ?? "1 day",
        // WCAG AA compliant: 4.8:1 contrast ratio
        bgClass: "bg-success hover:bg-success/90 border-success text-white",
        primary: true,
        icon: Check
      },
      {
        value: 5,
        key: "4",
        label: t("option:flashcards.ratingEasy", { defaultValue: "Easy" }),
        description: t("option:flashcards.ratingEasyHelp", {
          defaultValue: "I remembered easily; no problem."
        }),
        interval: intervals?.easy ?? "4 days",
        // WCAG AA compliant: 5.8:1 contrast ratio
        bgClass: "bg-primary hover:bg-primaryStrong border-primary text-white",
        icon: Star
      }
    ],
    [t, intervals]
  )

  const onSubmitReview = React.useCallback(
    async (rating: number) => {
      try {
        const card = activeCard
        if (!card) return
        // Auto-calculate answer time from when the answer was shown
        let answerTimeMs: number | undefined
        if (answerStartTimeRef.current) {
          answerTimeMs = Date.now() - answerStartTimeRef.current
        }

        // Store the card for potential undo before submitting
        const cardForUndo = { ...card }

        const advanceCramQueue = () => {
          if (reviewMode !== "cram") return
          const currentIndex = cramQueue.findIndex((queued) => queued.uuid === card.uuid)
          if (currentIndex >= 0) {
            setCramQueueIndex(Math.min(currentIndex + 1, cramQueue.length))
            return
          }
          setCramQueueIndex((idx) => Math.min(idx + 1, cramQueue.length))
        }

        if (reviewMode === "cram" && !cramUpdatesSchedule) {
          setShowAnswer(false)
          answerStartTimeRef.current = null
          setReviewedCount((c) => c + 1)
          setShowUndoButton(false)
          setLastReviewedCard(null)
          setUndoCountdown(0)
          if (undoTimeoutRef.current) {
            window.clearTimeout(undoTimeoutRef.current)
          }
          if (undoIntervalRef.current) {
            window.clearInterval(undoIntervalRef.current)
          }
          if (reviewOverrideCard) {
            onClearOverride?.()
          }
          if (localOverrideCard) {
            setLocalOverrideCard(null)
          }
          advanceCramQueue()
          message.success(
            t("option:flashcards.cramPracticeSaved", {
              defaultValue: "Practice saved. Scheduling unchanged."
            })
          )
          return
        }

        const reviewResult = await reviewMutation.mutateAsync({
          cardUuid: card.uuid,
          rating,
          answerTimeMs
        })
        setShowAnswer(false)
        answerStartTimeRef.current = null
        setReviewedCount((c) => c + 1)
        if (reviewOverrideCard) {
          onClearOverride?.()
        }
        if (localOverrideCard) {
          setLocalOverrideCard(null)
        }
        advanceCramQueue()

        // Enable undo for 10 seconds with visible countdown
        setLastReviewedCard(cardForUndo)
        setShowUndoButton(true)
        setUndoCountdown(10)
        if (undoTimeoutRef.current) {
          window.clearTimeout(undoTimeoutRef.current)
        }
        if (undoIntervalRef.current) {
          window.clearInterval(undoIntervalRef.current)
        }
        // Countdown interval for visual feedback
        undoIntervalRef.current = window.setInterval(() => {
          setUndoCountdown((prev) => {
            if (prev <= 1) {
              if (undoIntervalRef.current) {
                window.clearInterval(undoIntervalRef.current)
              }
              return 0
            }
            return prev - 1
          })
        }, 1000)
        // Timeout to hide undo button
        undoTimeoutRef.current = window.setTimeout(() => {
          setShowUndoButton(false)
          setLastReviewedCard(null)
          setUndoCountdown(0)
          if (undoIntervalRef.current) {
            window.clearInterval(undoIntervalRef.current)
          }
        }, 10000) // 10 second undo window

        const dueLabel = reviewResult.due_at
          ? dayjs(reviewResult.due_at).fromNow()
          : t("option:flashcards.nextReviewUnknown", {
              defaultValue: "soon"
            })
        const intervalLabel =
          reviewResult.interval_days === 1
            ? t("option:flashcards.intervalOneDay", { defaultValue: "1 day" })
            : t("option:flashcards.intervalManyDays", {
                defaultValue: "{{count}} days",
                count: reviewResult.interval_days
              })

        message.success(
          t("option:flashcards.reviewSavedWithSchedule", {
            defaultValue: "Saved. Next review {{due}} (next review gap: {{interval}}).",
            due: dueLabel,
            interval: intervalLabel
          })
        )
      } catch (e: unknown) {
        const errorMessage =
          e instanceof Error ? e.message : "Failed to submit review"
        message.error(errorMessage)
      }
    },
    [
      activeCard,
      cramQueue,
      cramUpdatesSchedule,
      localOverrideCard,
      message,
      onClearOverride,
      reviewMode,
      reviewMutation,
      reviewOverrideCard,
      t
    ]
  )

  // Handle undo - re-present the last reviewed card
  const handleUndoReview = React.useCallback(() => {
    const undoState = buildReviewUndoState(lastReviewedCard, reviewedCount)
    if (!undoState) return

    // Clear the undo state and countdown
    if (undoTimeoutRef.current) {
      window.clearTimeout(undoTimeoutRef.current)
    }
    if (undoIntervalRef.current) {
      window.clearInterval(undoIntervalRef.current)
    }
    setShowUndoButton(false)
    setUndoCountdown(0)
    setReviewedCount(undoState.nextReviewedCount)

    const shouldRevealOnCurrent = activeCard?.uuid === undoState.overrideCard.uuid
    if (shouldRevealOnCurrent) {
      autoRevealAnswerRef.current = false
      setShowAnswer(true)
      answerStartTimeRef.current = Date.now()
    } else {
      autoRevealAnswerRef.current = true
    }
    setLocalOverrideCard(undoState.overrideCard)

    message.info(
      t("option:flashcards.undoReviewHint", {
        defaultValue: "Rate this card again to update your response"
      })
    )
  }, [activeCard?.uuid, lastReviewedCard, reviewedCount, message, t])

  // Cleanup timeout and interval on unmount
  React.useEffect(() => {
    return () => {
      if (undoTimeoutRef.current) {
        window.clearTimeout(undoTimeoutRef.current)
      }
      if (undoIntervalRef.current) {
        window.clearInterval(undoIntervalRef.current)
      }
    }
  }, [])

  React.useEffect(() => {
    if (autoRevealAnswerRef.current) {
      autoRevealAnswerRef.current = false
      setShowAnswer(true)
      answerStartTimeRef.current = Date.now()
      return
    }
    setShowAnswer(false)
    setShowRatingRationale(false)
    answerStartTimeRef.current = null
  }, [activeCard?.uuid])

  // Track when the answer is shown (for auto-timing)
  const handleShowAnswer = React.useCallback(() => {
    setShowAnswer(true)
    answerStartTimeRef.current = Date.now()
  }, [])

  const handleOpenEdit = React.useCallback(() => {
    if (!activeCard) return
    setEditDrawerOpen(true)
  }, [activeCard])

  const handleSaveEdit = React.useCallback(
    async (values: FlashcardUpdate) => {
      if (!activeCard) return
      try {
        await updateMutation.mutateAsync({
          uuid: activeCard.uuid,
          update: values
        })
        message.success(
          t("option:flashcards.cardUpdated", {
            defaultValue: "Card updated."
          })
        )
        setEditDrawerOpen(false)
      } catch (error: unknown) {
        message.error(
          error instanceof Error
            ? error.message
            : t("option:flashcards.cardUpdateFailed", {
                defaultValue: "Failed to update card."
              })
        )
      }
    },
    [activeCard, updateMutation, message, t]
  )

  const handleDeleteFromReview = React.useCallback(async () => {
    if (!activeCard) return
    try {
      await deleteMutation.mutateAsync({
        uuid: activeCard.uuid,
        version: activeCard.version
      })
      message.success(
        t("option:flashcards.cardDeleted", {
          defaultValue: "Card deleted."
        })
      )
      setEditDrawerOpen(false)
      setShowAnswer(false)
      setShowRatingRationale(false)
      answerStartTimeRef.current = null
      if (reviewOverrideCard) {
        onClearOverride?.()
      }
      if (localOverrideCard?.uuid === activeCard.uuid) {
        setLocalOverrideCard(null)
      }
    } catch (error: unknown) {
      message.error(
        error instanceof Error
          ? error.message
          : t("option:flashcards.cardDeleteFailed", {
              defaultValue: "Failed to delete card."
            })
      )
    }
  }, [
    activeCard,
    deleteMutation,
    message,
    t,
    reviewOverrideCard,
    onClearOverride,
    localOverrideCard?.uuid
  ])

  const handleResetSchedulingFromReview = React.useCallback(async () => {
    if (!activeCard) return
    try {
      await resetSchedulingMutation.mutateAsync({
        uuid: activeCard.uuid,
        expectedVersion: activeCard.version
      })
      message.success(
        t("option:flashcards.schedulingResetSuccess", {
          defaultValue: "Scheduling reset to new-card defaults."
        })
      )
      setEditDrawerOpen(false)
    } catch (error: unknown) {
      message.error(
        error instanceof Error
          ? error.message
          : t("option:flashcards.schedulingResetFailed", {
              defaultValue: "Failed to reset scheduling."
            })
      )
    }
  }, [activeCard, resetSchedulingMutation, message, t])

  React.useEffect(() => {
    if (reviewMode !== "cram") return
    setCramQueueIndex((idx) => Math.min(idx, cramQueue.length))
  }, [reviewMode, cramQueue.length])

  // Reset reviewed/session state when review scope changes
  React.useEffect(() => {
    setReviewedCount(0)
    setCramQueueIndex(0)
    setLocalOverrideCard(null)
    setShowUndoButton(false)
    setLastReviewedCard(null)
    setUndoCountdown(0)
    autoRevealAnswerRef.current = false
  }, [reviewDeckId, reviewMode, cramTagFilter])

  React.useEffect(() => {
    if (reviewOverrideCard) {
      setLocalOverrideCard(null)
    }
  }, [reviewOverrideCard])

  // Keyboard shortcuts for review
  useFlashcardShortcuts({
    enabled: isActive && !!activeCard,
    showingAnswer: showAnswer,
    onFlip: handleShowAnswer,
    onRate: onSubmitReview,
    onEdit: handleOpenEdit,
    onUndo: showUndoButton ? handleUndoReview : undefined
  })

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Select
          placeholder={t("option:flashcards.selectDeck", {
            defaultValue: "Select deck (optional)"
          })}
          allowClear
          loading={decksQuery.isLoading}
          value={reviewDeckId ?? undefined}
          className="min-w-64 max-w-full flex-1"
          onChange={(v) => {
            onReviewDeckChange(v)
            if (reviewOverrideCard) {
              onClearOverride?.()
            }
          }}
          data-testid="flashcards-review-deck-select"
          options={(decksQuery.data || []).map((d) => ({
            label:
              ((deckDueCountsQuery.data?.[d.id]?.due ?? 0) > 0)
                ? t("option:flashcards.deckWithDueCount", {
                    defaultValue: "{{deckName}} ({{count}} due)",
                    deckName: d.name,
                    count: deckDueCountsQuery.data?.[d.id]?.due ?? 0
                  })
                : d.name,
            value: d.id
          }))}
        />
        <Segmented
          value={reviewMode}
          onChange={(value) => {
            setReviewMode(value as "due" | "cram")
          }}
          options={[
            {
              label: t("option:flashcards.reviewModeDueOnly", {
                defaultValue: "Due only"
              }),
              value: "due"
            },
            {
              label: t("option:flashcards.reviewModeCram", {
                defaultValue: "Cram"
              }),
              value: "cram"
            }
          ]}
          data-testid="flashcards-review-mode-toggle"
        />
        {reviewMode === "cram" && (
          <>
            <Input
              allowClear
              value={cramTag}
              onChange={(event) => setCramTag(event.target.value)}
              placeholder={t("option:flashcards.cramTagFilterPlaceholder", {
                defaultValue: "Filter cram by tag (optional)"
              })}
              className="min-w-56 max-w-full flex-1"
              data-testid="flashcards-review-cram-tag"
            />
            <Space size={6}>
              <Text type="secondary" className="text-xs">
                {t("option:flashcards.cramUpdateSchedule", {
                  defaultValue: "Update schedule"
                })}
              </Text>
              <Switch
                checked={cramUpdatesSchedule}
                onChange={setCramUpdatesSchedule}
                data-testid="flashcards-review-cram-update-schedule"
              />
            </Space>
          </>
        )}
        <Button
          type="primary"
          className="min-h-11"
          onClick={onNavigateToCreate}
          data-testid="flashcards-review-create-cta"
        >
          {t("option:flashcards.noDueCreateCta", { defaultValue: "Create card" })}
        </Button>
      </div>

      <ReviewAnalyticsSummary
        summary={analyticsSummaryQuery.data}
        isLoading={analyticsSummaryQuery.isLoading}
        selectedDeckId={reviewDeckId ?? null}
      />

      {reviewProgressTotal > 0 && (
        <ReviewProgress
          dueCount={reviewProgressTotal}
          reviewedCount={reviewedCount}
          deckName={currentDeckName}
        />
      )}

      {activeCard ? (
        <Card>
          <div className="flex flex-col gap-3">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Tag>{formatCardType(activeCard, t)}</Tag>
                {activeCard.tags?.map((tag) => (
                  <Tag key={tag}>{tag}</Tag>
                ))}
                {activeCardSource && (
                  <Tag
                    color={
                      activeCardSource.unavailable
                        ? "default"
                        : activeCardSource.type === "media"
                          ? "blue"
                          : activeCardSource.type === "note"
                            ? "gold"
                            : "green"
                    }
                  >
                    {activeCardSource.href ? (
                      <a href={activeCardSource.href}>{activeCardSource.label}</a>
                    ) : (
                      activeCardSource.label
                    )}
                  </Tag>
                )}
                <Tooltip
                  title={t("option:flashcards.shortcutEditTooltip", {
                    defaultValue: "Shortcut: E"
                  })}
                >
                  <Button
                    size="small"
                    onClick={handleOpenEdit}
                    data-testid="flashcards-review-edit-card"
                    aria-label={t("option:flashcards.shortcutEditAria", {
                      defaultValue: "Edit card (E)"
                    })}
                  >
                    {t("option:flashcards.editCardAction", {
                      defaultValue: "Edit"
                    })}
                  </Button>
                </Tooltip>
              </div>
            </div>

            <div>
              <Title level={5} className="!mb-2">
                {t("option:flashcards.front", { defaultValue: "Front" })}
              </Title>
              <div className="rounded border border-border bg-surface p-3 text-sm text-text">
                <MarkdownWithBoundary
                  content={activeCard.front}
                  size="sm"
                  className="prose-headings:!text-text prose-p:!text-text prose-li:!text-text prose-strong:!text-text"
                />
              </div>
            </div>

            {showAnswer && (
              <div>
                <Title level={5} className="!mb-2">
                  {t("option:flashcards.back", { defaultValue: "Back" })}
                </Title>
                <div className="rounded border border-border bg-surface p-3 text-sm text-text">
                  <MarkdownWithBoundary
                    content={activeCard.back}
                    size="sm"
                    className="prose-headings:!text-text prose-p:!text-text prose-li:!text-text prose-strong:!text-text"
                  />
                </div>
                {activeCard.extra && (
                  <div className="mt-2 rounded border border-border bg-surface p-3 text-sm text-text/80">
                    <MarkdownWithBoundary
                      content={activeCard.extra}
                      size="xs"
                      className="prose-headings:!text-text prose-p:!text-text prose-li:!text-text prose-strong:!text-text"
                    />
                  </div>
                )}
              </div>
            )}

            <div className="mt-2 flex flex-col gap-3">
              {!showAnswer ? (
                <div className="flex flex-col gap-2">
                  <Tooltip
                    title={t("option:flashcards.shortcutFlipTooltip", {
                      defaultValue: "Shortcut: Space"
                    })}
                  >
                    <Button
                      type="primary"
                      onClick={handleShowAnswer}
                      data-testid="flashcards-review-show-answer"
                      aria-label={t("option:flashcards.shortcutFlipAria", {
                        defaultValue: "Show answer (Space)"
                      })}
                    >
                      {t("option:flashcards.showAnswer", {
                        defaultValue: "Show Answer"
                      })}
                    </Button>
                  </Tooltip>
                  <div
                    className="flex flex-wrap items-center gap-2"
                    data-testid="flashcards-review-shortcut-chips-question"
                  >
                    {shortcutHintDensity === "expanded" && (
                      <>
                        <Tag className="!m-0">
                          {t("option:flashcards.shortcutChipFlip", {
                            defaultValue: "Space Flip"
                          })}
                        </Tag>
                        <Tag className="!m-0">
                          {t("option:flashcards.shortcutChipEdit", {
                            defaultValue: "E Edit"
                          })}
                        </Tag>
                      </>
                    )}
                    {shortcutHintDensity === "compact" && (
                      <Tag className="!m-0">
                        {t("option:flashcards.shortcutChipReviewCompactQuestion", {
                          defaultValue: "Space / E"
                        })}
                      </Tag>
                    )}
                    <Button
                      type="link"
                      size="small"
                      className="!h-auto !px-0 text-xs"
                      onClick={cycleShortcutHintDensity}
                      data-testid="flashcards-review-shortcut-hints-toggle"
                    >
                      {shortcutHintToggleLabel}
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex flex-col gap-2">
                    <Text>
                      {t("option:flashcards.rate", {
                        defaultValue: "How well did you remember this card?"
                      })}
                    </Text>
                    <div className="flex flex-wrap gap-2 justify-center" role="group" aria-label={t("option:flashcards.ratingGroup", { defaultValue: "Rating options" })}>
                      {ratingOptions.map((opt) => {
                        const Icon = opt.icon
                        return (
                          <Tooltip
                            key={opt.value}
                            title={`${opt.description} (${opt.key})`}
                          >
                            <Button
                              onClick={() => onSubmitReview(opt.value)}
                              aria-label={`${opt.label}: ${opt.description} Press ${opt.key}`}
                              className={`${opt.bgClass} ${opt.primary ? "!px-6" : ""} min-h-11 focus:ring-2 focus:ring-offset-2 focus:ring-current focus:outline-none`}
                              data-testid={`flashcards-review-rate-${opt.key}`}
                            >
                              <div className="flex flex-col items-center gap-0.5">
                                {/* Larger icons (24px) for colorblind accessibility */}
                                <Icon className="size-6" aria-hidden="true" />
                                <span className="font-medium">
                                  {opt.label}
                                  {/* Keyboard shortcut badge for additional visual differentiation */}
                                  <span className="ml-1.5 inline-flex items-center justify-center w-5 h-5 rounded text-xs font-bold bg-black/20">
                                    {opt.key}
                                  </span>
                                </span>
                                <span className="text-xs opacity-80">
                                  {opt.interval}
                                </span>
                              </div>
                            </Button>
                          </Tooltip>
                        )
                      })}
                    </div>
                    <Text type="secondary" className="text-xs text-center">
                      {t("option:flashcards.ratingIntervalsMeaning", {
                        defaultValue:
                          "Again = shortest gap, Hard = short gap, Good = medium gap, Easy = longest gap."
                      })}
                    </Text>
                    {isCramMode && !cramUpdatesSchedule && (
                      <Text type="secondary" className="text-xs text-center">
                        {t("option:flashcards.cramNoScheduleHint", {
                          defaultValue:
                            "Practice-only mode: ratings do not change your review schedule."
                        })}
                      </Text>
                    )}
                    <Button
                      type="link"
                      size="small"
                      className="self-start !px-0"
                      onClick={() => setShowRatingRationale((prev) => !prev)}
                    >
                      {t("option:flashcards.whyTheseRatings", {
                        defaultValue: "Why these ratings?"
                      })}
                    </Button>
                    {showRatingRationale && (
                      <div className="rounded border border-border bg-surface p-2 text-xs text-text-muted">
                        <Text className="block text-xs">
                          {t("option:flashcards.ratingMapAgain", {
                            defaultValue: "Again = 0: forgot it, repeat very soon."
                          })}
                        </Text>
                        <Text className="block text-xs">
                          {t("option:flashcards.ratingMapHard", {
                            defaultValue: "Hard = 2: remembered with strain, keep gap short."
                          })}
                        </Text>
                        <Text className="block text-xs">
                          {t("option:flashcards.ratingMapGood", {
                            defaultValue: "Good = 3: normal recall, use the default schedule step."
                          })}
                        </Text>
                        <Text className="block text-xs">
                          {t("option:flashcards.ratingMapEasy", {
                            defaultValue: "Easy = 5: effortless recall, jump to a longer gap."
                          })}
                        </Text>
                      </div>
                    )}
                    <div
                      className="flex flex-wrap items-center gap-2"
                      data-testid="flashcards-review-shortcut-chips-answer"
                    >
                      {shortcutHintDensity === "expanded" && (
                        <>
                          <Tag className="!m-0">
                            {t("option:flashcards.shortcutChipRate", {
                              defaultValue: "1-4 Rate"
                            })}
                          </Tag>
                          <Tag className="!m-0">
                            {t("option:flashcards.shortcutChipEdit", {
                              defaultValue: "E Edit"
                            })}
                          </Tag>
                          <Tag className="!m-0">
                            {t("option:flashcards.shortcutChipUndo", {
                              defaultValue: "Ctrl+Z Re-rate"
                            })}
                          </Tag>
                        </>
                      )}
                      {shortcutHintDensity === "compact" && (
                        <Tag className="!m-0">
                          {t("option:flashcards.shortcutChipReviewCompactAnswer", {
                            defaultValue: "1-4 / E / Ctrl+Z"
                          })}
                        </Tag>
                      )}
                      <Button
                        type="link"
                        size="small"
                        className="!h-auto !px-0 text-xs"
                        onClick={cycleShortcutHintDensity}
                        data-testid="flashcards-review-shortcut-hints-toggle"
                      >
                        {shortcutHintToggleLabel}
                      </Button>
                    </div>

                    {/* Re-rate button - appears briefly after rating with countdown */}
                    {showUndoButton && lastReviewedCard && (
                      <div className="mt-3 pt-3 border-t border-border">
                        <Button
                          type="text"
                          icon={<Undo2 className="size-4" />}
                          onClick={handleUndoReview}
                          className="text-text-muted hover:text-text min-h-11 focus:ring-2 focus:ring-primary focus:ring-offset-2"
                          aria-label={t("option:flashcards.undoRatingAria", {
                            defaultValue: "Re-rate last card, {{seconds}} seconds remaining",
                            seconds: undoCountdown
                          })}
                        >
                          <span className="flex items-center gap-2">
                            {t("option:flashcards.undoRating", {
                              defaultValue: "Re-rate last card"
                            })}
                            <span
                              className="inline-flex items-center justify-center min-w-6 h-6 px-1.5 rounded-full bg-surface2 text-xs font-medium tabular-nums"
                              role="timer"
                              aria-live="polite"
                            >
                              {undoCountdown}s
                            </span>
                          </span>
                        </Button>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        </Card>
      ) : (
        <Card>
          <Empty
            description={
              hasCardsQuery.data === false
                ? t("option:flashcards.noCardsYet", {
                    defaultValue: "No flashcards yet"
                  })
                : isCramMode && cramTagFilter
                  ? t("option:flashcards.cramNoCardsForTag", {
                      defaultValue: "No cards match this cram tag filter."
                    })
                  : isCramMode
                    ? t("option:flashcards.cramComplete", {
                        defaultValue: "Cram session complete!"
                      })
                : t("option:flashcards.allCaughtUp", {
                    defaultValue: "You're all caught up!"
                  })
            }
          >
            <Space orientation="vertical" align="center">
              {hasCardsQuery.data === false ? (
                <>
                  <Text type="secondary">
                    {t("option:flashcards.noCardsDescription", {
                      defaultValue:
                        "Create your first flashcard to start studying."
                    })}
                  </Text>
                  <Space>
                    <Button type="primary" onClick={onNavigateToCreate}>
                      {t("option:flashcards.createFirstCard", {
                        defaultValue: "Create card"
                      })}
                    </Button>
                    <Button onClick={onNavigateToImport}>
                      {t("option:flashcards.noDueImportCta", {
                        defaultValue: "Import a deck"
                      })}
                    </Button>
                  </Space>
                </>
              ) : (
                <>
                  {/* Celebratory state with session stats */}
                  {reviewedCount > 0 && (
                    <div className="text-center mb-3">
                      <Text className="text-4xl">🎉</Text>
                      <div className="mt-2">
                        <Text strong className="text-lg">
                          {isCramMode
                            ? t("option:flashcards.reviewedThisCramSession", {
                                defaultValue:
                                  "{{count}} cards practiced in this cram session",
                                count: reviewedCount
                              })
                            : t("option:flashcards.reviewedThisSession", {
                                defaultValue: "{{count}} cards reviewed this session",
                                count: reviewedCount
                              })}
                        </Text>
                      </div>
                    </div>
                  )}
                  <Text type="secondary">
                    {isCramMode
                      ? t("option:flashcards.cramCompleteDescription", {
                          defaultValue:
                            "You reached the end of your cram queue."
                        })
                      : t("option:flashcards.allCaughtUpDescription", {
                          defaultValue:
                            "No cards are due for review. Great job!"
                        })}
                  </Text>

                  {/* Next due date information */}
                  {!isCramMode && nextDueInfo && (
                    <div className="mt-4 p-3 rounded-lg bg-surface2 border border-border">
                      {nextDueInfo.nextDueAt ? (
                        <>
                          <div className="flex items-center gap-2 text-sm">
                            <Calendar className="size-4 text-primary" aria-hidden="true" />
                            <Text strong>
                              {t("option:flashcards.nextDueAt", {
                                defaultValue: "Next review: {{time}}",
                                time: dayjs(nextDueInfo.nextDueAt).fromNow()
                              })}
                            </Text>
                          </div>
                          <Text type="secondary" className="text-xs mt-1 block">
                            {dayjs(nextDueInfo.nextDueAt).format("dddd, MMMM D [at] h:mm A")}
                            {" · "}
                            {t("option:flashcards.nextDueCardCount", {
                              defaultValue: "{{count}} cards due",
                              count: nextDueInfo.cardsDue
                            })}
                          </Text>
                        </>
                      ) : (
                        <Text strong className="text-sm">
                          {t("option:flashcards.nextDueUnavailable", {
                            defaultValue: "Next review estimate unavailable"
                          })}
                        </Text>
                      )}
                      {nextDueInfo.isCapped && (
                        <Text type="secondary" className="text-xs mt-2 block">
                          {t("option:flashcards.nextDueCapped", {
                            defaultValue:
                              "Next review is beyond the first {{count}} cards. Narrow filters to improve the estimate.",
                            count: nextDueInfo.scanned
                          })}
                        </Text>
                      )}
                    </div>
                  )}

                  <Button type="link" onClick={onNavigateToCreate}>
                    {t("option:flashcards.createMoreCards", {
                      defaultValue: "Create card"
                    })}
                  </Button>
                </>
              )}
            </Space>
          </Empty>
        </Card>
      )}
      <FlashcardEditDrawer
        open={editDrawerOpen}
        onClose={() => setEditDrawerOpen(false)}
        card={activeCard ?? null}
        onSave={handleSaveEdit}
        onDelete={handleDeleteFromReview}
        onResetScheduling={handleResetSchedulingFromReview}
        isLoading={
          updateMutation.isPending ||
          deleteMutation.isPending ||
          resetSchedulingMutation.isPending
        }
        decks={decksQuery.data || []}
        decksLoading={decksQuery.isLoading}
      />
    </div>
  )
}

export default ReviewTab
