import type { CompanionHomeItem } from "@/services/companion-home"

import {
  CompanionHomeCardShell,
  type CompanionHomeCardState
} from "./CardShell"

type NeedsAttentionCardProps = {
  items: CompanionHomeItem[]
  state?: CompanionHomeCardState
}

export function NeedsAttentionCard({ items, state }: NeedsAttentionCardProps) {
  return (
    <CompanionHomeCardShell
      title="Needs Attention"
      items={items}
      state={state}
      emptyLabel="No follow-ups are overdue"
      emptyDescription="Derived reminders from goals, reading, and unfinished work will surface here."
    />
  )
}
