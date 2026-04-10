import { useCallback, useMemo } from "react"
import { useSearchParams } from "react-router-dom"

import type { SegmentType } from "./PromptWorkspaceProvider"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

const VALID_SEGMENTS: SegmentType[] = ["custom", "copilot", "studio", "trash"]

/** Parsed URL search-param values relevant to the Prompt workspace. */
export interface PromptUrlState {
  /** Active tab/segment (`?tab=`). Defaults to `"custom"` when absent or invalid. */
  tab: SegmentType
  /** Project filter (`?project=`). `null` when unset. */
  project: string | null
  /** Prompt deep-link id (`?prompt=`). `null` when unset. */
  prompt: string | null
  /** Deep-link source hint (`?source=`). `null` when unset. */
  source: string | null
  /** Full-editor edit target (`?edit=`). `null` when unset. */
  edit: string | null
  /** Whether the `?new=1` flag is set. */
  isNew: boolean
}

export interface PromptUrlActions {
  /**
   * Replace the `tab` search param.
   * Passing `"custom"` (the default segment) removes the param from the URL.
   */
  setTab: (segment: SegmentType) => void
  /** Remove the `?project=` param. */
  clearProjectFilter: () => void
  /** Remove the `?prompt=` and `?source=` params. */
  clearPromptParam: () => void
  /** Set `?edit=<id>` in the URL. */
  setEditParam: (id: string) => void
  /** Remove the `?edit=` param. */
  clearEditParam: () => void
  /** Remove the `?new=` param. */
  clearNewParam: () => void
  /** The raw `searchParams` object for edge-case reads. */
  searchParams: URLSearchParams
}

export type UsePromptUrlStateReturn = PromptUrlState & PromptUrlActions

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function parseSegment(raw: string | null): SegmentType {
  if (raw && VALID_SEGMENTS.includes(raw as SegmentType)) {
    return raw as SegmentType
  }
  return "custom"
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Centralises all URL search-param management for the Prompt workspace into a
 * single `useSearchParams()` call.  Every setter uses `replace: true` so the
 * browser history stays clean.
 *
 * **Why this exists**: the orchestrator (`index.tsx`) *and* sub-hooks both
 * called `useSearchParams()` independently, which caused state-tearing and
 * silent overwrites.  By funnelling everything through one hook instance we
 * eliminate that entire class of bugs.
 */
export function usePromptUrlState(): UsePromptUrlStateReturn {
  const [searchParams, setSearchParams] = useSearchParams()

  // --- Parsed values -------------------------------------------------------

  const tab = parseSegment(searchParams.get("tab"))
  const project = searchParams.get("project")
  const prompt = searchParams.get("prompt")
  const source = searchParams.get("source")
  const edit = searchParams.get("edit")
  const isNew = searchParams.get("new") === "1"

  // --- Setters -------------------------------------------------------------

  const setTab = useCallback(
    (segment: SegmentType) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (segment === "custom") {
            next.delete("tab")
          } else {
            next.set("tab", segment)
          }
          return next
        },
        { replace: true }
      )
    },
    [setSearchParams]
  )

  const clearProjectFilter = useCallback(() => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete("project")
        return next
      },
      { replace: true }
    )
  }, [setSearchParams])

  const clearPromptParam = useCallback(() => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete("prompt")
        next.delete("source")
        return next
      },
      { replace: true }
    )
  }, [setSearchParams])

  const setEditParam = useCallback(
    (id: string) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          next.set("edit", id)
          return next
        },
        { replace: true }
      )
    },
    [setSearchParams]
  )

  const clearEditParam = useCallback(() => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete("edit")
        return next
      },
      { replace: true }
    )
  }, [setSearchParams])

  const clearNewParam = useCallback(() => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete("new")
        return next
      },
      { replace: true }
    )
  }, [setSearchParams])

  // --- Return --------------------------------------------------------------

  return useMemo(
    () => ({
      // parsed state
      tab,
      project,
      prompt,
      source,
      edit,
      isNew,
      // actions
      setTab,
      clearProjectFilter,
      clearPromptParam,
      setEditParam,
      clearEditParam,
      clearNewParam,
      // escape hatch
      searchParams,
    }),
    [
      tab,
      project,
      prompt,
      source,
      edit,
      isNew,
      setTab,
      clearProjectFilter,
      clearPromptParam,
      setEditParam,
      clearEditParam,
      clearNewParam,
      searchParams,
    ]
  )
}

export type { SegmentType } from "./PromptWorkspaceProvider"
export default usePromptUrlState
