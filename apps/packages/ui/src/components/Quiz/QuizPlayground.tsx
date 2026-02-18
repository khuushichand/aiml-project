import React from "react"
import { Button, Tabs } from "antd"
import { useTranslation } from "react-i18next"
import { TakeQuizTab, GenerateTab, CreateTab, ManageTab, ResultsTab } from "./tabs"
import type { TakeTabNavigationIntent } from "./navigation"
import { RESULTS_FILTER_PREFS_KEY, TAKE_QUIZ_LIST_PREFS_KEY } from "./stateKeys"
import { useAttemptsQuery, useQuizzesQuery } from "./hooks"

type QuizTabKey = "take" | "generate" | "create" | "manage" | "results"

const INITIAL_TAB_RESET_VERSION: Record<QuizTabKey, number> = {
  take: 0,
  generate: 0,
  create: 0,
  manage: 0,
  results: 0
}

/**
 * QuizPlayground contains all the tabs and core quiz logic.
 * Connection state is handled by QuizWorkspace.
 */
export const QuizPlayground: React.FC = () => {
  const { t } = useTranslation(["option", "common"])
  const [activeTab, setActiveTab] = React.useState<QuizTabKey>("take")
  const [createTabDirty, setCreateTabDirty] = React.useState(false)
  const [takeTabIntent, setTakeTabIntent] = React.useState<TakeTabNavigationIntent | null>(null)
  const [globalSearchQuery, setGlobalSearchQuery] = React.useState("")
  const [takeSearchIntent, setTakeSearchIntent] = React.useState<{ query: string; token: number } | null>(null)
  const [manageSearchIntent, setManageSearchIntent] = React.useState<{ query: string; token: number } | null>(null)
  const [tabResetVersion, setTabResetVersion] = React.useState<Record<QuizTabKey, number>>(
    INITIAL_TAB_RESET_VERSION
  )
  const searchTokenCounter = React.useRef(0)

  const { data: quizCounts } = useQuizzesQuery({ limit: 1, offset: 0 })
  const { data: attemptCounts } = useAttemptsQuery({ limit: 1, offset: 0 })
  const totalQuizzes = quizCounts?.count ?? 0
  const totalAttempts = attemptCounts?.count ?? 0

  const renderTabLabel = React.useCallback((label: string, count?: number) => {
    if (typeof count !== "number" || count < 0) return label
    return (
      <span className="inline-flex items-center gap-1">
        <span>{label}</span>
        <span aria-hidden className="rounded bg-surface2 px-1.5 py-0.5 text-xs text-text">
          {count}
        </span>
      </span>
    )
  }, [])

  const navigateToTake = React.useCallback((intent?: TakeTabNavigationIntent) => {
    setTakeTabIntent({
      startQuizId: intent?.startQuizId ?? null,
      highlightQuizId: intent?.highlightQuizId ?? intent?.startQuizId ?? null,
      sourceTab: intent?.sourceTab ?? null,
      attemptId: intent?.attemptId ?? null
    })
    setActiveTab("take")
  }, [])

  const handleResetActiveTab = React.useCallback(() => {
    if (typeof window !== "undefined") {
      if (activeTab === "take") {
        window.sessionStorage.removeItem(TAKE_QUIZ_LIST_PREFS_KEY)
      }
      if (activeTab === "results") {
        window.sessionStorage.removeItem(RESULTS_FILTER_PREFS_KEY)
      }
    }
    if (activeTab === "take") {
      setTakeTabIntent(null)
    }
    if (activeTab === "create") {
      setCreateTabDirty(false)
    }
    setTabResetVersion((current) => ({
      ...current,
      [activeTab]: current[activeTab] + 1
    }))
  }, [activeTab])

  const handleTabChange = React.useCallback((nextTabRaw: string) => {
    const nextTab = nextTabRaw as QuizTabKey
    if (activeTab === "create" && nextTab !== "create" && createTabDirty) {
      const shouldLeave = window.confirm(
        t("option:quiz.unsavedCreateConfirm", {
          defaultValue: "You have unsaved quiz changes. Leave Create tab?"
        })
      )
      if (!shouldLeave) {
        return
      }
      setCreateTabDirty(false)
    }
    setActiveTab(nextTab)
  }, [activeTab, createTabDirty, t])

  const handleApplyGlobalSearch = React.useCallback(() => {
    const nextQuery = globalSearchQuery.trim()
    searchTokenCounter.current += 1
    const token = searchTokenCounter.current

    if (activeTab === "manage") {
      setManageSearchIntent({ query: nextQuery, token })
      return
    }

    setTakeSearchIntent({ query: nextQuery, token })
    setActiveTab("take")
  }, [activeTab, globalSearchQuery])

  return (
    <div className="mx-auto max-w-6xl p-4">
      <div className="mb-3 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div className="flex w-full gap-2 md:max-w-xl">
          <input
            type="text"
            className="w-full rounded border border-border bg-background px-3 py-1.5 text-sm"
            placeholder={t("option:quiz.globalSearchPlaceholder", { defaultValue: "Search quizzes across tabs..." })}
            value={globalSearchQuery}
            onChange={(event) => setGlobalSearchQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                handleApplyGlobalSearch()
              }
            }}
            data-testid="quiz-global-search-input"
          />
          <Button onClick={handleApplyGlobalSearch} size="small" data-testid="quiz-global-search-apply">
            {t("common:search", { defaultValue: "Search" })}
          </Button>
        </div>
        <Button
          onClick={handleResetActiveTab}
          size="small"
          data-testid="quiz-reset-current-tab"
        >
          {t("option:quiz.resetCurrentTab", { defaultValue: "Reset Current Tab" })}
        </Button>
      </div>
      <Tabs
        activeKey={activeTab}
        destroyInactiveTabPane={false}
        onChange={handleTabChange}
        items={[
          {
            key: "take",
            label: renderTabLabel(t("option:quiz.take", { defaultValue: "Take Quiz" }), totalQuizzes),
            children: (
              <TakeQuizTab
                key={`take-${tabResetVersion.take}`}
                startQuizId={takeTabIntent?.startQuizId ?? null}
                highlightQuizId={takeTabIntent?.highlightQuizId ?? null}
                navigationSource={takeTabIntent?.sourceTab ?? null}
                externalSearchQuery={takeSearchIntent?.query ?? null}
                externalSearchToken={takeSearchIntent?.token ?? null}
                onStartHandled={() =>
                  setTakeTabIntent((current) =>
                    current
                      ? {
                        ...current,
                        startQuizId: null
                      }
                      : current
                  )
                }
                onHighlightHandled={() =>
                  setTakeTabIntent((current) =>
                    current
                      ? {
                        ...current,
                        highlightQuizId: null,
                        sourceTab: null,
                        attemptId: null
                      }
                      : current
                  )
                }
                onExternalSearchHandled={() => {
                  setTakeSearchIntent(null)
                }}
                onNavigateToGenerate={() => setActiveTab("generate")}
                onNavigateToCreate={() => setActiveTab("create")}
              />
            )
          },
          {
            key: "generate",
            label: renderTabLabel(t("option:quiz.generate", { defaultValue: "Generate" })),
            children: (
              <GenerateTab
                key={`generate-${tabResetVersion.generate}`}
                onNavigateToTake={(intent) => navigateToTake(intent)}
              />
            )
          },
          {
            key: "create",
            label: renderTabLabel(t("option:quiz.create", { defaultValue: "Create" })),
            children: (
              <CreateTab
                key={`create-${tabResetVersion.create}`}
                onDirtyStateChange={setCreateTabDirty}
                onNavigateToTake={(intent) => navigateToTake(intent)}
              />
            )
          },
          {
            key: "manage",
            label: renderTabLabel(t("option:quiz.manage", { defaultValue: "Manage" }), totalQuizzes),
            children: (
              <ManageTab
                key={`manage-${tabResetVersion.manage}`}
                externalSearchQuery={manageSearchIntent?.query ?? null}
                externalSearchToken={manageSearchIntent?.token ?? null}
                onExternalSearchHandled={() => {
                  setManageSearchIntent(null)
                }}
                onNavigateToCreate={() => setActiveTab("create")}
                onNavigateToGenerate={() => setActiveTab("generate")}
                onStartQuiz={(quizId) => {
                  navigateToTake({
                    startQuizId: quizId,
                    highlightQuizId: quizId,
                    sourceTab: "manage"
                  })
                }}
              />
            )
          },
          {
            key: "results",
            label: renderTabLabel(t("option:quiz.results", { defaultValue: "Results" }), totalAttempts),
            children: (
              <ResultsTab
                key={`results-${tabResetVersion.results}`}
                onRetakeQuiz={(intent) => navigateToTake(intent)}
              />
            )
          }
        ]}
      />
    </div>
  )
}

export default QuizPlayground
