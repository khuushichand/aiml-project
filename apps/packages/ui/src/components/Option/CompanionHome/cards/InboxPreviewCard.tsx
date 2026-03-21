import {
  COMPANION_HOME_CARD_CONFIG,
  createCompanionHomeCard
} from "./factory"

export const InboxPreviewCard = createCompanionHomeCard(
  "InboxPreviewCard",
  COMPANION_HOME_CARD_CONFIG.inbox
)
