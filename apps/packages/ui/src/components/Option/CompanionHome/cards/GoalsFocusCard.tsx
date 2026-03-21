import type { CompanionHomeItem } from "@/services/companion-home"

import {
  CompanionHomeCardShell,
  type CompanionHomeCardState
} from "./CardShell"

type GoalsFocusCardProps = {
  items: CompanionHomeItem[]
  state?: CompanionHomeCardState
}

export function GoalsFocusCard({ items, state }: GoalsFocusCardProps) {
  return (
    <CompanionHomeCardShell
      title="Goals / Focus"
      items={items}
      state={state}
      emptyLabel="No active goals are in focus"
      emptyDescription="Active companion goals and their next progress checkpoints show up here."
    />
  )
}
