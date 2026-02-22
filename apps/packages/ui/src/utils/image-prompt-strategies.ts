import type { ImageGenerationPromptMode } from "@/utils/image-generation-chat"

export type ImagePromptContextDimension =
  | "conversation"
  | "character"
  | "mood"
  | "assistant_focus"
  | "user_intent"

export type ImagePromptWeightProfile = Record<ImagePromptContextDimension, number>

export type ImagePromptRawContext = {
  conversationSummary?: string | null
  characterName?: string | null
  moodLabel?: string | null
  assistantFocus?: string | null
  userIntent?: string | null
}

export type WeightedImagePromptContextEntry = {
  id: ImagePromptContextDimension
  label: string
  text: string
  weight: number
  quality: number
  score: number
}

export type WeightedImagePromptContext = {
  entries: WeightedImagePromptContextEntry[]
  summary: string
  profile: ImagePromptWeightProfile
}

export type ImagePromptStrategyDefinition = {
  id: ImageGenerationPromptMode
  label: string
  description: string
  defaultWeightOverrides?: Partial<ImagePromptWeightProfile>
  createPrompt: (args: {
    rawContext: ImagePromptRawContext
    weightedContext: WeightedImagePromptContext
  }) => string
}

type PromptStrategyRegistry = Map<
  ImagePromptStrategyDefinition["id"],
  ImagePromptStrategyDefinition
>

const CONTEXT_LABELS: Record<ImagePromptContextDimension, string> = {
  conversation: "Conversation",
  character: "Character",
  mood: "Mood",
  assistant_focus: "Assistant focus",
  user_intent: "User intent"
}

const CONTEXT_DIMENSION_ORDER: ImagePromptContextDimension[] = [
  "conversation",
  "character",
  "mood",
  "assistant_focus",
  "user_intent"
]

export const DEFAULT_IMAGE_PROMPT_WEIGHT_PROFILE: ImagePromptWeightProfile = {
  conversation: 0.34,
  character: 0.22,
  mood: 0.14,
  assistant_focus: 0.16,
  user_intent: 0.14
}

const normalizeWhitespace = (value: string): string =>
  value.replace(/\s+/g, " ").trim()

const normalizeText = (value?: string | null): string => {
  if (typeof value !== "string") return ""
  return normalizeWhitespace(value)
}

const clamp01 = (value: number): number => Math.max(0, Math.min(1, value))

const normalizeWeightProfile = (
  profile: ImagePromptWeightProfile
): ImagePromptWeightProfile => {
  const total = Object.values(profile).reduce((sum, current) => sum + current, 0)
  if (!Number.isFinite(total) || total <= 0) {
    return { ...DEFAULT_IMAGE_PROMPT_WEIGHT_PROFILE }
  }
  return CONTEXT_DIMENSION_ORDER.reduce((acc, key) => {
    acc[key] = clamp01(profile[key] / total)
    return acc
  }, {} as ImagePromptWeightProfile)
}

const mergeWeightProfiles = (
  base: ImagePromptWeightProfile,
  overrides?: Partial<ImagePromptWeightProfile>
): ImagePromptWeightProfile => {
  if (!overrides) return normalizeWeightProfile(base)
  return normalizeWeightProfile({
    ...base,
    ...overrides
  })
}

const qualityScoreForText = (text: string): number => {
  if (!text) return 0
  const lengthScore = Math.min(1, text.length / 180)
  const diversityScore = Math.min(
    1,
    new Set(text.toLowerCase().split(" ").filter(Boolean)).size / 36
  )
  return clamp01(lengthScore * 0.7 + diversityScore * 0.3)
}

const resolveSubject = (rawContext: ImagePromptRawContext): string => {
  const named = normalizeText(rawContext.characterName)
  return named || "the main subject"
}

const resolveContextSummary = (
  rawContext: ImagePromptRawContext,
  weightedContext: WeightedImagePromptContext
): string => {
  if (weightedContext.summary) return weightedContext.summary
  const fallback = normalizeText(rawContext.conversationSummary)
  return fallback || "the current scene context"
}

const truncate = (value: string, max = 320): string => {
  if (value.length <= max) return value
  return `${value.slice(0, max - 3).trimEnd()}...`
}

const STRATEGY_REGISTRY: PromptStrategyRegistry = new Map()

const DEFAULT_STRATEGIES: ImagePromptStrategyDefinition[] = [
  {
    id: "scene",
    label: "Scene",
    description: "Build a cinematic scene from current context.",
    defaultWeightOverrides: {
      conversation: 0.42,
      character: 0.2,
      assistant_focus: 0.2,
      mood: 0.1,
      user_intent: 0.08
    },
    createPrompt: ({ rawContext, weightedContext }) => {
      const subject = resolveSubject(rawContext)
      const summary = resolveContextSummary(rawContext, weightedContext)
      return truncate(
        `Cinematic scene featuring ${subject}. Context cues: ${summary}. Keep composition coherent, rich environmental detail, and strong visual storytelling.`
      )
    }
  },
  {
    id: "expression",
    label: "Expression",
    description: "Focus on facial expression, posture, and emotion.",
    defaultWeightOverrides: {
      mood: 0.34,
      character: 0.26,
      conversation: 0.2,
      user_intent: 0.12,
      assistant_focus: 0.08
    },
    createPrompt: ({ rawContext, weightedContext }) => {
      const subject = resolveSubject(rawContext)
      const mood = normalizeText(rawContext.moodLabel) || "focused"
      const summary = resolveContextSummary(rawContext, weightedContext)
      return truncate(
        `Portrait of ${subject} with a ${mood} expression and expressive body language. Reflect this context: ${summary}. Keep lighting and pose emotionally consistent.`
      )
    }
  },
  {
    id: "selfie",
    label: "Selfie",
    description: "Generate a close framing, handheld selfie look.",
    defaultWeightOverrides: {
      character: 0.3,
      user_intent: 0.24,
      conversation: 0.2,
      mood: 0.14,
      assistant_focus: 0.12
    },
    createPrompt: ({ rawContext, weightedContext }) => {
      const subject = resolveSubject(rawContext)
      const summary = resolveContextSummary(rawContext, weightedContext)
      return truncate(
        `Close-up selfie style photo of ${subject}, natural handheld framing, candid expression, soft depth of field. Context: ${summary}.`
      )
    }
  },
  {
    id: "camera-angle",
    label: "Camera Angle",
    description: "Compose a shot with deliberate angle and lens feel.",
    defaultWeightOverrides: {
      assistant_focus: 0.3,
      conversation: 0.26,
      user_intent: 0.2,
      character: 0.16,
      mood: 0.08
    },
    createPrompt: ({ rawContext, weightedContext }) => {
      const subject = resolveSubject(rawContext)
      const focus = normalizeText(rawContext.assistantFocus) || "dynamic framing"
      const summary = resolveContextSummary(rawContext, weightedContext)
      return truncate(
        `Shot of ${subject} using a dramatic camera angle and intentional lens perspective. Frame around: ${focus}. Context details: ${summary}.`
      )
    }
  },
  {
    id: "outfit",
    label: "Outfit",
    description: "Prioritize wardrobe styling and wearable details.",
    defaultWeightOverrides: {
      character: 0.32,
      user_intent: 0.24,
      conversation: 0.2,
      mood: 0.14,
      assistant_focus: 0.1
    },
    createPrompt: ({ rawContext, weightedContext }) => {
      const subject = resolveSubject(rawContext)
      const mood = normalizeText(rawContext.moodLabel)
      const summary = resolveContextSummary(rawContext, weightedContext)
      const moodClause = mood ? ` Mood: ${mood}.` : ""
      return truncate(
        `Fashion-focused image of ${subject} with clearly detailed outfit pieces, textures, and accessories. Style direction: ${summary}.${moodClause}`
      )
    }
  }
]

const ensureDefaultStrategies = () => {
  if (STRATEGY_REGISTRY.size > 0) return
  DEFAULT_STRATEGIES.forEach((strategy) => {
    STRATEGY_REGISTRY.set(strategy.id, strategy)
  })
}

export const registerImagePromptStrategy = (
  strategy: ImagePromptStrategyDefinition
) => {
  STRATEGY_REGISTRY.set(strategy.id, strategy)
}

export const getImagePromptStrategies = (): ImagePromptStrategyDefinition[] => {
  ensureDefaultStrategies()
  return Array.from(STRATEGY_REGISTRY.values())
}

export const getImagePromptStrategy = (
  id?: string | null
): ImagePromptStrategyDefinition => {
  ensureDefaultStrategies()
  if (id && STRATEGY_REGISTRY.has(id as ImageGenerationPromptMode)) {
    return STRATEGY_REGISTRY.get(id as ImageGenerationPromptMode)!
  }
  return STRATEGY_REGISTRY.get("scene")!
}

export const extractWeightedImagePromptContext = (
  rawContext: ImagePromptRawContext,
  weightOverrides?: Partial<ImagePromptWeightProfile>
): WeightedImagePromptContext => {
  const profile = mergeWeightProfiles(
    DEFAULT_IMAGE_PROMPT_WEIGHT_PROFILE,
    weightOverrides
  )
  const normalizedContext: Record<ImagePromptContextDimension, string> = {
    conversation: normalizeText(rawContext.conversationSummary),
    character: normalizeText(rawContext.characterName),
    mood: normalizeText(rawContext.moodLabel),
    assistant_focus: normalizeText(rawContext.assistantFocus),
    user_intent: normalizeText(rawContext.userIntent)
  }

  const entries = CONTEXT_DIMENSION_ORDER
    .filter((key) => normalizedContext[key].length > 0)
    .map((key) => {
      const text = normalizedContext[key]
      const weight = profile[key]
      const quality = qualityScoreForText(text)
      return {
        id: key,
        label: CONTEXT_LABELS[key],
        text,
        weight,
        quality,
        score: Number((weight * quality).toFixed(4))
      } satisfies WeightedImagePromptContextEntry
    })
    .sort((left, right) => {
      if (right.score !== left.score) return right.score - left.score
      return CONTEXT_DIMENSION_ORDER.indexOf(left.id) - CONTEXT_DIMENSION_ORDER.indexOf(right.id)
    })

  const summary = entries
    .slice(0, 3)
    .map((entry) => `${entry.label}: ${entry.text}`)
    .join(" | ")

  return {
    entries,
    summary,
    profile
  }
}

export const createImagePromptDraftFromStrategy = ({
  strategyId,
  rawContext
}: {
  strategyId: ImageGenerationPromptMode
  rawContext: ImagePromptRawContext
}): {
  strategy: ImagePromptStrategyDefinition
  prompt: string
  weightedContext: WeightedImagePromptContext
} => {
  const strategy = getImagePromptStrategy(strategyId)
  const weightedContext = extractWeightedImagePromptContext(
    rawContext,
    strategy.defaultWeightOverrides
  )
  const prompt = normalizeWhitespace(
    strategy.createPrompt({
      rawContext,
      weightedContext
    })
  )
  return {
    strategy,
    prompt,
    weightedContext
  }
}

const getLatestBotMessage = (messages: Array<{ isBot?: boolean; message?: string }>) => {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const entry = messages[i]
    if (!entry?.isBot) continue
    const content = normalizeText(entry.message)
    if (content) return content
  }
  return ""
}

const summarizeRecentConversation = (
  messages: Array<{ message?: string }>
): string => {
  const segments = messages
    .map((entry) => normalizeText(entry.message))
    .filter((entry) => entry.length > 0)
    .slice(-4)
  if (segments.length === 0) {
    return "the current scene context"
  }
  return truncate(segments.join(" "), 420)
}

export const deriveImagePromptRawContext = ({
  messages,
  characterName,
  moodLabel,
  userIntent
}: {
  messages: Array<{ isBot?: boolean; message?: string }>
  characterName?: string | null
  moodLabel?: string | null
  userIntent?: string | null
}): ImagePromptRawContext => {
  const assistantFocus = getLatestBotMessage(messages)
  return {
    conversationSummary: summarizeRecentConversation(messages),
    characterName: normalizeText(characterName),
    moodLabel: normalizeText(moodLabel),
    assistantFocus,
    userIntent: normalizeText(userIntent)
  }
}

