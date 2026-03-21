import type { CompanionHomeItem } from "@/services/companion-home"

import {
  CompanionHomeCardShell,
  type CompanionHomeCardState
} from "./CardShell"

type RecentActivityCardProps = {
  items: CompanionHomeItem[]
  state?: CompanionHomeCardState
}

export function RecentActivityCard({ items, state }: RecentActivityCardProps) {
  return (
    <CompanionHomeCardShell
      title="Recent Activity"
      items={items}
      state={state}
      emptyLabel="No recent activity yet"
      emptyDescription="Fresh captures and companion-linked events will show up here once the workspace is active."
    />
  )
}
