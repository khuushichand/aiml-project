import { useState, useEffect, useCallback } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { tldwClient } from "@/services/tldw"
import { saveQuizToHistory, getQuizHistory, updateQuizAnswers, type QuizHistoryEntry } from "./offlineQueue"

/**
 * Question type options
 */
export type QuestionType = "multiple_choice" | "true_false" | "short_answer" | "mixed"

/**
 * Difficulty level options
 */
export type DifficultyLevel = "easy" | "medium" | "hard"

/**
 * Quiz generation options
 */
export interface QuizGenerationOptions {
  numQuestions?: number
  questionType?: QuestionType
  difficulty?: DifficultyLevel
  llmProvider?: string
}

/**
 * A single quiz question
 */
export interface QuizQuestion {
  question: string
  options?: string[]
  correctAnswer: string
  explanation?: string
}

/**
 * Quiz response from API
 */
export interface QuizResponse {
  quizId: string
  mediaId: number
  questions: QuizQuestion[]
  generatedAt: string
}

/**
 * Default quiz generation options
 */
const DEFAULT_OPTIONS: Required<QuizGenerationOptions> = {
  numQuestions: 5,
  questionType: "multiple_choice",
  difficulty: "medium",
  llmProvider: "openai"
}

/**
 * Hook for generating quizzes from document content.
 *
 * Uses the Quiz API to generate questions based on document content.
 *
 * @param documentId - The document ID to generate quiz for
 * @returns Quiz generation utilities and state
 */
export function useDocumentQuiz(documentId: number | null) {
  const queryClient = useQueryClient()

  // Generate quiz mutation
  const generateMutation = useMutation({
    mutationFn: async (options: QuizGenerationOptions = {}): Promise<QuizResponse> => {
      if (!documentId) {
        throw new Error("No document selected")
      }

      const mergedOptions = { ...DEFAULT_OPTIONS, ...options }

      const response = await fetch("/api/v1/quizzes/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          media_id: documentId,
          num_questions: mergedOptions.numQuestions,
          question_type: mergedOptions.questionType,
          difficulty: mergedOptions.difficulty,
          llm_provider: mergedOptions.llmProvider
        })
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({}))
        throw new Error(error.detail || `Quiz generation failed: ${response.statusText}`)
      }

      const data = await response.json()

      // Normalize response to our interface
      return {
        quizId: data.quiz_id || `quiz_${Date.now()}`,
        mediaId: documentId,
        questions: (data.questions || []).map((q: any) => ({
          question: q.question,
          options: q.options,
          correctAnswer: q.correct_answer,
          explanation: q.explanation
        })),
        generatedAt: data.generated_at || new Date().toISOString()
      }
    },
    onSuccess: async (data) => {
      // Cache the generated quiz
      queryClient.setQueryData(["document-quiz", documentId], data)
      // Persist to IndexedDB and store the history entry ID
      if (documentId) {
        const historyId = await saveQuizToHistory({
          documentId,
          quiz: data,
          answers: {},
          createdAt: Date.now()
        })
        queryClient.setQueryData(["document-quiz-history-id", documentId], historyId)
      }
    }
  })

  // Fetch cached quiz (if any)
  const { data: cachedQuiz, isLoading: isCacheLoading } = useQuery({
    queryKey: ["document-quiz", documentId],
    queryFn: () => null, // We don't auto-fetch, just use cache
    enabled: false,
    staleTime: Infinity
  })

  const historyId = queryClient.getQueryData<number>(["document-quiz-history-id", documentId])

  const persistAnswer = useCallback(
    (answers: Record<number, string>, score?: number, completedAt?: number) => {
      if (historyId && historyId > 0) {
        updateQuizAnswers(historyId, answers, score, completedAt)
      }
    },
    [historyId]
  )

  return {
    // State
    quiz: generateMutation.data || cachedQuiz,
    isGenerating: generateMutation.isPending,
    error: generateMutation.error,
    historyId: historyId ?? null,

    // Actions
    generateQuiz: (options?: QuizGenerationOptions) => generateMutation.mutate(options),
    clearQuiz: () => {
      queryClient.removeQueries({ queryKey: ["document-quiz", documentId] })
      queryClient.removeQueries({ queryKey: ["document-quiz-history-id", documentId] })
    },
    loadQuiz: (quiz: QuizResponse, entryId?: number) => {
      generateMutation.reset()
      queryClient.setQueryData(["document-quiz", documentId], quiz)
      if (entryId) {
        queryClient.setQueryData(["document-quiz-history-id", documentId], entryId)
      }
    },
    persistAnswer,

    // Reset mutation state
    reset: generateMutation.reset
  }
}

/**
 * Display information for question types
 */
export const QUESTION_TYPE_INFO: Record<QuestionType, { label: string; description: string }> = {
  multiple_choice: {
    label: "Multiple Choice",
    description: "Questions with 4 options, one correct answer"
  },
  true_false: {
    label: "True/False",
    description: "Statement verification questions"
  },
  short_answer: {
    label: "Short Answer",
    description: "Open-ended questions requiring brief responses"
  },
  mixed: {
    label: "Mixed",
    description: "A variety of question types"
  }
}

/**
 * Display information for difficulty levels
 */
export const DIFFICULTY_INFO: Record<DifficultyLevel, { label: string; description: string }> = {
  easy: {
    label: "Easy",
    description: "Basic comprehension questions"
  },
  medium: {
    label: "Medium",
    description: "Questions requiring understanding and analysis"
  },
  hard: {
    label: "Hard",
    description: "Complex questions requiring synthesis"
  }
}

/**
 * Hook to load quiz history from IndexedDB.
 */
export function useQuizHistory(documentId: number | null) {
  const [history, setHistory] = useState<QuizHistoryEntry[]>([])
  const [isLoading, setIsLoading] = useState(false)

  const loadHistory = useCallback(async () => {
    if (!documentId) {
      setHistory([])
      return
    }
    setIsLoading(true)
    try {
      const entries = await getQuizHistory(documentId)
      setHistory(entries)
    } catch {
      setHistory([])
    } finally {
      setIsLoading(false)
    }
  }, [documentId])

  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  return { history, isLoading, refresh: loadHistory }
}

export default useDocumentQuiz
