import { getModelInfo, isCustomModel } from "@/db/dexie/models"
import { createSafeStorage } from "@/utils/safe-storage"

const storage = createSafeStorage()

export const getSelectedModelName = async (): Promise<string> => {
    const selectedModel = await storage.get("selectedModel")
    const selectedModelValue =
        typeof selectedModel === "string" ? selectedModel : ""
    const isCustom = isCustomModel(selectedModelValue)
    if (isCustom) {
        const customModel = await getModelInfo(selectedModelValue)
        if (customModel) {
            return customModel.name
        } else {
            return selectedModelValue
        }
    }
    return selectedModelValue
}
