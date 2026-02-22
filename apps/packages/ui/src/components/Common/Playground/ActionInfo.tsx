import React from "react"
import { useTranslation } from "react-i18next"
import { Globe, Cpu, Database, Sparkles, Loader2 } from "lucide-react"

type Props = {
  action: string
}

// Screen reader only announcement component
const SrAnnouncement: React.FC<{ message: string }> = ({ message }) => (
  <div
    role="status"
    aria-live="polite"
    aria-atomic="true"
    className="sr-only"
  >
    {message}
  </div>
)

// Map action types to icons and labels
const actionConfig: Record<string, { icon: React.ElementType; labelKey: string; defaultLabel: string }> = {
  webSearch: { icon: Globe, labelKey: "actionInfo.webSearch", defaultLabel: "Searching the web..." },
  ragSearch: { icon: Database, labelKey: "actionInfo.ragSearch", defaultLabel: "Searching knowledge base..." },
  embedding: { icon: Database, labelKey: "actionInfo.embedding", defaultLabel: "Processing context..." },
  generating: { icon: Sparkles, labelKey: "actionInfo.generating", defaultLabel: "Generating response..." },
  processing: { icon: Cpu, labelKey: "actionInfo.processing", defaultLabel: "Processing..." },
  thinking: { icon: Sparkles, labelKey: "actionInfo.thinking", defaultLabel: "Thinking..." },
}

export const ActionInfo = ({ action }: Props) => {
  const { t } = useTranslation("common")

  const config = actionConfig[action]
  const IconComponent = config?.icon || Loader2
  const label = config
    ? t(config.labelKey, config.defaultLabel)
    : t(`actionInfo.${action}`, action)

  return (
    <div
      className="inline-flex items-center gap-2 px-3 py-2 rounded-full bg-primary/10 border border-primary/30"
      role="status"
      aria-live="polite"
    >
      <IconComponent className="size-4 text-primary animate-pulse" />
      <span className="text-sm font-medium text-primary shimmer-text">
        {label}
      </span>
    </div>
  )
}

// Unified loading status component for chat messages
type LoadingStatusProps = {
  isProcessing?: boolean
  isStreaming?: boolean
  isSearchingInternet?: boolean
  isEmbedding?: boolean
  actionInfo?: string | null
}

export const LoadingStatus = ({
  isProcessing,
  isStreaming,
  isSearchingInternet,
  isEmbedding,
  actionInfo
}: LoadingStatusProps) => {
  const { t } = useTranslation("common")
  const [completionAnnouncement, setCompletionAnnouncement] = React.useState<string | null>(null)
  const [liveAnnouncement, setLiveAnnouncement] = React.useState<string | null>(null)
  const wasActiveRef = React.useRef(false)
  const previousActionRef = React.useRef<string | null>(null)
  const progressCheckpointRef = React.useRef(0)

  // Determine the current action based on state
  let currentAction: string | null = null

  if (isSearchingInternet) {
    currentAction = "webSearch"
  } else if (isEmbedding) {
    currentAction = "embedding"
  } else if (actionInfo) {
    currentAction = actionInfo
  } else if (isStreaming) {
    currentAction = "generating"
  } else if (isProcessing) {
    currentAction = "processing"
  }

  const isActive = currentAction !== null

  React.useEffect(() => {
    if (!currentAction) {
      setLiveAnnouncement(null)
      progressCheckpointRef.current = 0
      previousActionRef.current = null
      return
    }
    if (previousActionRef.current === currentAction) {
      return
    }
    previousActionRef.current = currentAction
    const startedLabel = t("actionInfo.started", "{{label}} started", {
      label: t(
        actionConfig[currentAction]?.labelKey || `actionInfo.${currentAction}`,
        actionConfig[currentAction]?.defaultLabel || currentAction
      )
    })
    setLiveAnnouncement(startedLabel)
  }, [currentAction, t])

  React.useEffect(() => {
    if (!isStreaming || !isActive) {
      progressCheckpointRef.current = 0
      return
    }

    const timer = window.setInterval(() => {
      progressCheckpointRef.current += 1
      setLiveAnnouncement(
        t(
          "actionInfo.progressCheckpoint",
          "Still generating response (checkpoint {{count}}).",
          {
            count: progressCheckpointRef.current
          }
        )
      )
    }, 5000)

    return () => {
      window.clearInterval(timer)
    }
  }, [isActive, isStreaming, t])

  // Announce completion when transitioning from active to inactive
  React.useEffect(() => {
    if (wasActiveRef.current && !isActive) {
      // Was active, now complete - announce to screen readers
      setCompletionAnnouncement(t("actionInfo.complete", "Response complete"))
      // Clear announcement after a short delay
      const timer = setTimeout(() => setCompletionAnnouncement(null), 1000)
      return () => clearTimeout(timer)
    }
    wasActiveRef.current = isActive
  }, [isActive, t])

  return (
    <>
      {/* Live updates for start/progress checkpoints */}
      {liveAnnouncement && (
        <SrAnnouncement message={liveAnnouncement} />
      )}
      {/* Screen reader announcement for completion */}
      {completionAnnouncement && (
        <SrAnnouncement message={completionAnnouncement} />
      )}
      {/* Visual status indicator */}
      {currentAction && <ActionInfo action={currentAction} />}
    </>
  )
}
