import React from "react"
import { useTranslation } from "react-i18next"
import { Sparkles } from "lucide-react"
import type { DocumentType } from "../types"

interface SuggestedQuestion {
  key: string
  label: string
}

interface SuggestedQuestionsProps {
  documentType: DocumentType | null
  variant?: "research" | "general"
  onQuestionClick: (question: string) => void
  disabled?: boolean
}

/**
 * Displays suggested questions as clickable chips based on document type.
 * Research papers get academic-focused questions, while general documents
 * get broader analysis questions.
 */
export const SuggestedQuestions: React.FC<SuggestedQuestionsProps> = ({
  documentType,
  variant,
  onQuestionClick,
  disabled = false
}) => {
  const { t } = useTranslation(["option", "common"])

  // Questions tailored to document type
  const questions: SuggestedQuestion[] = React.useMemo(() => {
    if (documentType === "epub") {
      // EPUB-specific questions (books, narratives)
      return [
        {
          key: "summarize",
          label: t(
            "option:documentWorkspace.questions.summarize",
            "Summarize this document"
          )
        },
        {
          key: "themes",
          label: t(
            "option:documentWorkspace.questions.themes",
            "What are the main themes?"
          )
        },
        {
          key: "keyPoints",
          label: t(
            "option:documentWorkspace.questions.keyPoints",
            "What are the key points?"
          )
        },
        {
          key: "audience",
          label: t(
            "option:documentWorkspace.questions.audience",
            "Who is the target audience?"
          )
        }
      ]
    }

    const useResearchQuestions = variant === "research"

    if (useResearchQuestions) {
      return [
        {
          key: "findings",
          label: t(
            "option:documentWorkspace.questions.findings",
            "Summarize the main findings"
          )
        },
        {
          key: "methods",
          label: t(
            "option:documentWorkspace.questions.methods",
            "What methods were used?"
          )
        },
        {
          key: "limitations",
          label: t(
            "option:documentWorkspace.questions.limitations",
            "What are the limitations?"
          )
        },
        {
          key: "actionItems",
          label: t(
            "option:documentWorkspace.questions.actionItems",
            "Extract action items"
          )
        }
      ]
    }

    return [
      {
        key: "summarize",
        label: t(
          "option:documentWorkspace.questions.summarize",
          "Summarize this document"
        )
      },
      {
        key: "keyPoints",
        label: t(
          "option:documentWorkspace.questions.keyPoints",
          "What are the key points?"
        )
      },
      {
        key: "actionItems",
        label: t(
          "option:documentWorkspace.questions.actionItems",
          "Extract action items"
        )
      }
    ]
  }, [documentType, t, variant])

  if (!documentType) {
    return null
  }

  return (
    <div className="px-3 py-4">
      <div className="mb-3 flex items-center gap-2 text-sm text-text-muted">
        <Sparkles className="h-4 w-4" />
        <span>
          {t(
            "option:documentWorkspace.suggestedQuestions",
            "Suggested questions"
          )}
        </span>
      </div>

      <div className="flex flex-wrap gap-2">
        {questions.map((question) => (
          <button
            key={question.key}
            type="button"
            onClick={() => onQuestionClick(question.label)}
            disabled={disabled}
            className={`
              rounded-full border border-border bg-surface px-3 py-1.5
              text-sm text-text transition-colors
              ${
                disabled
                  ? "cursor-not-allowed opacity-50"
                  : "hover:border-primary hover:bg-surface2"
              }
            `}
          >
            {question.label}
          </button>
        ))}
      </div>
    </div>
  )
}

export default SuggestedQuestions
