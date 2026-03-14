import React from "react"
import { useQueryClient, type InfiniteData } from "@tanstack/react-query"

import { getFlashcard, type Flashcard, type FlashcardBulkUpdateItem, type FlashcardBulkUpdateResponse } from "@/services/flashcards"
import type { FlashcardDocumentPage } from "./useFlashcardDocumentQuery"
import { normalizeFlashcardTemplateFields } from "../utils/template-helpers"
import { shouldRefetchDocumentQueryAfterRowSave, type DocumentQueryFilterContext } from "../utils/document-cache-policy"

export type FlashcardDocumentTemplate = Flashcard["model_type"]

export type FlashcardDocumentRowStatus =
  | "clean"
  | "dirty"
  | "saving"
  | "saved"
  | "conflict"
  | "validation_error"
  | "not_found"

export interface FlashcardDocumentRowDraft {
  front: string
  back: string
  notes: string
  deck_id: number | null
  tags_text: string
  template: FlashcardDocumentTemplate
}

export interface UseFlashcardDocumentRowStateOptions {
  card: Flashcard
  filterContext: DocumentQueryFilterContext
  queryKey: readonly unknown[]
  bulkUpdate: (items: FlashcardBulkUpdateItem[]) => Promise<FlashcardBulkUpdateResponse>
  loadLatestCard?: (uuid: string) => Promise<Flashcard>
}

const tagsToText = (tags?: string[] | null) => (tags || []).join(", ")

const parseTagsText = (value: string): string[] =>
  Array.from(
    new Set(
      value
        .split(/[,\n]+/)
        .map((tag) => tag.trim())
        .filter(Boolean)
    )
  )

const arraysEqual = (left: string[], right: string[]) =>
  left.length === right.length && left.every((value, index) => value === right[index])

const createDraftFromCard = (card: Flashcard): FlashcardDocumentRowDraft => ({
  front: card.front,
  back: card.back,
  notes: card.notes || "",
  deck_id: card.deck_id ?? null,
  tags_text: tagsToText(card.tags),
  template: normalizeFlashcardTemplateFields(card).model_type
})

const buildPatchFromDraft = (
  savedCard: Flashcard,
  draft: FlashcardDocumentRowDraft
): FlashcardBulkUpdateItem | null => {
  const normalizedTemplate = normalizeFlashcardTemplateFields({
    model_type: draft.template
  })
  const nextTags = parseTagsText(draft.tags_text)
  const currentTags = savedCard.tags || []

  const patch: FlashcardBulkUpdateItem = {
    uuid: savedCard.uuid,
    expected_version: savedCard.version
  }

  if (draft.front !== savedCard.front) patch.front = draft.front
  if (draft.back !== savedCard.back) patch.back = draft.back

  const nextNotes = draft.notes.trim() ? draft.notes : null
  const currentNotes = savedCard.notes || null
  if (nextNotes !== currentNotes) patch.notes = nextNotes

  const nextDeckId = draft.deck_id ?? null
  const currentDeckId = savedCard.deck_id ?? null
  if (nextDeckId !== currentDeckId) patch.deck_id = nextDeckId

  if (!arraysEqual(nextTags, currentTags)) patch.tags = nextTags

  if (
    normalizedTemplate.model_type !== savedCard.model_type ||
    normalizedTemplate.reverse !== savedCard.reverse ||
    normalizedTemplate.is_cloze !== savedCard.is_cloze
  ) {
    patch.model_type = normalizedTemplate.model_type
    patch.reverse = normalizedTemplate.reverse
    patch.is_cloze = normalizedTemplate.is_cloze
  }

  return Object.keys(patch).length > 2 ? patch : null
}

const applyPatchToDraft = (
  card: Flashcard,
  patch: FlashcardBulkUpdateItem
): FlashcardDocumentRowDraft => {
  const patchHas = <K extends keyof FlashcardBulkUpdateItem>(field: K) =>
    Object.prototype.hasOwnProperty.call(patch, field)
  const template = normalizeFlashcardTemplateFields({
    model_type: patch.model_type ?? card.model_type,
    reverse: patch.reverse ?? card.reverse,
    is_cloze: patch.is_cloze ?? card.is_cloze
  }).model_type

  return {
    front: patch.front ?? card.front,
    back: patch.back ?? card.back,
    notes: patchHas("notes") ? (patch.notes ?? "") : card.notes ?? "",
    deck_id: patchHas("deck_id") ? (patch.deck_id ?? null) : card.deck_id ?? null,
    tags_text: patch.tags ? tagsToText(patch.tags) : tagsToText(card.tags),
    template
  }
}

const patchDocumentQueryRow = (
  current: InfiniteData<FlashcardDocumentPage, number> | undefined,
  updated: Flashcard
) => {
  if (!current) return current

  let changed = false
  const pages = current.pages.map((page) => {
    const items = page.items.map((item) => {
      if (item.uuid !== updated.uuid) return item
      changed = true
      return updated
    })
    return changed ? { ...page, items } : page
  })

  return changed ? { ...current, pages } : current
}

export function useFlashcardDocumentRowState({
  card,
  filterContext,
  queryKey,
  bulkUpdate,
  loadLatestCard
}: UseFlashcardDocumentRowStateOptions) {
  const queryClient = useQueryClient()
  const loadLatestCardFn = loadLatestCard ?? getFlashcard

  const [savedCard, setSavedCard] = React.useState(card)
  const [draft, setDraft] = React.useState<FlashcardDocumentRowDraft>(() => createDraftFromCard(card))
  const [status, setStatus] = React.useState<FlashcardDocumentRowStatus>("clean")
  const [isEditing, setIsEditing] = React.useState(false)
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null)
  const [validationFields, setValidationFields] = React.useState<string[]>([])
  const [undoSnapshot, setUndoSnapshot] = React.useState<Flashcard | null>(null)
  const [pendingConflictPatch, setPendingConflictPatch] = React.useState<FlashcardBulkUpdateItem | null>(null)

  const savedCardRef = React.useRef(savedCard)
  const draftRef = React.useRef(draft)
  const savingRef = React.useRef(false)
  const queuedDraftRef = React.useRef<FlashcardDocumentRowDraft | null>(null)
  const saveTimerRef = React.useRef<number | null>(null)

  React.useEffect(() => {
    savedCardRef.current = savedCard
  }, [savedCard])

  React.useEffect(() => {
    draftRef.current = draft
  }, [draft])

  React.useEffect(() => {
    if (card.version <= savedCardRef.current.version) return
    if (savingRef.current || status === "dirty" || status === "conflict") return
    setSavedCard(card)
    setDraft(createDraftFromCard(card))
  }, [card, status])

  React.useEffect(
    () => () => {
      if (saveTimerRef.current != null) {
        window.clearTimeout(saveTimerRef.current)
      }
    },
    []
  )

  const resetSavedIndicator = React.useCallback(() => {
    if (saveTimerRef.current != null) {
      window.clearTimeout(saveTimerRef.current)
    }
    saveTimerRef.current = window.setTimeout(() => {
      setStatus((current) => (current === "saved" ? "clean" : current))
    }, 1500)
  }, [])

  const flushDraft = React.useCallback(
    async (draftToSave: FlashcardDocumentRowDraft) => {
      const currentSaved = savedCardRef.current
      const patch = buildPatchFromDraft(currentSaved, draftToSave)

      if (!patch) {
        setSavedCard(currentSaved)
        setDraft(createDraftFromCard(currentSaved))
        setStatus("clean")
        setErrorMessage(null)
        setValidationFields([])
        setPendingConflictPatch(null)
        setIsEditing(false)
        return
      }

      savingRef.current = true
      setStatus("saving")
      setErrorMessage(null)
      setValidationFields([])
      setPendingConflictPatch(null)

      try {
        const response = await bulkUpdate([patch])
        const result = response.results[0]
        if (!result) {
          throw new Error("Bulk update returned no row result.")
        }

        if (result.status === "updated" && result.flashcard) {
          const previous = currentSaved
          const nextCard = result.flashcard
          const requiresRefetch = shouldRefetchDocumentQueryAfterRowSave(previous, nextCard, filterContext)

          setUndoSnapshot(previous)
          setSavedCard(nextCard)
          savedCardRef.current = nextCard

          if (requiresRefetch) {
            await queryClient.invalidateQueries({ queryKey })
          } else {
            queryClient.setQueryData<InfiniteData<FlashcardDocumentPage, number> | undefined>(
              queryKey,
              (current) => patchDocumentQueryRow(current, nextCard)
            )
          }

          if (queuedDraftRef.current) {
            setStatus("dirty")
          } else {
            const normalizedDraft = createDraftFromCard(nextCard)
            setDraft(normalizedDraft)
            draftRef.current = normalizedDraft
            setStatus("saved")
            setIsEditing(false)
            resetSavedIndicator()
          }
          return
        }

        if (result.status === "conflict") {
          setStatus("conflict")
          setErrorMessage(result.error?.message || "This row was changed elsewhere.")
          setPendingConflictPatch(patch)
          return
        }

        if (result.status === "not_found") {
          setStatus("not_found")
          setErrorMessage(result.error?.message || "This row no longer exists.")
          return
        }

        setStatus("validation_error")
        setErrorMessage(result.error?.message || "The row update is invalid.")
        setValidationFields(result.error?.invalid_fields || [])
      } finally {
        savingRef.current = false

        if (queuedDraftRef.current) {
          const nextDraft = queuedDraftRef.current
          queuedDraftRef.current = null
          void flushDraft(nextDraft)
        }
      }
    },
    [bulkUpdate, filterContext, queryClient, queryKey, resetSavedIndicator]
  )

  const setField = React.useCallback(
    <K extends keyof FlashcardDocumentRowDraft>(
      field: K,
      value: FlashcardDocumentRowDraft[K]
    ) => {
      setDraft((current) => {
        const next = { ...current, [field]: value }
        draftRef.current = next
        return next
      })
      setStatus("dirty")
      setErrorMessage(null)
      setValidationFields([])
      setPendingConflictPatch(null)
    },
    []
  )

  const commit = React.useCallback(
    async (nextDraft?: FlashcardDocumentRowDraft) => {
      const draftToSave = nextDraft ?? draftRef.current
      if (savingRef.current) {
        queuedDraftRef.current = draftToSave
        setStatus("dirty")
        return
      }
      await flushDraft(draftToSave)
    },
    [flushDraft]
  )

  const enterEditMode = React.useCallback(() => {
    setIsEditing(true)
  }, [])

  const cancelEdit = React.useCallback(() => {
    const resetDraft = createDraftFromCard(savedCardRef.current)
    queuedDraftRef.current = null
    setDraft(resetDraft)
    draftRef.current = resetDraft
    setStatus("clean")
    setErrorMessage(null)
    setValidationFields([])
    setPendingConflictPatch(null)
    setIsEditing(false)
  }, [])

  const reloadRow = React.useCallback(async () => {
    const previous = savedCardRef.current
    const latest = await loadLatestCardFn(savedCardRef.current.uuid)
    const requiresRefetch = shouldRefetchDocumentQueryAfterRowSave(previous, latest, filterContext)
    setSavedCard(latest)
    savedCardRef.current = latest
    const resetDraft = createDraftFromCard(latest)
    setDraft(resetDraft)
    draftRef.current = resetDraft
    setStatus("clean")
    setErrorMessage(null)
    setValidationFields([])
    setPendingConflictPatch(null)
    setIsEditing(false)
    if (requiresRefetch) {
      await queryClient.invalidateQueries({ queryKey })
      return
    }
    queryClient.setQueryData<InfiniteData<FlashcardDocumentPage, number> | undefined>(
      queryKey,
      (current) => patchDocumentQueryRow(current, latest)
    )
  }, [filterContext, loadLatestCardFn, queryClient, queryKey])

  const reapplyConflict = React.useCallback(async () => {
    if (!pendingConflictPatch) return
    const latest = await loadLatestCardFn(savedCardRef.current.uuid)
    setSavedCard(latest)
    savedCardRef.current = latest
    const reappliedDraft = applyPatchToDraft(latest, pendingConflictPatch)
    setDraft(reappliedDraft)
    draftRef.current = reappliedDraft
    setStatus("dirty")
    setErrorMessage(null)
    setValidationFields([])
    setPendingConflictPatch(null)
    setIsEditing(true)
    await commit(reappliedDraft)
  }, [commit, loadLatestCardFn, pendingConflictPatch])

  const undo = React.useCallback(async () => {
    if (!undoSnapshot) return
    const undoDraft = createDraftFromCard(undoSnapshot)
    setDraft(undoDraft)
    draftRef.current = undoDraft
    setStatus("dirty")
    setIsEditing(true)
    await commit(undoDraft)
  }, [commit, undoSnapshot])

  return {
    card: savedCard,
    draft,
    isEditing,
    status,
    errorMessage,
    validationFields,
    undoSnapshot,
    isSaving: status === "saving",
    isDirty: status === "dirty",
    enterEditMode,
    cancelEdit,
    setField,
    commit,
    undo,
    reloadRow,
    reapplyConflict
  }
}

export default useFlashcardDocumentRowState
