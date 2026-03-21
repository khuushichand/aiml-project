import type { CompanionHomeItem } from "@/services/companion-home"

import {
  CompanionHomeCardShell,
  type CompanionHomeCardState
} from "./CardShell"

type ReadingQueueCardProps = {
  items: CompanionHomeItem[]
  state?: CompanionHomeCardState
}

export function ReadingQueueCard({ items, state }: ReadingQueueCardProps) {
  return (
    <CompanionHomeCardShell
      title="Reading Queue"
      items={items}
      state={state}
      emptyLabel="Reading queue is clear"
      emptyDescription="Saved and in-progress reading items stay visible here so they do not get buried."
    />
  )
}
