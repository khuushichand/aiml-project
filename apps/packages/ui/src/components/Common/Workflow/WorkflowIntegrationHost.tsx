import React, { useCallback, useEffect, useMemo, useRef } from "react"
import { useNavigate, useLocation } from "react-router-dom"
import { useConnectionUxState } from "@/hooks/useConnectionState"
import { useWorkflowsStore } from "@/store/workflows"
import { WorkflowLandingModal } from "./WorkflowLanding"
import { WorkflowOverlay } from "./WorkflowContainer"

interface WorkflowIntegrationHostProps {
  justChatPath?: string
  autoShow?: boolean
  autoShowPaths?: string[]
}

/**
 * WorkflowIntegrationHost
 *
 * Global host for workflow UI pieces:
 * - Loads landing/suggestion state on mount
 * - Renders the landing modal
 * - Renders the workflow overlay for active flows
 */
export const WorkflowIntegrationHost: React.FC<
  WorkflowIntegrationHostProps
> = ({
  justChatPath = "/chat",
  autoShow = true,
  autoShowPaths = ["/"]
}) => {
  const navigate = useNavigate()
  const location = useLocation()
  const { hasCompletedFirstRun } = useConnectionUxState()
  const loadLandingConfig = useWorkflowsStore((s) => s.loadLandingConfig)
  const loadDismissedSuggestions = useWorkflowsStore(
    (s) => s.loadDismissedSuggestions
  )
  const markLandingSeen = useWorkflowsStore((s) => s.markLandingSeen)
  const showLanding = useWorkflowsStore((s) => s.showLanding)
  const autoShowRequestedRef = useRef(false)

  const shouldAutoShow = useMemo(() => {
    if (!autoShow) return false
    return autoShowPaths.includes(location.pathname)
  }, [autoShow, autoShowPaths, location.pathname])

  useEffect(() => {
    if (!hasCompletedFirstRun) return
    if (shouldAutoShow) {
      autoShowRequestedRef.current = true
      loadLandingConfig()
    }
    loadDismissedSuggestions()
  }, [
    hasCompletedFirstRun,
    loadLandingConfig,
    loadDismissedSuggestions,
    shouldAutoShow
  ])

  useEffect(() => {
    if (!showLanding) return
    if (!autoShowRequestedRef.current) return
    markLandingSeen()
    autoShowRequestedRef.current = false
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showLanding]) // markLandingSeen excluded: it's a stable store action but creates new reference each render

  const handleJustChat = useCallback(() => {
    navigate(justChatPath)
  }, [navigate, justChatPath])

  return (
    <>
      <WorkflowOverlay />
      <WorkflowLandingModal onJustChat={handleJustChat} />
    </>
  )
}
