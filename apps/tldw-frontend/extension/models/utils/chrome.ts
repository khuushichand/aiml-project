type ChromeLanguageModel = {
  availability?: () => Promise<string>
  create?: (options: Record<string, unknown>) => Promise<AITextSession>
}

type ChromeAI = {
  languageModel?: {
    capabilities?: () => Promise<{ available?: string }>
    create?: (options: Record<string, unknown>) => Promise<AITextSession>
  }
  assistant?: {
    capabilities?: () => Promise<{ available?: string }>
    create?: (options: Record<string, unknown>) => Promise<AITextSession>
  }
  canCreateTextSession?: () => Promise<string>
  createTextSession?: (options: Record<string, unknown>) => Promise<AITextSession>
}

export const checkChromeAIAvailability = async (): Promise<
  | "readily"
  | "unavailable"
  | "downloadable"
  | "downloading"
  | "no"
  | "after-download"
> => {
  try {
    // latest latest newer version
    const languageModel = (
      globalThis as { LanguageModel?: ChromeLanguageModel }
    ).LanguageModel
    if (languageModel?.availability) {
      const availability = await languageModel.availability()
      console.log("LanguageModel availability:", availability)
      if (availability === "downloadable") {
        return "downloadable"
      }
      if (availability === "downloading") {
        return "downloading"
      }
      return availability == "available" ? "readily" : "no"
    }
    const ai = (globalThis as { ai?: ChromeAI }).ai

    // latest i guess
    if (ai?.languageModel?.capabilities) {
      const capabilities = await ai.languageModel.capabilities()
      return capabilities?.available ?? "no"
    }

    // old version change
    if (ai?.assistant?.capabilities) {
      const capabilities = await ai.assistant.capabilities()
      return capabilities?.available ?? "no"
    }

    // too old version
    if (ai?.canCreateTextSession) {
      const available = await ai.canCreateTextSession()
      return available ?? "no"
    }

    return "no"
  } catch (e) {
    console.error("Error checking Chrome AI availability:", e)
    return "no"
  }
}

export interface AITextSession {
  prompt(input: string): Promise<string>
  promptStreaming(input: string): ReadableStream
  destroy(): void
  clone(): AITextSession
}

export const createAITextSession = async (
  data: Record<string, unknown>
): Promise<AITextSession> => {
  // even newer version
  const languageModel = (
    globalThis as { LanguageModel?: ChromeLanguageModel }
  ).LanguageModel
  if (languageModel?.create) {
    const session = await languageModel.create({
      ...data
    })
    return session
  }
  const ai = (globalThis as { ai?: ChromeAI }).ai

  // new version i guess
  if (ai?.languageModel?.create) {
    const session = await ai.languageModel.create({
      ...data
    })
    return session
  }

  // old version change
  if (ai?.assistant?.create) {
    const session = await ai.assistant.create({
      ...data
    })
    return session
  }

  // too old version
  if (ai.createTextSession) {
    const session = await ai.createTextSession({
      ...data
    })

    return session
  }

  throw new Error("Chrome AI is not available.")
}
