import { fetchChatModels } from "@/services/tldw-server"
import {
  buildAvailableChatModelIds,
  findUnavailableChatModel,
  normalizeChatModelId
} from "@/utils/chat-model-availability"

type FetchChatModels = typeof fetchChatModels

export type SelectedChatModelValidationResult =
  | { status: "valid" }
  | {
      status: "unknown"
      reason: "catalog-empty" | "model-unavailable-in-cache"
    }

export const validateSelectedChatModelAvailability = async (
  selectedModelId: string,
  options?: {
    fetchModels?: FetchChatModels
  }
): Promise<SelectedChatModelValidationResult> => {
  const normalizedSelectedModel = normalizeChatModelId(selectedModelId)
  const fetchModels = options?.fetchModels ?? fetchChatModels
  const models = await fetchModels({ returnEmpty: true, allowNetwork: false })
  const availableIds = buildAvailableChatModelIds(models as any[])

  if (availableIds.size === 0) {
    return {
      status: "unknown",
      reason: "catalog-empty"
    }
  }

  const unavailableModel = findUnavailableChatModel(
    [normalizedSelectedModel],
    availableIds
  )

  if (unavailableModel) {
    return {
      status: "unknown",
      reason: "model-unavailable-in-cache"
    }
  }

  return { status: "valid" }
}
