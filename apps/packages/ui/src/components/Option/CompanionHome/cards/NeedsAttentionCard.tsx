import {
  COMPANION_HOME_CARD_CONFIG,
  createCompanionHomeCard
} from "./factory"

export const NeedsAttentionCard = createCompanionHomeCard(
  "NeedsAttentionCard",
  COMPANION_HOME_CARD_CONFIG.needsAttention
)
