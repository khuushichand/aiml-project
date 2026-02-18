import React from "react"
import { Tabs } from "antd"
import { useTranslation } from "react-i18next"
import { TakeQuizTab, GenerateTab, CreateTab, ManageTab, ResultsTab } from "./tabs"
import type { TakeTabNavigationIntent } from "./navigation"

/**
 * QuizPlayground contains all the tabs and core quiz logic.
 * Connection state is handled by QuizWorkspace.
 */
export const QuizPlayground: React.FC = () => {
  const { t } = useTranslation(["option", "common"])
  const [activeTab, setActiveTab] = React.useState<string>("take")
  const [takeTabIntent, setTakeTabIntent] = React.useState<TakeTabNavigationIntent | null>(null)

  const navigateToTake = React.useCallback((intent?: TakeTabNavigationIntent) => {
    setTakeTabIntent({
      startQuizId: intent?.startQuizId ?? null,
      highlightQuizId: intent?.highlightQuizId ?? intent?.startQuizId ?? null,
      sourceTab: intent?.sourceTab ?? null,
      attemptId: intent?.attemptId ?? null
    })
    setActiveTab("take")
  }, [])

  return (
    <div className="mx-auto max-w-6xl p-4">
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: "take",
            label: t("option:quiz.take", { defaultValue: "Take Quiz" }),
            children: (
              <TakeQuizTab
                startQuizId={takeTabIntent?.startQuizId ?? null}
                highlightQuizId={takeTabIntent?.highlightQuizId ?? null}
                navigationSource={takeTabIntent?.sourceTab ?? null}
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
                onNavigateToGenerate={() => setActiveTab("generate")}
                onNavigateToCreate={() => setActiveTab("create")}
              />
            )
          },
          {
            key: "generate",
            label: t("option:quiz.generate", { defaultValue: "Generate" }),
            children: (
              <GenerateTab
                onNavigateToTake={(intent) => navigateToTake(intent)}
              />
            )
          },
          {
            key: "create",
            label: t("option:quiz.create", { defaultValue: "Create" }),
            children: (
              <CreateTab
                onNavigateToTake={(intent) => navigateToTake(intent)}
              />
            )
          },
          {
            key: "manage",
            label: t("option:quiz.manage", { defaultValue: "Manage" }),
            children: (
              <ManageTab
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
            label: t("option:quiz.results", { defaultValue: "Results" }),
            children: (
              <ResultsTab
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
