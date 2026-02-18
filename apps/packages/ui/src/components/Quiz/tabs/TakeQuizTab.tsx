import React from "react"
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Empty,
  Input,
  List,
  Modal,
  Progress,
  Radio,
  Select,
  Space,
  Spin,
  Tag,
  Tooltip,
  Typography,
  message
} from "antd"
import { useTranslation } from "react-i18next"
import {
  PlayCircleOutlined,
  ClockCircleOutlined,
  QuestionCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined
} from "@ant-design/icons"
import {
  useAttemptsQuery,
  useQuizzesQuery,
  useQuizQuery,
  useStartAttemptMutation,
  useSubmitAttemptMutation
} from "../hooks"
import { useQuizTimer } from "../hooks/useQuizTimer"
import { useQuizAutoSave } from "../hooks/useQuizAutoSave"
import {
  clearQueuedQuizSubmission,
  readQueuedQuizSubmission,
  writeQueuedQuizSubmission,
  type QueuedQuizSubmission
} from "../hooks/quizSubmissionQueue"
import { useServerOnline } from "@/hooks/useServerOnline"
import type { AnswerValue, QuestionPublic, Quiz, QuizAnswer, QuizAttempt } from "@/services/quizzes"
import type { TakeTabNavigationSource } from "../navigation"
import { TAKE_QUIZ_LIST_PREFS_KEY } from "../stateKeys"

interface TakeQuizTabProps {
  onNavigateToGenerate: () => void
  onNavigateToCreate: () => void
  startQuizId?: number | null
  highlightQuizId?: number | null
  navigationSource?: TakeTabNavigationSource | null
  externalSearchQuery?: string | null
  externalSearchToken?: number | null
  onStartHandled?: () => void
  onHighlightHandled?: () => void
  onExternalSearchHandled?: () => void
}

const DEFAULT_PASSING_SCORE = 70
type QuizSortKey = "name_asc" | "date_desc" | "questions_desc"

export const TakeQuizTab: React.FC<TakeQuizTabProps> = ({
  onNavigateToGenerate,
  onNavigateToCreate,
  startQuizId,
  highlightQuizId,
  navigationSource,
  externalSearchQuery,
  externalSearchToken,
  onStartHandled,
  onHighlightHandled,
  onExternalSearchHandled
}) => {
  const { t } = useTranslation(["option", "common"])
  const [messageApi, contextHolder] = message.useMessage()
  const [page, setPage] = React.useState(() => {
    if (typeof window === "undefined") return 1
    try {
      const raw = window.sessionStorage.getItem(TAKE_QUIZ_LIST_PREFS_KEY)
      if (!raw) return 1
      const parsed = JSON.parse(raw) as { page?: number }
      return typeof parsed.page === "number" && parsed.page > 0 ? parsed.page : 1
    } catch {
      return 1
    }
  })
  const [pageSize, setPageSize] = React.useState(() => {
    if (typeof window === "undefined") return 12
    try {
      const raw = window.sessionStorage.getItem(TAKE_QUIZ_LIST_PREFS_KEY)
      if (!raw) return 12
      const parsed = JSON.parse(raw) as { pageSize?: number }
      return typeof parsed.pageSize === "number" && parsed.pageSize > 0 ? parsed.pageSize : 12
    } catch {
      return 12
    }
  })
  const [searchQuery, setSearchQuery] = React.useState(() => {
    if (typeof window === "undefined") return ""
    try {
      const raw = window.sessionStorage.getItem(TAKE_QUIZ_LIST_PREFS_KEY)
      if (!raw) return ""
      const parsed = JSON.parse(raw) as { searchQuery?: string }
      return typeof parsed.searchQuery === "string" ? parsed.searchQuery : ""
    } catch {
      return ""
    }
  })
  const [sortBy, setSortBy] = React.useState<QuizSortKey>(() => {
    if (typeof window === "undefined") return "date_desc"
    try {
      const raw = window.sessionStorage.getItem(TAKE_QUIZ_LIST_PREFS_KEY)
      if (!raw) return "date_desc"
      const parsed = JSON.parse(raw) as { sortBy?: QuizSortKey }
      if (parsed.sortBy === "name_asc" || parsed.sortBy === "date_desc" || parsed.sortBy === "questions_desc") {
        return parsed.sortBy
      }
      return "date_desc"
    } catch {
      return "date_desc"
    }
  })
  const [activeQuizId, setActiveQuizId] = React.useState<number | null>(null)
  const [pendingQuizId, setPendingQuizId] = React.useState<number | null>(null)
  const [autoSaveWarningDismissed, setAutoSaveWarningDismissed] = React.useState(false)
  const [focusedQuestionId, setFocusedQuestionId] = React.useState<number | null>(null)
  const [unansweredQuestionNumbers, setUnansweredQuestionNumbers] = React.useState<number[]>([])
  const [attempt, setAttempt] = React.useState<QuizAttempt | null>(null)
  const [result, setResult] = React.useState<QuizAttempt | null>(null)
  const [questions, setQuestions] = React.useState<QuestionPublic[]>([])
  const [answers, setAnswers] = React.useState<Record<number, AnswerValue>>({})
  const [queuedSubmission, setQueuedSubmission] = React.useState<QueuedQuizSubmission | null>(null)
  const [isRetryingQueuedSubmission, setIsRetryingQueuedSubmission] = React.useState(false)
  const [submissionQueueStorageUnavailable, setSubmissionQueueStorageUnavailable] = React.useState(false)
  const [highlightedQuizId, setHighlightedQuizId] = React.useState<number | null>(null)
  const lastAutoStartId = React.useRef<number | null>(null)
  const lastAutoHighlightId = React.useRef<number | null>(null)
  const lastExternalSearchToken = React.useRef<number | null>(null)
  const searchInputRef = React.useRef<any>(null)
  const hasInitializedSearchRef = React.useRef(false)
  const questionRefs = React.useRef<Map<number, HTMLDivElement | null>>(new Map())
  const isOnline = useServerOnline()
  const wasOnlineRef = React.useRef(isOnline)
  const offset = (page - 1) * pageSize

  const normalizedSearchQuery = searchQuery.trim()
  const { data, isLoading } = useQuizzesQuery({
    limit: pageSize,
    offset,
    q: normalizedSearchQuery.length > 0 ? normalizedSearchQuery : undefined
  })
  const { data: attemptsData } = useAttemptsQuery({ limit: 200, offset: 0 })
  const detailQuizId = pendingQuizId ?? activeQuizId
  const { data: quizDetails } = useQuizQuery(detailQuizId, { enabled: detailQuizId != null })
  const startAttemptMutation = useStartAttemptMutation()
  const submitAttemptMutation = useSubmitAttemptMutation()

  const quizzes = data?.items ?? []
  const attempts = attemptsData?.items ?? []
  const total = data?.count ?? 0
  const sortedQuizzes = React.useMemo(() => {
    const items = [...quizzes]
    if (sortBy === "name_asc") {
      items.sort((left, right) => left.name.localeCompare(right.name))
    } else if (sortBy === "questions_desc") {
      items.sort((left, right) => right.total_questions - left.total_questions)
    } else {
      items.sort((left, right) => {
        const leftTs = new Date(left.created_at ?? 0).getTime()
        const rightTs = new Date(right.created_at ?? 0).getTime()
        return rightTs - leftTs
      })
    }
    return items
  }, [quizzes, sortBy])

  const {
    storageUnavailable,
    restoreSavedAnswers,
    clearSavedProgress
  } = useQuizAutoSave(attempt?.id ?? null, attempt?.quiz_id ?? activeQuizId, answers, setAnswers)

  const timerState = useQuizTimer({
    timeLimitSeconds: quizDetails?.time_limit_seconds,
    startedAt: attempt?.started_at,
    enabled: attempt != null && result == null,
    onExpire: () => {
      void handleSubmit({ allowPartial: true })
    }
  })

  const timerAnnouncement = React.useMemo(() => {
    if (!timerState || timerState.isExpired || timerState.totalSeconds <= 0) return ""
    if (timerState.totalSeconds <= 60) {
      return t("option:quiz.timerSecondsRemaining", {
        defaultValue: "{{count}} seconds remaining",
        count: timerState.totalSeconds
      })
    }
    if (timerState.totalSeconds % 60 === 0) {
      return t("option:quiz.timerMinutesRemaining", {
        defaultValue: "{{count}} minutes remaining",
        count: Math.floor(timerState.totalSeconds / 60)
      })
    }
    return ""
  }, [timerState, t])

  const statusAnnouncement = React.useMemo(() => {
    if (result) {
      const total = result.total_possible || 0
      const score = result.score ?? 0
      const percentage = total > 0 ? Math.round((score / total) * 100) : 0
      return t("option:quiz.resultAnnouncement", {
        defaultValue: "Quiz submitted. Score {{score}} out of {{total}} ({{percent}} percent).",
        score,
        total,
        percent: percentage
      })
    }
    if (queuedSubmission) {
      return queuedSubmission.allowPartial
        ? t("option:quiz.queueAnnouncementTimer", {
            defaultValue:
              "Time expired and submission is queued. We will retry when connection is restored."
          })
        : t("option:quiz.queueAnnouncement", {
            defaultValue: "Submission failed and is queued locally. Retry is available."
          })
    }
    return ""
  }, [queuedSubmission, result, t])

  const getSubmissionErrorMessage = React.useCallback((error: unknown) => {
    if (error instanceof Error && error.message.trim().length > 0) {
      return error.message
    }
    const messageCandidate = (error as { message?: unknown } | null)?.message
    if (typeof messageCandidate === "string" && messageCandidate.trim().length > 0) {
      return messageCandidate
    }
    return t("option:quiz.submitErrorUnknown", {
      defaultValue: "Unknown submission error"
    })
  }, [t])

  const persistQueuedSubmission = React.useCallback(async (next: QueuedQuizSubmission) => {
    const saved = await writeQueuedQuizSubmission(next)
    setQueuedSubmission(next)
    setSubmissionQueueStorageUnavailable(!saved)
    return saved
  }, [])

  const clearCurrentQueuedSubmission = React.useCallback(async (attemptId: number | null | undefined) => {
    if (attemptId == null) return
    await clearQueuedQuizSubmission(attemptId)
    setQueuedSubmission((current) => (current?.attemptId === attemptId ? null : current))
    setSubmissionQueueStorageUnavailable(false)
  }, [])

  const retryQueuedSubmission = React.useCallback(async (source: "manual" | "online") => {
    if (!queuedSubmission || submitAttemptMutation.isPending || isRetryingQueuedSubmission) return
    setIsRetryingQueuedSubmission(true)
    try {
      const submission = await submitAttemptMutation.mutateAsync({
        attemptId: queuedSubmission.attemptId,
        answers: queuedSubmission.answers
      })
      await clearCurrentQueuedSubmission(queuedSubmission.attemptId)
      if (attempt?.id === queuedSubmission.attemptId) {
        setResult(submission)
        setUnansweredQuestionNumbers([])
        await clearSavedProgress()
      }
      messageApi.success(
        source === "online"
          ? t("option:quiz.submitRetryAutoSuccess", {
              defaultValue: "Connection restored. Queued quiz submission sent."
            })
          : t("option:quiz.submitRetrySuccess", {
              defaultValue: "Submission retry succeeded."
            })
      )
    } catch (error) {
      const updated: QueuedQuizSubmission = {
        ...queuedSubmission,
        retryCount: queuedSubmission.retryCount + 1,
        lastAttemptedAt: Date.now(),
        lastError: getSubmissionErrorMessage(error)
      }
      await persistQueuedSubmission(updated)
      messageApi.error(
        source === "online"
          ? t("option:quiz.submitRetryAutoFailed", {
              defaultValue: "Auto-retry failed. Your answers are still queued locally."
            })
          : t("option:quiz.submitRetryFailed", {
              defaultValue: "Retry failed. Your answers are still queued locally."
            })
      )
    } finally {
      setIsRetryingQueuedSubmission(false)
    }
  }, [
    attempt?.id,
    clearCurrentQueuedSubmission,
    clearSavedProgress,
    getSubmissionErrorMessage,
    isRetryingQueuedSubmission,
    messageApi,
    persistQueuedSubmission,
    queuedSubmission,
    submitAttemptMutation,
    t
  ])

  const resetSession = () => {
    setAttempt(null)
    setResult(null)
    setQuestions([])
    setAnswers({})
    setQueuedSubmission(null)
    setIsRetryingQueuedSubmission(false)
    setSubmissionQueueStorageUnavailable(false)
    setFocusedQuestionId(null)
    setUnansweredQuestionNumbers([])
    setActiveQuizId(null)
    setPendingQuizId(null)
  }

  const handleStart = async (quizId: number): Promise<boolean> => {
    try {
      setActiveQuizId(quizId)
      setResult(null)
      setAnswers({})
      setQueuedSubmission(null)
      setIsRetryingQueuedSubmission(false)
      setSubmissionQueueStorageUnavailable(false)
      setFocusedQuestionId(null)
      setUnansweredQuestionNumbers([])
      const newAttempt = await startAttemptMutation.mutateAsync(quizId)
      const newQuestions = newAttempt.questions ?? []
      if (newQuestions.length === 0) {
        setAttempt(null)
        setQuestions([])
        setActiveQuizId(null)
        messageApi.error(
          t("option:quiz.noQuestionsToStart", {
            defaultValue: "This quiz has no questions yet."
          })
        )
        return false
      }
      setAttempt(newAttempt)
      setQuestions(newQuestions)
      return true
    } catch (error) {
      messageApi.error(
        t("option:quiz.startError", { defaultValue: "Failed to start quiz" })
      )
      return false
    }
  }

  const requestStart = (quizId: number) => {
    setPendingQuizId(quizId)
  }

  const handleConfirmStart = async () => {
    if (pendingQuizId == null) return
    await handleStart(pendingQuizId)
    setPendingQuizId(null)
  }

  React.useEffect(() => {
    if (startQuizId == null) {
      lastAutoStartId.current = null
      return
    }
    if (lastAutoStartId.current === startQuizId) {
      return
    }
    lastAutoStartId.current = startQuizId
    requestStart(startQuizId)
    onStartHandled?.()
  }, [startQuizId, onStartHandled])

  React.useEffect(() => {
    if (highlightQuizId == null) {
      lastAutoHighlightId.current = null
      return
    }
    if (lastAutoHighlightId.current === highlightQuizId) {
      return
    }
    lastAutoHighlightId.current = highlightQuizId
    setHighlightedQuizId(highlightQuizId)
    setSearchQuery("")
    setPage(1)
    onHighlightHandled?.()
  }, [highlightQuizId, onHighlightHandled])

  React.useEffect(() => {
    if (externalSearchToken == null || lastExternalSearchToken.current === externalSearchToken) {
      return
    }
    lastExternalSearchToken.current = externalSearchToken
    setSearchQuery(externalSearchQuery ?? "")
    setPage(1)
    window.setTimeout(() => {
      searchInputRef.current?.focus?.()
    }, 0)
    onExternalSearchHandled?.()
  }, [externalSearchQuery, externalSearchToken, onExternalSearchHandled])

  React.useEffect(() => {
    if (highlightedQuizId == null) return
    const timeoutId = window.setTimeout(() => {
      setHighlightedQuizId(null)
    }, 12000)
    return () => {
      window.clearTimeout(timeoutId)
    }
  }, [highlightedQuizId])

  React.useEffect(() => {
    if (!attempt) return
    void restoreSavedAnswers().then((restored) => {
      if (restored) {
        messageApi.info(
          t("option:quiz.progressRestored", {
            defaultValue: "Restored your saved quiz progress."
          })
        )
      }
    })
  }, [attempt?.id, restoreSavedAnswers, messageApi, t])

  React.useEffect(() => {
    if (!attempt?.id) return
    let cancelled = false
    void readQueuedQuizSubmission(attempt.id).then((queued) => {
      if (cancelled) return
      if (!queued || queued.quizId !== attempt.quiz_id) {
        setQueuedSubmission(null)
        return
      }
      setQueuedSubmission(queued)
    })
    return () => {
      cancelled = true
    }
  }, [attempt?.id, attempt?.quiz_id])

  React.useEffect(() => {
    const becameOnline = !wasOnlineRef.current && isOnline
    wasOnlineRef.current = isOnline
    if (!becameOnline || !queuedSubmission) return
    messageApi.info(
      t("option:quiz.submitRetryingWhenOnline", {
        defaultValue: "Connection restored. Retrying queued quiz submission..."
      })
    )
    void retryQueuedSubmission("online")
  }, [isOnline, queuedSubmission, retryQueuedSubmission, messageApi, t])

  React.useEffect(() => {
    if (typeof window === "undefined") return
    try {
      window.sessionStorage.setItem(
        TAKE_QUIZ_LIST_PREFS_KEY,
        JSON.stringify({
          page,
          pageSize,
          searchQuery,
          sortBy
        })
      )
    } catch {
      // ignore sessionStorage write errors
    }
  }, [page, pageSize, searchQuery, sortBy])

  React.useEffect(() => {
    if (!hasInitializedSearchRef.current) {
      hasInitializedSearchRef.current = true
      return
    }
    setPage(1)
  }, [normalizedSearchQuery])

  const hasAnswerValue = (value: AnswerValue | null | undefined) => {
    if (value === null || value === undefined) return false
    if (typeof value === "string") return value.trim().length > 0
    return true
  }

  const updateAnswer = (questionId: number, value: AnswerValue) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }))
    setFocusedQuestionId(questionId)
    setUnansweredQuestionNumbers([])
  }

  const hasAnswer = (questionId: number) => {
    return hasAnswerValue(answers[questionId])
  }

  const answeredCount = questions.filter((q) => hasAnswer(q.id)).length
  const progress = questions.length > 0 ? Math.round((answeredCount / questions.length) * 100) : 0

  const setQuestionRef = React.useCallback((questionId: number, node: HTMLDivElement | null) => {
    questionRefs.current.set(questionId, node)
  }, [])

  const focusQuestion = React.useCallback((questionId: number) => {
    setFocusedQuestionId(questionId)
    questionRefs.current.get(questionId)?.scrollIntoView({
      behavior: "smooth",
      block: "center"
    })
  }, [])

  const handleSubmit = async (options?: { allowPartial?: boolean }) => {
    if (!attempt) return
    if (submitAttemptMutation.isPending || isRetryingQueuedSubmission) return

    const missing = questions.filter((q) => !hasAnswer(q.id))
    if (!options?.allowPartial && missing.length > 0) {
      const missingQuestionNumbers = missing
        .map((question) => questions.findIndex((item) => item.id === question.id) + 1)
        .filter((num) => num > 0)
      setUnansweredQuestionNumbers(missingQuestionNumbers)
      focusQuestion(missing[0].id)
      messageApi.warning(
        t("option:quiz.answerAll", {
          defaultValue: "Please answer all questions before submitting. Unanswered: {{numbers}}",
          numbers: missingQuestionNumbers.join(", ")
        })
      )
      return
    }
    if (options?.allowPartial && missing.length > 0) {
      messageApi.warning(
        t("option:quiz.timerExpiredSubmitting", {
          defaultValue: "Time expired. Submitting your current answers."
        })
      )
    }
    const payload = questions.map((q) => ({
      question_id: q.id,
      user_answer: answers[q.id]
    })).filter((entry) => entry.user_answer !== null && entry.user_answer !== undefined)

    try {
      const submission = await submitAttemptMutation.mutateAsync({
        attemptId: attempt.id,
        answers: payload
      })
      await clearCurrentQueuedSubmission(attempt.id)
      setResult(submission)
      setUnansweredQuestionNumbers([])
      await clearSavedProgress()
    } catch (error) {
      const previousQueue = queuedSubmission?.attemptId === attempt.id ? queuedSubmission : null
      const didPersist = await persistQueuedSubmission({
        attemptId: attempt.id,
        quizId: attempt.quiz_id,
        answers: payload as Omit<QuizAnswer, "is_correct">[],
        allowPartial: Boolean(options?.allowPartial),
        queuedAt: previousQueue?.queuedAt ?? Date.now(),
        retryCount: previousQueue ? previousQueue.retryCount + 1 : 0,
        lastAttemptedAt: Date.now(),
        lastError: getSubmissionErrorMessage(error)
      })
      messageApi.error(
        options?.allowPartial
          ? t("option:quiz.submitQueuedForRetryOnTimerExpire", {
            defaultValue:
              "Your time expired and submission failed. We'll retry automatically when connection is restored."
          })
          : didPersist
            ? t("option:quiz.submitQueuedForRetry", {
              defaultValue:
                "Submission failed. Your answers are saved locally. Use Retry to submit when reconnected."
            })
            : t("option:quiz.submitQueuedStorageUnavailable", {
              defaultValue:
                "Submission failed and local retry storage is unavailable. Keep this tab open and retry again."
            })
      )
    }
  }

  const renderAnswerInput = (question: QuestionPublic) => {
    if (question.question_type === "multiple_choice") {
      return (
        <fieldset className="border-0 m-0 p-0">
          <legend className="sr-only">{question.question_text}</legend>
          <Radio.Group
            value={answers[question.id]}
            onChange={(e) => updateAnswer(question.id, e.target.value)}
            aria-label={question.question_text}
          >
            <Space orientation="vertical">
              {(question.options ?? []).map((option, index) => (
                <Radio key={index} value={index}>
                  {option || `${t("option:quiz.option", { defaultValue: "Option" })} ${index + 1}`}
                </Radio>
              ))}
            </Space>
          </Radio.Group>
        </fieldset>
      )
    }
    if (question.question_type === "true_false") {
      const legendText = t("option:quiz.trueFalseLegend", {
        defaultValue: "True or false for: {{question}}",
        question: question.question_text
      })
      return (
        <fieldset className="border-0 m-0 p-0">
          <legend className="sr-only">{legendText}</legend>
          <Radio.Group
            value={answers[question.id]}
            onChange={(e) => updateAnswer(question.id, e.target.value)}
            aria-label={legendText}
          >
            <Space orientation="vertical">
              <Radio value="true">{t("option:quiz.true", { defaultValue: "True" })}</Radio>
              <Radio value="false">{t("option:quiz.false", { defaultValue: "False" })}</Radio>
            </Space>
          </Radio.Group>
        </fieldset>
      )
    }
    const helperId = `fill-blank-guidance-${question.id}`
    return (
      <Space orientation="vertical" className="w-full" size={4}>
        <Input
          placeholder={t("option:quiz.correctAnswerPlaceholder", {
            defaultValue: "Enter the correct answer..."
          })}
          aria-label={t("option:quiz.answerForQuestion", {
            defaultValue: "Answer for question: {{question}}",
            question: question.question_text
          })}
          aria-describedby={helperId}
          value={typeof answers[question.id] === "string" ? (answers[question.id] as string) : ""}
          onChange={(e) => updateAnswer(question.id, e.target.value)}
        />
        <Typography.Text id={helperId} type="secondary" className="text-xs">
          {t("option:quiz.fillBlankGuidance", {
            defaultValue: "Case-insensitive exact match. Extra spaces are ignored."
          })}
        </Typography.Text>
      </Space>
    )
  }

  const renderResults = () => {
    if (!result) return null
    const total = result.total_possible || 0
    const score = result.score ?? 0
    const percentage = total > 0 ? Math.round((score / total) * 100) : 0
    const passingScore = quizDetails?.passing_score ?? DEFAULT_PASSING_SCORE
    const passed = percentage >= passingScore
    const answerMap = new Map(result.answers.map((a) => [a.question_id, a]))

    return (
      <div className="space-y-4">
        <Alert
          type={passed ? "success" : "warning"}
          title={t("option:quiz.scoreSummary", {
            defaultValue: "Score: {{score}} / {{total}} ({{percent}}%)",
            score,
            total,
            percent: percentage
          })}
          description={quizDetails?.passing_score != null
            ? t("option:quiz.passingScoreLabel", { defaultValue: "Pass" }) +
              `: ${quizDetails.passing_score}%`
            : t("option:quiz.noPassingScoreDefault", {
              defaultValue: "No passing score set. Using default: {{score}}%.",
              score: DEFAULT_PASSING_SCORE
            })}
          showIcon
        />

        <List
          dataSource={questions}
          renderItem={(question, index) => {
            const answer = answerMap.get(question.id)
            const isCorrect = answer?.is_correct
            const userAnswer = answer?.user_answer
            const correctAnswer = answer?.correct_answer
            const optionFor = (value: AnswerValue | undefined) => {
              if (value == null) return "-"
              if (question.question_type !== "multiple_choice") return String(value)
              const idx = Number(value)
              const options = question.options ?? []
              return options[idx] ?? String(value)
            }

            return (
              <List.Item>
                <div className="w-full space-y-2">
                  <div className="flex items-start justify-between gap-3">
                    <div className="font-medium">
                      {index + 1}. {question.question_text}
                    </div>
                    <Tag
                      color={isCorrect ? "green" : "red"}
                      icon={isCorrect ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
                    >
                      {isCorrect
                        ? t("option:quiz.correct", { defaultValue: "Correct" })
                        : t("option:quiz.incorrect", { defaultValue: "Incorrect" })}
                    </Tag>
                  </div>
                  <div className="text-sm text-text-muted">
                    {t("option:quiz.yourAnswer", { defaultValue: "Your answer" })}:{" "}
                    <span className="font-medium">{optionFor(userAnswer)}</span>
                  </div>
                  <div className="text-sm text-text-muted">
                    {t("option:quiz.correctAnswerLabel", { defaultValue: "Correct answer" })}:{" "}
                    <span className="font-medium">{optionFor(correctAnswer)}</span>
                  </div>
                  {answer?.explanation && (
                    <Typography.Paragraph className="text-sm text-text-subtle mb-0">
                      {answer.explanation}
                    </Typography.Paragraph>
                  )}
                </div>
              </List.Item>
            )
          }}
        />

        <Space>
          <Button onClick={resetSession}>
            {t("option:quiz.backToList", { defaultValue: "Back to list" })}
          </Button>
          <Tooltip
            title={t("option:quiz.retakeBehavior", {
              defaultValue: "Retake uses the same questions in the same order."
            })}
          >
            <Button
              type="primary"
              onClick={() => activeQuizId != null && requestStart(activeQuizId)}
            >
              {t("option:quiz.retake", { defaultValue: "Retake Quiz" })}
            </Button>
          </Tooltip>
        </Space>
      </div>
    )
  }

  const formatQuizTimeLimit = (timeLimitSeconds: number | null | undefined) => {
    if (!timeLimitSeconds || timeLimitSeconds <= 0) {
      return t("option:quiz.noTimeLimit", { defaultValue: "No time limit" })
    }
    const minutes = Math.floor(timeLimitSeconds / 60)
    const seconds = timeLimitSeconds % 60
    if (minutes === 0) {
      return t("option:quiz.secondsShort", { defaultValue: "{{count}} sec", count: seconds })
    }
    if (seconds === 0) {
      return `${minutes} ${t("option:quiz.minutes", { defaultValue: "min" })}`
    }
    return `${minutes}m ${seconds}s`
  }

  const formatQuizDate = (dateString: string | null | undefined) => {
    if (!dateString) return null
    const parsed = new Date(dateString)
    if (Number.isNaN(parsed.getTime())) return null
    return parsed.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric"
    })
  }

  const getQuizDifficultyLabel = (quiz: Quiz | null | undefined) => {
    const rawDifficulty = (quiz as Quiz & { difficulty?: string | null } | null)?.difficulty
    if (!rawDifficulty) {
      return t("option:quiz.notSpecified", { defaultValue: "Not specified" })
    }
    return `${rawDifficulty.charAt(0).toUpperCase()}${rawDifficulty.slice(1)}`
  }

  const lastScoreByQuizId = React.useMemo(() => {
    const scoreMap = new Map<number, number>()
    const sortedAttempts = [...attempts].sort((left, right) => {
      const leftDate = new Date(left.completed_at ?? left.started_at).getTime()
      const rightDate = new Date(right.completed_at ?? right.started_at).getTime()
      return rightDate - leftDate
    })
    sortedAttempts.forEach((entry) => {
      if (scoreMap.has(entry.quiz_id)) return
      if (!entry.completed_at) return
      if (!entry.total_possible || entry.total_possible <= 0) return
      const percentage = Math.round(((entry.score ?? 0) / entry.total_possible) * 100)
      scoreMap.set(entry.quiz_id, percentage)
    })
    return scoreMap
  }, [attempts])

  const pendingQuiz = React.useMemo(() => {
    if (pendingQuizId == null) return null
    if (quizDetails?.id === pendingQuizId) return quizDetails
    return quizzes.find((quiz) => quiz.id === pendingQuizId) ?? null
  }, [pendingQuizId, quizDetails, quizzes])

  const highlightedQuiz = React.useMemo(() => {
    if (highlightedQuizId == null) return null
    return sortedQuizzes.find((quiz) => quiz.id === highlightedQuizId) ?? null
  }, [highlightedQuizId, sortedQuizzes])

  const highlightNotice = React.useMemo(() => {
    if (!highlightedQuiz) return null
    if (navigationSource === "generate") {
      return t("option:quiz.generatedHighlightNotice", {
        defaultValue: "Quiz generated successfully: {{name}}. It is highlighted below.",
        name: highlightedQuiz.name
      })
    }
    if (navigationSource === "create") {
      return t("option:quiz.createdHighlightNotice", {
        defaultValue: "Quiz created successfully: {{name}}. It is highlighted below.",
        name: highlightedQuiz.name
      })
    }
    if (navigationSource === "results") {
      return t("option:quiz.retakeHighlightNotice", {
        defaultValue: "Retake ready for {{name}}.",
        name: highlightedQuiz.name
      })
    }
    if (navigationSource === "manage") {
      return t("option:quiz.manageHighlightNotice", {
        defaultValue: "{{name}} selected from Manage tab.",
        name: highlightedQuiz.name
      })
    }
    return t("option:quiz.highlightNotice", {
      defaultValue: "Quiz selected: {{name}}.",
      name: highlightedQuiz.name
    })
  }, [highlightedQuiz, navigationSource, t])

  const renderStartConfirmationModal = () => (
    <Modal
      title={t("option:quiz.readyToBegin", { defaultValue: "Ready to begin?" })}
      open={pendingQuizId != null}
      onCancel={() => setPendingQuizId(null)}
      onOk={handleConfirmStart}
      okText={t("option:quiz.begin", { defaultValue: "Begin Quiz" })}
      cancelText={t("common:cancel", { defaultValue: "Cancel" })}
      confirmLoading={startAttemptMutation.isPending}
      destroyOnHidden
    >
      <div className="space-y-3">
        <Typography.Text className="block text-text-muted">
          {pendingQuiz?.name ?? t("option:quiz.selectedQuiz", { defaultValue: "Selected quiz" })}
        </Typography.Text>
        <Descriptions size="small" bordered column={1}>
          <Descriptions.Item
            label={t("option:quiz.questions", { defaultValue: "Questions" })}
          >
            {pendingQuiz?.total_questions ?? "-"}
          </Descriptions.Item>
          <Descriptions.Item
            label={t("option:quiz.timeLimit", { defaultValue: "Time limit" })}
          >
            {formatQuizTimeLimit(pendingQuiz?.time_limit_seconds)}
          </Descriptions.Item>
          <Descriptions.Item
            label={t("option:quiz.passingScore", { defaultValue: "Passing score" })}
          >
            {pendingQuiz?.passing_score != null
              ? `${pendingQuiz.passing_score}%`
              : `${DEFAULT_PASSING_SCORE}% (${t("option:quiz.defaultLabel", { defaultValue: "default" })})`}
          </Descriptions.Item>
          <Descriptions.Item
            label={t("option:quiz.difficulty", { defaultValue: "Difficulty" })}
          >
            {getQuizDifficultyLabel(pendingQuiz)}
          </Descriptions.Item>
        </Descriptions>
        <Alert
          type="info"
          showIcon
          title={t("option:quiz.retakeBehavior", {
            defaultValue: "Retake uses the same questions in the same order."
          })}
        />
      </div>
    </Modal>
  )

  const renderAutoSaveWarning = () => {
    if (!storageUnavailable || autoSaveWarningDismissed) return null
    return (
      <Alert
        type="warning"
        showIcon
        closable
        onClose={() => setAutoSaveWarningDismissed(true)}
        title={t("option:quiz.autosaveUnavailable", {
          defaultValue:
            "Auto-save unavailable — your progress won't be preserved if you navigate away."
        })}
      />
    )
  }

  const renderSubmissionQueueAlert = () => {
    if (!queuedSubmission) return null
    const queuedAtLabel = new Date(queuedSubmission.queuedAt).toLocaleTimeString()
    return (
      <Alert
        type="error"
        showIcon
        title={queuedSubmission.allowPartial
          ? t("option:quiz.submitQueueTitleTimer", {
            defaultValue: "Time expired. Submission pending retry."
          })
          : t("option:quiz.submitQueueTitle", {
            defaultValue: "Submission failed. Answers queued locally."
          })}
        description={(
          <div className="space-y-2">
            <Typography.Text className="block text-xs text-text-muted">
              {t("option:quiz.submitQueueMeta", {
                defaultValue:
                  "Queued at {{time}}. Retry attempts: {{count}}.",
                time: queuedAtLabel,
                count: queuedSubmission.retryCount
              })}
            </Typography.Text>
            {queuedSubmission.lastError && (
              <Typography.Text className="block text-xs text-text-muted">
                {t("option:quiz.submitQueueLastError", {
                  defaultValue: "Last error: {{error}}",
                  error: queuedSubmission.lastError
                })}
              </Typography.Text>
            )}
            <Typography.Text className="block text-xs text-text-muted">
              {isOnline
                ? t("option:quiz.submitQueueOnlineHint", {
                  defaultValue:
                    "You're online. Retry now to submit immediately, or we'll retry when connectivity changes."
                })
                : t("option:quiz.submitQueueOfflineHint", {
                  defaultValue:
                    "You're offline. We'll retry automatically when your connection returns."
                })}
            </Typography.Text>
            {submissionQueueStorageUnavailable && (
              <Typography.Text className="block text-xs text-text-warning">
                {t("option:quiz.submitQueueStorageUnavailable", {
                  defaultValue:
                    "Local queue storage is unavailable in this browser session."
                })}
              </Typography.Text>
            )}
          </div>
        )}
        action={(
          <Button
            size="small"
            type="primary"
            onClick={() => {
              void retryQueuedSubmission("manual")
            }}
            loading={submitAttemptMutation.isPending || isRetryingQueuedSubmission}
            disabled={!isOnline || submitAttemptMutation.isPending || isRetryingQueuedSubmission}
          >
            {t("option:quiz.retrySubmission", { defaultValue: "Retry submission" })}
          </Button>
        )}
      />
    )
  }

  const renderLiveRegions = () => (
    <>
      {timerAnnouncement && (
        <div
          className="sr-only"
          aria-live={timerState?.isDanger ? "assertive" : "polite"}
          aria-atomic="true"
        >
          {timerAnnouncement}
        </div>
      )}
      {statusAnnouncement && (
        <div className="sr-only" aria-live="polite" aria-atomic="true">
          {statusAnnouncement}
        </div>
      )}
    </>
  )

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        {contextHolder}
        {renderLiveRegions()}
        {renderStartConfirmationModal()}
        <Spin size="large" />
      </div>
    )
  }

  if (attempt && result) {
    return (
      <div className="space-y-4">
        {contextHolder}
        {renderLiveRegions()}
        {renderAutoSaveWarning()}
        {renderSubmissionQueueAlert()}
        {renderStartConfirmationModal()}
        {renderResults()}
      </div>
    )
  }

  if (attempt && questions.length > 0) {
    return (
      <div className="space-y-4">
        {contextHolder}
        {renderLiveRegions()}
        {renderAutoSaveWarning()}
        {renderSubmissionQueueAlert()}
        {renderStartConfirmationModal()}
        <Card
          title={quizDetails?.name || t("option:quiz.take", { defaultValue: "Take Quiz" })}
          extra={
            <Space>
              <Tag icon={<QuestionCircleOutlined />}>
                {answeredCount}/{questions.length}
              </Tag>
              {timerState && (
                <Tag
                  icon={<ClockCircleOutlined />}
                  color={timerState.isDanger ? "red" : timerState.isWarning ? "orange" : "default"}
                  aria-label={t("option:quiz.timerDisplayAria", {
                    defaultValue: "Time remaining: {{time}}",
                    time: timerState.formattedTime
                  })}
                >
                  {timerState.formattedTime}
                </Tag>
              )}
            </Space>
          }
        >
          <div className="space-y-4">
            <Card size="small">
              <div className="space-y-2">
                <Typography.Text className="text-xs text-text-muted">
                  {t("option:quiz.questionNavigator", { defaultValue: "Question navigator" })}
                </Typography.Text>
                <div className="flex flex-wrap gap-2">
                  {questions.map((question, index) => {
                    const answered = hasAnswer(question.id)
                    const focused = focusedQuestionId === question.id
                    return (
                      <Button
                        key={question.id}
                        size="small"
                        type={focused ? "primary" : "default"}
                        danger={!answered}
                        onClick={() => focusQuestion(question.id)}
                        aria-label={t("option:quiz.goToQuestion", {
                          defaultValue: "Go to question {{number}}",
                          number: index + 1
                        })}
                      >
                        {index + 1}
                      </Button>
                    )
                  })}
                </div>
              </div>
            </Card>

            {unansweredQuestionNumbers.length > 0 && (
              <Alert
                type="warning"
                showIcon
                title={t("option:quiz.unansweredSummary", {
                  defaultValue: "Unanswered questions: {{numbers}}",
                  numbers: unansweredQuestionNumbers.join(", ")
                })}
              />
            )}

            <div
              role="progressbar"
              aria-label={t("option:quiz.progressAria", { defaultValue: "Quiz completion progress" })}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(progress)}
            >
              <Progress percent={progress} />
            </div>
            <List
              dataSource={questions}
              renderItem={(question, index) => (
                <List.Item>
                  <div
                    ref={(node) => setQuestionRef(question.id, node)}
                    data-testid={`quiz-question-${question.id}`}
                    data-highlighted={focusedQuestionId === question.id}
                    className={`w-full space-y-2 rounded-md p-2 transition-colors ${
                      focusedQuestionId === question.id ? "border border-warning/60 bg-warning/10" : ""
                    }`}
                  >
                    <div className="font-medium">
                      {index + 1}. {question.question_text}
                    </div>
                    {renderAnswerInput(question)}
                  </div>
                </List.Item>
              )}
            />
            <Space>
              <Button onClick={resetSession}>
                {t("option:quiz.backToList", { defaultValue: "Back to list" })}
              </Button>
              <Button
                type="primary"
                onClick={() => handleSubmit()}
                loading={submitAttemptMutation.isPending || isRetryingQueuedSubmission}
                disabled={submitAttemptMutation.isPending || isRetryingQueuedSubmission}
              >
                {t("common:submit", { defaultValue: "Submit" })}
              </Button>
            </Space>
          </div>
        </Card>
      </div>
    )
  }

  if (quizzes.length === 0) {
    return (
      <>
        {contextHolder}
        {renderLiveRegions()}
        {renderAutoSaveWarning()}
        {renderSubmissionQueueAlert()}
        {renderStartConfirmationModal()}
        <Empty
          description={
            <div className="space-y-2">
              <p className="text-text-muted">
                {t("option:quiz.empty.noQuizzes", {
                  defaultValue: "No quizzes available to take yet"
                })}
              </p>
              <p className="text-sm text-text-subtle">
                {t("option:quiz.empty.createFirst", {
                  defaultValue:
                    "Generate one from media or create one manually, then come back to take it"
                })}
              </p>
            </div>
          }
        >
          <div className="flex gap-2 justify-center">
            <Button type="primary" onClick={onNavigateToGenerate}>
              {t("option:quiz.generateFromMedia", { defaultValue: "Generate from Media" })}
            </Button>
            <Button onClick={onNavigateToCreate}>
              {t("option:quiz.createManually", { defaultValue: "Create Manually" })}
            </Button>
          </div>
        </Empty>
      </>
    )
  }

  return (
    <div className="space-y-4">
      {contextHolder}
      {renderLiveRegions()}
      {renderAutoSaveWarning()}
      {renderSubmissionQueueAlert()}
      {renderStartConfirmationModal()}
      <div className="text-sm text-text-muted">
        {t("option:quiz.selectQuiz", { defaultValue: "Select a quiz to begin" })}
      </div>

      {highlightNotice && (
        <Alert
          type="info"
          showIcon
          title={highlightNotice}
          closable
          onClose={() => setHighlightedQuizId(null)}
        />
      )}

      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <Input.Search
          ref={searchInputRef}
          allowClear
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
          placeholder={t("option:quiz.searchPlaceholder", { defaultValue: "Search quizzes..." })}
          className="w-full md:max-w-md"
        />
        <Select
          className="w-full md:w-56"
          value={sortBy}
          onChange={(nextValue) => setSortBy(nextValue)}
          options={[
            {
              value: "date_desc",
              label: t("option:quiz.sortNewest", { defaultValue: "Newest first" })
            },
            {
              value: "name_asc",
              label: t("option:quiz.sortName", { defaultValue: "Name (A-Z)" })
            },
            {
              value: "questions_desc",
              label: t("option:quiz.sortQuestionCount", { defaultValue: "Most questions" })
            }
          ]}
        />
      </div>

      <List
        grid={{ gutter: 16, xs: 1, sm: 2, md: 2, lg: 3, xl: 3, xxl: 4 }}
        dataSource={sortedQuizzes}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          locale: {
            items_per_page: t("option:quiz.itemsPerPage", { defaultValue: "items/page" })
          },
          onChange: (nextPage, nextPageSize) => {
            setPage(nextPage)
            if (nextPageSize && nextPageSize !== pageSize) {
              setPageSize(nextPageSize)
              setPage(1)
            }
          }
        }}
        renderItem={(quiz) => {
          const isHighlighted = quiz.id === highlightedQuizId
          return (
            <List.Item>
              <Card
                hoverable
                className="h-full"
                style={isHighlighted
                  ? {
                    borderColor: "var(--color-primary, #1677ff)",
                    boxShadow: "0 0 0 2px rgba(22, 119, 255, 0.2)"
                  }
                  : undefined}
                data-testid={`take-quiz-card-${quiz.id}`}
                data-highlighted={isHighlighted ? "true" : undefined}
                actions={[
                  <Button
                    key="start"
                    type="primary"
                    icon={<PlayCircleOutlined />}
                    onClick={() => {
                      setHighlightedQuizId(null)
                      requestStart(quiz.id)
                    }}
                  >
                    {t("option:quiz.startQuiz", { defaultValue: "Start Quiz" })}
                  </Button>
                ]}
              >
                <Card.Meta
                  title={quiz.name}
                  description={
                    <div className="space-y-2">
                      {quiz.description && (
                        <p className="text-sm text-text-muted line-clamp-2">
                          {quiz.description}
                        </p>
                      )}
                      <div className="flex flex-wrap gap-2">
                        <Tag icon={<QuestionCircleOutlined />}>
                          {quiz.total_questions}{" "}
                          {t("option:quiz.questions", { defaultValue: "questions" })}
                        </Tag>
                        {quiz.time_limit_seconds && (
                          <Tag icon={<ClockCircleOutlined />}>
                            {formatQuizTimeLimit(quiz.time_limit_seconds)}
                          </Tag>
                        )}
                        {quiz.passing_score != null && (
                          <Tag color="blue">
                            {t("option:quiz.passingScoreLabel", { defaultValue: "Pass" })}: {quiz.passing_score}%
                          </Tag>
                        )}
                        {(quiz as Quiz & { difficulty?: string | null }).difficulty && (
                          <Tag color="purple">
                            {getQuizDifficultyLabel(quiz)}
                          </Tag>
                        )}
                        {quiz.media_id != null && (
                          <Tag color="green">
                            <Typography.Link href={`/media?id=${quiz.media_id}`}>
                              {t("option:quiz.sourceMedia", { defaultValue: "Source media #{{id}}", id: quiz.media_id })}
                            </Typography.Link>
                          </Tag>
                        )}
                        {lastScoreByQuizId.has(quiz.id) && (
                          <Tag color="geekblue">
                            {t("option:quiz.lastScore", { defaultValue: "Last score: {{score}}%", score: lastScoreByQuizId.get(quiz.id) })}
                          </Tag>
                        )}
                      </div>
                      {formatQuizDate(quiz.created_at) && (
                        <p className="text-xs text-text-subtle">
                          {t("option:quiz.createdOn", { defaultValue: "Created: {{date}}", date: formatQuizDate(quiz.created_at) })}
                        </p>
                      )}
                    </div>
                  }
                />
              </Card>
            </List.Item>
          )
        }}
      />
    </div>
  )
}

export default TakeQuizTab
