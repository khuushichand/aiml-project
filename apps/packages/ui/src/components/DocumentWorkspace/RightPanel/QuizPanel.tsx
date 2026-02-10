import React, { useState, useCallback } from "react"
import { useTranslation } from "react-i18next"
import {
  Empty,
  Spin,
  Button,
  Segmented,
  InputNumber,
  Collapse,
  Radio,
  Space,
  Tag,
  message
} from "antd"
import {
  HelpCircle,
  Sparkles,
  Check,
  X,
  RotateCcw,
  Download,
  ChevronRight,
  ChevronDown
} from "lucide-react"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"
import {
  useDocumentQuiz,
  QUESTION_TYPE_INFO,
  DIFFICULTY_INFO,
  type QuestionType,
  type DifficultyLevel,
  type QuizQuestion
} from "@/hooks/document-workspace/useDocumentQuiz"

/**
 * Individual question display with answer reveal
 */
const QuestionCard: React.FC<{
  question: QuizQuestion
  index: number
}> = ({ question, index }) => {
  const { t } = useTranslation(["option", "common"])
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null)
  const [showAnswer, setShowAnswer] = useState(false)

  const isCorrect = selectedAnswer === question.correctAnswer
  const hasAnswered = selectedAnswer !== null

  const handleCheckAnswer = () => {
    setShowAnswer(true)
  }

  const handleReset = () => {
    setSelectedAnswer(null)
    setShowAnswer(false)
  }

  return (
    <div className="rounded-lg border border-border p-4">
      {/* Question header */}
      <div className="mb-3 flex items-start gap-2">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
          {index + 1}
        </span>
        <p className="text-sm font-medium leading-relaxed">{question.question}</p>
      </div>

      {/* Options for multiple choice */}
      {question.options && question.options.length > 0 && (
        <div className="mb-3 space-y-2 pl-8">
          <Radio.Group
            value={selectedAnswer}
            onChange={(e) => setSelectedAnswer(e.target.value)}
            disabled={showAnswer}
            className="w-full"
          >
            <Space direction="vertical" className="w-full">
              {question.options.map((option, i) => {
                const isThisCorrect = option === question.correctAnswer
                const isSelected = selectedAnswer === option

                let className = "w-full rounded-lg border p-2.5 transition-colors"
                if (showAnswer) {
                  if (isThisCorrect) {
                    className += " border-success bg-success/10"
                  } else if (isSelected && !isThisCorrect) {
                    className += " border-danger bg-danger/10"
                  } else {
                    className += " border-border"
                  }
                } else {
                  className += isSelected
                    ? " border-primary bg-primary/5"
                    : " border-border hover:border-primary/50"
                }

                return (
                  <Radio
                    key={i}
                    value={option}
                    className={className}
                  >
                    <span className="text-sm">{option}</span>
                    {showAnswer && isThisCorrect && (
                      <Check className="ml-2 inline h-4 w-4 text-success" />
                    )}
                    {showAnswer && isSelected && !isThisCorrect && (
                      <X className="ml-2 inline h-4 w-4 text-danger" />
                    )}
                  </Radio>
                )
              })}
            </Space>
          </Radio.Group>
        </div>
      )}

      {/* For non-multiple choice, show answer directly */}
      {(!question.options || question.options.length === 0) && showAnswer && (
        <div className="mb-3 rounded-lg border border-success bg-success/10 p-3 pl-8">
          <p className="text-sm">
            <span className="font-medium">{t("option:documentWorkspace.answer", "Answer:")}</span>{" "}
            {question.correctAnswer}
          </p>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between pl-8">
        {!showAnswer ? (
          <Button
            size="small"
            type="primary"
            onClick={handleCheckAnswer}
            disabled={!hasAnswered && question.options && question.options.length > 0}
          >
            {t("option:documentWorkspace.checkAnswer", "Check Answer")}
          </Button>
        ) : (
          <Button
            size="small"
            icon={<RotateCcw className="h-3.5 w-3.5" />}
            onClick={handleReset}
          >
            {t("option:documentWorkspace.tryAgain", "Try Again")}
          </Button>
        )}

        {showAnswer && hasAnswered && (
          <Tag color={isCorrect ? "success" : "error"}>
            {isCorrect
              ? t("option:documentWorkspace.correct", "Correct!")
              : t("option:documentWorkspace.incorrect", "Incorrect")}
          </Tag>
        )}
      </div>

      {/* Explanation */}
      {showAnswer && question.explanation && (
        <div className="mt-3 rounded-lg bg-surface-hover p-3 pl-8">
          <p className="text-xs text-text-secondary">
            <span className="font-medium">{t("option:documentWorkspace.explanation", "Explanation:")}</span>{" "}
            {question.explanation}
          </p>
        </div>
      )}
    </div>
  )
}

/**
 * QuizPanel - Generate and take quizzes from document content.
 *
 * Features:
 * - Configure question count, type, and difficulty
 * - Interactive quiz taking with answer checking
 * - Export quiz as JSON
 */
export const QuizPanel: React.FC = () => {
  const { t } = useTranslation(["option", "common"])
  const activeDocumentId = useDocumentWorkspaceStore((s) => s.activeDocumentId)

  // Quiz config state
  const [numQuestions, setNumQuestions] = useState(5)
  const [questionType, setQuestionType] = useState<QuestionType>("multiple_choice")
  const [difficulty, setDifficulty] = useState<DifficultyLevel>("medium")
  const [showConfig, setShowConfig] = useState(true)

  const { quiz, isGenerating, error, generateQuiz, clearQuiz } = useDocumentQuiz(activeDocumentId)

  const handleGenerate = useCallback(() => {
    generateQuiz({
      numQuestions,
      questionType,
      difficulty
    })
    setShowConfig(false)
  }, [generateQuiz, numQuestions, questionType, difficulty])

  const handleNewQuiz = () => {
    clearQuiz()
    setShowConfig(true)
  }

  const handleExport = () => {
    if (!quiz) return

    const content = JSON.stringify(quiz, null, 2)
    const blob = new Blob([content], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = `quiz_${quiz.quizId}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)

    message.success(t("option:documentWorkspace.quizExported", "Quiz exported"))
  }

  // No document selected
  if (!activeDocumentId) {
    return (
      <div className="flex h-full items-center justify-center p-4">
        <Empty
          image={<HelpCircle className="h-12 w-12 text-muted mx-auto mb-2" />}
          description={t(
            "option:documentWorkspace.noDocumentForQuiz",
            "Open a document to generate a quiz"
          )}
        />
      </div>
    )
  }

  // Loading state
  if (isGenerating) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 p-4">
        <Spin size="large" />
        <p className="text-sm text-text-secondary">
          {t("option:documentWorkspace.generatingQuiz", "Generating quiz...")}
        </p>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-4 text-center">
        <X className="h-10 w-10 text-danger" />
        <p className="text-sm text-danger">
          {error instanceof Error ? error.message : t("option:documentWorkspace.quizError", "Failed to generate quiz")}
        </p>
        <Button onClick={handleNewQuiz}>
          {t("common:tryAgain", "Try Again")}
        </Button>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {/* Configuration or quiz display */}
      {!quiz ? (
        // Config panel
        <div className="flex-1 overflow-y-auto p-4">
          <div className="mb-4 flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <h3 className="font-medium">
              {t("option:documentWorkspace.generateQuiz", "Generate Quiz")}
            </h3>
          </div>

          <div className="space-y-4">
            {/* Number of questions */}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-text-secondary">
                {t("option:documentWorkspace.numQuestions", "Number of Questions")}
              </label>
              <InputNumber
                min={1}
                max={20}
                value={numQuestions}
                onChange={(v) => setNumQuestions(v || 5)}
                className="w-full"
              />
            </div>

            {/* Question type */}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-text-secondary">
                {t("option:documentWorkspace.questionType", "Question Type")}
              </label>
              <Segmented
                value={questionType}
                onChange={(v) => setQuestionType(v as QuestionType)}
                options={Object.entries(QUESTION_TYPE_INFO).map(([key, info]) => ({
                  value: key,
                  label: info.label
                }))}
                block
                size="small"
              />
              <p className="mt-1 text-[11px] text-text-muted">
                {QUESTION_TYPE_INFO[questionType].description}
              </p>
            </div>

            {/* Difficulty */}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-text-secondary">
                {t("option:documentWorkspace.difficulty", "Difficulty")}
              </label>
              <Segmented
                value={difficulty}
                onChange={(v) => setDifficulty(v as DifficultyLevel)}
                options={Object.entries(DIFFICULTY_INFO).map(([key, info]) => ({
                  value: key,
                  label: info.label
                }))}
                block
                size="small"
              />
              <p className="mt-1 text-[11px] text-text-muted">
                {DIFFICULTY_INFO[difficulty].description}
              </p>
            </div>

            {/* Generate button */}
            <Button
              type="primary"
              icon={<Sparkles className="h-4 w-4" />}
              onClick={handleGenerate}
              className="w-full"
            >
              {t("option:documentWorkspace.generate", "Generate")}
            </Button>
          </div>
        </div>
      ) : (
        // Quiz display
        <>
          {/* Header */}
          <div className="flex items-center justify-between border-b border-border p-3">
            <div>
              <p className="text-sm font-medium">
                {quiz.questions.length} {t("option:documentWorkspace.questions", "questions")}
              </p>
              <p className="text-xs text-text-muted">
                {t("option:documentWorkspace.generatedAt", "Generated")} {new Date(quiz.generatedAt).toLocaleString()}
              </p>
            </div>
            <div className="flex items-center gap-1">
              <Button
                size="small"
                type="text"
                icon={<Download className="h-3.5 w-3.5" />}
                onClick={handleExport}
                title={t("option:documentWorkspace.exportQuiz", "Export Quiz")}
              />
              <Button
                size="small"
                icon={<RotateCcw className="h-3.5 w-3.5" />}
                onClick={handleNewQuiz}
              >
                {t("option:documentWorkspace.newQuiz", "New Quiz")}
              </Button>
            </div>
          </div>

          {/* Questions */}
          <div className="flex-1 overflow-y-auto p-3">
            <div className="space-y-4">
              {quiz.questions.map((q, i) => (
                <QuestionCard key={i} question={q} index={i} />
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default QuizPanel
