import Dexie, { type Table } from "dexie"
import type { Annotation } from "@/components/DocumentWorkspace/types"

/**
 * Persisted quiz with user answers.
 */
export interface QuizHistoryEntry {
  id?: number // Auto-incremented
  documentId: number
  quiz: {
    quizId: string
    mediaId: number
    questions: Array<{
      question: string
      options?: string[]
      correctAnswer: string
      explanation?: string
    }>
    generatedAt: string
  }
  answers: Record<number, string> // questionIndex -> selectedAnswer
  score?: number // Percentage 0-100
  completedAt?: number // timestamp when all questions answered
  createdAt: number
}

/**
 * Pending annotation action for offline queue.
 */
export interface PendingAnnotationAction {
  id?: number // Auto-incremented
  documentId: number
  annotation: Annotation
  action: "add" | "update" | "delete"
  createdAt: number
}

/**
 * Lightweight Dexie DB for document workspace offline queues.
 * Separate from the main PageAssistDatabase to avoid schema conflicts.
 */
class DocumentWorkspaceOfflineDB extends Dexie {
  pendingAnnotationQueue!: Table<PendingAnnotationAction, number>
  quizHistory!: Table<QuizHistoryEntry, number>

  constructor() {
    super("DocumentWorkspaceOfflineDB")

    this.version(1).stores({
      pendingAnnotationQueue: "++id, documentId, createdAt"
    })

    this.version(2).stores({
      pendingAnnotationQueue: "++id, documentId, createdAt",
      quizHistory: "++id, documentId, createdAt, completedAt"
    })
  }
}

let dbInstance: DocumentWorkspaceOfflineDB | null = null

function getDB(): DocumentWorkspaceOfflineDB {
  if (!dbInstance) {
    dbInstance = new DocumentWorkspaceOfflineDB()
  }
  return dbInstance
}

/**
 * Add an annotation action to the offline queue.
 */
export async function queueAnnotationAction(
  documentId: number,
  annotation: Annotation,
  action: "add" | "update" | "delete"
): Promise<void> {
  try {
    const db = getDB()
    await db.pendingAnnotationQueue.add({
      documentId,
      annotation,
      action,
      createdAt: Date.now()
    })
  } catch (error) {
    console.error("Failed to queue annotation action:", error)
  }
}

/**
 * Get all pending annotation actions for a document.
 */
export async function getPendingActions(
  documentId: number
): Promise<PendingAnnotationAction[]> {
  try {
    const db = getDB()
    return await db.pendingAnnotationQueue
      .where("documentId")
      .equals(documentId)
      .sortBy("createdAt")
  } catch (error) {
    console.error("Failed to get pending actions:", error)
    return []
  }
}

/**
 * Remove a pending action by ID after successful sync.
 */
export async function removePendingAction(id: number): Promise<void> {
  try {
    const db = getDB()
    await db.pendingAnnotationQueue.delete(id)
  } catch (error) {
    console.error("Failed to remove pending action:", error)
  }
}

/**
 * Remove all pending actions for a document (after bulk sync success).
 */
export async function clearPendingActions(documentId: number): Promise<void> {
  try {
    const db = getDB()
    await db.pendingAnnotationQueue
      .where("documentId")
      .equals(documentId)
      .delete()
  } catch (error) {
    console.error("Failed to clear pending actions:", error)
  }
}

/**
 * Get count of all pending actions across all documents.
 */
export async function getPendingActionCount(): Promise<number> {
  try {
    const db = getDB()
    return await db.pendingAnnotationQueue.count()
  } catch (error) {
    console.error("Failed to count pending actions:", error)
    return 0
  }
}

/**
 * Save a quiz to history.
 */
export async function saveQuizToHistory(entry: Omit<QuizHistoryEntry, "id">): Promise<number> {
  try {
    const db = getDB()
    return await db.quizHistory.add(entry as QuizHistoryEntry)
  } catch (error) {
    console.error("Failed to save quiz to history:", error)
    return -1
  }
}

/**
 * Update quiz answers and score.
 */
export async function updateQuizAnswers(
  id: number,
  answers: Record<number, string>,
  score?: number,
  completedAt?: number
): Promise<void> {
  try {
    const db = getDB()
    await db.quizHistory.update(id, { answers, score, completedAt })
  } catch (error) {
    console.error("Failed to update quiz answers:", error)
  }
}

/**
 * Get quiz history for a document, most recent first.
 */
export async function getQuizHistory(documentId: number): Promise<QuizHistoryEntry[]> {
  try {
    const db = getDB()
    const entries = await db.quizHistory
      .where("documentId")
      .equals(documentId)
      .sortBy("createdAt")

    return entries.reverse()
  } catch (error) {
    console.error("Failed to get quiz history:", error)
    return []
  }
}

/**
 * Get a single quiz by ID.
 */
export async function getQuizById(id: number): Promise<QuizHistoryEntry | undefined> {
  try {
    const db = getDB()
    return await db.quizHistory.get(id)
  } catch (error) {
    console.error("Failed to get quiz:", error)
    return undefined
  }
}
