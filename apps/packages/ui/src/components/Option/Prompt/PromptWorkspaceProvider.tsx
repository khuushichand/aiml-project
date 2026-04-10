import React, { createContext, useContext, useEffect, useState } from "react"
import { useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import { useServerOnline } from "@/hooks/useServerOnline"
import type { Prompt } from "@/db/dexie/types"
import {
  getAllPrompts,
  getDeletedPrompts
} from "@/db/dexie/helpers"
import { usePromptUtilities } from "./hooks/usePromptUtilities"

// ---------------------------------------------------------------------------
// Shared types
// ---------------------------------------------------------------------------

export type SegmentType = "custom" | "copilot" | "studio" | "trash"

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PROMPTS_MOBILE_BREAKPOINT_PX = 768

// ---------------------------------------------------------------------------
// Context value type
// ---------------------------------------------------------------------------

export interface PromptWorkspaceContextValue {
  queryClient: QueryClient
  isOnline: boolean
  t: (key: string, opts?: Record<string, any>) => string
  isCompactViewport: boolean
  selectedSegment: SegmentType
  setSelectedSegment: React.Dispatch<React.SetStateAction<SegmentType>>
  data: Prompt[] | undefined
  dataStatus: "pending" | "error" | "success"
  trashData: Prompt[] | undefined
  trashStatus: "pending" | "error" | "success"
  utils: ReturnType<typeof usePromptUtilities>
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const PromptWorkspaceContext = createContext<PromptWorkspaceContextValue | null>(
  null
)

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function PromptWorkspaceProvider({
  children
}: {
  children: React.ReactNode
}) {
  const queryClient = useQueryClient()
  const { t } = useTranslation(["settings", "common", "option"])
  const isOnline = useServerOnline()

  // ---- Segment selection ----
  const [selectedSegment, setSelectedSegment] =
    useState<SegmentType>("custom")

  // ---- Responsive breakpoint ----
  const [isCompactViewport, setIsCompactViewport] = useState(() =>
    typeof window !== "undefined"
      ? window.innerWidth < PROMPTS_MOBILE_BREAKPOINT_PX
      : false
  )

  useEffect(() => {
    if (typeof window === "undefined") return
    const handleResize = () => {
      setIsCompactViewport(window.innerWidth < PROMPTS_MOBILE_BREAKPOINT_PX)
    }
    window.addEventListener("resize", handleResize)
    return () => {
      window.removeEventListener("resize", handleResize)
    }
  }, [])

  // ---- Queries (slow-changing) ----
  const { data, status: dataStatus } = useQuery({
    queryKey: ["fetchAllPrompts"],
    queryFn: getAllPrompts
  })

  const { data: trashData, status: trashStatus } = useQuery({
    queryKey: ["fetchDeletedPrompts"],
    queryFn: getDeletedPrompts
  })

  // ---- Pure-derived utilities ----
  const utils = usePromptUtilities({ t, data })

  // ---- Memoised context value ----
  const value = React.useMemo<PromptWorkspaceContextValue>(
    () => ({
      queryClient,
      isOnline,
      t,
      isCompactViewport,
      selectedSegment,
      setSelectedSegment,
      data,
      dataStatus,
      trashData,
      trashStatus,
      utils
    }),
    [
      queryClient,
      isOnline,
      t,
      isCompactViewport,
      selectedSegment,
      setSelectedSegment,
      data,
      dataStatus,
      trashData,
      trashStatus,
      utils
    ]
  )

  return (
    <PromptWorkspaceContext.Provider value={value}>
      {children}
    </PromptWorkspaceContext.Provider>
  )
}

// ---------------------------------------------------------------------------
// Convenience hook
// ---------------------------------------------------------------------------

export function usePromptWorkspace(): PromptWorkspaceContextValue {
  const ctx = useContext(PromptWorkspaceContext)
  if (!ctx) {
    throw new Error(
      "usePromptWorkspace must be used within a <PromptWorkspaceProvider>. " +
        "Wrap the consuming component tree with <PromptWorkspaceProvider>."
    )
  }
  return ctx
}
