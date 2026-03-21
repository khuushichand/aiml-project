import type { CompanionHomeItem } from "@/services/companion-home"

import {
  CompanionHomeCardShell,
  type CompanionHomeCardState
} from "./CardShell"

type InboxPreviewCardProps = {
  items: CompanionHomeItem[]
  state?: CompanionHomeCardState
}

export function InboxPreviewCard({ items, state }: InboxPreviewCardProps) {
  return (
    <CompanionHomeCardShell
      title="Inbox Preview"
      items={items}
      state={state}
      emptyLabel="Inbox is clear"
      emptyDescription="Authoritative companion notifications will show up here first."
    />
  )
}
