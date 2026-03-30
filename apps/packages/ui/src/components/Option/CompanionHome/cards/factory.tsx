import type { CompanionHomeItem } from "@/services/companion-home"

import {
  CompanionHomeCardShell,
  type CompanionHomeCardState
} from "./CardShell"

type CompanionHomeCardProps = {
  items: CompanionHomeItem[]
  state?: CompanionHomeCardState
}

type CompanionHomeCardConfig = {
  title: string
  emptyLabel: string
  emptyDescription: string
}

export const COMPANION_HOME_CARD_CONFIG = {
  inbox: {
    title: "Inbox Preview",
    emptyLabel: "Inbox is clear",
    emptyDescription: "Authoritative companion notifications will show up here first."
  },
  needsAttention: {
    title: "Needs Attention",
    emptyLabel: "No follow-ups are overdue",
    emptyDescription: "Derived reminders from goals, reading, and unfinished work will surface here."
  },
  resumeWork: {
    title: "Resume Work",
    emptyLabel: "No resumable work yet",
    emptyDescription: "Goal follow-ups, reading queue items, and unfinished notes will appear here."
  },
  goalsFocus: {
    title: "Goals / Focus",
    emptyLabel: "No active goals are in focus",
    emptyDescription: "Active companion goals and their next progress checkpoints show up here."
  },
  recentActivity: {
    title: "Recent Activity",
    emptyLabel: "No recent activity yet",
    emptyDescription: "Fresh captures and companion-linked events will show up here once the workspace is active."
  },
  readingQueue: {
    title: "Reading Queue",
    emptyLabel: "Reading queue is clear",
    emptyDescription: "Saved and in-progress reading items stay visible here so they do not get buried."
  }
} as const satisfies Record<string, CompanionHomeCardConfig>

export const createCompanionHomeCard = (
  displayName: string,
  config: CompanionHomeCardConfig
) => {
  const CompanionHomeCard = ({ items, state }: CompanionHomeCardProps) => (
    <CompanionHomeCardShell
      title={config.title}
      items={items}
      state={state}
      emptyLabel={config.emptyLabel}
      emptyDescription={config.emptyDescription}
    />
  )

  CompanionHomeCard.displayName = displayName

  return CompanionHomeCard
}
