import React from "react"
import { Button, Card, Empty, Select, Space, Tag, Tooltip, Typography } from "antd"
import { X, Minus, Check, Star, Calendar, Undo2 } from "lucide-react"
import dayjs from "dayjs"
import relativeTime from "dayjs/plugin/relativeTime"
import { useTranslation } from "react-i18next"
import { useAntdMessage } from "@/hooks/useAntdMessage"
import type { Flashcard } from "@/services/flashcards"
import {
  useDecksQuery,
  useReviewQuery,
  useReviewFlashcardMutation,
  useFlashcardShortcuts,
  useDueCountsQuery,
  useHasCardsQuery,
  useNextDueQuery
} from "../hooks"
import { MarkdownWithBoundary, ReviewProgress } from "../components"
import { calculateIntervals } from "../utils/calculateIntervals"
import { formatCardType } from "../utils/model-type-labels"
import { buildReviewUndoState } from "../utils/review-undo"

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
  const reviewQuery = useReviewQuery(reviewDeckId)
  const reviewMutation = useReviewFlashcardMutation()
  const dueCountsQuery = useDueCountsQuery(reviewDeckId)
  const hasCardsQuery = useHasCardsQuery()
  const nextDueQuery = useNextDueQuery(reviewDeckId)
  const nextDueInfo = nextDueQuery.data
  const activeCard = localOverrideCard ?? reviewOverrideCard ?? reviewQuery.data

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
        bgClass: "bg-red-700 hover:bg-red-800 border-red-700 text-white",
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
        bgClass: "bg-amber-100 hover:bg-amber-200 border-amber-300 !text-amber-900",
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
        bgClass: "bg-green-700 hover:bg-green-800 border-green-700 text-white",
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
        bgClass: "bg-blue-700 hover:bg-blue-800 border-blue-700 text-white",
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

        await reviewMutation.mutateAsync({
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

        message.success(t("common:success", { defaultValue: "Success" }))
      } catch (e: unknown) {
        const errorMessage =
          e instanceof Error ? e.message : "Failed to submit review"
        message.error(errorMessage)
      }
    },
    [activeCard, reviewMutation, message, t, reviewOverrideCard, onClearOverride, localOverrideCard]
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
    answerStartTimeRef.current = null
  }, [activeCard?.uuid])

  // Track when the answer is shown (for auto-timing)
  const handleShowAnswer = React.useCallback(() => {
    setShowAnswer(true)
    answerStartTimeRef.current = Date.now()
  }, [])

  // Reset reviewed count when deck changes
  React.useEffect(() => {
    setReviewedCount(0)
    setLocalOverrideCard(null)
    setShowUndoButton(false)
    setLastReviewedCard(null)
    autoRevealAnswerRef.current = false
  }, [reviewDeckId])

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
    onUndo: showUndoButton ? handleUndoReview : undefined
  })

  return (
    <div>
      <div className="mb-3">
        <Select
          placeholder={t("option:flashcards.selectDeck", {
            defaultValue: "Select deck (optional)"
          })}
          allowClear
          loading={decksQuery.isLoading}
          value={reviewDeckId ?? undefined}
          className="min-w-64"
          onChange={(v) => {
            onReviewDeckChange(v)
            if (reviewOverrideCard) {
              onClearOverride?.()
            }
          }}
          data-testid="flashcards-review-deck-select"
          options={(decksQuery.data || []).map((d) => ({
            label: d.name,
            value: d.id
          }))}
        />
      </div>

      {dueCountsQuery.data && dueCountsQuery.data.total > 0 && (
        <ReviewProgress
          dueCount={dueCountsQuery.data.total}
          reviewedCount={reviewedCount}
          deckName={currentDeckName}
        />
      )}

      {activeCard ? (
        <Card>
          <div className="flex flex-col gap-3">
            <div>
              <Tag>{formatCardType(activeCard, t)}</Tag>
              {activeCard.tags?.map((tag) => (
                <Tag key={tag}>{tag}</Tag>
              ))}
            </div>

            <div>
              <Title level={5} className="!mb-2">
                {t("option:flashcards.front", { defaultValue: "Front" })}
              </Title>
              <div className="rounded border border-border bg-surface p-3 text-sm">
                <MarkdownWithBoundary
                  content={activeCard.front}
                  size="sm"
                />
              </div>
            </div>

            {showAnswer && (
              <div>
                <Title level={5} className="!mb-2">
                  {t("option:flashcards.back", { defaultValue: "Back" })}
                </Title>
                <div className="rounded border border-border bg-surface p-3 text-sm">
                  <MarkdownWithBoundary
                    content={activeCard.back}
                    size="sm"
                  />
                </div>
                {activeCard.extra && (
                  <div className="mt-2 text-sm opacity-80">
                    <MarkdownWithBoundary
                      content={activeCard.extra}
                      size="xs"
                    />
                  </div>
                )}
              </div>
            )}

            <div className="mt-2 flex flex-col gap-3">
              {!showAnswer ? (
                <div className="flex flex-col gap-2">
                  <Button
                    type="primary"
                    onClick={handleShowAnswer}
                    data-testid="flashcards-review-show-answer"
                  >
                    {t("option:flashcards.showAnswer", {
                      defaultValue: "Show Answer"
                    })}
                  </Button>
                  <Text type="secondary" className="text-xs">
                    {t("option:flashcards.shortcutFlip", {
                      defaultValue: "Press Space to flip"
                    })}
                  </Text>
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
                    <Text type="secondary" className="text-xs">
                      {t("option:flashcards.shortcutRate", {
                        defaultValue: "Press 1-4 to rate"
                      })}
                    </Text>

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
                : t("option:flashcards.allCaughtUp", {
                    defaultValue: "You're all caught up!"
                  })
            }
          >
            <Space direction="vertical" align="center">
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
                        defaultValue: "Create a flashcard"
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
                          {t("option:flashcards.reviewedThisSession", {
                            defaultValue: "{{count}} cards reviewed this session",
                            count: reviewedCount
                          })}
                        </Text>
                      </div>
                    </div>
                  )}
                  <Text type="secondary">
                    {t("option:flashcards.allCaughtUpDescription", {
                      defaultValue:
                        "No cards are due for review. Great job!"
                    })}
                  </Text>

                  {/* Next due date information */}
                  {nextDueInfo && (
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
                      defaultValue: "Create more cards"
                    })}
                  </Button>
                </>
              )}
            </Space>
          </Empty>
        </Card>
      )}
    </div>
  )
}

export default ReviewTab
