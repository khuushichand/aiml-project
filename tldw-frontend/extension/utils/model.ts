import { getModelInfo, isCustomModel } from "@/db/dexie/models"
import { Storage } from "@plasmohq/storage"
import { createSafeStorage } from "@/utils/safe-storage"

const storage = createSafeStorage()

export const getSelectedModelName = async (): Promise<string> => {
    const selectedModel = await storage.get<string>("selectedModel")
    const resolvedModel = typeof selectedModel === "string" ? selectedModel : ""
    const isCustom = isCustomModel(resolvedModel)
    if (isCustom) {
        const customModel = await getModelInfo(resolvedModel)
        if (customModel) {
            return customModel.name
        } else {
            return resolvedModel
        }
    }
    return resolvedModel
}
