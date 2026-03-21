import {
  COMPANION_HOME_CARD_CONFIG,
  createCompanionHomeCard
} from "./factory"

export const ReadingQueueCard = createCompanionHomeCard(
  "ReadingQueueCard",
  COMPANION_HOME_CARD_CONFIG.readingQueue
)
