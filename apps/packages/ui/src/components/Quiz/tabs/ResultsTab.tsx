import React from "react"
import {
  Button,
  Card,
  Select,
  Descriptions,
  Empty,
  List,
  Modal,
  Progress,
  Spin,
  Statistic,
  Tag,
  Typography
} from "antd"
import { useTranslation } from "react-i18next"
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  EyeOutlined,
  RedoOutlined,
  TrophyOutlined
} from "@ant-design/icons"
import { useAllAttemptsQuery, useAttemptQuery, useQuizzesQuery } from "../hooks"
import type { AnswerValue, QuestionPublic, QuizAnswer } from "@/services/quizzes"

const { Text } = Typography

const RESULTS_FILTER_PREFS_KEY = "quiz-results-filters-v1"
const DEFAULT_PASSING_SCORE = 70
type PassFilterKey = "all" | "pass" | "fail"
type DateRangeFilterKey = "all" | "7d" | "30d" | "90d"

type ResultsFilterPrefs = {
  page: number
  pageSize: number
  quizFilterId: number | null
  passFilter: PassFilterKey
  dateRangeFilter: DateRangeFilterKey
}

const DEFAULT_RESULTS_FILTER_PREFS: ResultsFilterPrefs = {
  page: 1,
  pageSize: 10,
  quizFilterId: null,
  passFilter: "all",
  dateRangeFilter: "all"
}

const readStoredResultsFilterPrefs = (): ResultsFilterPrefs => {
  if (typeof window === "undefined") {
    return DEFAULT_RESULTS_FILTER_PREFS
  }
  try {
    const raw = window.sessionStorage.getItem(RESULTS_FILTER_PREFS_KEY)
    if (!raw) return DEFAULT_RESULTS_FILTER_PREFS
    const parsed = JSON.parse(raw) as Partial<ResultsFilterPrefs>
    const page = typeof parsed.page === "number" && parsed.page > 0 ? parsed.page : DEFAULT_RESULTS_FILTER_PREFS.page
    const pageSize = typeof parsed.pageSize === "number" && parsed.pageSize > 0
      ? parsed.pageSize
      : DEFAULT_RESULTS_FILTER_PREFS.pageSize
    const quizFilterId = typeof parsed.quizFilterId === "number" ? parsed.quizFilterId : null
    const passFilter = parsed.passFilter === "pass" || parsed.passFilter === "fail" ? parsed.passFilter : "all"
    const dateRangeFilter = parsed.dateRangeFilter === "7d"
      || parsed.dateRangeFilter === "30d"
      || parsed.dateRangeFilter === "90d"
      ? parsed.dateRangeFilter
      : "all"
    return {
      page,
      pageSize,
      quizFilterId,
      passFilter,
      dateRangeFilter
    }
  } catch {
    return DEFAULT_RESULTS_FILTER_PREFS
  }
}

interface ResultsTabProps {
  onRetakeQuiz?: (quizId: number) => void
}

export const ResultsTab: React.FC<ResultsTabProps> = ({ onRetakeQuiz }) => {
  const { t } = useTranslation(["option", "common"])

  const [page, setPage] = React.useState(() => readStoredResultsFilterPrefs().page)
  const [pageSize, setPageSize] = React.useState(() => readStoredResultsFilterPrefs().pageSize)
  const [quizFilterId, setQuizFilterId] = React.useState<number | null>(
    () => readStoredResultsFilterPrefs().quizFilterId
  )
  const [passFilter, setPassFilter] = React.useState<PassFilterKey>(
    () => readStoredResultsFilterPrefs().passFilter
  )
  const [dateRangeFilter, setDateRangeFilter] = React.useState<DateRangeFilterKey>(
    () => readStoredResultsFilterPrefs().dateRangeFilter
  )
  const [selectedAttemptId, setSelectedAttemptId] = React.useState<number | null>(null)
  const attemptsQueryParams = React.useMemo(() => ({
    limit: 200,
    offset: 0,
    quiz_id: quizFilterId ?? undefined
  }), [quizFilterId])

  React.useEffect(() => {
    if (typeof window === "undefined") return
    try {
      window.sessionStorage.setItem(RESULTS_FILTER_PREFS_KEY, JSON.stringify({
        page,
        pageSize,
        quizFilterId,
        passFilter,
        dateRangeFilter
      } satisfies ResultsFilterPrefs))
    } catch {
      // Ignore session-storage persistence failures for filter prefs.
    }
  }, [page, pageSize, quizFilterId, passFilter, dateRangeFilter])

  const { data: attemptsData, isLoading: attemptsLoading } = useAllAttemptsQuery({
    quiz_id: attemptsQueryParams.quiz_id
  })
  const { data: quizzesData, isLoading: quizzesLoading } = useQuizzesQuery({
    limit: 200,
    offset: 0
  })
  const {
    data: selectedAttemptDetails,
    isLoading: selectedAttemptLoading,
    isFetching: selectedAttemptFetching
  } = useAttemptQuery(
    selectedAttemptId,
    { includeQuestions: true },
    { enabled: selectedAttemptId != null }
  )

  const attempts = attemptsData?.items ?? []
  const quizzes = quizzesData?.items ?? []

  const quizMap = React.useMemo(() => {
    const map = new Map<number, { name: string; passingScore: number | null }>()
    quizzes.forEach((q) => {
      map.set(q.id, {
        name: q.name,
        passingScore: typeof q.passing_score === "number" ? q.passing_score : null
      })
    })
    return map
  }, [quizzes])
  const getPassingScoreForQuiz = React.useCallback((quizId: number) => {
    return quizMap.get(quizId)?.passingScore ?? DEFAULT_PASSING_SCORE
  }, [quizMap])

  const filteredAttempts = React.useMemo(() => {
    const nowMs = Date.now()
    const dateRangeDays = dateRangeFilter === "7d"
      ? 7
      : dateRangeFilter === "30d"
        ? 30
        : dateRangeFilter === "90d"
          ? 90
          : null

    return attempts.filter((attempt) => {
      if (quizFilterId != null && attempt.quiz_id !== quizFilterId) {
        return false
      }

      if (passFilter !== "all") {
        if (!attempt.completed_at) return false
        const percentage = attempt.total_possible > 0
          ? Math.round(((attempt.score ?? 0) / attempt.total_possible) * 100)
          : 0
        const passingScore = getPassingScoreForQuiz(attempt.quiz_id)
        if (passFilter === "pass" && percentage < passingScore) return false
        if (passFilter === "fail" && percentage >= passingScore) return false
      }

      if (dateRangeDays != null) {
        const referenceDate = attempt.completed_at ?? attempt.started_at
        if (!referenceDate) return false
        const referenceMs = new Date(referenceDate).getTime()
        if (Number.isNaN(referenceMs)) return false
        const windowMs = dateRangeDays * 24 * 60 * 60 * 1000
        if (nowMs - referenceMs > windowMs) return false
      }

      return true
    })
  }, [attempts, dateRangeFilter, getPassingScoreForQuiz, passFilter, quizFilterId])

  const totalFilteredAttempts = filteredAttempts.length
  const paginatedAttempts = React.useMemo(() => {
    const offset = (page - 1) * pageSize
    return filteredAttempts.slice(offset, offset + pageSize)
  }, [filteredAttempts, page, pageSize])

  React.useEffect(() => {
    const maxPage = Math.max(1, Math.ceil(totalFilteredAttempts / pageSize))
    if (page > maxPage) {
      setPage(maxPage)
    }
  }, [page, pageSize, totalFilteredAttempts])

  const isLoading = attemptsLoading || quizzesLoading
  const hasActiveFilters = quizFilterId != null || passFilter !== "all" || dateRangeFilter !== "all"

  // Calculate stats
  const stats = React.useMemo(() => {
    if (filteredAttempts.length === 0) return null

    const completedAttempts = filteredAttempts.filter((a) => a.completed_at)
    const totalScore = completedAttempts.reduce((sum, a) => sum + (a.score ?? 0), 0)
    const totalPossible = completedAttempts.reduce((sum, a) => sum + a.total_possible, 0)
    const avgScore = totalPossible > 0 ? Math.round((totalScore / totalPossible) * 100) : 0

    const totalTime = completedAttempts.reduce((sum, a) => sum + (a.time_spent_seconds ?? 0), 0)
    const avgTime = completedAttempts.length > 0 ? Math.round(totalTime / completedAttempts.length) : 0

    return {
      totalAttempts: completedAttempts.length,
      avgScore,
      avgTime,
      uniqueQuizzes: new Set(completedAttempts.map((a) => a.quiz_id)).size
    }
  }, [filteredAttempts])

  const scoreTrend = React.useMemo(() => {
    return filteredAttempts
      .filter((attempt) => attempt.completed_at && attempt.total_possible > 0)
      .map((attempt) => ({
        attemptId: attempt.id,
        completedAt: attempt.completed_at ?? attempt.started_at,
        scorePct: Math.round(((attempt.score ?? 0) / attempt.total_possible) * 100)
      }))
      .sort((left, right) => new Date(left.completedAt).getTime() - new Date(right.completedAt).getTime())
      .slice(-20)
  }, [filteredAttempts])

  const scoreDistribution = React.useMemo(() => {
    const buckets = [
      { label: "0-49%", min: 0, max: 49, count: 0 },
      { label: "50-69%", min: 50, max: 69, count: 0 },
      { label: "70-84%", min: 70, max: 84, count: 0 },
      { label: "85-100%", min: 85, max: 100, count: 0 }
    ]

    filteredAttempts
      .filter((attempt) => attempt.completed_at && attempt.total_possible > 0)
      .forEach((attempt) => {
        const scorePct = Math.round(((attempt.score ?? 0) / attempt.total_possible) * 100)
        const bucket = buckets.find((candidate) => scorePct >= candidate.min && scorePct <= candidate.max)
        if (bucket) {
          bucket.count += 1
        }
      })

    return buckets
  }, [filteredAttempts])

  const scoreTrendPolylinePoints = React.useMemo(() => {
    if (scoreTrend.length < 2) return null
    const width = 360
    const height = 84
    const padding = 8
    const drawableWidth = width - padding * 2
    const drawableHeight = height - padding * 2
    return scoreTrend
      .map((entry, index) => {
        const x = padding + (index / (scoreTrend.length - 1)) * drawableWidth
        const y = padding + ((100 - entry.scorePct) / 100) * drawableHeight
        return `${x},${y}`
      })
      .join(" ")
  }, [scoreTrend])

  const scoreDistributionMaxCount = React.useMemo(() => {
    const max = Math.max(...scoreDistribution.map((bucket) => bucket.count), 0)
    return max > 0 ? max : 1
  }, [scoreDistribution])

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, "0")}`
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    })
  }

  const resetFilters = () => {
    setQuizFilterId(null)
    setPassFilter("all")
    setDateRangeFilter("all")
    setPage(1)
  }

  const buildCsvCell = (value: string | number | null | undefined) => {
    const normalized = value == null ? "" : String(value)
    return `"${normalized.replace(/"/g, "\"\"")}"`
  }

  const exportFilteredAttemptsCsv = () => {
    if (filteredAttempts.length === 0) return

    const now = new Date()
    const fileDate = now.toISOString().slice(0, 10)
    const dateRangeEndIso = now.toISOString()
    const dateRangeStartIso = dateRangeFilter === "7d"
      ? new Date(now.getTime() - (7 * 24 * 60 * 60 * 1000)).toISOString()
      : dateRangeFilter === "30d"
        ? new Date(now.getTime() - (30 * 24 * 60 * 60 * 1000)).toISOString()
        : dateRangeFilter === "90d"
          ? new Date(now.getTime() - (90 * 24 * 60 * 60 * 1000)).toISOString()
          : ""

    const headers = [
      "attempt_id",
      "quiz_id",
      "quiz_name",
      "started_at",
      "completed_at",
      "time_spent_seconds",
      "score",
      "total_possible",
      "percentage",
      "passing_score",
      "is_passing",
      "filter_quiz_id",
      "filter_pass_state",
      "filter_date_range",
      "filter_date_start_iso",
      "filter_date_end_iso"
    ]

    const lines = filteredAttempts.map((attempt) => {
      const score = attempt.score ?? 0
      const total = attempt.total_possible
      const percentage = total > 0 ? Math.round((score / total) * 100) : 0
      const passingScore = getPassingScoreForQuiz(attempt.quiz_id)
      const isPassing = percentage >= passingScore
      const quizName = quizMap.get(attempt.quiz_id)?.name ?? `Quiz #${attempt.quiz_id}`

      return [
        attempt.id,
        attempt.quiz_id,
        quizName,
        attempt.started_at,
        attempt.completed_at ?? "",
        attempt.time_spent_seconds ?? "",
        score,
        total,
        percentage,
        passingScore,
        isPassing,
        quizFilterId ?? "",
        passFilter,
        dateRangeFilter,
        dateRangeStartIso,
        dateRangeEndIso
      ]
        .map((value) => buildCsvCell(value))
        .join(",")
    })

    const csv = [headers.join(","), ...lines].join("\n")
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement("a")
    const quizSegment = quizFilterId != null ? `quiz-${quizFilterId}` : "all-quizzes"
    const dateSegment = dateRangeFilter === "all" ? "all-dates" : dateRangeFilter
    link.href = url
    link.download = `quiz-results-${quizSegment}-${dateSegment}-${fileDate}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  }

  const formatAnswerValue = (
    value: AnswerValue | null | undefined,
    question?: QuestionPublic
  ) => {
    if (value === null || value === undefined) {
      return t("option:quiz.noAnswer", { defaultValue: "No answer" })
    }
    if (question?.question_type === "multiple_choice") {
      const index = Number(value)
      if (!Number.isNaN(index)) {
        return question.options?.[index] ?? String(value)
      }
      return String(value)
    }
    if (question?.question_type === "true_false") {
      const normalized = String(value).trim().toLowerCase()
      if (normalized === "true") return t("option:quiz.true", { defaultValue: "True" })
      if (normalized === "false") return t("option:quiz.false", { defaultValue: "False" })
    }
    return String(value)
  }

  const detailRows = React.useMemo(() => {
    if (!selectedAttemptDetails) return []

    const questions = selectedAttemptDetails.questions ?? []
    const answers = selectedAttemptDetails.answers ?? []
    const answerMap = new Map<number, QuizAnswer>(answers.map((answer) => [answer.question_id, answer]))

    if (questions.length > 0) {
      return questions.map((question, index) => {
        const answer = answerMap.get(question.id)
        return {
          key: `q-${question.id}`,
          order: index + 1,
          questionText: question.question_text || `Question #${question.id}`,
          question,
          answer
        }
      })
    }

    return answers.map((answer, index) => ({
      key: `a-${answer.question_id}-${index}`,
      order: index + 1,
      questionText: t("option:quiz.questionFallbackLabel", {
        defaultValue: "Question #{{id}}",
        id: answer.question_id
      }),
      question: undefined,
      answer
    }))
  }, [selectedAttemptDetails, t])

  const renderAttemptDetailsModal = () => (
    <Modal
      title={t("option:quiz.attemptDetails", { defaultValue: "Attempt Details" })}
      open={selectedAttemptId != null}
      onCancel={() => setSelectedAttemptId(null)}
      footer={(
        <Button onClick={() => setSelectedAttemptId(null)}>
          {t("common:close", { defaultValue: "Close" })}
        </Button>
      )}
      width={920}
      destroyOnHidden
    >
      {selectedAttemptLoading || selectedAttemptFetching ? (
        <div className="flex justify-center py-12">
          <Spin size="large" />
        </div>
      ) : !selectedAttemptDetails ? (
        <Empty
          description={t("option:quiz.attemptDetailsUnavailable", {
            defaultValue: "Attempt details are unavailable."
          })}
        />
      ) : (
        <div className="space-y-4">
          <Descriptions size="small" bordered column={1}>
            <Descriptions.Item label={t("option:quiz.quiz", { defaultValue: "Quiz" })}>
              {quizMap.get(selectedAttemptDetails.quiz_id)?.name ?? `Quiz #${selectedAttemptDetails.quiz_id}`}
            </Descriptions.Item>
            <Descriptions.Item label={t("option:quiz.started", { defaultValue: "Started" })}>
              {formatDate(selectedAttemptDetails.started_at)}
            </Descriptions.Item>
            <Descriptions.Item label={t("option:quiz.completed", { defaultValue: "Completed" })}>
              {selectedAttemptDetails.completed_at
                ? formatDate(selectedAttemptDetails.completed_at)
                : t("option:quiz.inProgress", { defaultValue: "In progress" })}
            </Descriptions.Item>
            <Descriptions.Item label={t("option:quiz.timeSpent", { defaultValue: "Time Spent" })}>
              {selectedAttemptDetails.time_spent_seconds != null
                ? formatTime(selectedAttemptDetails.time_spent_seconds)
                : t("option:quiz.notAvailable", { defaultValue: "Not available" })}
            </Descriptions.Item>
          </Descriptions>

          <List
            dataSource={detailRows}
            locale={{
              emptyText: t("option:quiz.noAnswersSubmitted", {
                defaultValue: "No answer breakdown available."
              })
            }}
            renderItem={(entry) => {
              const wasAnswered = entry.answer != null
              const isCorrect = Boolean(entry.answer?.is_correct)

              return (
                <List.Item>
                  <div className="w-full space-y-2">
                    <div className="flex items-start justify-between gap-3">
                      <div className="font-medium">
                        {entry.order}. {entry.questionText}
                      </div>
                      {!wasAnswered ? (
                        <Tag>{t("option:quiz.unanswered", { defaultValue: "Unanswered" })}</Tag>
                      ) : (
                        <Tag
                          color={isCorrect ? "success" : "error"}
                          icon={isCorrect ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
                        >
                          {isCorrect
                            ? t("option:quiz.correct", { defaultValue: "Correct" })
                            : t("option:quiz.incorrect", { defaultValue: "Incorrect" })}
                        </Tag>
                      )}
                    </div>

                    <div className="text-sm text-text-muted">
                      {t("option:quiz.yourAnswer", { defaultValue: "Your answer" })}:{" "}
                      <span className="font-medium">
                        {formatAnswerValue(entry.answer?.user_answer, entry.question)}
                      </span>
                    </div>

                    <div className="text-sm text-text-muted">
                      {t("option:quiz.correctAnswerLabel", { defaultValue: "Correct answer" })}:{" "}
                      <span className="font-medium">
                        {formatAnswerValue(entry.answer?.correct_answer, entry.question)}
                      </span>
                    </div>

                    {entry.answer?.explanation && (
                      <Typography.Paragraph className="text-sm text-text-subtle mb-0">
                        {entry.answer.explanation}
                      </Typography.Paragraph>
                    )}
                  </div>
                </List.Item>
              )
            }}
          />
        </div>
      )}
    </Modal>
  )

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spin size="large" />
      </div>
    )
  }

  if (attempts.length === 0 && !hasActiveFilters) {
    return (
      <Empty
        description={
          <div className="space-y-2">
            <p className="text-text-muted">
              {t("option:quiz.noAttempts", { defaultValue: "No quiz attempts yet" })}
            </p>
            <p className="text-sm text-text-subtle">
              {t("option:quiz.noAttemptsHint", {
                defaultValue: "Complete a quiz to see your results here"
              })}
            </p>
          </div>
        }
      />
    )
  }

  return (
    <div className="space-y-6">
      {renderAttemptDetailsModal()}
      {/* Stats summary */}
      {stats && (
        <Card size="small">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Statistic
              title={t("option:quiz.totalAttempts", { defaultValue: "Total Attempts" })}
              value={stats.totalAttempts}
              prefix={<TrophyOutlined />}
            />
            <Statistic
              title={t("option:quiz.avgScore", { defaultValue: "Average Score" })}
              value={stats.avgScore}
              suffix="%"
              valueStyle={{
                color:
                  stats.avgScore >= 70
                    ? "var(--color-success)"
                    : stats.avgScore >= 50
                      ? "var(--color-warn)"
                      : "var(--color-danger)"
              }}
            />
            <Statistic
              title={t("option:quiz.avgTime", { defaultValue: "Average Time" })}
              value={formatTime(stats.avgTime)}
              prefix={<ClockCircleOutlined />}
            />
            <Statistic
              title={t("option:quiz.uniqueQuizzes", { defaultValue: "Quizzes Taken" })}
              value={stats.uniqueQuizzes}
            />
          </div>
        </Card>
      )}

      <Card size="small" title={t("option:quiz.scoreTrend", { defaultValue: "Score Trend" })}>
        {scoreTrendPolylinePoints ? (
          <div className="space-y-4">
            <div className="overflow-x-auto">
              <svg
                viewBox="0 0 360 84"
                role="img"
                aria-label={t("option:quiz.scoreTrendAria", {
                  defaultValue: "Score percentage trend over recent attempts"
                })}
                className="w-full min-w-[280px] h-24"
              >
                <line x1="8" y1="76" x2="352" y2="76" stroke="var(--color-border)" strokeWidth="1" />
                <polyline
                  fill="none"
                  stroke="var(--color-primary)"
                  strokeWidth="2"
                  points={scoreTrendPolylinePoints}
                />
              </svg>
            </div>
            <div className="grid gap-2">
              {scoreDistribution.map((bucket) => (
                <div key={bucket.label} className="flex items-center gap-3">
                  <span className="w-16 text-xs text-text-muted">{bucket.label}</span>
                  <div className="h-2 flex-1 rounded bg-surface2 overflow-hidden">
                    <div
                      className="h-full bg-primary"
                      style={{ width: `${(bucket.count / scoreDistributionMaxCount) * 100}%` }}
                    />
                  </div>
                  <span className="w-8 text-right text-xs text-text-subtle">{bucket.count}</span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <Text type="secondary">
            {t("option:quiz.scoreTrendNotEnoughData", {
              defaultValue: "Complete at least two attempts to see a trend."
            })}
          </Text>
        )}
      </Card>

      {/* Attempt history */}
      <div>
        <h3 className="text-lg font-medium mb-4">
          {t("option:quiz.attemptHistory", { defaultValue: "Attempt History" })}
        </h3>

        <div className="mb-4 flex flex-wrap items-center gap-3">
          <Select<number | "all">
            value={quizFilterId ?? "all"}
            onChange={(next) => {
              setQuizFilterId(next === "all" ? null : Number(next))
              setPage(1)
            }}
            style={{ minWidth: 220 }}
            options={[
              {
                value: "all",
                label: t("option:quiz.filterAllQuizzes", { defaultValue: "All quizzes" })
              },
              ...quizzes.map((quiz) => ({
                value: quiz.id,
                label: quiz.name
              }))
            ]}
          />

          <Select<PassFilterKey>
            value={passFilter}
            onChange={(next) => {
              setPassFilter(next)
              setPage(1)
            }}
            style={{ minWidth: 170 }}
            options={[
              {
                value: "all",
                label: t("option:quiz.filterAllResults", { defaultValue: "All results" })
              },
              {
                value: "pass",
                label: t("option:quiz.filterPassingOnly", { defaultValue: "Passing only" })
              },
              {
                value: "fail",
                label: t("option:quiz.filterFailingOnly", { defaultValue: "Failing only" })
              }
            ]}
          />

          <Select<DateRangeFilterKey>
            value={dateRangeFilter}
            onChange={(next) => {
              setDateRangeFilter(next)
              setPage(1)
            }}
            style={{ minWidth: 180 }}
            options={[
              {
                value: "all",
                label: t("option:quiz.filterAllDates", { defaultValue: "All dates" })
              },
              {
                value: "7d",
                label: t("option:quiz.filterLast7Days", { defaultValue: "Last 7 days" })
              },
              {
                value: "30d",
                label: t("option:quiz.filterLast30Days", { defaultValue: "Last 30 days" })
              },
              {
                value: "90d",
                label: t("option:quiz.filterLast90Days", { defaultValue: "Last 90 days" })
              }
            ]}
          />

          <Button onClick={resetFilters}>
            {t("common:reset", { defaultValue: "Reset" })}
          </Button>
          <Button onClick={exportFilteredAttemptsCsv} disabled={filteredAttempts.length === 0}>
            {t("option:quiz.exportCsv", { defaultValue: "Export CSV" })}
          </Button>
        </div>

        <List
          dataSource={paginatedAttempts}
          locale={{
            emptyText: t("option:quiz.noAttemptsMatchFilters", {
              defaultValue: "No attempts match the selected filters."
            })
          }}
          pagination={{
            current: page,
            pageSize,
            total: totalFilteredAttempts,
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
          renderItem={(attempt) => {
            const quizMeta = quizMap.get(attempt.quiz_id)
            const quizName = quizMeta?.name ?? `Quiz #${attempt.quiz_id}`
            const score = attempt.score ?? 0
            const total = attempt.total_possible
            const percentage = total > 0 ? Math.round((score / total) * 100) : 0
            const passingScore = getPassingScoreForQuiz(attempt.quiz_id)
            const isPassing = percentage >= passingScore

            return (
              <List.Item>
                <div className="w-full">
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <Text strong>{quizName}</Text>
                      <div className="text-sm text-text-subtle">
                        {attempt.completed_at
                          ? formatDate(attempt.completed_at)
                          : t("option:quiz.inProgress", { defaultValue: "In progress" })}
                      </div>
                    </div>
                    <div className="text-right">
                      {attempt.completed_at ? (
                        <div className="space-y-1">
                          <Tag
                            color={isPassing ? "success" : "error"}
                            icon={isPassing ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
                          >
                            {score}/{total} ({percentage}%)
                          </Tag>
                          <div>
                            <Button
                              type="link"
                              size="small"
                              icon={<EyeOutlined />}
                              onClick={() => setSelectedAttemptId(attempt.id)}
                            >
                              {t("option:quiz.viewDetails", { defaultValue: "View Details" })}
                            </Button>
                            {onRetakeQuiz && (
                              <Button
                                type="link"
                                size="small"
                                icon={<RedoOutlined />}
                                onClick={() => onRetakeQuiz(attempt.quiz_id)}
                              >
                                {t("option:quiz.retake", { defaultValue: "Retake" })}
                              </Button>
                            )}
                          </div>
                        </div>
                      ) : (
                        <Tag color="processing">
                          {t("option:quiz.incomplete", { defaultValue: "Incomplete" })}
                        </Tag>
                      )}
                    </div>
                  </div>

                  {attempt.completed_at && (
                    <div className="flex items-center gap-4">
                      <Progress
                        percent={percentage}
                        size="small"
                        aria-label={t("option:quiz.progressAria", {
                          defaultValue: "Quiz completion progress"
                        })}
                        strokeColor={
                          isPassing
                            ? "var(--color-success)"
                            : percentage >= 50
                              ? "var(--color-warn)"
                              : "var(--color-danger)"
                        }
                        className="flex-1"
                      />
                      {attempt.time_spent_seconds && (
                        <Text type="secondary" className="text-sm whitespace-nowrap">
                          <ClockCircleOutlined className="mr-1" />
                          {formatTime(attempt.time_spent_seconds)}
                        </Text>
                      )}
                    </div>
                  )}
                </div>
              </List.Item>
            )
          }}
        />
      </div>
    </div>
  )
}

export default ResultsTab
