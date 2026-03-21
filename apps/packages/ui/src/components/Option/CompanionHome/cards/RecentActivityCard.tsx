import {
  COMPANION_HOME_CARD_CONFIG,
  createCompanionHomeCard
} from "./factory"

export const RecentActivityCard = createCompanionHomeCard(
  "RecentActivityCard",
  COMPANION_HOME_CARD_CONFIG.recentActivity
)
