import React from "react"
import {
  DEFAULT_PROMPT_QUERY_STATE,
  PROMPTS_WORKSPACE_MOBILE_BREAKPOINT_PX,
  type PromptListQueryState,
  type PromptWorkspaceState
} from "./prompt-workspace-types"

const PROMPTS_WORKSPACE_QUERY_STORAGE_KEY = "tldw-prompts-workspace-query-v1"

const isSortKey = (value: unknown) =>
  value === null || value === "title" || value === "modifiedAt"

const isSortOrder = (value: unknown) =>
  value === null || value === "ascend" || value === "descend"

const readStoredQueryState = (): PromptListQueryState => {
  if (typeof window === "undefined") {
    return DEFAULT_PROMPT_QUERY_STATE
  }

  try {
    const raw = window.sessionStorage.getItem(PROMPTS_WORKSPACE_QUERY_STORAGE_KEY)
    if (!raw) {
      return DEFAULT_PROMPT_QUERY_STATE
    }
    const parsed = JSON.parse(raw) as Partial<PromptListQueryState>
    const sortKey = isSortKey(parsed?.sort?.key)
      ? parsed?.sort?.key
      : DEFAULT_PROMPT_QUERY_STATE.sort.key
    const sortOrder = isSortOrder(parsed?.sort?.order)
      ? parsed?.sort?.order
      : DEFAULT_PROMPT_QUERY_STATE.sort.order

    return {
      ...DEFAULT_PROMPT_QUERY_STATE,
      ...parsed,
      tagFilter: Array.isArray(parsed?.tagFilter)
        ? parsed?.tagFilter.filter((value): value is string => typeof value === "string")
        : [],
      sort: {
        key: sortKey,
        order: sortOrder
      }
    }
  } catch {
    return DEFAULT_PROMPT_QUERY_STATE
  }
}

const getInitialCompactViewport = () => {
  if (typeof window === "undefined") {
    return false
  }
  return window.innerWidth < PROMPTS_WORKSPACE_MOBILE_BREAKPOINT_PX
}

export const usePromptWorkspaceState = () => {
  const [state, setState] = React.useState<PromptWorkspaceState>(() => ({
    query: readStoredQueryState(),
    selection: {
      selectedIds: []
    },
    panel: {
      open: false,
      promptId: null
    },
    isCompactViewport: getInitialCompactViewport()
  }))

  React.useEffect(() => {
    if (typeof window === "undefined") return
    const handleResize = () => {
      setState((previous) => ({
        ...previous,
        isCompactViewport:
          window.innerWidth < PROMPTS_WORKSPACE_MOBILE_BREAKPOINT_PX
      }))
    }
    window.addEventListener("resize", handleResize)
    return () => {
      window.removeEventListener("resize", handleResize)
    }
  }, [])

  React.useEffect(() => {
    if (typeof window === "undefined") return
    try {
      window.sessionStorage.setItem(
        PROMPTS_WORKSPACE_QUERY_STORAGE_KEY,
        JSON.stringify(state.query)
      )
    } catch {
      // Ignore storage failures in restricted browser modes.
    }
  }, [state.query])

  const setQuery = React.useCallback(
    (patch: Partial<PromptListQueryState>) => {
      setState((previous) => ({
        ...previous,
        query: {
          ...previous.query,
          ...patch
        }
      }))
    },
    []
  )

  const setSelection = React.useCallback((selectedIds: string[]) => {
    setState((previous) => ({
      ...previous,
      selection: {
        selectedIds
      }
    }))
  }, [])

  const clearSelection = React.useCallback(() => {
    setState((previous) => ({
      ...previous,
      selection: {
        selectedIds: []
      }
    }))
  }, [])

  const openPanel = React.useCallback((promptId: string) => {
    setState((previous) => ({
      ...previous,
      panel: {
        open: true,
        promptId
      }
    }))
  }, [])

  const closePanel = React.useCallback(() => {
    setState((previous) => ({
      ...previous,
      panel: {
        open: false,
        promptId: null
      }
    }))
  }, [])

  return {
    state,
    setQuery,
    setSelection,
    clearSelection,
    openPanel,
    closePanel
  }
}
