import React from "react"
import { Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import type { QueryStage } from "../types"
import { ConversationThread } from "../ConversationThread"
import { AnswerPanel } from "../AnswerPanel"
import { FollowUpInput } from "../FollowUpInput"

type AnswerWorkspaceProps = {
  queryStage: QueryStage
  className?: string
}

const STAGE_COPY: Record<QueryStage, string> = {
  idle: "Ready to search",
  searching: "Searching selected sources",
  ranking: "Ranking best evidence",
  generating: "Generating answer",
  verifying: "Verifying citations",
  complete: "Answer complete",
  error: "Search needs attention",
}

export function AnswerWorkspace({ queryStage, className }: AnswerWorkspaceProps) {
  const isActiveStage =
    queryStage !== "idle" && queryStage !== "complete" && queryStage !== "error"

  return (
    <div className={cn("space-y-6", className)}>
      {isActiveStage ? (
        <div className="rounded-lg border border-border bg-muted/20 px-3 py-2 text-sm text-text-muted">
          <span className="inline-flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
            {STAGE_COPY[queryStage]}
          </span>
        </div>
      ) : null}

      <ConversationThread />
      <AnswerPanel />
      <FollowUpInput />
    </div>
  )
}
