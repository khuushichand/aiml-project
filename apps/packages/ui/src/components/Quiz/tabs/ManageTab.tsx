import React from "react"
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Divider,
  Empty,
  Form,
  Input,
  InputNumber,
  List,
  Modal,
  Popconfirm,
  Radio,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
  message
} from "antd"
import { useTranslation } from "react-i18next"
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  CopyOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  PlayCircleOutlined,
  QuestionCircleOutlined,
  SearchOutlined,
  UndoOutlined
} from "@ant-design/icons"
import {
  useCreateQuizMutation,
  useCreateQuestionMutation,
  useDeleteQuestionMutation,
  useDeleteQuizMutation,
  useQuestionsQuery,
  useQuizzesQuery,
  useUpdateQuestionMutation,
  useUpdateQuizMutation
} from "../hooks"
import { listQuestions } from "@/services/quizzes"
import type { AnswerValue, Question, QuestionType, Quiz } from "@/services/quizzes"

interface ManageTabProps {
  onNavigateToCreate: () => void
  onNavigateToGenerate: () => void
  onStartQuiz: (quizId: number) => void
  externalSearchQuery?: string | null
  externalSearchToken?: number | null
  onExternalSearchHandled?: () => void
}

type QuestionDraft = {
  id?: number
  question_type: QuestionType
  question_text: string
  options: string[]
  correct_answer: AnswerValue
  explanation?: string | null
  points: number
  order_index: number
}

type QuestionValidationErrors = {
  questionText?: string
  options?: string
}

const QUESTION_TEXT_ERROR_ID = "manage-question-text-error"
const QUESTION_OPTIONS_ERROR_ID = "manage-question-options-error"

export const ManageTab: React.FC<ManageTabProps> = ({
  onNavigateToCreate,
  onNavigateToGenerate,
  onStartQuiz,
  externalSearchQuery,
  externalSearchToken,
  onExternalSearchHandled
}) => {
  const { t } = useTranslation(["option", "common"])
  const [searchQuery, setSearchQuery] = React.useState("")
  const [messageApi, contextHolder] = message.useMessage()
  const [page, setPage] = React.useState(1)
  const [pageSize, setPageSize] = React.useState(10)
  const [editingQuiz, setEditingQuiz] = React.useState<Quiz | null>(null)
  const [editModalOpen, setEditModalOpen] = React.useState(false)
  const [questionModalOpen, setQuestionModalOpen] = React.useState(false)
  const [questionDraft, setQuestionDraft] = React.useState<QuestionDraft | null>(null)
  const [isNewQuestion, setIsNewQuestion] = React.useState(false)
  const [reorderPendingQuestionId, setReorderPendingQuestionId] = React.useState<number | null>(null)
  const [editForm] = Form.useForm()
  const [questionValidationErrors, setQuestionValidationErrors] = React.useState<QuestionValidationErrors>({})
  const editModalTriggerRef = React.useRef<HTMLElement | null>(null)
  const questionModalTriggerRef = React.useRef<HTMLElement | null>(null)
  const lastExternalSearchToken = React.useRef<number | null>(null)
  const searchInputRef = React.useRef<any>(null)

  // Undo deletion state
  const UNDO_GRACE_PERIOD = 8000 // 8 seconds
  const pendingQuizDeletion = React.useRef<{
    quiz: Quiz
    timeoutId: ReturnType<typeof setTimeout>
  } | null>(null)
  const pendingQuestionDeletion = React.useRef<{
    question: Question
    timeoutId: ReturnType<typeof setTimeout>
  } | null>(null)
  const [deletedQuizIds, setDeletedQuizIds] = React.useState<Set<number>>(new Set())
  const [deletedQuestionIds, setDeletedQuestionIds] = React.useState<Set<number>>(new Set())
  const [pendingQuizUndoName, setPendingQuizUndoName] = React.useState<string | null>(null)
  const [pendingQuestionUndoText, setPendingQuestionUndoText] = React.useState<string | null>(null)
  const [selectedQuizIds, setSelectedQuizIds] = React.useState<Set<number>>(new Set())
  const [bulkDeleteInFlight, setBulkDeleteInFlight] = React.useState(false)
  const [duplicateInFlightQuizId, setDuplicateInFlightQuizId] = React.useState<number | null>(null)

  // Cleanup pending deletions on unmount
  React.useEffect(() => {
    return () => {
      if (pendingQuizDeletion.current) {
        clearTimeout(pendingQuizDeletion.current.timeoutId)
      }
      if (pendingQuestionDeletion.current) {
        clearTimeout(pendingQuestionDeletion.current.timeoutId)
      }
    }
  }, [])

  React.useEffect(() => {
    setPage(1)
  }, [searchQuery])

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

  const offset = (page - 1) * pageSize
  const { data, isLoading, refetch } = useQuizzesQuery({
    q: searchQuery || undefined,
    limit: pageSize,
    offset
  })
  const createQuizMutation = useCreateQuizMutation()
  const deleteMutation = useDeleteQuizMutation()
  const updateQuizMutation = useUpdateQuizMutation()
  const createQuestionMutation = useCreateQuestionMutation()
  const updateQuestionMutation = useUpdateQuestionMutation()
  const deleteQuestionMutation = useDeleteQuestionMutation()

  const questionsQuery = useQuestionsQuery(
    editingQuiz?.id,
    {
      include_answers: true,
      limit: 200,
      offset: 0
    },
    { enabled: editModalOpen && !!editingQuiz }
  )

  const allQuizzes = data?.items ?? []
  const quizzes = allQuizzes.filter((q) => !deletedQuizIds.has(q.id))
  const total = data?.count ?? 0
  const allQuestions = (questionsQuery.data?.items ?? []) as Question[]
  const questions = allQuestions.filter((q) => !deletedQuestionIds.has(q.id))
  const questionTotal = questionsQuery.data?.count ?? 0
  const sortedQuestions = React.useMemo(
    () => [...questions].sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0)),
    [questions]
  )
  const reorderBusy = reorderPendingQuestionId != null || updateQuestionMutation.isPending

  React.useEffect(() => {
    setSelectedQuizIds((prev) => {
      const visibleIds = new Set(quizzes.map((quiz) => quiz.id))
      const next = new Set<number>()
      prev.forEach((id) => {
        if (visibleIds.has(id)) next.add(id)
      })
      return next
    })
  }, [quizzes])

  const questionTypeLabel = (questionType: QuestionType) => {
    if (questionType === "multiple_choice") {
      return t("option:quiz.multipleChoice", { defaultValue: "Multiple Choice" })
    }
    if (questionType === "true_false") {
      return t("option:quiz.trueFalse", { defaultValue: "True/False" })
    }
    return t("option:quiz.fillBlank", { defaultValue: "Fill in the Blank" })
  }

  const captureFocusTarget = (ref: React.MutableRefObject<HTMLElement | null>) => {
    const activeElement = document.activeElement
    ref.current = activeElement instanceof HTMLElement ? activeElement : null
  }

  const restoreFocusTarget = (ref: React.MutableRefObject<HTMLElement | null>) => {
    const element = ref.current
    if (!element) return
    window.setTimeout(() => {
      if (!element.isConnected) return
      if ("disabled" in element && (element as HTMLButtonElement).disabled) return
      element.focus()
    }, 0)
  }

  const handleUndoQuizDelete = () => {
    if (!pendingQuizDeletion.current) return
    clearTimeout(pendingQuizDeletion.current.timeoutId)
    const quiz = pendingQuizDeletion.current.quiz
    pendingQuizDeletion.current = null
    setPendingQuizUndoName(null)
    setDeletedQuizIds((prev) => {
      const next = new Set(prev)
      next.delete(quiz.id)
      return next
    })
    messageApi.success(
      t("option:quiz.undoSuccess", { defaultValue: "Deletion undone" })
    )
  }

  const executeQuizDelete = async (quiz: Quiz) => {
    try {
      await deleteMutation.mutateAsync({ quizId: quiz.id, version: quiz.version })
      pendingQuizDeletion.current = null
      setPendingQuizUndoName(null)
      setDeletedQuizIds((prev) => {
        const next = new Set(prev)
        next.delete(quiz.id)
        return next
      })
      refetch()
    } catch (error) {
      // Deletion failed, restore the quiz in UI
      setDeletedQuizIds((prev) => {
        const next = new Set(prev)
        next.delete(quiz.id)
        return next
      })
      pendingQuizDeletion.current = null
      setPendingQuizUndoName(null)
      messageApi.error(
        t("option:quiz.deleteError", { defaultValue: "Failed to delete quiz" })
      )
    }
  }

  const handleDelete = (quiz: Quiz) => {
    // Cancel any existing pending deletion
    if (pendingQuizDeletion.current) {
      clearTimeout(pendingQuizDeletion.current.timeoutId)
      // Execute the previous pending deletion immediately
      executeQuizDelete(pendingQuizDeletion.current.quiz)
    }

    // Optimistically hide the quiz from UI
    setDeletedQuizIds((prev) => new Set(prev).add(quiz.id))
    setPendingQuizUndoName(quiz.name)

    // Schedule actual deletion
    const timeoutId = setTimeout(() => {
      executeQuizDelete(quiz)
    }, UNDO_GRACE_PERIOD)

    pendingQuizDeletion.current = { quiz, timeoutId }
  }

  const toggleQuizSelection = (quizId: number, checked: boolean) => {
    setSelectedQuizIds((prev) => {
      const next = new Set(prev)
      if (checked) {
        next.add(quizId)
      } else {
        next.delete(quizId)
      }
      return next
    })
  }

  const clearQuizSelection = () => {
    setSelectedQuizIds(new Set())
  }

  const handleDuplicateQuiz = async (quiz: Quiz) => {
    setDuplicateInFlightQuizId(quiz.id)
    try {
      const response = await listQuestions(quiz.id, {
        include_answers: true,
        limit: 200,
        offset: 0
      })
      const sourceQuestions = (response.items as Question[]).slice()
      sourceQuestions.sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0))

      const duplicateQuiz = await createQuizMutation.mutateAsync({
        name: t("option:quiz.duplicateQuizName", {
          defaultValue: "{{name}} (Copy)",
          name: quiz.name
        }),
        description: quiz.description ?? undefined,
        workspace_tag: quiz.workspace_tag ?? undefined,
        media_id: quiz.media_id ?? undefined,
        time_limit_seconds: quiz.time_limit_seconds ?? undefined,
        passing_score: quiz.passing_score ?? undefined
      })

      const failedQuestionNumbers: number[] = []
      for (let i = 0; i < sourceQuestions.length; i++) {
        const sourceQuestion = sourceQuestions[i]
        try {
          await createQuestionMutation.mutateAsync({
            quizId: duplicateQuiz.id,
            question: {
              question_type: sourceQuestion.question_type,
              question_text: sourceQuestion.question_text,
              options:
                sourceQuestion.question_type === "multiple_choice"
                  ? (sourceQuestion.options ?? [])
                  : undefined,
              correct_answer: sourceQuestion.correct_answer,
              explanation: sourceQuestion.explanation ?? undefined,
              points: sourceQuestion.points,
              order_index: sourceQuestion.order_index
            }
          })
        } catch {
          failedQuestionNumbers.push(i + 1)
        }
      }

      if (failedQuestionNumbers.length > 0) {
        messageApi.warning(
          t("option:quiz.duplicatePartialFailure", {
            defaultValue:
              "Quiz duplicated, but failed to copy question(s): {{questions}}.",
            questions: failedQuestionNumbers.join(", ")
          })
        )
      } else {
        messageApi.success(
          t("option:quiz.duplicateSuccess", {
            defaultValue: "Quiz duplicated successfully."
          })
        )
      }
      refetch()
    } catch (error) {
      messageApi.error(
        t("option:quiz.duplicateError", {
          defaultValue: "Failed to duplicate quiz."
        })
      )
    } finally {
      setDuplicateInFlightQuizId(null)
    }
  }

  const executeBulkDelete = async () => {
    const selectedQuizzes = quizzes.filter((quiz) => selectedQuizIds.has(quiz.id))
    if (selectedQuizzes.length === 0) {
      return
    }

    setBulkDeleteInFlight(true)
    const failed: string[] = []
    let successCount = 0

    try {
      for (const quiz of selectedQuizzes) {
        try {
          await deleteMutation.mutateAsync({ quizId: quiz.id, version: quiz.version })
          successCount += 1
        } catch {
          failed.push(quiz.name)
        }
      }

      if (successCount > 0) {
        refetch()
      }

      if (failed.length === 0) {
        messageApi.success(
          t("option:quiz.bulkDeleteSuccess", {
            defaultValue: "Deleted {{count}} quiz(es).",
            count: successCount
          })
        )
      } else {
        messageApi.warning(
          t("option:quiz.bulkDeletePartialFailure", {
            defaultValue:
              "Deleted {{success}} quiz(es). Failed to delete: {{failed}}.",
            success: successCount,
            failed: failed.join(", ")
          })
        )
      }
    } finally {
      setBulkDeleteInFlight(false)
      if (failed.length === 0) {
        clearQuizSelection()
      } else {
        const failedSet = new Set(
          selectedQuizzes
            .filter((quiz) => failed.includes(quiz.name))
            .map((quiz) => quiz.id)
        )
        setSelectedQuizIds(failedSet)
      }
    }
  }

  React.useEffect(() => {
    if (!editingQuiz) return
    editForm.setFieldsValue({
      name: editingQuiz.name,
      description: editingQuiz.description ?? "",
      timeLimit: editingQuiz.time_limit_seconds
        ? Math.round(editingQuiz.time_limit_seconds / 60)
        : undefined,
      passingScore: editingQuiz.passing_score ?? undefined
    })
  }, [editingQuiz, editForm])

  const openEditModal = (quiz: Quiz) => {
    captureFocusTarget(editModalTriggerRef)
    setEditingQuiz(quiz)
    setEditModalOpen(true)
  }

  const closeEditModal = () => {
    setEditModalOpen(false)
    setEditingQuiz(null)
    setQuestionModalOpen(false)
    setQuestionDraft(null)
    setQuestionValidationErrors({})
    editForm.resetFields()
    restoreFocusTarget(editModalTriggerRef)
  }

  const handleSaveQuiz = async () => {
    if (!editingQuiz) return
    try {
      const values = await editForm.validateFields()
      await updateQuizMutation.mutateAsync({
        quizId: editingQuiz.id,
        update: {
          name: values.name,
          description: values.description || null,
          time_limit_seconds: values.timeLimit ? values.timeLimit * 60 : null,
          passing_score: values.passingScore ?? null,
          expected_version: editingQuiz.version
        }
      })
      messageApi.success(
        t("option:quiz.updateSuccess", { defaultValue: "Quiz updated successfully" })
      )
      closeEditModal()
      refetch()
    } catch (error) {
      messageApi.error(
        t("option:quiz.updateError", { defaultValue: "Failed to update quiz" })
      )
    }
  }

  const baseQuestionDraft = (): QuestionDraft => ({
    question_type: "multiple_choice",
    question_text: "",
    options: ["", "", "", ""],
    correct_answer: 0,
    explanation: "",
    points: 1,
    order_index: questionTotal
  })

  const openQuestionModal = (question?: Question) => {
    captureFocusTarget(questionModalTriggerRef)
    if (question) {
      setIsNewQuestion(false)
      setQuestionDraft({
        id: question.id,
        question_type: question.question_type,
        question_text: question.question_text,
        options:
          question.question_type === "multiple_choice"
            ? (question.options ?? ["", "", "", ""])
            : ["", "", "", ""],
        correct_answer: question.correct_answer ?? (question.question_type === "true_false" ? "true" : ""),
        explanation: question.explanation ?? "",
        points: question.points ?? 1,
        order_index: question.order_index ?? 0
      })
    } else {
      setIsNewQuestion(true)
      setQuestionDraft(baseQuestionDraft())
    }
    setQuestionValidationErrors({})
    setQuestionModalOpen(true)
  }

  const closeQuestionModal = () => {
    setQuestionModalOpen(false)
    setQuestionDraft(null)
    setQuestionValidationErrors({})
    restoreFocusTarget(questionModalTriggerRef)
  }

  const updateQuestionDraft = (updates: Partial<QuestionDraft>) => {
    setQuestionDraft((prev) => (prev ? { ...prev, ...updates } : prev))
  }

  const normalizeOptions = (options: string[]) => {
    const trimmed = options.map((opt) => opt.trim())
    const filtered: string[] = []
    const indexMap = new Map<number, number>()
    trimmed.forEach((opt, idx) => {
      if (!opt) return
      indexMap.set(idx, filtered.length)
      filtered.push(opt)
    })
    return { filtered, indexMap }
  }

  const handleSaveQuestion = async () => {
    if (!editingQuiz || !questionDraft) return

    const validationErrors: QuestionValidationErrors = {}
    if (!questionDraft.question_text.trim()) {
      validationErrors.questionText = t("option:quiz.questionTextRequired", {
        defaultValue: "Question text is required."
      })
    }

    let optionsPayload: string[] | undefined
    let correctAnswer: AnswerValue = questionDraft.correct_answer

    if (questionDraft.question_type === "multiple_choice") {
      const { filtered, indexMap } = normalizeOptions(questionDraft.options)
      if (filtered.length < 2) {
        validationErrors.options = t("option:quiz.optionsRequired", {
          defaultValue: "Please provide at least two options."
        })
      }
      const rawIndex = Number(correctAnswer)
      const mapped = indexMap.get(Number.isNaN(rawIndex) ? 0 : rawIndex)
      correctAnswer = mapped ?? 0
      optionsPayload = filtered
    } else if (questionDraft.question_type === "true_false") {
      correctAnswer = String(correctAnswer || "true").toLowerCase() === "true" ? "true" : "false"
    } else {
      correctAnswer = String(correctAnswer || "").trim()
    }

    if (validationErrors.questionText || validationErrors.options) {
      setQuestionValidationErrors(validationErrors)
      return
    }
    setQuestionValidationErrors({})

    try {
      if (isNewQuestion) {
        await createQuestionMutation.mutateAsync({
          quizId: editingQuiz.id,
          question: {
            question_type: questionDraft.question_type,
            question_text: questionDraft.question_text,
            options: optionsPayload,
            correct_answer: correctAnswer,
            explanation: questionDraft.explanation || undefined,
            points: questionDraft.points,
            order_index: questionDraft.order_index
          }
        })
        messageApi.success(
          t("option:quiz.questionSaveSuccess", { defaultValue: "Question created successfully." })
        )
      } else if (questionDraft.id != null) {
        await updateQuestionMutation.mutateAsync({
          quizId: editingQuiz.id,
          questionId: questionDraft.id,
          update: {
            question_type: questionDraft.question_type,
            question_text: questionDraft.question_text,
            options: optionsPayload,
            correct_answer: correctAnswer,
            explanation: questionDraft.explanation || undefined,
            points: questionDraft.points,
            order_index: questionDraft.order_index
          }
        })
        messageApi.success(
          t("option:quiz.questionUpdateSuccess", { defaultValue: "Question updated successfully." })
        )
      }
      closeQuestionModal()
      questionsQuery.refetch()
    } catch (error) {
      messageApi.error(
        t("option:quiz.questionSaveError", { defaultValue: "Failed to save question." })
      )
    }
  }

  const handleUndoQuestionDelete = () => {
    if (!pendingQuestionDeletion.current) return
    clearTimeout(pendingQuestionDeletion.current.timeoutId)
    const question = pendingQuestionDeletion.current.question
    pendingQuestionDeletion.current = null
    setPendingQuestionUndoText(null)
    setDeletedQuestionIds((prev) => {
      const next = new Set(prev)
      next.delete(question.id)
      return next
    })
    messageApi.success(
      t("option:quiz.undoSuccess", { defaultValue: "Deletion undone" })
    )
  }

  const executeQuestionDelete = async (question: Question, quizId: number) => {
    try {
      await deleteQuestionMutation.mutateAsync({
        quizId,
        questionId: question.id,
        version: question.version
      })
      pendingQuestionDeletion.current = null
      setPendingQuestionUndoText(null)
      setDeletedQuestionIds((prev) => {
        const next = new Set(prev)
        next.delete(question.id)
        return next
      })
      questionsQuery.refetch()
    } catch (error) {
      // Deletion failed, restore the question in UI
      setDeletedQuestionIds((prev) => {
        const next = new Set(prev)
        next.delete(question.id)
        return next
      })
      pendingQuestionDeletion.current = null
      setPendingQuestionUndoText(null)
      messageApi.error(
        t("option:quiz.questionDeleteError", { defaultValue: "Failed to delete question." })
      )
    }
  }

  const handleDeleteQuestion = (question: Question) => {
    if (!editingQuiz) return

    // Cancel any existing pending question deletion
    if (pendingQuestionDeletion.current && editingQuiz) {
      clearTimeout(pendingQuestionDeletion.current.timeoutId)
      executeQuestionDelete(pendingQuestionDeletion.current.question, editingQuiz.id)
    }

    // Optimistically hide the question from UI
    setDeletedQuestionIds((prev) => new Set(prev).add(question.id))
    setPendingQuestionUndoText(question.question_text || t("option:quiz.question", { defaultValue: "Question" }))

    // Schedule actual deletion
    const quizId = editingQuiz.id
    const timeoutId = setTimeout(() => {
      executeQuestionDelete(question, quizId)
    }, UNDO_GRACE_PERIOD)

    pendingQuestionDeletion.current = { question, timeoutId }
  }

  const handleReorderQuestion = async (questionId: number, direction: "up" | "down") => {
    if (!editingQuiz) return
    const currentIndex = sortedQuestions.findIndex((question) => question.id === questionId)
    if (currentIndex < 0) return

    const nextIndex = direction === "up" ? currentIndex - 1 : currentIndex + 1
    if (nextIndex < 0 || nextIndex >= sortedQuestions.length) return

    const currentQuestion = sortedQuestions[currentIndex]
    const targetQuestion = sortedQuestions[nextIndex]
    const currentOrder = currentQuestion.order_index ?? currentIndex
    const targetOrder = targetQuestion.order_index ?? nextIndex

    setReorderPendingQuestionId(questionId)
    try {
      await updateQuestionMutation.mutateAsync({
        quizId: editingQuiz.id,
        questionId: currentQuestion.id,
        update: {
          order_index: targetOrder
        }
      })
      await updateQuestionMutation.mutateAsync({
        quizId: editingQuiz.id,
        questionId: targetQuestion.id,
        update: {
          order_index: currentOrder
        }
      })
      messageApi.success(
        t("option:quiz.reorderQuestionsSuccess", {
          defaultValue: "Question order updated."
        })
      )
      questionsQuery.refetch()
    } catch (error) {
      messageApi.error(
        t("option:quiz.reorderQuestionsError", {
          defaultValue: "Failed to reorder questions."
        })
      )
    } finally {
      setReorderPendingQuestionId(null)
    }
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {contextHolder}

      {pendingQuizUndoName && (
        <Alert
          type="info"
          showIcon
          title={t("option:quiz.quizDeletedUndoPrompt", {
            defaultValue: "Quiz deleted: {{name}}",
            name: pendingQuizUndoName
          })}
          action={(
            <Button
              type="link"
              size="small"
              icon={<UndoOutlined />}
              onClick={handleUndoQuizDelete}
            >
              {t("option:quiz.undo", { defaultValue: "Undo" })}
            </Button>
          )}
        />
      )}

      {pendingQuestionUndoText && (
        <Alert
          type="info"
          showIcon
          title={t("option:quiz.questionDeletedUndoPrompt", {
            defaultValue: "Question deleted: {{question}}",
            question: pendingQuestionUndoText
          })}
          action={(
            <Button
              type="link"
              size="small"
              icon={<UndoOutlined />}
              onClick={handleUndoQuestionDelete}
            >
              {t("option:quiz.undo", { defaultValue: "Undo" })}
            </Button>
          )}
        />
      )}

      <div className="flex justify-between items-center">
        <Input
          ref={searchInputRef}
          placeholder={t("option:quiz.searchQuizzes", { defaultValue: "Search quizzes..." })}
          prefix={<SearchOutlined />}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="max-w-xs"
          allowClear
        />
        <Space>
          <Button onClick={onNavigateToGenerate}>
            {t("option:quiz.generateNew", { defaultValue: "Generate New" })}
          </Button>
          <Button type="primary" onClick={onNavigateToCreate}>
            {t("option:quiz.createNew", { defaultValue: "Create New" })}
          </Button>
        </Space>
      </div>

      {selectedQuizIds.size > 0 && (
        <Alert
          type="info"
          showIcon
          message={t("option:quiz.bulkSelectionMessage", {
            defaultValue: "{{count}} quiz(es) selected",
            count: selectedQuizIds.size
          })}
          action={(
            <Space>
              <Button size="small" onClick={clearQuizSelection} disabled={bulkDeleteInFlight}>
                {t("common:clear", { defaultValue: "Clear" })}
              </Button>
              <Popconfirm
                title={t("option:quiz.bulkDeleteConfirmTitle", {
                  defaultValue: "Delete selected quizzes?"
                })}
                description={t("option:quiz.bulkDeleteConfirmDescription", {
                  defaultValue: "This will permanently delete {{count}} quiz(es).",
                  count: selectedQuizIds.size
                })}
                okText={t("common:delete", { defaultValue: "Delete" })}
                cancelText={t("common:cancel", { defaultValue: "Cancel" })}
                onConfirm={() => executeBulkDelete()}
              >
                <Button
                  size="small"
                  danger
                  loading={bulkDeleteInFlight}
                  data-testid="manage-bulk-delete"
                >
                  {t("option:quiz.deleteSelected", { defaultValue: "Delete Selected" })}
                </Button>
              </Popconfirm>
            </Space>
          )}
        />
      )}

      {quizzes.length === 0 ? (
        <Empty
          description={
            searchQuery
              ? t("option:quiz.noSearchResults", { defaultValue: "No quizzes match your search" })
              : t("option:quiz.noQuizzesYet", { defaultValue: "No quizzes yet" })
          }
        >
          {!searchQuery && (
            <Space>
              <Button type="primary" onClick={onNavigateToGenerate}>
                {t("option:quiz.generateFromMedia", { defaultValue: "Generate from Media" })}
              </Button>
              <Button onClick={onNavigateToCreate}>
                {t("option:quiz.createManually", { defaultValue: "Create Manually" })}
              </Button>
            </Space>
          )}
        </Empty>
      ) : (
        <List
          dataSource={quizzes}
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
          renderItem={(quiz) => (
            <List.Item
              actions={[
                <Button
                  key="start"
                  type="link"
                  icon={<PlayCircleOutlined />}
                  onClick={() => {
                    onStartQuiz(quiz.id)
                  }}
                  data-testid={`quiz-start-${quiz.id}`}
                >
                  {t("option:quiz.start", { defaultValue: "Start" })}
                </Button>,
                <Button
                  key="duplicate"
                  type="link"
                  icon={<CopyOutlined />}
                  onClick={() => {
                    void handleDuplicateQuiz(quiz)
                  }}
                  loading={duplicateInFlightQuizId === quiz.id}
                  data-testid={`quiz-duplicate-${quiz.id}`}
                >
                  {t("option:quiz.duplicate", { defaultValue: "Duplicate" })}
                </Button>,
                <Button
                  key="edit"
                  type="link"
                  icon={<EditOutlined />}
                  onClick={() => {
                    openEditModal(quiz)
                  }}
                  data-testid={`quiz-edit-${quiz.id}`}
                >
                  {t("option:quiz.edit", { defaultValue: "Edit" })}
                </Button>,
                <Button
                  key="delete"
                  type="link"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => handleDelete(quiz)}
                >
                  {t("option:quiz.delete", { defaultValue: "Delete" })}
                </Button>
              ]}
            >
              <List.Item.Meta
                title={
                  <Space size="small" align="center">
                    <Checkbox
                      checked={selectedQuizIds.has(quiz.id)}
                      onChange={(event) => toggleQuizSelection(quiz.id, event.target.checked)}
                      aria-label={t("option:quiz.selectQuiz", {
                        defaultValue: "Select quiz {{name}}",
                        name: quiz.name
                      })}
                    />
                    <span className="font-medium">{quiz.name}</span>
                  </Space>
                }
                description={
                  <div className="space-y-1">
                    {quiz.description && (
                      <p className="text-sm text-text-muted line-clamp-1">
                        {quiz.description}
                      </p>
                    )}
                    <div className="flex gap-2">
                      <Tag icon={<QuestionCircleOutlined />}>
                        {quiz.total_questions}{" "}
                        {t("option:quiz.questions", { defaultValue: "questions" })}
                      </Tag>
                      {quiz.passing_score && (
                        <Tag color="blue">
                          {t("option:quiz.passingScoreLabel", { defaultValue: "Pass" })}: {quiz.passing_score}%
                        </Tag>
                      )}
                      {quiz.media_id && (
                        <Tag color="green">
                          {t("option:quiz.fromMedia", { defaultValue: "From Media" })}
                        </Tag>
                      )}
                    </div>
                  </div>
                }
              />
            </List.Item>
          )}
        />
      )}

      <Modal
        title={t("option:quiz.editQuizTitle", { defaultValue: "Edit Quiz" })}
        open={editModalOpen}
        onCancel={closeEditModal}
        onOk={handleSaveQuiz}
        okText={t("common:save", { defaultValue: "Save" })}
        cancelText={t("common:cancel", { defaultValue: "Cancel" })}
        confirmLoading={updateQuizMutation.isPending}
        width="95vw"
        style={{ top: 16 }}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item
            name="name"
            label={t("option:quiz.quizName", { defaultValue: "Quiz Name" })}
            rules={[
              {
                required: true,
                message: t("option:quiz.nameRequired", { defaultValue: "Please enter a quiz name" })
              }
            ]}
          >
            <Input />
          </Form.Item>

          <Form.Item
            name="description"
            label={t("option:quiz.description", { defaultValue: "Description" })}
          >
            <Input.TextArea rows={2} />
          </Form.Item>

          <div className="grid grid-cols-2 gap-4">
            <Form.Item
              name="timeLimit"
              label={t("option:quiz.timeLimit", { defaultValue: "Time Limit (minutes)" })}
            >
              <InputNumber min={1} max={180} className="w-full" />
            </Form.Item>
            <Form.Item
              name="passingScore"
              label={t("option:quiz.passingScore", { defaultValue: "Passing Score (%)" })}
            >
              <InputNumber min={1} max={100} className="w-full" />
            </Form.Item>
          </div>
        </Form>

        <Divider />

        <div className="flex items-center justify-between mb-3">
          <Typography.Title level={5} className="!mb-0">
            {t("option:quiz.questionsSection", { defaultValue: "Questions" })}
          </Typography.Title>
          <Button
            type="dashed"
            icon={<PlusOutlined />}
            onClick={() => openQuestionModal()}
            data-testid="manage-add-question"
          >
            {t("option:quiz.addQuestion", { defaultValue: "Add Question" })}
          </Button>
        </div>

        {questionsQuery.isLoading ? (
          <div className="flex justify-center py-6">
            <Spin />
          </div>
        ) : questions.length === 0 ? (
          <Empty
            description={t("option:quiz.noQuestionsYet", { defaultValue: "No questions added yet" })}
          />
        ) : (
          <div className="max-h-[50vh] overflow-y-auto pr-1" data-testid="manage-questions-scroll-container">
            <List
              dataSource={sortedQuestions}
              renderItem={(question, index) => (
                <List.Item
                  actions={[
                    <Button
                      key="move-up"
                      type="text"
                      icon={<ArrowUpOutlined />}
                      aria-label={t("option:quiz.moveQuestionUp", {
                        defaultValue: "Move question {{number}} up",
                        number: index + 1
                      })}
                      disabled={reorderBusy || index === 0}
                      onClick={() => handleReorderQuestion(question.id, "up")}
                    />,
                    <Button
                      key="move-down"
                      type="text"
                      icon={<ArrowDownOutlined />}
                      aria-label={t("option:quiz.moveQuestionDown", {
                        defaultValue: "Move question {{number}} down",
                        number: index + 1
                      })}
                      disabled={reorderBusy || index === sortedQuestions.length - 1}
                      onClick={() => handleReorderQuestion(question.id, "down")}
                    />,
                    <Button
                      key="edit"
                      type="link"
                      onClick={() => openQuestionModal(question)}
                      data-testid={`manage-edit-question-${question.id}`}
                    >
                      {t("common:edit", { defaultValue: "Edit" })}
                    </Button>,
                    <Button
                      key="delete"
                      type="link"
                      danger
                      onClick={() => handleDeleteQuestion(question)}
                    >
                      {t("option:quiz.delete", { defaultValue: "Delete" })}
                    </Button>
                  ]}
                >
                  <List.Item.Meta
                    title={question.question_text}
                    description={(
                      <div className="flex flex-wrap gap-2">
                        <Tag>{questionTypeLabel(question.question_type)}</Tag>
                        <Tag>{t("option:quiz.points", { defaultValue: "Points" })}: {question.points}</Tag>
                        <Tag>{t("option:quiz.orderIndex", { defaultValue: "Order" })}: {(question.order_index ?? 0) + 1}</Tag>
                      </div>
                    )}
                  />
                </List.Item>
              )}
            />
          </div>
        )}
      </Modal>

      <Modal
        title={
          isNewQuestion
            ? t("option:quiz.addQuestion", { defaultValue: "Add Question" })
            : t("option:quiz.editQuestion", { defaultValue: "Edit Question" })
        }
        open={questionModalOpen}
        onCancel={closeQuestionModal}
        onOk={handleSaveQuestion}
        okText={t("common:save", { defaultValue: "Save" })}
        cancelText={t("common:cancel", { defaultValue: "Cancel" })}
        confirmLoading={createQuestionMutation.isPending || updateQuestionMutation.isPending}
        width={760}
      >
        {questionDraft && (
          <Space orientation="vertical" className="w-full">
            <Select
              value={questionDraft.question_type}
              onChange={(value: QuestionType) => {
                const updates: Partial<QuestionDraft> = { question_type: value }
                if (value === "multiple_choice") {
                  updates.correct_answer = 0
                  if (questionDraft.options.length === 0) {
                    updates.options = ["", "", "", ""]
                  }
                } else if (value === "true_false") {
                  updates.correct_answer = "true"
                } else {
                  updates.correct_answer = ""
                }
                updateQuestionDraft(updates)
                setQuestionValidationErrors({})
              }}
              options={[
                { label: t("option:quiz.multipleChoice", { defaultValue: "Multiple Choice" }), value: "multiple_choice" },
                { label: t("option:quiz.trueFalse", { defaultValue: "True/False" }), value: "true_false" },
                { label: t("option:quiz.fillBlank", { defaultValue: "Fill in the Blank" }), value: "fill_blank" }
              ]}
              className="w-60"
            />

            <Input.TextArea
              placeholder={t("option:quiz.questionText", { defaultValue: "Enter your question..." })}
              value={questionDraft.question_text}
              onChange={(e) => {
                updateQuestionDraft({ question_text: e.target.value })
                if (questionValidationErrors.questionText) {
                  setQuestionValidationErrors((prev) => ({ ...prev, questionText: undefined }))
                }
              }}
              aria-invalid={questionValidationErrors.questionText ? true : undefined}
              aria-describedby={questionValidationErrors.questionText ? QUESTION_TEXT_ERROR_ID : undefined}
              rows={2}
            />
            {questionValidationErrors.questionText && (
              <div
                id={QUESTION_TEXT_ERROR_ID}
                className="text-sm text-red-600"
                role="alert"
              >
                {questionValidationErrors.questionText}
              </div>
            )}

            {questionDraft.question_type === "multiple_choice" && (
              <div className="space-y-2">
                <div className="text-sm font-medium">
                  {t("option:quiz.options", { defaultValue: "Options" })}
                </div>
                {questionDraft.options.map((option, optIndex) => (
                  <div key={optIndex} className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="edit-correct"
                      checked={Number(questionDraft.correct_answer) === optIndex}
                      onChange={() => updateQuestionDraft({ correct_answer: optIndex })}
                    />
                    <Input
                      placeholder={`${t("option:quiz.option", { defaultValue: "Option" })} ${optIndex + 1}`}
                      value={option}
                      onChange={(e) => {
                        const newOptions = [...questionDraft.options]
                        newOptions[optIndex] = e.target.value
                        updateQuestionDraft({ options: newOptions })
                        if (questionValidationErrors.options) {
                          setQuestionValidationErrors((prev) => ({ ...prev, options: undefined }))
                        }
                      }}
                      aria-invalid={questionValidationErrors.options ? true : undefined}
                      aria-describedby={questionValidationErrors.options ? QUESTION_OPTIONS_ERROR_ID : undefined}
                      className="flex-1"
                    />
                  </div>
                ))}
                {questionValidationErrors.options && (
                  <div
                    id={QUESTION_OPTIONS_ERROR_ID}
                    className="text-sm text-red-600"
                    role="alert"
                  >
                    {questionValidationErrors.options}
                  </div>
                )}
              </div>
            )}

            {questionDraft.question_type === "true_false" && (
              <fieldset className="border-0 m-0 p-0">
                <legend className="sr-only">
                  {t("option:quiz.trueFalseLegend", {
                    defaultValue: "True or false for: {{question}}",
                    question: questionDraft.question_text || t("option:quiz.question", { defaultValue: "question" })
                  })}
                </legend>
                <Radio.Group
                  value={questionDraft.correct_answer}
                  onChange={(e) => updateQuestionDraft({ correct_answer: e.target.value })}
                >
                  <Space orientation="vertical">
                    <Radio value="true">{t("option:quiz.true", { defaultValue: "True" })}</Radio>
                    <Radio value="false">{t("option:quiz.false", { defaultValue: "False" })}</Radio>
                  </Space>
                </Radio.Group>
              </fieldset>
            )}

            {questionDraft.question_type === "fill_blank" && (
              <Input
                placeholder={t("option:quiz.correctAnswerPlaceholder", {
                  defaultValue: "Enter the correct answer..."
                })}
                value={typeof questionDraft.correct_answer === "string" ? questionDraft.correct_answer : ""}
                onChange={(e) => updateQuestionDraft({ correct_answer: e.target.value })}
              />
            )}

            <div className="grid grid-cols-2 gap-4">
              <InputNumber
                min={1}
                className="w-full"
                value={questionDraft.points}
                onChange={(value) => updateQuestionDraft({ points: Number(value) || 1 })}
                placeholder={t("option:quiz.points", { defaultValue: "Points" })}
              />
              <InputNumber
                min={0}
                className="w-full"
                value={questionDraft.order_index}
                onChange={(value) => updateQuestionDraft({ order_index: Number(value) || 0 })}
                placeholder={t("option:quiz.orderIndex", { defaultValue: "Order" })}
              />
            </div>

            <Input.TextArea
              placeholder={t("option:quiz.explanationPlaceholder", {
                defaultValue: "Explanation (shown after answering)..."
              })}
              value={questionDraft.explanation ?? ""}
              onChange={(e) => updateQuestionDraft({ explanation: e.target.value })}
              rows={2}
            />
          </Space>
        )}
      </Modal>
    </div>
  )
}

export default ManageTab
