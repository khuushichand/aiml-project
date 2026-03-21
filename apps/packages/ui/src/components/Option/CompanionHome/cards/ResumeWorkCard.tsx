import type { CompanionHomeItem } from "@/services/companion-home"

import {
  CompanionHomeCardShell,
  type CompanionHomeCardState
} from "./CardShell"

type ResumeWorkCardProps = {
  items: CompanionHomeItem[]
  state?: CompanionHomeCardState
}

export function ResumeWorkCard({ items, state }: ResumeWorkCardProps) {
  return (
    <CompanionHomeCardShell
      title="Resume Work"
      items={items}
      state={state}
      emptyLabel="No resumable work yet"
      emptyDescription="Goal follow-ups, reading queue items, and unfinished notes will appear here."
    />
  )
}
