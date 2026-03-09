import React from "react"

type LiveSessionPanelProps = {
  controls: React.ReactNode
  error: React.ReactNode
  pendingPlan: React.ReactNode
  transcript: React.ReactNode
  composer: React.ReactNode
}

export const LiveSessionPanel: React.FC<LiveSessionPanelProps> = ({
  controls,
  error,
  pendingPlan,
  transcript,
  composer
}) => {
  return (
    <div className="flex flex-1 flex-col gap-3">
      {controls}
      {error}
      {pendingPlan}
      {transcript}
      {composer}
    </div>
  )
}
