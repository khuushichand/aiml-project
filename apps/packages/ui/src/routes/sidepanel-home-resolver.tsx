import React from "react"
import { useLocation } from "react-router-dom"

import { PageAssistLoader } from "@/components/Common/PageAssistLoader"
import { hasResumableSidepanelChat } from "./sidepanel-chat-resume"

const LazySidepanelChat = React.lazy(() => import("./sidepanel-chat"))
const LazySidepanelCompanion = React.lazy(() => import("./sidepanel-companion"))

export default function SidepanelHomeResolver() {
  const location = useLocation()
  const [target, setTarget] = React.useState<"chat" | "companion" | null>(null)

  const forcedView = React.useMemo(() => {
    const params = new URLSearchParams(location.search)
    return params.get("view")
  }, [location.search])

  React.useEffect(() => {
    if (forcedView === "chat") {
      setTarget("chat")
      return
    }

    let cancelled = false

    const resolveTarget = async () => {
      try {
        const hasResume = await hasResumableSidepanelChat()
        if (!cancelled) {
          setTarget(hasResume ? "chat" : "companion")
        }
      } catch {
        if (!cancelled) {
          setTarget("companion")
        }
      }
    }

    void resolveTarget()

    return () => {
      cancelled = true
    }
  }, [forcedView])

  if (target === "chat") {
    return (
      <React.Suspense
        fallback={
          <PageAssistLoader
            label="Loading chat..."
            description="Preparing your assistant"
          />
        }
      >
        <LazySidepanelChat />
      </React.Suspense>
    )
  }

  if (target === "companion") {
    return (
      <React.Suspense
        fallback={
          <PageAssistLoader
            label="Loading chat..."
            description="Preparing your assistant"
          />
        }
      >
        <LazySidepanelCompanion />
      </React.Suspense>
    )
  }

  return (
    <PageAssistLoader
      label="Loading chat..."
      description="Preparing your assistant"
    />
  )
}
