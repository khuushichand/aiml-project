import { ChatHistory } from "@/store"

export type BotResponse = {
    bot: {
        text: string
        sourceDocuments: unknown[]
    }
    history: ChatHistory
    history_id: string
}
